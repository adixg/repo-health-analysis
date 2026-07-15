from datetime import UTC, datetime
from unittest.mock import MagicMock

from src.analytics.metrics import calculate_label_distribution
from src.database.models import Issue, Repository


def test_calculate_label_distribution() -> None:
    repository = Repository(id=1, full_name="owner/repo", owner="owner", name="repo")
    now = datetime.now(UTC)
    issues = [
        Issue(
            id=1,
            repository_id=1,
            number=1,
            title="bug",
            state="open",
            labels=["bug"],
            created_at=now,
            updated_at=now,
        ),
        Issue(
            id=2,
            repository_id=1,
            number=2,
            title="feature",
            state="open",
            labels=["enhancement", "help wanted"],
            created_at=now,
            updated_at=now,
        ),
        Issue(
            id=3,
            repository_id=1,
            number=3,
            title="no labels",
            state="open",
            labels=[],
            created_at=now,
            updated_at=now,
        ),
    ]
    session = MagicMock()
    session.scalars.return_value.all.return_value = [["bug"], ["enhancement", "help wanted"], []]

    distribution = calculate_label_distribution(session, repository, limit=5)

    assert distribution.total_issues == 3
    assert distribution.labeled_issues == 2
    assert distribution.unlabeled_issues == 1
    assert distribution.top_labels[0].label == "bug"
    assert distribution.top_labels[0].count == 1
