"""RAG 引擎：检索 + 生成"""

import os
import re
from typing import AsyncGenerator
from openai import AsyncOpenAI
from rag.vector_store import VectorStore

RAG_PROMPT = """你是一个基于本地文档回答问题的智能助手。请严格遵守以下规则：

1. 你必须严格基于下方提供的文档内容来回答，不要使用你自身的知识
2. 如果检索到的文档内容不足以完全回答问题，如实告知用户哪些部分找到了、哪些没找到
3. 在答案末尾用「参考来源」列出引用的文件名
4. 使用 Makedown 格式排版
5. 回答要简洁、准确

以下是与用户问题相关的文档内容："""

WEB_PROMPT = """你是一个智能问答助手。用户要求联网回答，请基于你自身的知识来回答问题。注意：
1. 如实告知用户这是基于你自身知识的回答，不一定与用户本地文档相关
2. 使用 Makedown 格式排版
3. 回答要简洁、准确"""

NO_CONTEXT_MSG = "我无法从已导入的文档中找到与这个问题相关的信息。请先导入相关文档再让我回答,或明确要求请联网回答让我基于自身知识来回答。"

# 触发联网模式的短语
WEB_TRIGGERS = [
    "请联网回答", "联网回答", "联网搜索", "上网查", "请上网查",
    "web search", "search online", "联网",
]


def _is_web_mode(message: str) -> bool:
    """判断用户是否要求联网回答"""
    msg = message.strip().lower()
    for t in WEB_TRIGGERS:
        if t.lower() in msg:
            return True
    return False


class RAGEngine:
    """RAG 引擎"""

    def __init__(self, vector_store: VectorStore, model: str = "gpt-3.5-turbo"):
        self.vector_store = vector_store
        self.model = model
        self.client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1"),
        )

    async def chat_stream(
        self,
        message: str,
        document_ids: list[str] | None = None,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式 RAG 对话"""

        # 判断模式
        is_web = _is_web_mode(message)

        if is_web:
            # 联网模式：跳过 RAG，直接使用 LLM
            messages = [{"role": "system", "content": WEB_PROMPT}]
            if history:
                for h in history[-10:]:
                    messages.append(h)
            messages.append({"role": "user", "content": message})

            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                temperature=0.7,
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            return

        # 本地文档模式：检索相关文档
        relevant_docs = self.vector_store.similarity_search(message, k=5)

        # 按 file_id 过滤
        if document_ids:
            relevant_docs = [
                d for d in relevant_docs
                if d["metadata"].get("file_id") in document_ids
            ]

        # 无相关文档时直接返回固定提示
        if not relevant_docs:
            yield NO_CONTEXT_MSG
            return

        # 构建上下文
        context = ""
        seen_files = set()
        for doc in relevant_docs:
            context += f"\n---\n{doc['content']}\n"
            file_id = doc["metadata"].get("file_id", doc["metadata"].get("source", ""))
            if file_id and file_id not in seen_files:
                seen_files.add(file_id)

        messages = [{"role": "system", "content": RAG_PROMPT}]
        messages.append({
            "role": "system",
            "content": f"以下是用户文档中的相关内容：\n{context}",
        })

        if history:
            for h in history[-10:]:
                messages.append(h)

        messages.append({"role": "user", "content": message})

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            temperature=0.3,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def get_references(self, query: str, document_ids: list[str] | None = None) -> list[dict]:
        """获取问答的引用来源"""
        docs = self.vector_store.similarity_search(query, k=5)
        if document_ids:
            docs = [d for d in docs if d["metadata"].get("file_id") in document_ids]
        sources = []
        seen_files = set()
        for doc in docs:
            file_id = doc["metadata"].get("file_id", doc["metadata"].get("source", ""))
            if file_id and file_id not in seen_files:
                seen_files.add(file_id)
                sources.append({
                    "title": f"参考自《{doc['metadata'].get('filename', file_id)}》",
                    "snippet": doc["content"][:200],
                })
        return sources
