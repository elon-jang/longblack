# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 개발 명령어

```bash
# 의존성 설치
uv sync --python 3.12

# 서버 실행 (테스트)
uv run python -m src.server

# 테스트 실행
uv run pytest

# 단일 테스트 실행
uv run pytest tests/test_storage.py::test_function_name -v
```

## 아키텍처

Claude MCP 플러그인으로 아티클을 스크랩하여 RAG 기반으로 저장/검색. 듀얼 스토리지 구조:
- **ChromaDB**: 벡터 임베딩 저장, 시맨틱 검색 (코사인 유사도)
- **SQLite**: 메타데이터, 전문(FTS5) 검색

### 데이터 흐름

1. **저장**: URL/PDF → `scraper.py` 추출 → `embeddings.py` 청킹(1000자, 200자 오버랩) + 임베딩 → `storage.py` ChromaDB/SQLite 저장
2. **검색**: 쿼리 → 임베딩 → ChromaDB 유사도 검색 → 청크별 점수 집계 → SQLite에서 전체 아티클 조회

### 임베딩 프로바이더

`EMBEDDING_PROVIDER` 환경변수로 선택 (기본값: `local`):
- `local`: all-MiniLM-L6-v2 (384차원, 무료)
- `openai`: text-embedding-3-small (1536차원, API키 필요)

프로바이더별 별도 ChromaDB 컬렉션 사용 (`articles_local`, `articles_openai`)

### 핵심 모듈

- `server.py`: MCP 서버 진입점, FastMCP 데코레이터로 6개 tool 정의
- `storage.py`: ArticleStorage 클래스 - ChromaDB + SQLite 통합 관리
- `scraper.py`: trafilatura/BeautifulSoup(URL), PyMuPDF(PDF) 콘텐츠 추출
- `embeddings.py`: 청킹 및 임베딩 생성 (OpenAI/Local 선택)
- `models.py`: Pydantic 모델 (Article, SearchResult, ScrapedContent 등)

### MCP Tools (6개)

| Tool | 설명 | 예상 크기 |
|------|------|----------|
| `save` | URL/PDF 저장 (자동 감지) | ~200자 |
| `search` | 하이브리드 검색 (제목+FTS+시맨틱) | ~1,200자 |
| `list` | 카테고리 + 아티클 목록 | ~2,500자 |
| `get` | 메타데이터 + summary (+ 선택적 본문) | ~1,500자 / ~4,500자 |
| `ask` | RAG 질문 답변용 청크 | ~5,500자 |
| `delete` | 삭제 | ~10자 |

### 도구 통합

| Before (9개) | After (6개) |
|--------------|-------------|
| save_article, save_pdf | save |
| list_articles, list_categories | list |
| get_article, read_content | get |
| get_relevant_chunks | ask |
| search, delete_article | search, delete |

### 워크플로우

```
# RAG 질문 → 1회 호출
ask("9.81파크 비즈니스 모델은?")

# 목록 조회 → 1회 호출
list()

# 상세 조회 → 1회 호출
get(article_id, include_content=True)
```

### 토큰 최적화 (Compacting 방지)

Claude Desktop 토큰 한도: 190,000

**문제**: 기존 구조에서 RAG 질문 시 연쇄 호출로 ~11,000자 소비
```
search(1,171) → get_article(906) → read_content(3,063) × 3회
```

**해결**: 도구 통합으로 호출 횟수 및 응답 크기 감소

| 시나리오 | Before | After | 절감 |
|----------|--------|-------|------|
| RAG 질문 | ~11,000자 (3회+) | ~5,500자 (1회) | 50%↓ |
| 목록 조회 | ~4,000자 (2회) | ~2,500자 (1회) | 37%↓ |
| 상세+본문 | ~4,500자 (2회) | ~4,500자 (1회) | 호출↓ |

**핵심 전략**:
- 연쇄 호출 제거 (2-3회 → 1회)
- 조건부 응답 (summary 있으면 본문 불포함)
- 강제 트렁케이션 (본문 3,000자 제한)

디버그 로그: `data/mcp_debug.log`
