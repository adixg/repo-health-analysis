from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from src.analytics.metrics import calculate_issue_metrics
from src.database.models import Issue, Repository


def test_calculate_issue_metrics() -> None:
    repository = Repository(
        id=1,
        full_name="owner/repo",
        owner="owner",
        name="repo",
    )
    now = datetime.now(UTC)
    issues = [
        Issue(
            id=1,
            repository_id=1,
            number=1,
            title="open recent",
            state="open",
            created_at=now - timedelta(days=10),
            updated_at=now,
        ),
        Issue(
            id=2,
            repository_id=1,
            number=2,
            title="open stale",
            state="open",
            created_at=now - timedelta(days=120),
            updated_at=now,
        ),
        Issue(
            id=3,
            repository_id=1,
            number=3,
            title="closed",
            state="closed",
            created_at=now - timedelta(days=20),
            closed_at=now - timedelta(days=10),
            updated_at=now,
        ),
    ]

    session = MagicMock()
    session.scalars.return_value.all.return_value = issues

    metrics = calculate_issue_metrics(session, repository, stale_days=90)

    assert metrics.total_issues == 3
    assert metrics.open_issues == 2
    assert metrics.closed_issues == 1
    assert metrics.closure_rate == round(1 / 3, 3)
    assert metrics.stale_open_issues == 1
    assert metrics.median_resolution_days == 10.0
