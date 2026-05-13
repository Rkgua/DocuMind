"""ChromaDB 向量存储封装"""

import os
import chromadb
from chromadb.config import Settings
from openai import OpenAI


class VectorStore:
    """向量数据库操作层"""

    def __init__(self, persist_dir: str = "./chroma_data"):
        os.makedirs(persist_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )
        self._openai = OpenAI()

    def add_documents(self, ids: list[str], texts: list[str], metadatas: list[dict]):
        """添加文档片段到向量库"""
        response = self._openai.embeddings.create(
            model="text-embedding-v2",
            input=texts,
        )
        embeddings = [item.embedding for item in response.data]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

    def similarity_search(self, query: str, k: int = 5) -> list[dict]:
        """向量相似度搜索"""
        response = self._openai.embeddings.create(
            model="text-embedding-v2",
            input=query,
        )
        query_embedding = response.data[0].embedding

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
        )

        sources = []
        for i in range(len(results["ids"][0])):
            sources.append({
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "score": results["distances"][0][i] if results.get("distances") else 0,
            })
        return sources

    def list_documents(self) -> list[dict]:
        """列出所有文档（按源文件去重）"""
        all_data = self.collection.get()
        seen = {}
        for i in range(len(all_data["ids"])):
            meta = all_data["metadatas"][i]
            file_id = meta.get("file_id", meta.get("source", "unknown"))
            if file_id not in seen:
                seen[file_id] = {
                    "id": file_id,
                    "name": meta.get("filename", file_id),
                    "pages": meta.get("pages", ""),
                }
        return list(seen.values())

    def delete_document(self, file_id: str):
        """删除某个文档的所有片段"""
        all_data = self.collection.get()
        ids_to_delete = []
        for i in range(len(all_data["ids"])):
            meta = all_data["metadatas"][i]
            if meta.get("file_id") == file_id or meta.get("source") == file_id:
                ids_to_delete.append(all_data["ids"][i])
        if ids_to_delete:
            self.collection.delete(ids=ids_to_delete)

    def count(self) -> int:
        """向量库中的片段总数"""
        return self.collection.count()
