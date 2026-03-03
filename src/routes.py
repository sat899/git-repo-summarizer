from fastapi import APIRouter, HTTPException
from src.schemas import SummarizeRequest, SummarizeResponse
from src.github_client import parse_github_url, fetch_repo_readme
from src.llm import summarize_repository

router = APIRouter()

@router.post("/summarize", response_model=SummarizeResponse)
def summarize_repo(payload: SummarizeRequest):
    try:
        owner, repo = parse_github_url(payload.github_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        readme_text = fetch_repo_readme(owner, repo)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    summary = summarize_repository(payload.github_url, readme_text)
    return summary