from urllib.parse import urlparse
import httpx

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
    url = f"https://api.github.com/repos/{owner}/{repo}/readme"
    headers = {"Accept": "application/vnd.github.v3.raw"}

    resp = httpx.get(url, headers=headers, timeout=10)

    if resp.status_code == 200:
        return resp.text

    raise RuntimeError(f"Failed to fetch README (status {resp.status_code})")