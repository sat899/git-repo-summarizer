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


def format_tree_for_prompt(
    tree: List[Dict[str, Any]],
    max_entries: int = 1000,
) -> str:
    """
    Renders the Git tree as a sorted list of paths with sizes,
    suitable for including in an LLM prompt.

    Truncates after max_entries to keep token usage reasonable.
    """
    lines: List[str] = []
    for entry in tree:
        path = entry.get("path")
        if not isinstance(path, str):
            continue
        entry_type = entry.get("type")
        if entry_type == "blob":
            size = entry.get("size", 0)
            if size >= 1024:
                size_label = f"{size / 1024:.1f} KB"
            else:
                size_label = f"{size} B"
            lines.append(f"{path}  ({size_label})")
        elif entry_type == "tree":
            lines.append(f"{path}/")

    lines.sort()

    total = len(lines)
    if total > max_entries:
        lines = lines[:max_entries]
        lines.append(f"... and {total - max_entries} more entries")

    return "\n".join(lines)


# Paths/patterns we never send to the LLM, even if the file-selector returns them.
_IGNORE_PATH_PREFIXES = (
    "node_modules/",
    ".git/",
    ".github/",
    "dist/",
    "build/",
    "__pycache__/",
    ".venv/",
    "venv/",
    "vendor/",
    ".next/",
    "target/",
    "coverage/",
    ".pytest_cache/",
)
_IGNORE_PATH_SUFFIXES = (
    ".lock",
    ".min.js",
    ".bundle.js",
    ".map",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
    ".woff",
    ".woff2",
    ".ttf",
    ".pyc",
    ".class",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
)


def _should_skip_path(path: str) -> bool:
    """True if this path should never be included in LLM context (lock files, binary, noise)."""
    if not path or not isinstance(path, str):
        return True
    path_lower = path.lower()
    if any(path_lower.startswith(p) for p in _IGNORE_PATH_PREFIXES):
        return True
    if any(path_lower.endswith(s) for s in _IGNORE_PATH_SUFFIXES):
        return True
    # Common lock/config filenames at repo root
    base = path_lower.split("/")[-1]
    if base in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "cargo.lock"):
        return True
    return False


def validate_llm_file_picks(
    picks: List[str],
    tree: List[Dict[str, Any]],
    max_file_size: int = 50_000,
) -> List[str]:
    """
    Validates and filters the file paths chosen by the LLM against the
    actual tree. Drops paths that are blocklisted (lock files, binary, noise),
    don't exist in the tree, or exceed max_file_size individually.

    Preserves the LLM's priority order so callers can enforce a total
    content budget by iterating through the returned list.
    """
    tree_blobs: Dict[str, int] = {}
    for entry in tree:
        if entry.get("type") == "blob" and isinstance(entry.get("path"), str):
            tree_blobs[entry["path"]] = entry.get("size", 0)

    validated: List[str] = []
    for path in picks:
        if _should_skip_path(path):
            continue
        if path not in tree_blobs:
            continue
        if tree_blobs[path] > max_file_size:
            continue
        validated.append(path)

    return validated