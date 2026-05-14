"""向量存储 — vectors.npy 存向量，SQLite 存文本和元数据"""

import os
import re
import json
import numpy as np
from typing import Optional
from sqlmodel import select
from database import get_session, DocumentChunkDB


class LocalEmbedding:
    """基于字符 n-gram 哈希的轻量 embedding"""

    def __init__(self, dim: int = 256):
        self.dim = dim
        self._rng = np.random.RandomState(42)
        self._hash_coeff = self._rng.randn(dim, 128)

    def _tokenize(self, text: str) -> list[str]:
        text = text.lower()
        text = re.sub(r'[^a-z0-9\u4e00-\u9fff]', ' ', text)
        tokens = []
        for n in (2, 3):
            for i in range(len(text) - n + 1):
                gram = text[i:i+n]
                if gram.strip():
                    tokens.append(gram)
        return tokens

    def _hash_ngram(self, gram: str) -> int:
        return abs(hash(gram)) % 128

    def encode(self, texts: list[str]) -> np.ndarray:
        embeddings = []
        for text in texts:
            vec = np.zeros(self.dim)
            tokens = self._tokenize(text)
            if not tokens:
                embeddings.append(vec)
                continue
            for token in tokens:
                bucket = self._hash_ngram(token)
                vec += self._hash_coeff[:, bucket]
            vec /= max(len(tokens), 1)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            embeddings.append(vec)
        return np.array(embeddings, dtype=np.float32)


class VectorStore:
    """向量存储 — vectors.npy 做快速检索，SQLite 存完整数据"""

    def __init__(self, persist_dir: str = "./data/vector_store"):
        self.persist_dir = persist_dir
        os.makedirs(persist_dir, exist_ok=True)
        self._embedder = LocalEmbedding()
        self._vectors_path = os.path.join(persist_dir, "vectors.npy")
        self._vectors: Optional[np.ndarray] = None

        # 加载向量缓存
        if os.path.exists(self._vectors_path):
            try:
                self._vectors = np.load(self._vectors_path, allow_pickle=False)
            except Exception:
                self._vectors = None
        # 如果 SQLite 有数据但向量缓存为空，重建
        if self._vectors is None:
            self._rebuild_cache()

    def _rebuild_cache(self):
        """从 SQLite 重建向量缓存"""
        with get_session() as db:
            stmt = select(DocumentChunkDB).order_by(DocumentChunkDB.created_at)
            rows = db.exec(stmt).all()
            if not rows:
                self._vectors = None
                return
            texts = [r.content for r in rows]
            self._vectors = self._embedder.encode(texts)
            np.save(self._vectors_path, self._vectors)

    def _save_vectors(self):
        if self._vectors is not None:
            np.save(self._vectors_path, self._vectors)

    def add_documents(self, ids: list[str], texts: list[str], metadatas: list[dict]):
        # 写入 SQLite
        with get_session() as db:
            for i, chunk_id in enumerate(ids):
                meta = metadatas[i]
                chunk = DocumentChunkDB(
                    id=chunk_id,
                    file_id=meta.get("file_id", ""),
                    filename=meta.get("filename", ""),
                    content=texts[i],
                    page_info=meta.get("pages", ""),
                )
                chunk.set_metadata(meta)
                db.add(chunk)
            db.commit()

        # 更新向量缓存
        new_vecs = self._embedder.encode(texts)
        if self._vectors is None:
            self._vectors = new_vecs
        else:
            self._vectors = np.vstack([self._vectors, new_vecs])
        self._save_vectors()

    def similarity_search(self, query: str, k: int = 5) -> list[dict]:
        if self._vectors is None or self._vectors.shape[0] == 0:
            return []

        query_vec = self._embedder.encode([query])[0]
        norms = np.linalg.norm(self._vectors, axis=1)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []
        similarities = np.dot(self._vectors, query_vec) / (norms * query_norm + 1e-10)
        top_k = min(k, len(similarities))
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        # 从 SQLite 获取完整数据
        results = []
        with get_session() as db:
            for idx in top_indices:
                row = db.get(DocumentChunkDB, self._get_chunk_id(idx))
                if row:
                    results.append({
                        "id": row.id,
                        "content": row.content,
                        "metadata": row.get_metadata(),
                        "score": float(1 - similarities[idx]),
                    })
        return results

    def _get_chunk_id(self, vector_index: int) -> str:
        """从向量索引获取对应的 chunk id（通过 SQLite 有序查询）"""
        with get_session() as db:
            stmt = select(DocumentChunkDB.id).order_by(DocumentChunkDB.created_at)
            rows = db.exec(stmt).all()
            if vector_index < len(rows):
                return rows[vector_index]
        return ""

    def list_documents(self) -> list[dict]:
        """按 file_id 去重列出文档"""
        with get_session() as db:
            stmt = select(
                DocumentChunkDB.file_id,
                DocumentChunkDB.filename,
                DocumentChunkDB.metadata_json,
            ).distinct().order_by(DocumentChunkDB.filename)
            rows = db.exec(stmt).all()

        seen = {}
        for file_id, filename, meta_json in rows:
            if file_id not in seen:
                meta = json.loads(meta_json) if meta_json else {}
                with get_session() as db2:
                    count = db2.exec(
                        select(DocumentChunkDB).where(DocumentChunkDB.file_id == file_id)
                    ).all()
                seen[file_id] = {
                    "id": file_id,
                    "name": filename,
                    "title": meta.get("title", filename),
                    "pages": f"{len(count)}段",
                }
        return list(seen.values())

    def delete_document(self, file_id: str):
        # 从 SQLite 删除
        with get_session() as db:
            stmt = select(DocumentChunkDB).where(DocumentChunkDB.file_id == file_id)
            rows = db.exec(stmt).all()
            for r in rows:
                db.delete(r)
            db.commit()

        # 重建向量缓存
        self._vectors = None
        self._rebuild_cache()

    def find_by_filename(self, filename: str) -> bool:
        """检查文件名是否已存在"""
        with get_session() as db:
            stmt = select(DocumentChunkDB).where(
                DocumentChunkDB.filename == filename
            ).limit(1)
            row = db.exec(stmt).first()
            return row is not None

    def count(self) -> int:
        with get_session() as db:
            stmt = select(DocumentChunkDB)
            rows = db.exec(stmt).all()
            return len(rows)
