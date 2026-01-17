"""MCP Server for Article RAG Plugin."""

from typing import Optional
from fastmcp import FastMCP

from .models import Article
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
    summary: Optional[str] = None,
    keywords: Optional[str] = None,
    insights: Optional[str] = None,
) -> dict:
    """Save an article from a URL.

    Args:
        url: The URL of the article to save
        categories: List of categories to tag the article with (e.g., ["ai", "tech"])
        summary: 3-5 sentence summary (optional, Claude can generate)
        keywords: Comma-separated keywords (optional)
        insights: Key insights, newline-separated (optional)

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
        summary=summary,
        keywords=keywords,
        insights=insights,
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
    summary: Optional[str] = None,
    keywords: Optional[str] = None,
    insights: Optional[str] = None,
) -> dict:
    """Save an article from a PDF file.

    Args:
        file_path: Path to the PDF file
        categories: List of categories to tag the article with
        summary: 3-5 sentence summary (optional, Claude can generate)
        keywords: Comma-separated keywords (optional)
        insights: Key insights, newline-separated (optional)

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
        summary=summary,
        keywords=keywords,
        insights=insights,
    )

    article_id = storage.save_article(article)
    return {
        "id": article_id,
        "title": article.title,
        "categories": categories,
        "content_length": len(article.content),
    }


@mcp.tool
def search(query: str, category: Optional[str] = None, limit: int = 10) -> list[dict]:
    """Search articles using semantic similarity.

    Args:
        query: Search query (natural language)
        category: Optional category to filter by
        limit: Maximum number of results (default: 10)

    Returns:
        List of matching articles with relevance scores
    """
    storage = get_storage()
    results = storage.search(query, category=category, limit=limit)

    return [
        {
            "id": r.article.id,
            "title": r.article.title,
            "score": round(r.score, 3),
            "url": r.article.url,
            "categories": r.article.categories,
            "author": r.article.author,
            "excerpt": r.matched_chunks[0][:500] if r.matched_chunks else r.article.content[:500],
        }
        for r in results
    ]


@mcp.tool
def list_categories() -> list[dict]:
    """List all categories with article counts.

    Returns:
        List of categories with their names and article counts
    """
    storage = get_storage()
    categories = storage.list_categories()
    return [{"name": c.name, "count": c.count} for c in categories]


@mcp.tool
def get_article(article_id: str) -> Optional[dict]:
    """Get article metadata by ID (use read_content for full text).

    Args:
        article_id: The article ID

    Returns:
        Article metadata or None if not found
    """
    storage = get_storage()
    article = storage.get_article(article_id)

    if not article:
        return None

    return {
        "id": article.id,
        "title": article.title,
        "content_length": len(article.content),
        "url": article.url,
        "source_type": article.source_type,
        "author": article.author,
        "published_date": article.published_date.isoformat() if article.published_date else None,
        "categories": article.categories,
        "created_at": article.created_at.isoformat(),
        "summary": article.summary,
        "keywords": article.keywords,
        "insights": article.insights,
    }


@mcp.tool
def read_content(article_id: str) -> str:
    """Read article content as plain text.

    Args:
        article_id: The article ID

    Returns:
        Article content as formatted text, or error message if not found
    """
    storage = get_storage()
    article = storage.get_article(article_id)

    if not article:
        return f"Article not found: {article_id}"

    # Format as readable text
    lines = [
        f"# {article.title}",
        "",
        f"- 카테고리: {', '.join(article.categories)}",
        f"- 저자: {article.author or '(없음)'}",
        f"- 출처: {article.url or article.source_type}",
        f"- 저장일: {article.created_at.strftime('%Y-%m-%d %H:%M')}",
    ]

    if article.summary:
        lines.extend(["", "## 요약", article.summary])

    if article.insights:
        lines.extend(["", "## 핵심 인사이트", article.insights])

    lines.extend(["", "---", "", article.content])
    return "\n".join(lines)


@mcp.tool
def list_articles(
    category: Optional[str] = None,
    limit: int = 20,
    sort_by: str = "created_at",
) -> list[dict]:
    """List articles with optional filtering.

    Args:
        category: Filter by category (optional)
        limit: Maximum number of results (default: 20)
        sort_by: Sort field - "created_at", "title", or "published_date" (default: created_at)

    Returns:
        List of articles with metadata
    """
    storage = get_storage()
    articles = storage.list_articles(category=category, limit=limit, sort_by=sort_by)

    return [
        {
            "id": a.id,
            "title": a.title,
            "categories": a.categories,
            "author": a.author,
            "created_at": a.created_at.isoformat(),
            "summary": a.summary,
            "keywords": a.keywords,
        }
        for a in articles
    ]


@mcp.tool
def get_relevant_chunks(
    query: str,
    article_id: Optional[str] = None,
    limit: int = 5,
) -> list[dict]:
    """Get relevant chunks for RAG-based question answering.

    Args:
        query: The question or search query
        article_id: Limit to specific article (optional)
        limit: Maximum number of chunks (default: 5)

    Returns:
        List of relevant text chunks with scores
    """
    storage = get_storage()
    return storage.get_relevant_chunks(query=query, article_id=article_id, limit=limit)


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
