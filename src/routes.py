import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.schemas import SummarizeRequest, SummarizeResponse
from src.github_client import (
    GitHubAPIError,
    parse_github_url,
    fetch_repo_languages,
    fetch_repo_readme,
    fetch_repo_tree,
    fetch_file_contents,
    select_files_for_context,
)
from src.llm import summarize_repository


router = APIRouter()


@router.post(
    "/summarize",
    response_model=SummarizeResponse,
    response_model_exclude_none=True,
)
def summarize_repo(payload: SummarizeRequest, debug: bool = False):
    try:
        owner, repo = parse_github_url(payload.github_url)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": str(exc)},
        )

    try:
        repo_languages = fetch_repo_languages(owner, repo)
        readme_text = fetch_repo_readme(owner, repo)
        tree = fetch_repo_tree(owner, repo)
        sample_paths = select_files_for_context(tree)

        file_sections: list[str] = []
        for path in sample_paths:
            try:
                content = fetch_file_contents(owner, repo, path)
            except GitHubAPIError:
                continue
            file_sections.append(f"FILE: {path}\n{content}")

        files_context = "\n\n".join(file_sections) if file_sections else None
    except GitHubAPIError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "message": exc.message},
        )
    except httpx.HTTPError as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": f"Network error: {exc!s}"},
        )

    try:
        summary = summarize_repository(
            payload.github_url,
            readme_text,
            repo_languages=repo_languages,
            files_context=files_context,
        )
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": f"Summarization failed: {exc!s}"},
        )

    if not debug:
        summary.llm_input = None

    return summary