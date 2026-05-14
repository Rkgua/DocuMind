"""文档解析器：支持 PDF、DOCX、MD、TXT"""

import os
import uuid
from langchain_text_splitters import RecursiveCharacterTextSplitter


def parse_file(file_path: str, original_filename: str = "") -> list[dict]:
    """解析文件并返回分块后的文档片段

    Args:
        file_path: 临时文件路径
        original_filename: 上传时的原始文件名，用于从 .md 提取标题
    """
    ext = os.path.splitext(file_path)[1].lower()
    filename = original_filename or os.path.basename(file_path)

    if ext == ".pdf":
        text = _parse_pdf(file_path)
    elif ext in (".docx", ".doc"):
        text = _parse_docx(file_path)
    else:
        # .md / .txt 直接读（utf-8-sig 兼容 BOM）
        with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            text = f.read()

    if not text.strip():
        return []

    # 从 .md 文件提取标题（第一个 # 标题）
    title = filename
    if ext == ".md":
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                title = stripped[2:].strip()
                break

    # 分块
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        separators=["\n\n", "\n", "。", ".", "!", "？", " ", ""],
    )
    chunks = splitter.split_text(text)

    # 构造片段
    doc_id = str(uuid.uuid4())
    documents = []
    for i, chunk in enumerate(chunks):
        documents.append({
            "id": f"{doc_id}_seg{i}",
            "text": chunk,
            "metadata": {
                "file_id": doc_id,
                "filename": filename,
                "title": title,
                "chunk": i,
                "source": file_path,
            },
        })

    return documents


def _parse_pdf(file_path: str) -> str:
    """解析 PDF 文件"""
    from PyPDF2 import PdfReader
    
    try:
        reader = PdfReader(file_path)
        text = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)
        return "\n".join(text)
    except Exception as e:
        print(f"PDF解析错误: {e}")
        return ""


def _parse_docx(file_path: str) -> str:
    """解析 DOCX 文件"""
    from docx import Document
    doc = Document(file_path)
    text = []
    for para in doc.paragraphs:
        if para.text.strip():
            text.append(para.text)
    return "\n".join(text)
