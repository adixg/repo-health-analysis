from unittest.mock import MagicMock

from src.database.models import Repository
from src.reporting.report import generate_repository_report


def test_generate_repository_report_renders_sections() -> None:
    repository = Repository(
        id=1,
        full_name="psf/requests",
        owner="psf",
        name="requests",
        stars=52000,
        forks=9300,
        open_issues=200,
        language="Python",
    )
    session = MagicMock()
    session.scalar.side_effect = [repository, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    session.execute.return_value.all.return_value = []
    session.scalars.return_value.all.return_value = []

    report = generate_repository_report(session, "psf/requests")

    assert report.startswith("# Repository Health Report — psf/requests")
    assert "## Issue health" in report
    assert "## Pull requests" in report
    assert "## Contributors" in report
    assert "## Top issue labels" in report
    # exploratory / non-causal framing must be present
    assert "not causal conclusions" in report
    # with no ingested issues the label table shows the empty-state row
    assert "_no labeled issues_" in report
