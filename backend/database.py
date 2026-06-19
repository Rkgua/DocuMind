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
    """历史对话元信息"""
    __tablename__ = "conversations"

    id: str = Field(primary_key=True)
    title: str = Field(max_length=100)
    created_at: datetime = Field(default_factory=datetime.now)


class MessageDB(SQLModel, table=True):
    """单条对话消息"""
    __tablename__ = "messages"

    id: str = Field(primary_key=True)
    conversation_id: str = Field(foreign_key="conversations.id", index=True)
    role: str                                   # "user" | "assistant"
    content: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.now)


class DocumentChunkDB(SQLModel, table=True):
    """文档块 — 每个文件切分为多个块，逐行存储"""
    __tablename__ = "document_chunks"

    id: str = Field(primary_key=True)
    file_id: str = Field(index=True)
    filename: str = Field(index=True)
    content: str = Field(default="")
    page_info: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.now)

    metadata_json: str = Field(default="{}")

    def get_metadata(self) -> dict:
        return json.loads(self.metadata_json)

    def set_metadata(self, meta: dict):
        self.metadata_json = json.dumps(meta, ensure_ascii=False)
