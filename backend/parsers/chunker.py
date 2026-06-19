"""文本分块器 — 共用配置"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

# 唯一分块实例
_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
    separators=["\n\n", "\n", "。", ".", "!", "？", " ", ""],
)


def split_text(text: str) -> list[str]:
    return _splitter.split_text(text)
