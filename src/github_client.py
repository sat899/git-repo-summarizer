from urllib.parse import urlparse
from typing import Any, Dict, List
import httpx

GITHUB_API_BASE = "https://api.github.com"

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

    if resp.status_code == 200:
        return resp.text

    raise RuntimeError(f"Failed to fetch README (status {resp.status_code})")

def fetch_repo_metadata(owner: str, repo: str) -> Dict[str, Any]:
    """
    Fetches basic repository metadata, including default branch and description.
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
    resp = httpx.get(url, timeout=10)

    if resp.status_code == 200:
        return resp.json()

    raise RuntimeError(f"Failed to fetch repo metadata (status {resp.status_code})")

def fetch_repo_languages(owner: str, repo: str) -> Dict[str, int]:
    """
    Fetches language usage statistics for the repository.

    Returns a mapping of language -> bytes of code.
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/languages"
    resp = httpx.get(url, timeout=10)

    if resp.status_code == 200:
        data = resp.json()
        return {str(k): int(v) for k, v in data.items()}

    raise RuntimeError(f"Failed to fetch repo languages (status {resp.status_code})")

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
            raise RuntimeError("Could not determine default branch for repository")

    # Get the commit SHA for the ref
    branch_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/branches/{ref}"
    branch_resp = httpx.get(branch_url, timeout=10)
    if branch_resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch branch info for {ref} (status {branch_resp.status_code})")

    branch_data = branch_resp.json()
    commit = branch_data.get("commit") or {}
    commit_sha = commit.get("sha")
    if not commit_sha:
        raise RuntimeError("Could not determine commit SHA for branch")

    params = {"recursive": "1"} if recursive else None
    tree_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{commit_sha}"
    tree_resp = httpx.get(tree_url, params=params, timeout=10)
    if tree_resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch repo tree (status {tree_resp.status_code})")

    tree_data = tree_resp.json()
    tree = tree_data.get("tree")
    if not isinstance(tree, list):
        raise RuntimeError("Unexpected tree format from GitHub API")

    return tree