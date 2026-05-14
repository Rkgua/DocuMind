"""Pydantic 请求/响应模型"""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    document_ids: list[str] | None = None
    session_id: str | None = None


class ScrapeRequest(BaseModel):
    url: str


class Conversation(BaseModel):
    id: str
    title: str
    created_at: str


class ConversationListResponse(BaseModel):
    conversations: list[Conversation]


class DocumentItem(BaseModel):
    id: str
    name: str
    title: str = ""
    pages: str = ""
    selected: bool = True


class DocumentListResponse(BaseModel):
    documents: list[DocumentItem]


class ReferenceSource(BaseModel):
    title: str
    snippet: str


class ReferencesResponse(BaseModel):
    sources: list[ReferenceSource]


class UploadResponse(BaseModel):
    files: list[dict]
