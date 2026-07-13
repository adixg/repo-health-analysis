"""MCP server exposing RepoSense metrics and retrieval to a local LLM.

Every tool returns exact, deterministically-computed values from PostgreSQL so
the model answers are grounded in real repository data rather than estimated.
Run with:  ``python -m src.mcp_servers.server``  (requires the ``mcp`` package).
"""

from __future__ import annotations

from contextlib import contextmanager

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from src.analytics.correlation import (
    correlation_matrix,
    popularity_correlations,
)
from src.analytics.health_metrics import (
    calculate_all_commit_activity_metrics,
    calculate_all_contributor_metrics,
    calculate_all_pull_request_metrics,
    calculate_all_release_metrics,
    calculate_all_repository_comparisons,
)
from src.analytics.metrics import (
    calculate_all_issue_metrics,
    calculate_issue_metrics,
    calculate_label_distribution,
    label_distribution_as_rows,
    summarize_all_repositories,
)
from src.database.models import Repository
from src.database.session import get_session_factory, init_db
from src.retrieval.corpus import SemanticRetriever

mcp = FastMCP("reposense")


@contextmanager
def _session():
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def _repository(session, full_name: str) -> Repository | None:
    return session.scalar(select(Repository).where(Repository.full_name == full_name))


@mcp.tool()
def list_repositories() -> list[dict]:
    """List every ingested repository with its headline metadata."""
    with _session() as session:
        return summarize_all_repositories(session)


@mcp.tool()
def issue_metrics() -> list[dict]:
    """Issue-health metrics (closure rate, stale issues, resolution time) per repository."""
    with _session() as session:
        return calculate_all_issue_metrics(session)


@mcp.tool()
def label_distribution(full_name: str) -> dict:
    """Top issue-label distribution for a single ``owner/repo``."""
    with _session() as session:
        repository = _repository(session, full_name)
        if repository is None:
            return {"error": f"repository not found: {full_name}"}
        distribution = calculate_label_distribution(session, repository)
        return {
            "full_name": distribution.full_name,
            "total_issues": distribution.total_issues,
            "labeled_issues": distribution.labeled_issues,
            "top_labels": label_distribution_as_rows(distribution),
        }


@mcp.tool()
def pull_request_metrics() -> list[dict]:
    """Pull-request merge metrics per repository."""
    with _session() as session:
        return calculate_all_pull_request_metrics(session)


@mcp.tool()
def commit_activity() -> list[dict]:
    """Commit-activity metrics (6-month windows and change) per repository."""
    with _session() as session:
        return calculate_all_commit_activity_metrics(session)


@mcp.tool()
def contributor_metrics() -> list[dict]:
    """Contributor counts and concentration per repository."""
    with _session() as session:
        return calculate_all_contributor_metrics(session)


@mcp.tool()
def release_metrics() -> list[dict]:
    """Release frequency metrics per repository."""
    with _session() as session:
        return calculate_all_release_metrics(session)


@mcp.tool()
def repository_comparison() -> list[dict]:
    """Cross-repository comparison across all headline health signals."""
    with _session() as session:
        return calculate_all_repository_comparisons(session, calculate_issue_metrics)


@mcp.tool()
def popularity_correlation(popularity: str = "stars", method: str = "spearman") -> list[dict]:
    """Exploratory correlation of a popularity measure vs each maintenance metric.

    Results are exploratory associations, not causal claims.
    """
    with _session() as session:
        results = popularity_correlations(session, popularity=popularity, method=method)
        return [
            {
                "metric_a": r.metric_a,
                "metric_b": r.metric_b,
                "method": r.method,
                "coefficient": r.coefficient,
                "n": r.n,
            }
            for r in results
        ]


@mcp.tool()
def correlation_table(method: str = "spearman") -> list[dict]:
    """Full pairwise correlation matrix across numeric repository metrics."""
    with _session() as session:
        matrix = correlation_matrix(session, method=method)
        return matrix.reset_index(names="metric").to_dict(orient="records")


@mcp.tool()
def search_repository_evidence(query: str, full_name: str | None = None, top_k: int = 5) -> list[dict]:
    """Semantic search over ingested issues, comments, and documentation."""
    with _session() as session:
        repository = _repository(session, full_name) if full_name else None
        retriever = SemanticRetriever.from_session(session, repository)
        return [
            {
                "repository": chunk.repository_full_name,
                "source_type": chunk.source_type,
                "source_id": chunk.source_id,
                "title": chunk.title,
                "score": chunk.score,
                "url": chunk.url,
                "text": chunk.text[:800],
            }
            for chunk in retriever.search(query, top_k=top_k)
        ]


def main() -> None:
    init_db()
    mcp.run()


if __name__ == "__main__":
    main()
