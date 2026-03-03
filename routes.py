from fastapi import APIRouter

from schemas import SummarizeRequest, SummarizeResponse

router = APIRouter()

@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_repo(payload: SummarizeRequest):
    print(f"Received request to summarize repo: {payload.github_url}")

    return SummarizeResponse(
        summary="This is a placeholder summary for now.",
        technologies=["Python"],
        structure="This is a placeholder structure description.",
    )