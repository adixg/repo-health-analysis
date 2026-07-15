from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.ingestion.github_client import GITHUB_MAX_PAGE, GitHubClient


def test_paginate_stops_at_github_page_limit() -> None:
    client = GitHubClient()
    full_page = [{"id": index} for index in range(100)]

    with patch.object(client, "get", return_value=full_page) as mock_get:
        pages = list(client.paginate("repos/o/r/issues/comments"))

    assert len(pages) == GITHUB_MAX_PAGE * 100
    assert mock_get.call_count == GITHUB_MAX_PAGE


def test_paginate_handles_422_gracefully() -> None:
    client = GitHubClient()
    response = httpx.Response(422, request=httpx.Request("GET", "https://api.github.com/test"))
    error = httpx.HTTPStatusError("422", request=response.request, response=response)

    with patch.object(client, "get", side_effect=error):
        pages = list(client.paginate("repos/o/r/issues/comments"))

    assert pages == []


def test_request_retries_transient_502() -> None:
    client = GitHubClient()
    request = httpx.Request("GET", "https://api.github.com/repos/o/r/pulls/comments")
    bad = httpx.Response(502, request=request)
    good = httpx.Response(200, request=request, json=[{"id": 1}])
    mock_http = MagicMock()
    mock_http.get.side_effect = [bad, good]
    client._http = mock_http

    with patch("src.ingestion.github_client.time.sleep"):
        response = client._request("https://api.github.com/repos/o/r/pulls/comments")

    assert response.status_code == 200
    assert mock_http.get.call_count == 2
