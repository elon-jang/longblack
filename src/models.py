"""Data models for the Article RAG Plugin."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class Article(BaseModel):
    """Article model for storage and retrieval."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    content: str
    url: Optional[str] = None
    source_type: str = "url"  # "url" or "pdf"
    author: Optional[str] = None
    published_date: Optional[datetime] = None
    categories: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    description: Optional[str] = None  # 150자 이내 후킹/소개글
    summary: Optional[str] = None  # 400-600자, bullet 3-5개, 시사점/배울점 위주
    keywords: Optional[str] = None  # 쉼표 구분 키워드
    tags: Optional[str] = None  # 카테고리성 태그 (쉼표 구분)

    def to_metadata(self) -> dict:
        """Convert to metadata dict for ChromaDB."""
        return {
            "article_id": self.id,
            "title": self.title,
            "url": self.url or "",
            "source_type": self.source_type,
            "author": self.author or "",
            "published_date": self.published_date.isoformat() if self.published_date else "",
            "categories": ",".join(self.categories),
            "created_at": self.created_at.isoformat(),
            "summary": self.summary or "",
            "keywords": self.keywords or "",
            "description": self.description or "",
            "tags": self.tags or "",
        }


class ArticleChunk(BaseModel):
    """A chunk of article content for embedding."""

    article_id: str
    chunk_index: int
    content: str


class SearchResult(BaseModel):
    """Search result with article and relevance score."""

    article: Article
    score: float
    matched_chunks: list[str] = Field(default_factory=list)


class Category(BaseModel):
    """Category with article count."""

    name: str
    count: int


class ScrapedContent(BaseModel):
    """Content extracted from URL or PDF."""

    title: str
    content: str
    author: Optional[str] = None
    published_date: Optional[datetime] = None
    url: Optional[str] = None
