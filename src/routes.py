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
    format_tree_for_prompt,
    validate_llm_file_picks,
)
from src.llm import select_files, summarize_repository


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
        tree_text = format_tree_for_prompt(tree)
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

    # LLM pass 1: ask the model which files to read
    try:
        raw_picks = select_files(tree_text, readme_text, repo_languages=repo_languages)
        picked_paths = validate_llm_file_picks(raw_picks, tree)
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": f"File selection failed: {exc!s}"},
        )

    # Fetch the selected files
    try:
        file_sections: list[str] = []
        for path in picked_paths:
            try:
                content = fetch_file_contents(owner, repo, path)
            except GitHubAPIError:
                continue
            file_sections.append(f"FILE: {path}\n{content}")

        files_context = "\n\n".join(file_sections) if file_sections else None
    except httpx.HTTPError as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": f"Network error: {exc!s}"},
        )

    # LLM pass 2: produce the final summary
    try:
        summary = summarize_repository(
            payload.github_url,
            readme_text,
            tree_text,
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