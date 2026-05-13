"""RAG 引擎：检索 + 生成"""

from typing import AsyncGenerator
from openai import AsyncOpenAI
from rag.vector_store import VectorStore

SYSTEM_PROMPT = """你是一个智能文档助手，基于用户提供的文档内容来回答问题。
请遵循以下规则：
1. 仅基于检索到的文档内容回答，不要编造信息
2. 如果检索内容不足以回答问题，明确告知用户
3. 引用文档时，在答案末尾注明参考来源
4. 使用 Markdown 格式排版，代码块用 ``` 标注
5. 回答要简洁、准确、有条理"""


class RAGEngine:
    """RAG 引擎"""

    def __init__(self, vector_store: VectorStore, model: str = "gpt-3.5-turbo"):
        self.vector_store = vector_store
        self.model = model
        self.client = AsyncOpenAI()

    async def chat_stream(
        self,
        message: str,
        document_ids: list[str] | None = None,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式 RAG 对话"""
        # 1. 检索相关文档
        relevant_docs = self.vector_store.similarity_search(message, k=5)

        # 按 file_id 过滤
        if document_ids:
            relevant_docs = [
                d for d in relevant_docs
                if d["metadata"].get("file_id") in document_ids
            ]

        # 2. 构建上下文
        context = ""
        sources = []
        seen_files = set()
        for doc in relevant_docs:
            context += f"\n---\n{doc['content']}\n"
            file_id = doc["metadata"].get("file_id", doc["metadata"].get("source", ""))
            if file_id and file_id not in seen_files:
                seen_files.add(file_id)
                sources.append({
                    "title": f"参考自《{doc['metadata'].get('filename', file_id)}》",
                    "snippet": doc["content"][:150],
                })

        # 3. 构建消息列表
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if context:
            messages.append({
                "role": "system",
                "content": f"以下是用户文档中的相关内容，请基于这些内容回答问题：\n{context}",
            })

        if history:
            for h in history[-10:]:  # 保留最近10轮上下文
                messages.append(h)

        messages.append({"role": "user", "content": message})

        # 4. 流式生成
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
