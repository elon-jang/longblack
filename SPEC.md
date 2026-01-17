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

## MCP Tools

### save_article
URL에서 아티클을 스크랩하여 저장
```
Input:
  - url: str (필수) - 아티클 URL
  - categories: list[str] (필수) - 카테고리 목록
  - summary: str (선택) - 3-5문장 요약
  - keywords: str (선택) - 쉼표 구분 키워드
  - insights: str (선택) - 핵심 인사이트 (줄바꿈 구분)

Output:
  - id: str - 저장된 아티클 ID
  - title: str - 추출된 제목
  - categories: list[str]
  - content_length: int
```

### save_pdf
PDF 파일에서 텍스트를 추출하여 저장
```
Input:
  - file_path: str (필수) - PDF 파일 경로
  - categories: list[str] (필수) - 카테고리 목록
  - summary: str (선택) - 3-5문장 요약
  - keywords: str (선택) - 쉼표 구분 키워드
  - insights: str (선택) - 핵심 인사이트 (줄바꿈 구분)

Output:
  - id: str
  - title: str
  - categories: list[str]
  - content_length: int
```

### search
시맨틱 검색으로 관련 아티클 조회
```
Input:
  - query: str (필수) - 검색 쿼리
  - category: str (선택) - 카테고리 필터
  - limit: int (선택, 기본값: 10) - 최대 결과 수

Output: list of
  - id: str
  - title: str
  - score: float (0~1, 높을수록 관련성 높음)
  - url: str
  - categories: list[str]
  - author: str
  - excerpt: str (매칭된 청크 일부)
```

### list_articles
아티클 목록 조회
```
Input:
  - category: str (선택) - 카테고리 필터
  - limit: int (선택, 기본값: 20) - 최대 결과 수
  - sort_by: str (선택, 기본값: created_at) - 정렬 기준

Output: list of
  - id: str
  - title: str
  - categories: list[str]
  - author: str
  - created_at: str
  - summary: str
  - keywords: str
```

### get_article
아티클 메타데이터 조회 (본문은 read_content 사용)
```
Input:
  - article_id: str (필수)

Output:
  - id, title, content_length, url, source_type
  - author, published_date, categories, created_at
  - summary, keywords, insights
```

### get_relevant_chunks
RAG용 관련 청크 검색
```
Input:
  - query: str (필수) - 질문 또는 검색 쿼리
  - article_id: str (선택) - 특정 아티클로 제한
  - limit: int (선택, 기본값: 5) - 최대 청크 수

Output: list of
  - article_id: str
  - title: str
  - content: str (청크 내용)
  - score: float (0~1)
```

### read_content
아티클 전체 본문 읽기
```
Input:
  - article_id: str (필수)

Output:
  - str (마크다운 포맷 본문, 요약/인사이트 포함)
```

### list_categories
저장된 모든 카테고리와 아티클 수 조회
```
Output: list of
  - name: str
  - count: int
```

### delete_article
아티클 삭제
```
Input:
  - article_id: str (필수)

Output:
  - bool (성공 여부)
```

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
    "summary": "string | null",      # 3-5문장 요약
    "keywords": "string | null",     # 쉼표 구분 키워드
    "insights": "string | null"      # 핵심 인사이트 (줄바꿈 구분)
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
│   └── articles.db    # SQLite DB
├── pyproject.toml
├── CLAUDE.md
├── SPEC.md
└── README.md
```

## 플랫폼
- **PC 전용** (Claude Code, Claude Desktop)
- 로컬 MCP 서버로 실행
- 인증 불필요 (개인용)

## 제약사항
- 로컬 저장소 사용 (클라우드 동기화 없음)
- Python 3.11 이상 필요 (3.14 미지원 - ChromaDB 호환성)
- 임베딩 프로바이더 변경 시 기존 데이터 재인덱싱 필요
