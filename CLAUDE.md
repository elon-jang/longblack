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

- `server.py`: MCP 서버 진입점, FastMCP 데코레이터로 9개 tool 정의
- `storage.py`: ArticleStorage 클래스 - ChromaDB + SQLite 통합 관리
- `scraper.py`: trafilatura/BeautifulSoup(URL), PyMuPDF(PDF) 콘텐츠 추출
- `embeddings.py`: 청킹 및 임베딩 생성 (OpenAI/Local 선택)
- `models.py`: Pydantic 모델 (Article, SearchResult, ScrapedContent 등)

### MCP Tools 요약

| Tool | 설명 | 응답 내용 | limit/max | 예상 크기 |
|------|------|----------|-----------|----------|
| `search` | 시맨틱 검색 | id, title, score, author, excerpt(200자) | limit=5 | ~3,000자 |
| `list_articles` | 목록 조회 | id, title, categories, author, created_at | limit=20 | ~2,000자 |
| `list_categories` | 카테고리 목록 | name, count | - | ~200자 |
| `get_article` | 메타데이터 | 전체 메타 + summary 또는 content_preview(500자) | - | ~1,500자 |
| `read_content` | 본문 읽기 | 제목 + content만 | max=3000 | ~3,100자 |
| `get_relevant_chunks` | RAG 청크 | article_id, title, content(청크), score | limit=5 | ~5,000자 |
| `save_article` | URL 저장 | id, title, categories, content_length | - | ~200자 |
| `save_pdf` | PDF 저장 | id, title, categories, content_length | - | ~200자 |
| `delete_article` | 삭제 | boolean | - | ~10자 |

### RAG 워크플로우

```
1. search → 관련 아티클 찾기
2. get_article → 메타데이터 + summary/preview 확인
3. (summary로 충분하면 끝)
4. get_relevant_chunks → 질문에 관련된 청크만 조회 (권장)
5. read_content → 전문 필요시에만 (비권장)
```

### 토큰 최적화 (Compacting 방지)

Claude Desktop 토큰 한도(190K) 대응:

| 시나리오 | 호출 | 예상 토큰 |
|----------|------|----------|
| 검색 + 요약 확인 | search → get_article | ~1,500 |
| 검색 + RAG 답변 | search → get_relevant_chunks | ~2,700 |
| 검색 + 전문 읽기 | search → get_article → read_content | ~2,500 |

**핵심 전략**:
1. `get_article`: summary 또는 content_preview(500자) 조건부 반환
2. `list_articles`: summary, description, tags 제외
3. `read_content`: 메타데이터 제외, 본문만 반환
4. 디버그 로그: `data/mcp_debug.log`
