from typing import Optional

from pydantic import BaseModel


class SummarizeRequest(BaseModel):
    github_url: str


class SummarizeResponse(BaseModel):
    summary: str
    technologies: list[str]
    structure: str
    llm_input: Optional[str] = None