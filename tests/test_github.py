from unittest.mock import Mock, patch

import pytest

from src.github_client import (
    GITHUB_API_BASE,
    fetch_repo_languages,
    fetch_repo_metadata,
    fetch_repo_readme,
    fetch_repo_tree,
    parse_github_url,
)


def test_parse_github_url_valid():
    owner, repo = parse_github_url("https://github.com/psf/requests")
    assert owner == "psf"
    assert repo == "requests"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/psf/requests",
        "https://github.com/psf",
        "not-a-url",
        "https://github.com/",
    ],
)
def test_parse_github_url_invalid(url: str):
    with pytest.raises(ValueError):
        parse_github_url(url)


def test_fetch_repo_readme_success():
    mock_resp = Mock(status_code=200, text="# README")

    with patch("src.github_client.httpx.get", return_value=mock_resp) as mock_get:
        text = fetch_repo_readme("owner", "repo")

    assert text == "# README"
    mock_get.assert_called_once_with(
        f"{GITHUB_API_BASE}/repos/owner/repo/readme",
        headers={"Accept": "application/vnd.github.v3.raw"},
        timeout=10,
    )


def test_fetch_repo_readme_error():
    mock_resp = Mock(status_code=404)

    with patch("src.github_client.httpx.get", return_value=mock_resp):
        with pytest.raises(RuntimeError):
            fetch_repo_readme("owner", "repo")


def test_fetch_repo_metadata_success():
    payload = {"full_name": "owner/repo", "default_branch": "main"}
    mock_resp = Mock(status_code=200, json=lambda: payload)

    with patch("src.github_client.httpx.get", return_value=mock_resp):
        data = fetch_repo_metadata("owner", "repo")

    assert data == payload


def test_fetch_repo_metadata_error():
    mock_resp = Mock(status_code=500)

    with patch("src.github_client.httpx.get", return_value=mock_resp):
        with pytest.raises(RuntimeError):
            fetch_repo_metadata("owner", "repo")


def test_fetch_repo_languages_success():
    payload = {"Python": 1234, "C": 10}
    mock_resp = Mock(status_code=200, json=lambda: payload)

    with patch("src.github_client.httpx.get", return_value=mock_resp):
        data = fetch_repo_languages("owner", "repo")

    assert data == {"Python": 1234, "C": 10}


def test_fetch_repo_languages_error():
    mock_resp = Mock(status_code=404)

    with patch("src.github_client.httpx.get", return_value=mock_resp):
        with pytest.raises(RuntimeError):
            fetch_repo_languages("owner", "repo")


def test_fetch_repo_tree_success_uses_default_branch_and_returns_tree():
    metadata_resp = Mock(
        status_code=200,
        json=lambda: {"default_branch": "main"},
    )
    branch_resp = Mock(
        status_code=200,
        json=lambda: {"commit": {"sha": "abc123"}},
    )
    tree_payload = {"tree": [{"path": "README.md", "type": "blob"}]}
    tree_resp = Mock(status_code=200, json=lambda: tree_payload)

    with patch(
        "src.github_client.httpx.get",
        side_effect=[metadata_resp, branch_resp, tree_resp],
    ):
        tree = fetch_repo_tree("owner", "repo")

    assert tree == tree_payload["tree"]


def test_fetch_repo_tree_raises_when_branch_request_fails():
    metadata_resp = Mock(
        status_code=200,
        json=lambda: {"default_branch": "main"},
    )
    branch_resp = Mock(status_code=404)

    with patch(
        "src.github_client.httpx.get",
        side_effect=[metadata_resp, branch_resp],
    ):
        with pytest.raises(RuntimeError):
            fetch_repo_tree("owner", "repo")
