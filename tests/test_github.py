from unittest.mock import Mock, patch

import pytest

from src.github_client import (
    GITHUB_API_BASE,
    GitHubAPIError,
    fetch_repo_languages,
    fetch_repo_metadata,
    fetch_repo_readme,
    fetch_repo_tree,
    format_tree_for_prompt,
    validate_llm_file_picks,
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
        with pytest.raises(GitHubAPIError) as exc_info:
            fetch_repo_readme("owner", "repo")
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.message.lower()


def test_fetch_repo_metadata_success():
    payload = {"full_name": "owner/repo", "default_branch": "main"}
    mock_resp = Mock(status_code=200, json=lambda: payload)

    with patch("src.github_client.httpx.get", return_value=mock_resp):
        data = fetch_repo_metadata("owner", "repo")

    assert data == payload


def test_fetch_repo_metadata_error():
    mock_resp = Mock(status_code=500)

    with patch("src.github_client.httpx.get", return_value=mock_resp):
        with pytest.raises(GitHubAPIError) as exc_info:
            fetch_repo_metadata("owner", "repo")
    assert exc_info.value.status_code == 502


def test_fetch_repo_languages_success():
    payload = {"Python": 1234, "C": 10}
    mock_resp = Mock(status_code=200, json=lambda: payload)

    with patch("src.github_client.httpx.get", return_value=mock_resp):
        data = fetch_repo_languages("owner", "repo")

    assert data == {"Python": 1234, "C": 10}


def test_fetch_repo_languages_error():
    mock_resp = Mock(status_code=404)

    with patch("src.github_client.httpx.get", return_value=mock_resp):
        with pytest.raises(GitHubAPIError) as exc_info:
            fetch_repo_languages("owner", "repo")
    assert exc_info.value.status_code == 404


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
        with pytest.raises(GitHubAPIError) as exc_info:
            fetch_repo_tree("owner", "repo")
    assert exc_info.value.status_code == 422
    assert "empty" in exc_info.value.message.lower()


# --- format_tree_for_prompt ---

def test_format_tree_basic():
    tree = [
        {"path": "src", "type": "tree"},
        {"path": "src/main.py", "type": "blob", "size": 2048},
        {"path": "README.md", "type": "blob", "size": 500},
    ]
    result = format_tree_for_prompt(tree)
    assert "README.md  (500 B)" in result
    assert "src/" in result
    assert "src/main.py  (2.0 KB)" in result


def test_format_tree_truncates():
    tree = [{"path": f"file{i}.py", "type": "blob", "size": 100} for i in range(10)]
    result = format_tree_for_prompt(tree, max_entries=3)
    assert "... and 7 more entries" in result


# --- validate_llm_file_picks ---

def test_validate_picks_filters_missing_paths():
    tree = [
        {"path": "a.py", "type": "blob", "size": 100},
        {"path": "b.py", "type": "blob", "size": 100},
    ]
    picks = ["a.py", "nonexistent.py", "b.py"]
    result = validate_llm_file_picks(picks, tree)
    assert result == ["a.py", "b.py"]


def test_validate_picks_skips_large_files():
    tree = [
        {"path": "big.py", "type": "blob", "size": 999_999},
        {"path": "small.py", "type": "blob", "size": 100},
    ]
    result = validate_llm_file_picks(["big.py", "small.py"], tree, max_size_bytes=50_000)
    assert result == ["small.py"]


def test_validate_picks_respects_max_files():
    tree = [{"path": f"f{i}.py", "type": "blob", "size": 10} for i in range(20)]
    picks = [f"f{i}.py" for i in range(20)]
    result = validate_llm_file_picks(picks, tree, max_files=5)
    assert len(result) == 5
