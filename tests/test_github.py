from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.github_client import (
    GITHUB_API_BASE,
    GitHubAPIError,
    fetch_file_contents,
    fetch_repo_languages,
    fetch_repo_metadata,
    fetch_repo_readme,
    fetch_repo_tree,
    format_tree_for_prompt,
    validate_llm_file_picks,
    parse_github_url,
)


def _mock_client(get_return_value):
    """Return a mock AsyncClient whose get() returns the given response."""
    client = Mock()
    client.get = AsyncMock(return_value=get_return_value)
    return client


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


async def test_fetch_repo_readme_success():
    mock_resp = Mock(status_code=200, text="# README")
    client = _mock_client(mock_resp)

    text = await fetch_repo_readme("owner", "repo", client=client)

    assert text == "# README"
    client.get.assert_called_once_with(
        f"{GITHUB_API_BASE}/repos/owner/repo/readme",
        headers={"Accept": "application/vnd.github.v3.raw"},
        timeout=10,
    )


async def test_fetch_repo_readme_error():
    mock_resp = Mock(status_code=404)
    client = _mock_client(mock_resp)

    with pytest.raises(GitHubAPIError) as exc_info:
        await fetch_repo_readme("owner", "repo", client=client)
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.message.lower()


async def test_fetch_repo_metadata_success():
    payload = {"full_name": "owner/repo", "default_branch": "main"}
    mock_resp = Mock(status_code=200, json=lambda: payload)
    client = _mock_client(mock_resp)

    data = await fetch_repo_metadata("owner", "repo", client=client)

    assert data == payload


async def test_fetch_repo_metadata_error():
    mock_resp = Mock(status_code=500)
    client = _mock_client(mock_resp)

    with pytest.raises(GitHubAPIError) as exc_info:
        await fetch_repo_metadata("owner", "repo", client=client)
    assert exc_info.value.status_code == 502


async def test_fetch_repo_languages_success():
    payload = {"Python": 1234, "C": 10}
    mock_resp = Mock(status_code=200, json=lambda: payload)
    client = _mock_client(mock_resp)

    data = await fetch_repo_languages("owner", "repo", client=client)

    assert data == {"Python": 1234, "C": 10}


async def test_fetch_repo_languages_error():
    mock_resp = Mock(status_code=404)
    client = _mock_client(mock_resp)

    with pytest.raises(GitHubAPIError) as exc_info:
        await fetch_repo_languages("owner", "repo", client=client)
    assert exc_info.value.status_code == 404


async def test_fetch_repo_tree_success_uses_default_branch_and_returns_tree():
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
    client = Mock()
    client.get = AsyncMock(side_effect=[metadata_resp, branch_resp, tree_resp])

    tree = await fetch_repo_tree("owner", "repo", client=client)

    assert tree == tree_payload["tree"]


async def test_fetch_repo_tree_raises_when_branch_request_fails():
    metadata_resp = Mock(
        status_code=200,
        json=lambda: {"default_branch": "main"},
    )
    branch_resp = Mock(status_code=404)
    client = Mock()
    client.get = AsyncMock(side_effect=[metadata_resp, branch_resp])

    with pytest.raises(GitHubAPIError) as exc_info:
        await fetch_repo_tree("owner", "repo", client=client)
    assert exc_info.value.status_code == 422
    assert "empty" in exc_info.value.message.lower()


# --- fetch_file_contents ---

async def test_fetch_file_contents_success():
    mock_resp = Mock(status_code=200, text="print('hello')")
    client = _mock_client(mock_resp)

    text = await fetch_file_contents("owner", "repo", "src/main.py", client=client)

    assert text == "print('hello')"
    client.get.assert_called_once_with(
        f"{GITHUB_API_BASE}/repos/owner/repo/contents/src/main.py",
        headers={"Accept": "application/vnd.github.v3.raw"},
        params=None,
        timeout=10,
    )


async def test_fetch_file_contents_with_ref():
    mock_resp = Mock(status_code=200, text="content")
    client = _mock_client(mock_resp)

    await fetch_file_contents("owner", "repo", "README.md", ref="main", client=client)

    client.get.assert_called_once_with(
        f"{GITHUB_API_BASE}/repos/owner/repo/contents/README.md",
        headers={"Accept": "application/vnd.github.v3.raw"},
        params={"ref": "main"},
        timeout=10,
    )


async def test_fetch_file_contents_error():
    mock_resp = Mock(status_code=404)
    client = _mock_client(mock_resp)

    with pytest.raises(GitHubAPIError) as exc_info:
        await fetch_file_contents("owner", "repo", "missing.py", client=client)
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.message.lower()


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
    result = validate_llm_file_picks(["big.py", "small.py"], tree, max_file_size=50_000)
    assert result == ["small.py"]


def test_validate_picks_preserves_priority_order():
    tree = [{"path": f"f{i}.py", "type": "blob", "size": 10} for i in range(20)]
    picks = [f"f{i}.py" for i in range(20)]
    result = validate_llm_file_picks(picks, tree)
    assert result == picks


def test_validate_picks_filters_blocklisted_paths():
    tree = [
        {"path": "src/main.py", "type": "blob", "size": 100},
        {"path": "package-lock.json", "type": "blob", "size": 100},
        {"path": "node_modules/foo/index.js", "type": "blob", "size": 100},
        {"path": "image.png", "type": "blob", "size": 100},
    ]
    picks = ["src/main.py", "package-lock.json", "node_modules/foo/index.js", "image.png"]
    result = validate_llm_file_picks(picks, tree)
    assert result == ["src/main.py"]
