"""SQLite 数据库 — 统一存储所有数据"""

import json
import os
from datetime import datetime
from sqlmodel import SQLModel, Field, create_engine, Session, select

os.makedirs("data/database", exist_ok=True)
DATABASE_URL = "sqlite:///./data/database/documind.db"
engine = create_engine(DATABASE_URL, echo=False)


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)


class ConversationDB(SQLModel, table=True):
    """历史对话"""
    __tablename__ = "conversations"

    id: str = Field(primary_key=True)
    title: str = Field(max_length=100)
    created_at: datetime = Field(default_factory=datetime.now)
    messages: str = Field(default="[]")

    def get_messages(self) -> list[dict]:
        return json.loads(self.messages)

    def set_messages(self, msgs: list[dict]):
        self.messages = json.dumps(msgs, ensure_ascii=False)


class DocumentChunkDB(SQLModel, table=True):
    """文档块 — 每个文件切分为多个块，逐行存储"""
    __tablename__ = "document_chunks"

    id: str = Field(primary_key=True)              # 形如 "<file_uuid>_seg0"
    file_id: str = Field(index=True)               # 文件 UUID
    filename: str = Field(index=True)               # 原始文件名
    content: str = Field(default="")                # 块文本
    page_info: str = Field(default="")              # 页面/段信息
    created_at: datetime = Field(default_factory=datetime.now)

    # 元数据（JSON 字符串，存放 file_id/filename/source 等）
    metadata_json: str = Field(default="{}")

    def get_metadata(self) -> dict:
        return json.loads(self.metadata_json)

    def set_metadata(self, meta: dict):
        self.metadata_json = json.dumps(meta, ensure_ascii=False)
