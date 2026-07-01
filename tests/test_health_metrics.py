from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from src.analytics.health_metrics import (
    calculate_commit_activity_metrics,
    calculate_contributor_metrics,
    calculate_pull_request_metrics,
    calculate_release_metrics,
)
from src.database.models import Commit, Contributor, PullRequest, Release, Repository


def test_calculate_pull_request_metrics() -> None:
    repository = Repository(id=1, full_name="owner/repo", owner="owner", name="repo")
    now = datetime.now(UTC)
    pull_requests = [
        PullRequest(
            id=1,
            repository_id=1,
            number=1,
            title="merged",
            state="closed",
            merged=True,
            created_at=now - timedelta(days=10),
            merged_at=now - timedelta(days=5),
            updated_at=now,
        ),
        PullRequest(
            id=2,
            repository_id=1,
            number=2,
            title="open",
            state="open",
            merged=False,
            created_at=now - timedelta(days=3),
            updated_at=now,
        ),
    ]
    session = MagicMock()
    session.scalars.return_value.all.return_value = pull_requests

    metrics = calculate_pull_request_metrics(session, repository)
    assert metrics.total_prs == 2
    assert metrics.merge_rate == 0.5
    assert metrics.median_merge_days == 5.0


def test_calculate_contributor_metrics() -> None:
    repository = Repository(id=1, full_name="owner/repo", owner="owner", name="repo")
    contributors = [
        Contributor(id=1, repository_id=1, login="alice", contributions=80),
        Contributor(id=2, repository_id=1, login="bob", contributions=20),
    ]
    session = MagicMock()
    session.scalars.return_value.all.return_value = contributors

    metrics = calculate_contributor_metrics(session, repository)
    assert metrics.contributor_count == 2
    assert metrics.top_contributor == "alice"
    assert metrics.top_contributor_share == 0.8


def test_calculate_commit_activity_metrics() -> None:
    repository = Repository(id=1, full_name="owner/repo", owner="owner", name="repo")
    now = datetime.now(UTC)
    commits = [
        Commit(
            sha="a" * 40,
            repository_id=1,
            committed_at=now - timedelta(days=30),
        ),
        Commit(
            sha="b" * 40,
            repository_id=1,
            committed_at=now - timedelta(days=200),
        ),
    ]
    session = MagicMock()
    session.scalars.return_value.all.return_value = commits

    metrics = calculate_commit_activity_metrics(session, repository, now=now)
    assert metrics.total_commits == 2
    assert metrics.commits_last_6_months == 1
    assert metrics.commits_prior_6_months == 1


def test_calculate_release_metrics() -> None:
    repository = Repository(id=1, full_name="owner/repo", owner="owner", name="repo")
    now = datetime.now(UTC)
    releases = [
        Release(
            id=1,
            github_id=10,
            repository_id=1,
            tag_name="v1.0.0",
            draft=False,
            published_at=now - timedelta(days=400),
        ),
        Release(
            id=2,
            github_id=11,
            repository_id=1,
            tag_name="v1.1.0",
            draft=False,
            published_at=now - timedelta(days=30),
        ),
    ]
    session = MagicMock()
    session.scalars.return_value.all.return_value = releases

    metrics = calculate_release_metrics(session, repository, now=now)
    assert metrics.total_releases == 2
    assert metrics.releases_last_12_months == 1
    assert metrics.days_since_last_release == 30.0
