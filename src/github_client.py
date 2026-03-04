from urllib.parse import urlparse
from typing import Any, Dict, List

import httpx

GITHUB_API_BASE = "https://api.github.com"


class GitHubAPIError(Exception):
    """Raised when a GitHub API call fails. Carries HTTP status and a user-facing message."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def _raise_for_status(resp: httpx.Response, context: str = "Request") -> None:
    if resp.status_code == 200:
        return
    if resp.status_code == 404:
        raise GitHubAPIError(404, "Repository not found")
    if resp.status_code == 403:
        raise GitHubAPIError(403, "Repository is private or access denied")
    raise GitHubAPIError(502, f"{context} failed (status {resp.status_code})")


def parse_github_url(url: str) -> tuple[str, str]:
    """
    Accepts URLs like:
    - https://github.com/owner/repo
    - https://github.com/owner/repo/
    and returns (owner, repo).
    """
    parsed = urlparse(url)
    if parsed.netloc not in {"github.com", "www.github.com"}:
        raise ValueError("URL must be a github.com URL")

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError("URL must be of the form https://github.com/<owner>/<repo>")

    owner, repo = parts[0], parts[1]
    return owner, repo

def fetch_repo_readme(owner: str, repo: str) -> str:
    """
    Fetches the README using the GitHub API (public repos only).
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/readme"
    headers = {"Accept": "application/vnd.github.v3.raw"}

    resp = httpx.get(url, headers=headers, timeout=10)
    _raise_for_status(resp, "README")
    return resp.text

def fetch_repo_metadata(owner: str, repo: str) -> Dict[str, Any]:
    """
    Fetches basic repository metadata, including default branch and description.
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
    resp = httpx.get(url, timeout=10)
    _raise_for_status(resp, "Repository metadata")
    return resp.json()

def fetch_repo_languages(owner: str, repo: str) -> Dict[str, int]:
    """
    Fetches language usage statistics for the repository.

    Returns a mapping of language -> bytes of code.
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/languages"
    resp = httpx.get(url, timeout=10)
    _raise_for_status(resp, "Repository languages")
    data = resp.json()
    return {str(k): int(v) for k, v in data.items()}

def fetch_repo_tree(owner: str, repo: str, ref: str | None = None, recursive: bool = True) -> List[Dict[str, Any]]:
    """
    Fetches the repository file tree for the given ref (branch/sha).

    If ref is None, uses the repository's default branch from metadata.
    Returns the 'tree' list from the Git Trees API.
    """
    if ref is None:
        metadata = fetch_repo_metadata(owner, repo)
        ref = metadata.get("default_branch")
        if not ref:
            raise GitHubAPIError(422, "Repository appears to be empty (no default branch)")

    branch_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/branches/{ref}"
    branch_resp = httpx.get(branch_url, timeout=10)
    if branch_resp.status_code == 404:
        raise GitHubAPIError(422, "Repository appears to be empty (no branches)")
    _raise_for_status(branch_resp, "Branch info")

    branch_data = branch_resp.json()
    commit = branch_data.get("commit") or {}
    commit_sha = commit.get("sha")
    if not commit_sha:
        raise GitHubAPIError(422, "Repository appears to be empty")

    params = {"recursive": "1"} if recursive else None
    tree_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{commit_sha}"
    tree_resp = httpx.get(tree_url, params=params, timeout=10)
    _raise_for_status(tree_resp, "Repository tree")

    tree_data = tree_resp.json()
    tree = tree_data.get("tree")
    if not isinstance(tree, list):
        raise GitHubAPIError(502, "Unexpected tree format from GitHub API")

    return tree


def fetch_file_contents(owner: str, repo: str, path: str, ref: str | None = None) -> str:
    """
    Fetches the contents of a single file at the given path.
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    params: Dict[str, str] | None = None
    if ref is not None:
        params = {"ref": ref}
    headers = {"Accept": "application/vnd.github.v3.raw"}

    resp = httpx.get(url, headers=headers, params=params, timeout=10)
    _raise_for_status(resp, f"File {path}")
    return resp.text


def select_files_for_context(
    tree: List[Dict[str, Any]],
    max_files: int = 5,
    max_size_bytes: int = 20_000,
) -> List[str]:
    """
    Very simple first-pass selection of files to include in LLM context.

    - Only includes regular files (type == 'blob')
    - Skips obviously noisy paths (e.g. node_modules, .git)
    - Skips files larger than max_size_bytes
    - Prefers common text/code extensions
    """
    ignore_prefixes = (
        "node_modules/",
        ".git/",
        ".github/",
        "dist/",
        "build/",
        "__pycache__/",
        ".venv/",
    )
    allowed_exts = (
        ".py",
        ".md",
        ".rst",
        ".txt",
        ".js",
        ".ts",
    )

    selected: List[str] = []

    for entry in tree:
        if entry.get("type") != "blob":
            continue

        path = entry.get("path")
        if not isinstance(path, str):
            continue

        # Avoid re-sending the top-level README via the tree;
        # we already include README content separately.
        lower_path = path.lower()
        if "/" not in path and lower_path.startswith("readme"):
            continue

        # Skip obvious noise directories
        if any(path.startswith(prefix) for prefix in ignore_prefixes):
            continue

        size = entry.get("size")
        if isinstance(size, int) and size > max_size_bytes:
            continue

        if not lower_path.endswith(allowed_exts):
            continue

        selected.append(path)
        if len(selected) >= max_files:
            break

    return selected