"""轻量向量存储（纯 numpy 实现，零网络依赖）"""

import os
import json
import re
import pickle
import numpy as np
from typing import Optional


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
    """轻量向量存储，使用 numpy + pickle 持久化"""

    def __init__(self, persist_dir: str = "./data/vector_store"):
        self.persist_dir = persist_dir
        os.makedirs(persist_dir, exist_ok=True)
        self._embedder = LocalEmbedding()
        self._data_path = os.path.join(persist_dir, "vectors.pkl")
        self._meta_path = os.path.join(persist_dir, "metadata.json")
        self._vectors: Optional[np.ndarray] = None
        self._ids: list[str] = []
        self._documents: list[str] = []
        self._metadatas: list[dict] = []
        self._load()

    def _load(self):
        if os.path.exists(self._data_path) and os.path.exists(self._meta_path):
            try:
                self._vectors = np.load(self._data_path, allow_pickle=False)
                with open(self._meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                self._ids = meta["ids"]
                self._documents = meta["documents"]
                self._metadatas = meta["metadatas"]
            except Exception:
                self._vectors = None

    def _save(self):
        if self._vectors is not None:
            np.save(self._data_path, self._vectors)
        with open(self._meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "ids": self._ids,
                "documents": self._documents,
                "metadatas": self._metadatas,
            }, f, ensure_ascii=False, indent=2)

    def add_documents(self, ids: list[str], texts: list[str], metadatas: list[dict]):
        new_vecs = self._embedder.encode(texts)
        if self._vectors is None:
            self._vectors = new_vecs
        else:
            self._vectors = np.vstack([self._vectors, new_vecs])
        self._ids.extend(ids)
        self._documents.extend(texts)
        self._metadatas.extend(metadatas)
        self._save()

    def similarity_search(self, query: str, k: int = 5) -> list[dict]:
        if self._vectors is None or len(self._ids) == 0:
            return []
        query_vec = self._embedder.encode([query])[0]
        # 余弦相似度
        norms = np.linalg.norm(self._vectors, axis=1)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []
        similarities = np.dot(self._vectors, query_vec) / (norms * query_norm + 1e-10)
        top_k = min(k, len(similarities))
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        results = []
        for idx in top_indices:
            results.append({
                "id": self._ids[idx],
                "content": self._documents[idx],
                "metadata": self._metadatas[idx],
                "score": float(1 - similarities[idx]),
            })
        return results

    def list_documents(self) -> list[dict]:
        seen = {}
        for i, mid in enumerate(self._ids):
            meta = self._metadatas[i]
            file_id = meta.get("file_id", meta.get("source", "unknown"))
            if file_id not in seen:
                seen[file_id] = {
                    "id": file_id,
                    "name": meta.get("filename", file_id),
                    "pages": meta.get("pages", ""),
                }
        return list(seen.values())

    def delete_document(self, file_id: str):
        keep_indices = []
        for i, mid in enumerate(self._ids):
            meta = self._metadatas[i]
            if meta.get("file_id") != file_id and meta.get("source") != file_id:
                keep_indices.append(i)
        if len(keep_indices) == len(self._ids):
            return
        if keep_indices:
            self._vectors = self._vectors[keep_indices]
            self._ids = [self._ids[i] for i in keep_indices]
            self._documents = [self._documents[i] for i in keep_indices]
            self._metadatas = [self._metadatas[i] for i in keep_indices]
        else:
            self._vectors = None
            self._ids = []
            self._documents = []
            self._metadatas = []
        self._save()

    def count(self) -> int:
        return len(self._ids)
