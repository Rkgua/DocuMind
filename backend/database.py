"""SQLite 数据库 — 模型与连接"""

import json
from datetime import datetime
from sqlmodel import SQLModel, Field, create_engine, Session, select


# ==================== 数据库连接 ====================

DATABASE_URL = "sqlite:///./documind.db"
engine = create_engine(DATABASE_URL, echo=False)


def init_db():
    """创建所有表（幂等，重复调用安全）"""
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """获取数据库会话"""
    return Session(engine)


# ==================== 数据表模型 ====================

class ConversationDB(SQLModel, table=True):
    """历史对话表"""
    __tablename__ = "conversations"

    id: str = Field(primary_key=True)
    title: str = Field(max_length=100)
    created_at: datetime = Field(default_factory=datetime.now)
    messages: str = Field(default="[]")  # JSON 字符串

    def get_messages(self) -> list[dict]:
        return json.loads(self.messages)

    def set_messages(self, msgs: list[dict]):
        self.messages = json.dumps(msgs, ensure_ascii=False)


class DocumentMetaDB(SQLModel, table=True):
    """文档元数据表（对应 ChromaDB 中的文档）"""
    __tablename__ = "document_meta"

    id: str = Field(primary_key=True)           # ChromaDB 中的 file_id
    name: str = Field(max_length=255)
    pages: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.now)
