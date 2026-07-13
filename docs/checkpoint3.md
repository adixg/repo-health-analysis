# Checkpoint 3 — MCP Agent, Retrieval, Grounded Chat, and Deployment

This document maps the Checkpoint 3 milestone (from the Checkpoint 2 report's
next-steps section) to the modules that implement it. Every statistic remains
deterministically computed in `src/analytics`; the local LLM only interprets
precomputed evidence, consistent with the project's original design principle.

## Deliverable → implementation

| Stated Checkpoint 3 deliverable | Module(s) |
|---------------------------------|-----------|
| Issue/PR comments ingestion | `src/ingestion/comments.py`, models `IssueComment` / `PullRequestComment` |
| Documentation (README) ingestion | `src/ingestion/documents.py`, model `Document` |
| Semantic retrieval | `src/retrieval/tfidf.py`, `src/retrieval/corpus.py` (`SemanticRetriever`) |
| MCP tools | `src/mcp_servers/server.py` (FastMCP tool surface over metrics + retrieval) |
| Ollama integration + grounded chat | `src/agent/grounded_chat.py` (`OllamaClient`, `GroundedChatAgent`) |
| Cross-repository correlation analysis | `src/analytics/correlation.py` (Spearman/Pearson via pandas) |
| Exportable health report | `src/reporting/report.py` (`export_report`, `export_all_reports`) |
| Full containerization | `Dockerfile`, extended `docker-compose.yml` (api, dashboard, ollama services) |

## New configuration (see `.env.example`)

- `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `RETRIEVAL_TOP_K`

## Data model additions

`init_db()` now also creates `issue_comments`, `pull_request_comments`, and
`documents`, and adds `comments_last_synced_at` / `documents_last_synced_at`
sync columns to `repositories` (idempotent `ADD COLUMN IF NOT EXISTS`).
`ingest_repository_data()` now returns the additional counts.

## How the grounded pipeline fits together

1. Ingestion persists issues, PRs, their comments, and README text.
2. `SemanticRetriever` builds a TF-IDF corpus over that text (no external vector
   DB required; a pgvector/ChromaDB backend can be swapped behind `search()`).
3. `GroundedChatAgent` retrieves the top-k evidence chunks, attaches
   deterministic metrics as context, and asks the Ollama model to answer using
   only that grounded context (citing evidence by number).
4. The same metrics and retrieval are exposed as MCP tools in
   `src/mcp_servers/server.py` for tool-calling clients.

## Tests

`tests/test_retrieval.py`, `tests/test_correlation.py`,
`tests/test_comments_ingestion.py`, `tests/test_grounded_chat.py`, and
`tests/test_reporting.py` cover the deterministic Checkpoint 3 components.
