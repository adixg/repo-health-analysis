from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    owner: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    forks: Mapped[int] = mapped_column(Integer, default=0)
    open_issues: Mapped[int] = mapped_column(Integer, default=0)
    default_branch: Mapped[str | None] = mapped_column(String(128))
    language: Mapped[str | None] = mapped_column(String(64))
    html_url: Mapped[str | None] = mapped_column(String(512))
    pushed_at: Mapped[str | None] = mapped_column(String(64))
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB)
    issues_last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pulls_last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    commits_last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contributors_last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    releases_last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comments_last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    documents_last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (UniqueConstraint("repository_id", "number", name="uq_issues_repo_number"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    author_login: Mapped[str | None] = mapped_column(String(128))
    labels: Mapped[list | None] = mapped_column(JSONB)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    html_url: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class PullRequest(Base):
    __tablename__ = "pull_requests"
    __table_args__ = (UniqueConstraint("repository_id", "number", name="uq_pull_requests_repo_number"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    author_login: Mapped[str | None] = mapped_column(String(128))
    merged: Mapped[bool] = mapped_column(Boolean, default=False)
    labels: Mapped[list | None] = mapped_column(JSONB)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    html_url: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Commit(Base):
    __tablename__ = "commits"

    sha: Mapped[str] = mapped_column(String(40), primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message: Mapped[str | None] = mapped_column(Text)
    author_login: Mapped[str | None] = mapped_column(String(128))
    author_name: Mapped[str | None] = mapped_column(String(255))
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    html_url: Mapped[str | None] = mapped_column(String(512))
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Contributor(Base):
    __tablename__ = "contributors"
    __table_args__ = (UniqueConstraint("repository_id", "login", name="uq_contributors_repo_login"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    login: Mapped[str] = mapped_column(String(128), nullable=False)
    contributions: Mapped[int] = mapped_column(Integer, default=0)
    html_url: Mapped[str | None] = mapped_column(String(512))
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Release(Base):
    __tablename__ = "releases"
    __table_args__ = (UniqueConstraint("repository_id", "github_id", name="uq_releases_repo_github_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    github_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    repository_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag_name: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    draft: Mapped[bool] = mapped_column(Boolean, default=False)
    prerelease: Mapped[bool] = mapped_column(Boolean, default=False)
    html_url: Mapped[str | None] = mapped_column(String(512))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class IssueComment(Base):
    """Comment posted on an issue (Checkpoint 3 text ingestion)."""

    __tablename__ = "issue_comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    issue_number: Mapped[int | None] = mapped_column(Integer, index=True)
    author_login: Mapped[str | None] = mapped_column(String(128))
    body: Mapped[str | None] = mapped_column(Text)
    html_url: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class PullRequestComment(Base):
    """Review comment posted on a pull request (Checkpoint 3 text ingestion)."""

    __tablename__ = "pull_request_comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pull_number: Mapped[int | None] = mapped_column(Integer, index=True)
    author_login: Mapped[str | None] = mapped_column(String(128))
    body: Mapped[str | None] = mapped_column(Text)
    html_url: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Document(Base):
    """Repository documentation (README / docs) for semantic retrieval (Checkpoint 3)."""

    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("repository_id", "path", name="uq_documents_repo_path"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    sha: Mapped[str | None] = mapped_column(String(64))
    html_url: Mapped[str | None] = mapped_column(String(512))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
