import pandas as pd

from src.analytics import correlation
from src.analytics.correlation import correlate, popularity_correlations


def _patch_frame(monkeypatch) -> None:
    frame = pd.DataFrame(
        {
            "stars": [10, 20, 30, 40],
            "forks": [1, 2, 3, 4],
            "issue_closure_rate": [0.9, 0.8, 0.7, 0.6],
            "pr_merge_rate": [0.5, 0.6, 0.7, 0.8],
            "stale_open_issues": [40, 30, 20, 10],
            "commits_last_6_months": [5, 10, 15, 20],
            "contributor_count": [2, 4, 6, 8],
            "top_contributor_share": [0.8, 0.6, 0.4, 0.2],
            "releases_last_12_months": [1, 2, 3, 4],
        },
        index=pd.Index(["a/one", "a/two", "a/three", "a/four"], name="full_name"),
    )
    monkeypatch.setattr(
        correlation,
        "build_metric_frame",
        lambda session, *, issue_metrics_fn=None: frame,
    )


def test_spearman_perfect_positive(monkeypatch) -> None:
    _patch_frame(monkeypatch)
    result = correlate(None, "stars", "commits_last_6_months", method="spearman")
    assert result.coefficient == 1.0
    assert result.n == 4
    assert result.method == "spearman"


def test_spearman_perfect_negative(monkeypatch) -> None:
    _patch_frame(monkeypatch)
    result = correlate(None, "stars", "stale_open_issues", method="spearman")
    assert result.coefficient == -1.0


def test_popularity_correlations_cover_all_maintenance_metrics(monkeypatch) -> None:
    _patch_frame(monkeypatch)
    results = popularity_correlations(None, popularity="stars", method="spearman")
    metrics = {r.metric_b for r in results}
    assert "issue_closure_rate" in metrics
    assert "releases_last_12_months" in metrics
    assert all(r.metric_a == "stars" for r in results)
