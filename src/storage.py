"""Storage module combining ChromaDB (vectors) and SQLite (metadata)."""

import sqlite3
from pathlib import Path
from typing import Optional
import json

import chromadb
from chromadb.config import Settings

from .models import Article, SearchResult, Category
from .embeddings import chunk_text, create_embeddings, create_embedding, get_provider

DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data"
BATCH_SIZE = 50  # Chunks per batch for ChromaDB add


class ArticleStorage:
    """Combined storage using ChromaDB for vectors and SQLite for metadata."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.provider = get_provider()

        # Initialize ChromaDB with provider-specific collection
        self.chroma_client = chromadb.PersistentClient(
            path=str(self.data_dir / "chroma"),
            settings=Settings(anonymized_telemetry=False),
        )
        # Use different collection per provider (different embedding dimensions)
        collection_name = f"articles_{self.provider}"
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        # Initialize SQLite
        self.db_path = self.data_dir / "articles.db"
        self._init_sqlite()

    def _init_sqlite(self):
        """Initialize SQLite database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    url TEXT,
                    source_type TEXT DEFAULT 'url',
                    author TEXT,
                    published_date TEXT,
                    categories TEXT,
                    created_at TEXT NOT NULL,
                    summary TEXT,
                    keywords TEXT,
                    insights TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_categories ON articles(categories)
            """)

            # Migration: add new columns if they don't exist
            cursor = conn.execute("PRAGMA table_info(articles)")
            columns = {row[1] for row in cursor.fetchall()}
            for col in ["summary", "keywords", "insights"]:
                if col not in columns:
                    conn.execute(f"ALTER TABLE articles ADD COLUMN {col} TEXT")

            # Drop and recreate FTS table with keywords
            conn.execute("DROP TABLE IF EXISTS articles_fts")
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                    id, title, content, keywords, tokenize='porter unicode61'
                )
            """)
            # Rebuild FTS index from existing data
            conn.execute("""
                INSERT INTO articles_fts (id, title, content, keywords)
                SELECT id, title, content, COALESCE(keywords, '') FROM articles
            """)
            conn.commit()

    def save_article(self, article: Article) -> str:
        """Save article to both ChromaDB and SQLite."""
        # Chunk content and create embeddings
        chunks = chunk_text(article.content)
        embeddings = create_embeddings(chunks)

        # Store in ChromaDB (batch processing)
        chunk_ids = [f"{article.id}_chunk_{i}" for i in range(len(chunks))]
        metadata = article.to_metadata()

        for i in range(0, len(chunks), BATCH_SIZE):
            batch_end = min(i + BATCH_SIZE, len(chunks))
            self.collection.add(
                ids=chunk_ids[i:batch_end],
                embeddings=embeddings[i:batch_end],
                documents=chunks[i:batch_end],
                metadatas=[metadata for _ in range(i, batch_end)],
            )

        # Store in SQLite
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO articles
                (id, title, content, url, source_type, author, published_date, categories, created_at, summary, keywords, insights)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article.id,
                    article.title,
                    article.content,
                    article.url,
                    article.source_type,
                    article.author,
                    article.published_date.isoformat() if article.published_date else None,
                    ",".join(article.categories),
                    article.created_at.isoformat(),
                    article.summary,
                    article.keywords,
                    article.insights,
                ),
            )
            # Update FTS index
            conn.execute("DELETE FROM articles_fts WHERE id = ?", (article.id,))
            conn.execute(
                "INSERT INTO articles_fts (id, title, content, keywords) VALUES (?, ?, ?, ?)",
                (article.id, article.title, article.content, article.keywords or ""),
            )
            conn.commit()

        return article.id

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Search articles using semantic similarity."""
        query_embedding = create_embedding(query)

        # Search ChromaDB (filter by category in post-processing)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit * 5,  # Get more to account for dedup and filtering
            include=["documents", "distances", "metadatas"],
        )

        # Deduplicate by article ID and aggregate scores
        article_scores: dict[str, tuple[float, list[str]]] = {}
        for i, doc_id in enumerate(results["ids"][0]):
            article_id = doc_id.rsplit("_chunk_", 1)[0]
            distance = results["distances"][0][i]
            score = 1 - distance  # Convert distance to similarity
            chunk = results["documents"][0][i]
            metadata = results["metadatas"][0][i]

            # Filter by category (post-processing)
            if category:
                chunk_categories = metadata.get("categories", "").split(",")
                if category not in chunk_categories:
                    continue

            if article_id not in article_scores:
                article_scores[article_id] = (score, [chunk])
            else:
                existing_score, chunks = article_scores[article_id]
                article_scores[article_id] = (max(existing_score, score), chunks + [chunk])

        # Get full articles from SQLite
        search_results = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            for article_id, (score, chunks) in sorted(
                article_scores.items(), key=lambda x: x[1][0], reverse=True
            )[:limit]:
                row = conn.execute(
                    "SELECT * FROM articles WHERE id = ?", (article_id,)
                ).fetchone()
                if row:
                    article = self._row_to_article(row)
                    search_results.append(
                        SearchResult(article=article, score=score, matched_chunks=chunks[:3])
                    )

        return search_results

    def fulltext_search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Full-text search using SQLite FTS5."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if category:
                rows = conn.execute(
                    """
                    SELECT a.*, bm25(articles_fts) as score
                    FROM articles_fts f
                    JOIN articles a ON a.id = f.id
                    WHERE articles_fts MATCH ? AND a.categories LIKE ?
                    ORDER BY score
                    LIMIT ?
                    """,
                    (query, f"%{category}%", limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT a.*, bm25(articles_fts) as score
                    FROM articles_fts f
                    JOIN articles a ON a.id = f.id
                    WHERE articles_fts MATCH ?
                    ORDER BY score
                    LIMIT ?
                    """,
                    (query, limit),
                ).fetchall()

            return [
                SearchResult(
                    article=self._row_to_article(row),
                    score=-row["score"],  # BM25 returns negative scores
                )
                for row in rows
            ]

    def get_article(self, article_id: str) -> Optional[Article]:
        """Get article by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM articles WHERE id = ?", (article_id,)
            ).fetchone()
            return self._row_to_article(row) if row else None

    def delete_article(self, article_id: str) -> bool:
        """Delete article from both stores."""
        # Delete from ChromaDB using where filter (efficient)
        self.collection.delete(where={"article_id": article_id})

        # Delete from SQLite
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM articles WHERE id = ?", (article_id,))
            conn.execute("DELETE FROM articles_fts WHERE id = ?", (article_id,))
            conn.commit()
            return cursor.rowcount > 0

    def list_categories(self) -> list[Category]:
        """List all categories with article counts."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT categories FROM articles").fetchall()

        category_counts: dict[str, int] = {}
        for (categories_str,) in rows:
            if categories_str:
                for cat in categories_str.split(","):
                    cat = cat.strip()
                    if cat:
                        category_counts[cat] = category_counts.get(cat, 0) + 1

        return [
            Category(name=name, count=count)
            for name, count in sorted(category_counts.items())
        ]

    def _row_to_article(self, row: sqlite3.Row) -> Article:
        """Convert SQLite row to Article model."""
        from datetime import datetime

        return Article(
            id=row["id"],
            title=row["title"],
            content=row["content"],
            url=row["url"],
            source_type=row["source_type"],
            author=row["author"],
            published_date=datetime.fromisoformat(row["published_date"]) if row["published_date"] else None,
            categories=row["categories"].split(",") if row["categories"] else [],
            created_at=datetime.fromisoformat(row["created_at"]),
            summary=row["summary"],
            keywords=row["keywords"],
            insights=row["insights"],
        )

    def list_articles(
        self,
        category: Optional[str] = None,
        limit: int = 20,
        sort_by: str = "created_at",
    ) -> list[Article]:
        """List articles with optional category filter."""
        valid_sorts = {"created_at", "title", "published_date"}
        if sort_by not in valid_sorts:
            sort_by = "created_at"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if category:
                rows = conn.execute(
                    f"""
                    SELECT * FROM articles
                    WHERE categories LIKE ?
                    ORDER BY {sort_by} DESC
                    LIMIT ?
                    """,
                    (f"%{category}%", limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    f"""
                    SELECT * FROM articles
                    ORDER BY {sort_by} DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

            return [self._row_to_article(row) for row in rows]

    def get_relevant_chunks(
        self,
        query: str,
        article_id: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Get relevant chunks for RAG."""
        query_embedding = create_embedding(query)

        # Build where filter
        where_filter = {"article_id": article_id} if article_id else None

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where=where_filter,
            include=["documents", "distances", "metadatas"],
        )

        chunks = []
        for i, doc_id in enumerate(results["ids"][0]):
            chunk_article_id = doc_id.rsplit("_chunk_", 1)[0]
            distance = results["distances"][0][i]
            score = 1 - distance
            content = results["documents"][0][i]
            metadata = results["metadatas"][0][i]

            chunks.append({
                "article_id": chunk_article_id,
                "title": metadata.get("title", ""),
                "content": content,
                "score": round(score, 3),
            })

        return chunks
