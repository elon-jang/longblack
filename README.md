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

## MCP Tools

| Tool | 설명 | 예시 |
|------|------|------|
| `save_article` | URL에서 아티클 저장 | `save_article("https://...", ["ai"], summary="...", keywords="...", insights="...")` |
| `save_pdf` | PDF 파일 저장 | `save_pdf("/path/to/doc.pdf", ["tech"])` |
| `list_articles` | 아티클 목록 조회 | `list_articles(category="ai", limit=20)` |
| `search` | 시맨틱 검색 | `search("AI 트렌드", category="ai")` |
| `get_article` | 메타데이터 조회 | `get_article("uuid-...")` |
| `get_relevant_chunks` | RAG용 청크 검색 | `get_relevant_chunks("질문", article_id="uuid-...")` |
| `read_content` | 전체 본문 읽기 | `read_content("uuid-...")` |
| `list_categories` | 카테고리 목록 | `list_categories()` |
| `delete_article` | 아티클 삭제 | `delete_article("uuid-...")` |

## 사용 예시

### 아티클 저장
```
save_article로 이 URL 저장해줘: https://example.com/article
카테고리는 ["ai", "tech"]로
```

### 검색
```
"RAG 구현 방법"에 대해 검색해줘
ai 카테고리에서 "임베딩" 관련 아티클 찾아줘
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
