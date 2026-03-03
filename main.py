from fastapi import FastAPI
from pydantic import BaseModel

class SummarizeRequest(BaseModel):
    github_url: str

class SummarizeResponse(BaseModel):
    summary: str
    technologies: list[str]
    structure: str

app = FastAPI()

@app.post("/summarize", response_model=SummarizeResponse)
async def summarize_repo(payload: SummarizeRequest):
    
    print(f"Received request to summarize repo: {payload.github_url}")

    return SummarizeResponse(
        summary="This is a placeholder summary for now.",
        technologies=["Python"],
        structure="This is a placeholder structure description.",
    )