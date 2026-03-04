import httpx
from fastapi import APIRouter, Request
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
async def summarize_repo(request: Request, payload: SummarizeRequest, debug: bool = False):
    try:
        owner, repo = parse_github_url(payload.github_url)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": str(exc)},
        )

    client = request.app.state.httpx_client
    MAX_README_CHARS = 30_000

    try:
        repo_languages = await fetch_repo_languages(owner, repo, client=client)
        readme_text = await fetch_repo_readme(owner, repo, client=client)
        if len(readme_text) > MAX_README_CHARS:
            readme_text = readme_text[:MAX_README_CHARS] + "\n\n[README truncated]"
        tree = await fetch_repo_tree(owner, repo, client=client)
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

    # Fetch the selected files, respecting a total content budget
    MAX_CONTENT_BUDGET = 200_000  # characters
    try:
        file_sections: list[str] = []
        budget_used = 0
        for path in picked_paths:
            try:
                content = await fetch_file_contents(owner, repo, path, client=client)
            except GitHubAPIError:
                continue
            section = f"FILE: {path}\n{content}"
            if budget_used + len(section) > MAX_CONTENT_BUDGET:
                remaining = MAX_CONTENT_BUDGET - budget_used
                if remaining > 200:
                    section = section[:remaining] + "\n\n[file truncated]"
                    file_sections.append(section)
                break
            file_sections.append(section)
            budget_used += len(section)

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