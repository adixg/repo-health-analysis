"""Build a searchable text corpus from ingested repository data and rank it.

The corpus draws on the entities persisted during ingestion — issues, pull
requests, their comments, and repository documentation — and exposes a
``SemanticRetriever`` that returns the most relevant evidence chunks for a
natural-language query. These chunks become the grounded context handed to the
local LLM in :mod:`src.agent.grounded_chat`.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import (
    Document,
    Issue,
    IssueComment,
    PullRequest,
    PullRequestComment,
    Repository,
)
from src.retrieval.tfidf import TfidfIndex


@dataclass
class EvidenceChunk:
    repository_full_name: str
    source_type: str  # "issue" | "pull_request" | "issue_comment" | "pr_comment" | "document"
    source_id: str
    title: str
    text: str
    url: str | None
    score: float = 0.0


def _issue_body(issue: Issue) -> str:
    body = (issue.raw_metadata or {}).get("body") if issue.raw_metadata else None
    return body or ""


def _pull_request_body(pull_request: PullRequest) -> str:
    body = (
        (pull_request.raw_metadata or {}).get("body") if pull_request.raw_metadata else None
    )
    return body or ""


def build_corpus(session: Session, repository: Repository | None = None) -> list[EvidenceChunk]:
    """Assemble evidence chunks from the ingested data for one or all repositories."""
    repo_filter = (repository.id,) if repository is not None else None

    def _scope(stmt, model):
        if repo_filter is not None:
            return stmt.where(model.repository_id == repo_filter[0])
        return stmt

    chunks: list[EvidenceChunk] = []

    repo_names = {
        repo.id: repo.full_name
        for repo in session.scalars(select(Repository)).all()
    }

    for issue in session.scalars(_scope(select(Issue), Issue)).all():
        text = f"{issue.title}\n{_issue_body(issue)}".strip()
        chunks.append(
            EvidenceChunk(
                repository_full_name=repo_names.get(issue.repository_id, ""),
                source_type="issue",
                source_id=str(issue.number),
                title=issue.title,
                text=text,
                url=issue.html_url,
            )
        )

    for pull_request in session.scalars(_scope(select(PullRequest), PullRequest)).all():
        text = f"{pull_request.title}\n{_pull_request_body(pull_request)}".strip()
        chunks.append(
            EvidenceChunk(
                repository_full_name=repo_names.get(pull_request.repository_id, ""),
                source_type="pull_request",
                source_id=str(pull_request.number),
                title=pull_request.title,
                text=text,
                url=pull_request.html_url,
            )
        )

    for comment in session.scalars(_scope(select(IssueComment), IssueComment)).all():
        if not comment.body:
            continue
        chunks.append(
            EvidenceChunk(
                repository_full_name=repo_names.get(comment.repository_id, ""),
                source_type="issue_comment",
                source_id=str(comment.id),
                title=f"Comment on issue #{comment.issue_number}",
                text=comment.body,
                url=comment.html_url,
            )
        )

    for comment in session.scalars(_scope(select(PullRequestComment), PullRequestComment)).all():
        if not comment.body:
            continue
        chunks.append(
            EvidenceChunk(
                repository_full_name=repo_names.get(comment.repository_id, ""),
                source_type="pr_comment",
                source_id=str(comment.id),
                title=f"Review comment on PR #{comment.pull_number}",
                text=comment.body,
                url=comment.html_url,
            )
        )

    for document in session.scalars(_scope(select(Document), Document)).all():
        if not document.content:
            continue
        chunks.append(
            EvidenceChunk(
                repository_full_name=repo_names.get(document.repository_id, ""),
                source_type="document",
                source_id=document.path,
                title=document.path,
                text=document.content,
                url=document.html_url,
            )
        )

    return chunks


class SemanticRetriever:
    """Rank corpus chunks against a query using the TF-IDF backend."""

    def __init__(self, chunks: list[EvidenceChunk]) -> None:
        self.chunks = chunks
        self._index = TfidfIndex()
        if chunks:
            self._index.fit([chunk.text for chunk in chunks])

    @classmethod
    def from_session(
        cls, session: Session, repository: Repository | None = None
    ) -> "SemanticRetriever":
        return cls(build_corpus(session, repository))

    def search(self, query: str, top_k: int = 5) -> list[EvidenceChunk]:
        if not self.chunks:
            return []
        results: list[EvidenceChunk] = []
        for index, score in self._index.query(query, top_k=top_k):
            chunk = self.chunks[index]
            results.append(
                EvidenceChunk(
                    repository_full_name=chunk.repository_full_name,
                    source_type=chunk.source_type,
                    source_id=chunk.source_id,
                    title=chunk.title,
                    text=chunk.text,
                    url=chunk.url,
                    score=round(score, 4),
                )
            )
        return results
