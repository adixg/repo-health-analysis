"""Exploratory cross-repository correlation analysis (Checkpoint 3).

Correlations are computed deterministically with pandas (rank-based Spearman by
default) rather than being estimated by the language model. Following the
project's Checkpoint 1 framing, results are reported as *exploratory
associations*, never as causal claims.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.analytics.health_metrics import calculate_all_repository_comparisons
from src.analytics.metrics import calculate_issue_metrics
from src.database.models import Repository

# Maintenance signals available for correlation against popularity measures.
MAINTENANCE_METRICS = (
    "issue_closure_rate",
    "pr_merge_rate",
    "stale_open_issues",
    "commits_last_6_months",
    "contributor_count",
    "top_contributor_share",
    "releases_last_12_months",
)
POPULARITY_METRICS = ("stars", "forks")


@dataclass
class CorrelationResult:
    metric_a: str
    metric_b: str
    method: str
    coefficient: float | None
    n: int


def build_metric_frame(session: Session, *, issue_metrics_fn=calculate_issue_metrics) -> pd.DataFrame:
    """One row per repository combining popularity and maintenance metrics."""
    comparisons = calculate_all_repository_comparisons(session, issue_metrics_fn)
    forks_by_name = {
        repo.full_name: repo.forks
        for repo in session.scalars(select(Repository)).all()
    }
    for row in comparisons:
        row["forks"] = forks_by_name.get(row["full_name"], 0)

    if not comparisons:
        columns = ["full_name", *POPULARITY_METRICS, *MAINTENANCE_METRICS]
        return pd.DataFrame(columns=columns).set_index("full_name")

    frame = pd.DataFrame(comparisons).set_index("full_name")
    return frame


def _clean(coefficient: float | None) -> float | None:
    if coefficient is None or (isinstance(coefficient, float) and math.isnan(coefficient)):
        return None
    return round(float(coefficient), 4)


def correlate(
    session: Session,
    metric_a: str,
    metric_b: str,
    *,
    method: str = "spearman",
    issue_metrics_fn=calculate_issue_metrics,
) -> CorrelationResult:
    frame = build_metric_frame(session, issue_metrics_fn=issue_metrics_fn)
    if metric_a not in frame.columns or metric_b not in frame.columns:
        raise KeyError(f"Unknown metric(s): {metric_a!r}, {metric_b!r}")

    pair = frame[[metric_a, metric_b]].dropna()
    coefficient = (
        pair[metric_a].corr(pair[metric_b], method=method) if len(pair) >= 2 else None
    )
    return CorrelationResult(
        metric_a=metric_a,
        metric_b=metric_b,
        method=method,
        coefficient=_clean(coefficient),
        n=int(len(pair)),
    )


def correlation_matrix(
    session: Session,
    *,
    method: str = "spearman",
    issue_metrics_fn=calculate_issue_metrics,
) -> pd.DataFrame:
    frame = build_metric_frame(session, issue_metrics_fn=issue_metrics_fn)
    numeric = frame.select_dtypes(include="number")
    return numeric.corr(method=method).round(4)


def popularity_correlations(
    session: Session,
    *,
    popularity: str = "stars",
    method: str = "spearman",
    issue_metrics_fn=calculate_issue_metrics,
) -> list[CorrelationResult]:
    """Correlate a popularity measure against each maintenance metric."""
    if popularity not in POPULARITY_METRICS:
        raise KeyError(f"Unknown popularity metric: {popularity!r}")
    return [
        correlate(
            session,
            popularity,
            metric,
            method=method,
            issue_metrics_fn=issue_metrics_fn,
        )
        for metric in MAINTENANCE_METRICS
    ]
