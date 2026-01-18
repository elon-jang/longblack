# Article RAG Plugin Specification

## 개요
좋은 아티클을 스크랩하여 RAG 기반으로 저장/검색하는 Claude MCP 플러그인

## 핵심 기능

### 1. 콘텐츠 수집
- **URL 스크랩**: 웹페이지 본문 추출 (article body, metadata)
- **PDF 추출**: PDF 파일에서 텍스트 추출
- **메타데이터**: 제목, 저자, 날짜, 소스 URL 자동 추출

### 2. 저장소
- **Vector DB**: ChromaDB - 임베딩 기반 유사도 검색
- **Metadata DB**: SQLite - 카테고리, 태그, 전문 검색
- **청킹**: 긴 문서를 1000자 단위로 분할 (200자 오버랩)

### 3. 임베딩 프로바이더
| Provider | 모델 | 차원 | 비용 |
|----------|------|------|------|
| `local` (기본값) | all-MiniLM-L6-v2 | 384 | 무료 |
| `openai` | text-embedding-3-small | 1536 | 유료 |

환경변수 `EMBEDDING_PROVIDER`로 선택 (기본값: `local`)

### 4. 카테고리 시스템
- 저장 시 카테고리 지정 (예: `longblack`, `ai`, `tech`)
- 검색 시 카테고리 필터링
- 다중 카테고리 지원

### 5. 검색
- **시맨틱 검색**: 의미 기반 유사도 검색 (코사인 유사도)
- **카테고리 필터**: 특정 카테고리 내 검색
- **전문 검색**: SQLite FTS5 기반 키워드 검색

## MCP Tools (6개)

기존 9개 도구를 6개로 통합하여 연쇄 호출 최소화.

### save
URL 또는 PDF에서 아티클 저장 (자동 감지)
```
Input:
  - source: str (필수) - URL 또는 파일 경로 (자동 감지)
  - categories: list[str] (필수) - 카테고리 목록
  - metadata: dict (선택) - {summary, keywords, tags}

Output:
  - id: str - 저장된 아티클 ID
  - title: str - 추출된 제목
  - categories: list[str]
  - content_length: int

Note: URL(http/https)과 파일 경로 자동 구분
```

### search
하이브리드 검색 (제목 + FTS + 시맨틱)
```
Input:
  - query: str (필수) - 검색 쿼리
  - category: str (선택) - 카테고리 필터
  - limit: int (선택, 기본값: 5) - 최대 결과 수

Output: list of
  - id: str
  - title: str
  - score: float (0~1)
  - author: str
  - excerpt: str (200자)
```

### list
카테고리 + 아티클 목록 통합 조회
```
Input:
  - category: str (선택) - 카테고리 필터
  - limit: int (선택, 기본값: 10) - 최대 아티클 수

Output:
  - categories: list of {name, count}
  - articles: list of {id, title, categories, author, created_at}

Note: 한 번 호출로 카테고리와 아티클 목록 동시 조회
```

### get
아티클 조회 (메타데이터 + 선택적 본문)
```
Input:
  - article_id: str (필수)
  - include_content: bool (선택, 기본값: false)

Output:
  - id, title, content_length, url, source_type
  - author, published_date, categories, created_at
  - description, keywords, tags
  - summary: str (있을 경우)
  - content_preview: str (summary 없을 경우, 500자)
  - content: str (include_content=true일 때만, 3000자 제한)

Note: include_content=false가 기본값. 대부분 summary로 충분.
```

### ask
RAG 질문 답변용 컨텍스트 조회
```
Input:
  - question: str (필수) - 질문
  - article_id: str (선택) - 특정 아티클로 제한
  - limit: int (선택, 기본값: 5) - 최대 청크 수

Output:
  - chunks: list of {article_id, title, content, score}
  - sources: list of {id, title} (중복 제거된 출처)

Note: search + get_relevant_chunks 통합. RAG 답변 생성에 최적화.
```

### delete
아티클 삭제
```
Input:
  - article_id: str (필수)

Output:
  - bool (성공 여부)
```

## 도구 통합 비교

| Before (9개) | After (6개) | 변경 |
|--------------|-------------|------|
| save_article, save_pdf | save | 통합 (자동 감지) |
| search | search | 유지 |
| list_articles, list_categories | list | 통합 |
| get_article, read_content | get | 통합 (include_content 옵션) |
| get_relevant_chunks | ask | 개선 (출처 정보 추가) |
| delete_article | delete | 이름 변경 |

## 기술 스택

| 영역 | 기술 | 버전 |
|------|------|------|
| Runtime | Python | 3.11+ |
| Package Manager | uv | latest |
| MCP Server | FastMCP | 2.x |
| Vector DB | ChromaDB | 1.x |
| Metadata DB | SQLite | 내장 |
| 임베딩 (로컬) | sentence-transformers | 2.x |
| 임베딩 (클라우드) | OpenAI text-embedding-3-small | - |
| URL 파싱 | trafilatura | 2.x |
| HTML 파싱 | BeautifulSoup4 | 4.x |
| PDF 파싱 | PyMuPDF (fitz) | 1.x |

## 환경 변수

| 변수 | 필수 | 기본값 | 설명 |
|------|------|--------|------|
| `EMBEDDING_PROVIDER` | 아니오 | `local` | 임베딩 프로바이더 (`local` 또는 `openai`) |
| `OPENAI_API_KEY` | openai 사용시 | - | OpenAI API 키 |

## 데이터 모델

### Article
```python
{
    "id": "uuid",
    "title": "string",
    "content": "string",
    "url": "string | null",
    "source_type": "url | pdf",
    "author": "string | null",
    "published_date": "datetime | null",
    "categories": ["string"],
    "created_at": "datetime",
    "summary": "string | null",      # 400-600자 요약
    "keywords": "string | null",     # 쉼표 구분 키워드
    "tags": "string | null"          # 태그 (쉼표 구분)
}
```

## 디렉토리 구조

```
longblack/
├── src/
│   ├── __init__.py
│   ├── server.py      # MCP 서버 메인
│   ├── scraper.py     # URL/PDF 콘텐츠 추출
│   ├── storage.py     # ChromaDB + SQLite 관리
│   ├── embeddings.py  # 임베딩 생성 (OpenAI/Local)
│   └── models.py      # Pydantic 데이터 모델
├── data/
│   ├── chroma/        # Vector DB (프로바이더별 컬렉션)
│   ├── articles.db    # SQLite DB
│   └── mcp_debug.log  # 디버그 로그 (도구 호출/응답 크기)
├── pyproject.toml
├── CLAUDE.md
├── SPEC.md
└── README.md
```

## 토큰 최적화

Claude Desktop 토큰 한도(190,000) 대응을 위한 최적화 전략:

### RAG 워크플로우 (권장)
```
# 간단한 질문
ask("9.81파크 비즈니스 모델은?")  # 원샷으로 컨텍스트 획득

# 목록 조회
list()  # 카테고리 + 아티클 목록 동시 조회

# 상세 조회
get(article_id)  # summary 포함
get(article_id, include_content=True)  # 본문 필요시
```

### 토큰 효율성 (Before vs After)
| 시나리오 | Before | After |
|----------|--------|-------|
| RAG 질문 | search → get_relevant_chunks (2회) | ask (1회) |
| 목록 조회 | list_categories + list_articles (2회) | list (1회) |
| 본문 읽기 | get_article → read_content (2회) | get(include_content=True) (1회) |

### 예상 응답 크기
| Tool | 응답 | 예상 크기 |
|------|------|----------|
| save | id, title, categories | ~200자 |
| search | 5개 결과 | ~1,200자 |
| list | 카테고리 + 10개 아티클 | ~2,500자 |
| get | 메타데이터 + summary | ~1,500자 |
| get (include_content) | + 본문 3000자 | ~4,500자 |
| ask | 5개 청크 + 출처 | ~5,500자 |
| delete | boolean | ~10자 |

### 디버그 로깅
- 위치: `data/mcp_debug.log`
- 각 도구 호출 시 응답 크기(chars) 기록

## 플랫폼
- **PC 전용** (Claude Code, Claude Desktop)
- 로컬 MCP 서버로 실행
- 인증 불필요 (개인용)

## 제약사항
- 로컬 저장소 사용 (클라우드 동기화 없음)
- Python 3.11 이상 필요 (3.14 미지원 - ChromaDB 호환성)
- 임베딩 프로바이더 변경 시 기존 데이터 재인덱싱 필요
