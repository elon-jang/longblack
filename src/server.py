"""MCP Server for Article RAG Plugin."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

from .models import Article

# Debug logging - 절대 경로 사용
_log_file = Path("/Users/elon/elon/ai/projects/longblack/data/mcp_debug.log")
_log_file.parent.mkdir(exist_ok=True)


def log_tool(msg: str) -> None:
    """Log with direct file write."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(_log_file, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} - {msg}\n")


# 서버 시작 로그
log_tool("=== MCP Server Started ===")
from .storage import ArticleStorage
from .scraper import scrape_url, extract_pdf

mcp = FastMCP(name="longblack")

# Initialize storage (lazy loading)
_storage: Optional[ArticleStorage] = None


def get_storage() -> ArticleStorage:
    """Get or create storage instance."""
    global _storage
    if _storage is None:
        _storage = ArticleStorage()
    return _storage


@mcp.tool
def save_article(
    url: str,
    categories: list[str],
    description: Optional[str] = None,
    summary: Optional[str] = None,
    keywords: Optional[str] = None,
    tags: Optional[str] = None,
) -> dict:
    """Save an article from a URL.

    Args:
        url: The URL of the article to save
        categories: List of categories to tag the article with (e.g., ["ai", "tech"])
        description: 150자 이내 후킹/소개글 (optional)
        summary: 400-600자 bullet point 요약, 시사점/배울점 위주 (optional)
        keywords: Comma-separated keywords (optional)
        tags: Category-style tags, comma-separated (optional)

    Returns:
        Article ID and title on success
    """
    storage = get_storage()
    scraped = scrape_url(url)

    article = Article(
        title=scraped.title,
        content=scraped.content,
        url=scraped.url,
        source_type="url",
        author=scraped.author,
        published_date=scraped.published_date,
        categories=categories,
        description=description,
        summary=summary,
        keywords=keywords,
        tags=tags,
    )

    article_id = storage.save_article(article)
    return {
        "id": article_id,
        "title": article.title,
        "categories": categories,
        "content_length": len(article.content),
    }


@mcp.tool
def save_pdf(
    file_path: str,
    categories: list[str],
    description: Optional[str] = None,
    summary: Optional[str] = None,
    keywords: Optional[str] = None,
    tags: Optional[str] = None,
) -> dict:
    """Save an article from a PDF file.

    Args:
        file_path: Path to the PDF file
        categories: List of categories to tag the article with
        description: 150자 이내 후킹/소개글 (optional)
        summary: 400-600자 bullet point 요약, 시사점/배울점 위주 (optional)
        keywords: Comma-separated keywords (optional)
        tags: Category-style tags, comma-separated (optional)

    Returns:
        Article ID and title on success
    """
    storage = get_storage()
    scraped = extract_pdf(file_path)

    article = Article(
        title=scraped.title,
        content=scraped.content,
        source_type="pdf",
        author=scraped.author,
        published_date=scraped.published_date,
        categories=categories,
        description=description,
        summary=summary,
        keywords=keywords,
        tags=tags,
    )

    article_id = storage.save_article(article)
    return {
        "id": article_id,
        "title": article.title,
        "categories": categories,
        "content_length": len(article.content),
    }


@mcp.tool
def search(query: str, category: Optional[str] = None, limit: int = 5) -> list[dict]:
    """Search articles (hybrid: FTS + semantic).

    Args:
        query: Search query (natural language)
        category: Optional category to filter by
        limit: Maximum number of results (default: 5)

    Returns:
        List of matching articles with relevance scores
    """
    storage = get_storage()
    results = storage.search(query, category=category, limit=limit)

    result = [
        {
            "id": r.article.id,
            "title": r.article.title,
            "score": round(r.score, 3),
            "author": r.article.author,
            "excerpt": (r.matched_chunks[0][:200] if r.matched_chunks else r.article.content[:200]) + "...",
        }
        for r in results
    ]
    log_tool(f"search: query='{query[:50]}', {len(result)} items, {len(json.dumps(result, ensure_ascii=False))} chars")
    return result


@mcp.tool
def list_categories() -> list[dict]:
    """List all categories with article counts.

    Returns:
        List of categories with their names and article counts
    """
    storage = get_storage()
    categories = storage.list_categories()
    result = [{"name": c.name, "count": c.count} for c in categories]
    log_tool(f"list_categories: {len(result)} items, {len(json.dumps(result, ensure_ascii=False))} chars")
    return result


@mcp.tool
def get_article(article_id: str) -> Optional[dict]:
    """Get article metadata with summary. SUFFICIENT for answering questions.

    IMPORTANT: Do NOT call read_content after this. The summary/content_preview
    included here is enough to answer most questions about the article.

    Args:
        article_id: The article ID

    Returns:
        Article metadata with summary (400-600 chars) or content_preview (500 chars)
    """
    storage = get_storage()
    article = storage.get_article(article_id)

    if not article:
        return None

    result = {
        "id": article.id,
        "title": article.title,
        "content_length": len(article.content),
        "url": article.url,
        "source_type": article.source_type,
        "author": article.author,
        "published_date": article.published_date.isoformat() if article.published_date else None,
        "categories": article.categories,
        "created_at": article.created_at.isoformat(),
        "description": article.description,
        "keywords": article.keywords,
        "tags": article.tags,
    }

    # 조건부 응답: summary 있으면 summary, 없으면 content_preview
    if article.summary:
        result["summary"] = article.summary
    else:
        result["content_preview"] = article.content[:500] + "..." if len(article.content) > 500 else article.content

    log_tool(f"get_article: id={article_id}, has_summary={bool(article.summary)}, {len(json.dumps(result, ensure_ascii=False))} chars")
    return result


@mcp.tool
def read_content(article_id: str) -> str:
    """Read full article content. RARELY needed - get_article summary is usually enough.

    Only use when: (1) get_article has no summary AND (2) user explicitly requests full text.
    Do NOT call this just to "get more detail" - use get_relevant_chunks instead.

    Args:
        article_id: The article ID

    Returns:
        Article content (max 3000 chars)
    """
    storage = get_storage()
    article = storage.get_article(article_id)

    if not article:
        return f"Article not found: {article_id}"

    # 강제 트렁케이션: 항상 3000자 제한
    max_length = 3000
    content = article.content
    total_len = len(content)

    if len(content) > max_length:
        content = content[:max_length] + f"\n\n... ({total_len - max_length}자 생략)"

    result = f"# {article.title}\n\n{content}"
    log_tool(f"read_content: id={article_id}, {len(result)} chars (원본 {total_len}자, 제한 {max_length})")
    return result


@mcp.tool
def list_articles(
    category: Optional[str] = None,
    limit: int = 10,
    sort_by: str = "created_at",
) -> list[dict]:
    """List articles with optional filtering.

    Args:
        category: Filter by category (optional)
        limit: Maximum number of results (default: 10)
        sort_by: Sort field - "created_at", "title", or "published_date" (default: created_at)

    Returns:
        List of articles with basic metadata (use get_article for full details)
    """
    storage = get_storage()
    articles = storage.list_articles(category=category, limit=limit, sort_by=sort_by)

    result = [
        {
            "id": a.id,
            "title": a.title,
            "categories": a.categories,
            "author": a.author,
            "created_at": a.created_at.isoformat(),
        }
        for a in articles
    ]
    log_tool(f"list_articles: {len(result)} items, {len(json.dumps(result, ensure_ascii=False))} chars")
    return result


@mcp.tool
def get_relevant_chunks(
    query: str,
    article_id: Optional[str] = None,
    limit: int = 5,
) -> list[dict]:
    """Primary tool for answering questions about article content.

    Returns only relevant passages (not full article), efficient for RAG.
    Use this instead of read_content for most questions.

    Args:
        query: The question or search query
        article_id: Limit to specific article (optional)
        limit: Maximum number of chunks (default: 5)

    Returns:
        List of relevant text chunks with scores
    """
    storage = get_storage()
    result = storage.get_relevant_chunks(query=query, article_id=article_id, limit=limit)
    log_tool(f"get_relevant_chunks: query='{query[:50]}', {len(result)} items, {len(json.dumps(result, ensure_ascii=False))} chars")
    return result


@mcp.tool
def delete_article(article_id: str) -> bool:
    """Delete an article by ID.

    Args:
        article_id: The article ID to delete

    Returns:
        True if deleted, False if not found
    """
    storage = get_storage()
    return storage.delete_article(article_id)


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
