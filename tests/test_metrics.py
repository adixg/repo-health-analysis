from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from src.analytics.metrics import calculate_issue_metrics
from src.database.models import Repository


def test_calculate_issue_metrics() -> None:
    repository = Repository(
        id=1,
        full_name="owner/repo",
        owner="owner",
        name="repo",
    )
    now = datetime.now(UTC)

    session = MagicMock()
    session.scalar.side_effect = [3, 2, 1, 1]
    session.execute.return_value.all.return_value = [
        (now - timedelta(days=20), now - timedelta(days=10)),
    ]

    metrics = calculate_issue_metrics(session, repository, stale_days=90)

    assert metrics.total_issues == 3
    assert metrics.open_issues == 2
    assert metrics.closed_issues == 1
    assert metrics.closure_rate == round(1 / 3, 3)
    assert metrics.stale_open_issues == 1
    assert metrics.median_resolution_days == 10.0
