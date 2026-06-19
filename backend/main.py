"""DocuMind 后端 API — FastAPI + RAG + SQLite"""

import os
import sys
import uuid
import time
import tempfile
from collections import defaultdict
from datetime import datetime
from contextlib import asynccontextmanager

# 加载 .env 文件（如果存在）
from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import select

from models.schemas import (
    ChatRequest,
    ScrapeRequest,
    DocumentListResponse,
    DocumentItem,
    ConversationListResponse,
    Conversation,
    ReferencesResponse,
    ReferenceSource,
    UploadResponse,
)
from rag.vector_store import VectorStore
from rag.engine import RAGEngine
from parsers.document_parser import parse_file
from parsers.web_scraper import scrape_url
from database import init_db, get_session, ConversationDB, MessageDB, DocumentChunkDB

# ---------- 简单限流 ----------
_rate_window = 60       # 60 秒窗口
_rate_limit = 30        # 窗口内最多 30 次（每秒 0.5 次，合理）
_rate_records: dict[str, list[float]] = defaultdict(list)


def _check_rate(client_ip: str) -> bool:
    """返回 True 表示允许，False 表示超限"""
    now = time.time()
    records = _rate_records[client_ip]
    records[:] = [t for t in records if now - t < _rate_window]
    records.append(now)
    return len(records) <= _rate_limit

# ---------- 全局状态 ----------
vector_store: VectorStore = None
rag_engine: RAGEngine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭事件"""
    global vector_store, rag_engine

    # 初始化数据库
    init_db()

    model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    vector_store = VectorStore()
    rag_engine = RAGEngine(vector_store=vector_store, model=model)

    yield


app = FastAPI(
    title="DocuMind API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 聊天 ====================

@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    """流式 RAG 对话"""
    # 限流检查
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate(client_ip):
        raise HTTPException(status_code=429, detail="请求太频繁，请稍后再试")
    async def generate():
        nonlocal req
        full_content = ""
        history = []

        # 从 MessageDB 加载历史消息作为上下文
        if req.session_id:
            with get_session() as db:
                stmt = (select(MessageDB)
                        .where(MessageDB.conversation_id == req.session_id)
                        .order_by(MessageDB.created_at.desc())
                        .limit(6))
                rows = db.exec(stmt).all()
                history = [{"role": r.role, "content": r.content}
                           for r in reversed(rows)]  # 时间升序

        async for chunk in rag_engine.chat_stream(
            message=req.message,
            document_ids=req.document_ids,
            history=history,
        ):
            full_content += chunk
            yield chunk

        # 保存消息到 MessageDB
        session_id = req.session_id or str(uuid.uuid4())
        with get_session() as db:
            conv = db.get(ConversationDB, session_id)
            if not conv:
                conv = ConversationDB(id=session_id, title=req.message[:30])
                db.add(conv)

            user_msg = MessageDB(
                id=str(uuid.uuid4()),
                conversation_id=session_id,
                role="user",
                content=req.message,
            )
            db.add(user_msg)
            if full_content.strip():
                ai_msg = MessageDB(
                    id=str(uuid.uuid4()),
                    conversation_id=session_id,
                    role="assistant",
                    content=full_content,
                )
                db.add(ai_msg)
            db.commit()

    return StreamingResponse(generate(), media_type="text/plain")


@app.get("/api/chat/{message_id}/references")
async def get_references(message_id: str, q: str = ""):
    """获取某条消息的引用来源"""
    if not q:
        return ReferencesResponse(sources=[])
    sources = rag_engine.get_references(query=q)
    return ReferencesResponse(sources=[
        ReferenceSource(title=s["title"], snippet=s["snippet"])
        for s in sources
    ])


# ==================== 文档管理 ====================

@app.post("/api/documents/upload")
async def upload_documents(files: list[UploadFile] = File(...)):
    """上传并解析文档"""
    # 批量去重
    all_names = [f.filename for f in files]
    dup = vector_store.find_any_filename(all_names)
    if dup:
        raise HTTPException(
            status_code=400,
            detail=f"文件「{dup}」已存在，请勿重复导入",
        )

    results = []
    for file in files:

        suffix = os.path.splitext(file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            chunks = parse_file(tmp_path, original_filename=file.filename)
            if not chunks:
                continue

            ids = [c["id"] for c in chunks]
            texts = [c["text"] for c in chunks]
            metadatas = [c["metadata"] for c in chunks]
            vector_store.add_documents(ids, texts, metadatas)

            file_id = chunks[0]["metadata"]["file_id"]
            doc_title = chunks[0]["metadata"].get("title", file.filename)
            results.append({"id": file_id, "name": file.filename, "title": doc_title})
        finally:
            os.unlink(tmp_path)

    return UploadResponse(files=results)


@app.post("/api/documents/scrape")
async def scrape_document(req: ScrapeRequest):
    """抓取网页并入库"""
    try:
        chunks = await scrape_url(req.url)
        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="无法从该 URL 提取内容。常见原因：① 网站内容由 JavaScript 动态渲染（SPA）；② 需要登录验证；③ 反爬机制拦截；④ URL 无效"
            )

        ids = [c["id"] for c in chunks]
        texts = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        vector_store.add_documents(ids, texts, metadatas)

        file_id = chunks[0]["metadata"]["file_id"]
        filename = chunks[0]["metadata"]["filename"]

        return {"id": file_id, "name": filename, "chunks": len(chunks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents")
async def list_documents():
    """列出已入库文档"""
    docs = vector_store.list_documents()
    return DocumentListResponse(documents=[
        DocumentItem(id=d["id"], name=d["name"], title=d.get("title", ""), pages=d.get("pages", ""))
        for d in docs
    ])


@app.get("/api/documents/{file_id}/chunks")
async def get_document_chunks(file_id: str):
    """获取某个文档的所有分块数据"""
    chunks = vector_store.get_chunks(file_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="文档未找到")
    return {"chunks": chunks}

@app.delete("/api/documents/{file_id}")
async def delete_document(file_id: str):
    """删除文档"""
    vector_store.delete_document(file_id)
    return {"ok": True}


# ==================== 会话管理 ====================

@app.get("/api/conversations")
async def list_conversations():
    """列出历史会话"""
    with get_session() as db:
        stmt = select(ConversationDB).order_by(ConversationDB.created_at.desc())
        rows = db.exec(stmt).all()

    return ConversationListResponse(conversations=[
        Conversation(id=r.id, title=r.title, created_at=r.created_at.isoformat())
        for r in rows
    ])


@app.get("/api/conversations/{session_id}")
async def get_conversation(session_id: str):
    """获取某个会话的完整消息"""
    with get_session() as db:
        conv = db.get(ConversationDB, session_id)
        if not conv:
            raise HTTPException(status_code=404, detail="会话未找到")
        stmt = (select(MessageDB)
                .where(MessageDB.conversation_id == session_id)
                .order_by(MessageDB.created_at))
        rows = db.exec(stmt).all()
        return {"messages": [{"role": r.role, "content": r.content} for r in rows]}


@app.delete("/api/conversations/{session_id}")
async def delete_conversation(session_id: str):
    """删除历史会话"""
    from sqlmodel import delete
    with get_session() as db:
        conv = db.get(ConversationDB, session_id)
        if not conv:
            raise HTTPException(status_code=404, detail="会话未找到")
        db.exec(delete(MessageDB).where(MessageDB.conversation_id == session_id))
        db.delete(conv)
        db.commit()
    return {"ok": True}


# ==================== 启动 ====================

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=True)
