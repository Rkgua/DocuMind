"""网页抓取与解析"""

import uuid
import httpx
from bs4 import BeautifulSoup
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 模拟真实浏览器请求头，降低被拦截概率
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


async def scrape_url(url: str) -> list[dict]:
    """抓取网页并返回分块后的文档片段"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=_HEADERS, follow_redirects=True)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # 移除无用标签
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else url
    body = soup.body
    text = body.get_text(separator="\n", strip=True) if body else ""

    if not text.strip():
        return []

    # 分块
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        separators=["\n\n", "\n", "。", ".", "!", "？", " ", ""],
    )
    chunks = splitter.split_text(text)

    doc_id = str(uuid.uuid4())
    documents = []
    for i, chunk in enumerate(chunks):
        documents.append({
            "id": f"{doc_id}_seg{i}",
            "text": chunk,
            "metadata": {
                "file_id": doc_id,
                "filename": f"{title}.web",
                "source": url,
                "chunk": i,
            },
        })

    return documents
