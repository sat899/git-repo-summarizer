from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.schemas import SummarizeRequest, SummarizeResponse
from src.github_client import (
    parse_github_url,
    fetch_repo_metadata,
    fetch_repo_languages,
    fetch_repo_readme,
)
from src.llm import summarize_repository


router = APIRouter()


@router.post("/summarize", response_model=SummarizeResponse)
def summarize_repo(payload: SummarizeRequest):
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
    except RuntimeError as exc:
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": str(exc)},
        )

    summary = summarize_repository(payload.github_url, readme_text)
    summary.repo_metadata = repo_metadata
    summary.repo_languages = repo_languages
    return summary