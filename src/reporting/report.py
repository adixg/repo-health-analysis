"""Render exportable Markdown health reports from the deterministic metrics."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.analytics.health_metrics import (
    calculate_commit_activity_metrics,
    calculate_contributor_metrics,
    calculate_pull_request_metrics,
    calculate_release_metrics,
)
from src.analytics.metrics import (
    calculate_issue_metrics,
    calculate_label_distribution,
    summarize_repository,
)
from src.database.models import Repository


def _fmt(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _get_repository(session: Session, full_name: str) -> Repository:
    repository = session.scalar(
        select(Repository).where(Repository.full_name == full_name)
    )
    if repository is None:
        raise ValueError(f"Repository not found: {full_name!r}")
    return repository


def generate_repository_report(session: Session, full_name: str) -> str:
    """Build a self-contained Markdown health report for a single repository."""
    repository = _get_repository(session, full_name)

    summary = summarize_repository(repository)
    issues = calculate_issue_metrics(session, repository)
    prs = calculate_pull_request_metrics(session, repository)
    commits = calculate_commit_activity_metrics(session, repository)
    contributors = calculate_contributor_metrics(session, repository)
    releases = calculate_release_metrics(session, repository)
    labels = calculate_label_distribution(session, repository)

    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        f"# Repository Health Report — {full_name}",
        "",
        f"_Generated {generated} by RepoSense. Correlations and metrics are "
        "exploratory operational signals, not causal conclusions._",
        "",
        "## Overview",
        "",
        f"- Stars: {_fmt(summary.stars)}",
        f"- Forks: {_fmt(summary.forks)}",
        f"- Primary language: {_fmt(summary.language)}",
        f"- Open issues (GitHub-reported): {_fmt(summary.open_issues)}",
        "",
        "## Issue health",
        "",
        f"- Total issues: {_fmt(issues.total_issues)}",
        f"- Closure rate: {_fmt(issues.closure_rate)}",
        f"- Stale open issues (>{'90'}d): {_fmt(issues.stale_open_issues)} "
        f"({_fmt(issues.stale_issue_pct)})",
        f"- Median resolution (days): {_fmt(issues.median_resolution_days)}",
        "",
        "## Pull requests",
        "",
        f"- Total PRs: {_fmt(prs.total_prs)}",
        f"- Merge rate: {_fmt(prs.merge_rate)}",
        f"- Median merge time (days): {_fmt(prs.median_merge_days)}",
        "",
        "## Commit activity",
        "",
        f"- Commits (last 6 months): {_fmt(commits.commits_last_6_months)}",
        f"- Commits (prior 6 months): {_fmt(commits.commits_prior_6_months)}",
        f"- Activity change: {_fmt(commits.activity_change_pct)}%",
        "",
        "## Contributors",
        "",
        f"- Contributor count: {_fmt(contributors.contributor_count)}",
        f"- Top contributor: {_fmt(contributors.top_contributor)} "
        f"({_fmt(contributors.top_contributor_share)} share)",
        f"- Top-3 concentration: {_fmt(contributors.top_3_contributor_share)}",
        "",
        "## Releases",
        "",
        f"- Total releases: {_fmt(releases.total_releases)}",
        f"- Releases (last 12 months): {_fmt(releases.releases_last_12_months)}",
        f"- Median days between releases: {_fmt(releases.median_days_between_releases)}",
        f"- Days since last release: {_fmt(releases.days_since_last_release)}",
        "",
        "## Top issue labels",
        "",
        "| Label | Count | Share |",
        "|-------|------:|------:|",
    ]
    for label in labels.top_labels:
        lines.append(f"| {label.label} | {label.count} | {_fmt(label.share)} |")
    if not labels.top_labels:
        lines.append("| _no labeled issues_ | 0 | 0.000 |")
    lines.append("")

    return "\n".join(lines)


def export_report(session: Session, full_name: str, *, out_dir: str | Path = "outputs") -> Path:
    """Write a repository's Markdown report to ``out_dir`` and return the path."""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    filename = f"health_report_{full_name.replace('/', '__')}.md"
    target = out_path / filename
    target.write_text(generate_repository_report(session, full_name), encoding="utf-8")
    return target


def export_all_reports(session: Session, *, out_dir: str | Path = "outputs") -> list[Path]:
    repositories = session.scalars(
        select(Repository).order_by(Repository.full_name)
    ).all()
    return [export_report(session, repo.full_name, out_dir=out_dir) for repo in repositories]
