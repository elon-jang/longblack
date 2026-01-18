# Longblack - Article RAG Plugin

Claude MCP 플러그인으로 좋은 아티클을 스크랩하여 RAG 기반으로 저장/검색합니다.

## 요구사항

- Python 3.11 ~ 3.13 (3.14 미지원)
- [uv](https://docs.astral.sh/uv/) 패키지 매니저

## 설치

```bash
# uv 설치 (없는 경우)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 의존성 설치
uv sync --python 3.12
```

## 임베딩 프로바이더

| Provider | 모델 | 설정 | 비용 |
|----------|------|------|------|
| `local` (기본값) | all-MiniLM-L6-v2 | 설정 불필요 | 무료 |
| `openai` | text-embedding-3-small | API 키 필요 | 유료 |

```bash
# 로컬 임베딩 사용 (기본값, API 키 불필요)
export EMBEDDING_PROVIDER=local

# OpenAI 임베딩 사용
export EMBEDDING_PROVIDER=openai
export OPENAI_API_KEY="sk-..."
```

## Claude Desktop 연동

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "longblack": {
      "command": "uv",
      "args": [
        "run", "--directory",
        "/Users/elon/elon/ai/projects/longblack",
        "python", "-m", "src.server"
      ],
      "env": {
        "EMBEDDING_PROVIDER": "local"
      }
    }
  }
}
```

OpenAI 사용 시:
```json
{
  "mcpServers": {
    "longblack": {
      "command": "uv",
      "args": [
        "run", "--directory",
        "/Users/elon/elon/ai/projects/longblack",
        "python", "-m", "src.server"
      ],
      "env": {
        "EMBEDDING_PROVIDER": "openai",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

설정 후 Claude Desktop 재시작

## Claude Code 연동

`~/.claude/settings.json` 또는 프로젝트의 `.mcp.json`:

```json
{
  "mcpServers": {
    "longblack": {
      "command": "uv",
      "args": [
        "run", "--directory",
        "/Users/elon/elon/ai/projects/longblack",
        "python", "-m", "src.server"
      ],
      "env": {
        "EMBEDDING_PROVIDER": "local"
      }
    }
  }
}
```

## MCP Tools (6개)

| Tool | 설명 | 예시 |
|------|------|------|
| `save` | URL/PDF 저장 (자동 감지) | `save("https://...", ["ai"], metadata={...})` |
| `search` | 하이브리드 검색 | `search("AI 트렌드", category="ai")` |
| `list` | 카테고리 + 목록 조회 | `list(category="ai", limit=10)` |
| `get` | 아티클 조회 (+ 선택적 본문) | `get("uuid-...", include_content=True)` |
| `ask` | RAG 질문 답변 | `ask("9.81파크 비즈니스 모델은?")` |
| `delete` | 삭제 | `delete("uuid-...")` |

> **연쇄 호출 최소화**: 기존 9개 → 6개 통합. 대부분 1회 호출로 완료.

### 토큰 절감 효과

| 시나리오 | Before | After | 절감 |
|----------|--------|-------|------|
| RAG 질문 | ~11,000자 (3회+) | ~5,500자 (1회) | **50%↓** |
| 목록 조회 | ~4,000자 (2회) | ~2,500자 (1회) | **37%↓** |
| 상세 조회 | ~4,500자 (2회) | ~4,500자 (1회) | 호출↓ |

> Claude Desktop 토큰 한도(190K) 대응. Compacting 방지로 대화 컨텍스트 유지.

### 워크플로우 예시
```
# RAG 질문 → 1회 호출 (기존: search → get_article → read_content)
ask("9.81파크 비즈니스 모델은?")

# 목록 조회 → 1회 호출 (기존: list_categories + list_articles)
list()

# 상세 조회 → 1회 호출 (기존: get_article → read_content)
get(article_id, include_content=True)
```

## 사용 예시

MCP 서버가 연동되면 자연어로 Claude에게 요청하면 됩니다.

### 아티클 저장 (메타데이터 자동 생성)
```
이 URL 저장해줘: https://example.com/article
카테고리는 ai, tech로 하고 요약이랑 키워드도 만들어줘
```

### 목록 조회
```
저장된 아티클 목록 보여줘
ai 카테고리 아티클만 보여줘
```

### 검색
```
"RAG 구현 방법"에 대해 검색해줘
ai 카테고리에서 "임베딩" 관련 아티클 찾아줘
```

### RAG 질문 답변
```
저장된 아티클 기반으로 "9.81파크의 비즈니스 모델"에 대해 알려줘
```

### 본문 읽기
```
이 아티클 전체 내용 보여줘
```

### 카테고리 확인
```
저장된 카테고리 목록 보여줘
```

## 데이터 저장 위치

| 저장소 | 경로 | 용도 |
|--------|------|------|
| ChromaDB | `data/chroma/` | 벡터 임베딩 (프로바이더별 컬렉션) |
| SQLite | `data/articles.db` | 메타데이터, 전문 검색 |
| Debug Log | `data/mcp_debug.log` | 도구 호출 로그 (응답 크기 분석) |

## 개발

```bash
# 서버 직접 실행 (테스트용)
uv run python -m src.server

# 테스트
uv run pytest
```

## 문제 해결

### Python 버전 오류
- ChromaDB는 Python 3.14를 아직 지원하지 않음
- `uv sync --python 3.12` 명령으로 Python 3.12 사용

### MCP 서버 연결 안됨
- 경로가 절대 경로인지 확인
- Claude Desktop/Code 재시작
- `uv run python -m src.server`로 직접 실행하여 오류 확인

### 임베딩 프로바이더 변경
- 프로바이더별로 별도 컬렉션 사용 (`articles_local`, `articles_openai`)
- 기존 데이터는 유지되며, 프로바이더 변경 시 해당 컬렉션의 데이터만 검색됨
