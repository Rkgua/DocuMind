"""向量存储 — ChromaDB + BAAI/bge-small-zh-v1.5 (ONNX 本地推理)"""

import os
import json
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer
from sqlmodel import select, func, delete
from database import get_session, DocumentChunkDB
from chromadb import PersistentClient
from chromadb.config import Settings


# ---------- BGE ONNX embedding ----------

class BGEOnnxEmbedding:
    """BAAI/bge-small-zh-v1.5 ONNX 本地推理（零 PyTorch 依赖）"""

    def __init__(self, model_id: str = "Xenova/bge-small-zh-v1.5"):
        cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
        # 查找下载好的 ONNX 模型文件
        self._model_path = self._find_file(cache_dir, "model_quantized.onnx")
        self._tokenizer_path = self._find_file(cache_dir, "tokenizer.json")

        self._session = ort.InferenceSession(self._model_path, providers=["CPUExecutionProvider"])
        self._tokenizer = Tokenizer.from_file(self._tokenizer_path)
        self._tokenizer.enable_truncation(max_length=512)
        self._tokenizer.enable_padding(pad_id=0, pad_token="[PAD]", length=512)
        self._query_prefix = "为这个句子生成表示以用于检索相关文章："

    def _find_file(self, root: str, name: str) -> str:
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                if fn == name:
                    return os.path.join(dirpath, fn)
        raise FileNotFoundError(f"找不到模型文件 {name}，请确保已通过 huggingface_hub 下载")

    def _mean_pooling(self, token_embeds: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
        mask = attention_mask.astype(float)[:, :, np.newaxis]
        return (token_embeds * mask).sum(axis=1) / mask.sum(axis=1).clip(min=1e-9)

    def _normalize(self, vecs: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / norms.clip(min=1e-9)

    def _tokenize(self, texts: list[str]):
        encoded = self._tokenizer.encode_batch(texts)
        input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
        return input_ids, attention_mask

    def encode(self, texts: list[str]) -> np.ndarray:
        input_ids, attention_mask = self._tokenize(texts)
        token_type_ids = np.zeros_like(input_ids)
        outputs = self._session.run(None, {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids,
        })
        token_embeds = outputs[0]
        vecs = self._mean_pooling(token_embeds, attention_mask)
        return self._normalize(vecs).astype(np.float32)

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        return self.encode(texts)

    def encode_query(self, query: str) -> list[float]:
        return self.encode([self._query_prefix + query])[0].tolist()


# 全局 embedding 实例
_embedder = BGEOnnxEmbedding()


# ---------- ChromaDB 向量存储 ----------

class VectorStore:
    """向量存储 — ChromaDB 持久化"""

    def __init__(self, persist_dir: str = "./data/vector_store"):
        os.makedirs(persist_dir, exist_ok=True)
        self.client = PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )

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

        # BGE 编码并写入 ChromaDB
        embeddings = _embedder.encode_documents(texts)
        self.collection.add(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=texts,
            metadatas=metadatas,
        )

    def similarity_search(self, query: str, k: int = 5) -> list[dict]:
        query_vec = _embedder.encode_query(query)
        results = self.collection.query(
            query_embeddings=[query_vec],
            n_results=k,
        )
        sources = []
        for i in range(len(results["ids"][0])):
            sources.append({
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "score": float(results["distances"][0][i]) if results.get("distances") else 0,
            })
        return sources

    def list_documents(self) -> list[dict]:
        """按 file_id 去重列出文档（单次 GROUP BY 查询，无 N+1）"""
        all_data = self.collection.get(include=["metadatas"])
        seen = {}
        for i in range(len(all_data["ids"])):
            meta = all_data["metadatas"][i]
            file_id = meta.get("file_id", meta.get("source", "unknown"))
            if file_id not in seen:
                seen[file_id] = {
                    "id": file_id,
                    "name": meta.get("filename", file_id),
                    "title": meta.get("title", meta.get("filename", file_id)),
                    "pages": "",
                }
        # 一次性统计所有文档块数
        if seen:
            with get_session() as db:
                stmt = (
                    select(DocumentChunkDB.file_id, func.count())
                    .where(DocumentChunkDB.file_id.in_(seen.keys()))
                    .group_by(DocumentChunkDB.file_id)
                )
                rows = db.exec(stmt).all()
                for file_id, cnt in rows:
                    if file_id in seen:
                        seen[file_id]["pages"] = f"{cnt}段"
        return list(seen.values())

    def delete_document(self, file_id: str):
        # ChromaDB：按 metadata 过滤删除
        chunk_data = self.collection.get(
            include=[],
            where={"file_id": file_id},
        )
        if chunk_data["ids"]:
            self.collection.delete(ids=chunk_data["ids"])
        elif not self.collection.get(include=[], where={"source": file_id})["ids"]:
            pass  # 未找到也无所谓，继续清 SQLite

        # SQLite：批量删除
        with get_session() as db:
            db.exec(delete(DocumentChunkDB).where(DocumentChunkDB.file_id == file_id))
            db.commit()

    def find_any_filename(self, filenames: list[str]) -> str | None:
        """批量检查，返回第一个已存在的文件名（单次 SQL）"""
        if not filenames:
            return None
        with get_session() as db:
            stmt = select(DocumentChunkDB.filename).where(
                DocumentChunkDB.filename.in_(filenames)
            ).limit(1)
            row = db.exec(stmt).first()
            return row if row else None

    def find_by_filename(self, filename: str) -> bool:
        return self.find_any_filename([filename]) is not None

    def get_chunks(self, file_id: str) -> list[dict]:
        with get_session() as db:
            stmt = select(DocumentChunkDB).where(DocumentChunkDB.file_id == file_id).order_by(DocumentChunkDB.id)
            rows = db.exec(stmt).all()
        return [{
            "id": r.id,
            "content": r.content,
            "page_info": r.page_info,
            "metadata": r.get_metadata(),
        } for r in rows]

    def count(self) -> int:
        return self.collection.count()
