"""Content extraction from URLs and PDFs."""

from datetime import datetime
from pathlib import Path
from typing import Optional
import re

import httpx
import trafilatura
from bs4 import BeautifulSoup
import fitz  # PyMuPDF

from .models import ScrapedContent


def clean_pdf_text(text: str) -> str:
    """Clean up PDF text with encoding issues (common in Korean PDFs)."""
    # Replace corrupted space characters
    replacements = {
        "#": " ",
        "$": ",",
        "!": " ",
        "%": " ",
        "&": "",
        "*": "",
        "(": "(",
        ")": ")",
        "'": "'",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # Clean up multiple spaces
    text = re.sub(r" +", " ", text)
    # Clean up multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def scrape_url(url: str) -> ScrapedContent:
    """Extract content from a URL using trafilatura."""
    # Fetch the page
    response = httpx.get(
        url,
        follow_redirects=True,
        timeout=30.0,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        },
    )
    response.raise_for_status()
    html = response.text

    # Extract main content using trafilatura
    content = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
    )

    if not content:
        # Fallback to BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()
        content = soup.get_text(separator="\n", strip=True)

    # Extract metadata
    metadata = trafilatura.extract_metadata(html)

    title = ""
    author = None
    published_date = None

    if metadata:
        title = metadata.title or ""
        author = metadata.author
        if metadata.date:
            try:
                published_date = datetime.fromisoformat(metadata.date)
            except ValueError:
                pass

    # Fallback title extraction
    if not title:
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)

    return ScrapedContent(
        title=title or "Untitled",
        content=content or "",
        author=author,
        published_date=published_date,
        url=url,
    )


def extract_pdf(file_path: str) -> ScrapedContent:
    """Extract content from a PDF file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    doc = fitz.open(file_path)

    # Extract text from all pages
    text_parts = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            text_parts.append(text)

    content = "\n\n".join(text_parts)

    # Clean up PDF encoding issues
    content = clean_pdf_text(content)

    # Try to extract title from metadata or first line
    title = doc.metadata.get("title", "") if doc.metadata else ""
    author = doc.metadata.get("author", "") if doc.metadata else ""

    if not title:
        # Use first non-empty line as title
        first_line = content.split("\n")[0].strip() if content else ""
        title = first_line[:100] if first_line else path.stem

    # Try to parse creation date
    published_date = None
    if doc.metadata and doc.metadata.get("creationDate"):
        date_str = doc.metadata["creationDate"]
        # PDF dates are often in format D:YYYYMMDDHHmmSS
        match = re.match(r"D:(\d{4})(\d{2})(\d{2})", date_str)
        if match:
            try:
                published_date = datetime(
                    int(match.group(1)),
                    int(match.group(2)),
                    int(match.group(3)),
                )
            except ValueError:
                pass

    doc.close()

    return ScrapedContent(
        title=title,
        content=content,
        author=author or None,
        published_date=published_date,
    )
