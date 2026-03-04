from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.schemas import SummarizeRequest, SummarizeResponse
from src.github_client import (
    parse_github_url,
    fetch_repo_metadata,
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
        repo_metadata = fetch_repo_metadata(owner, repo)
        repo_languages = fetch_repo_languages(owner, repo)
        readme_text = fetch_repo_readme(owner, repo)

        # Minimal v1: fetch tree and a small sample of representative files
        tree = fetch_repo_tree(owner, repo)
        sample_paths = select_files_for_context(tree)

        file_sections: list[str] = []
        for path in sample_paths:
            try:
                content = fetch_file_contents(owner, repo, path)
            except RuntimeError:
                continue
            file_sections.append(f"FILE: {path}\n{content}")

        files_context = "\n\n".join(file_sections) if file_sections else None
    except RuntimeError as exc:
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": str(exc)},
        )

    summary = summarize_repository(
        payload.github_url,
        readme_text,
        repo_metadata=repo_metadata,
        repo_languages=repo_languages,
        files_context=files_context,
    )
    if not debug:
        summary.llm_input = None

    return summary