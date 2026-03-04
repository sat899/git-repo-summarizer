from typing import Any, Dict, Optional

from pydantic import BaseModel


class SummarizeRequest(BaseModel):
    github_url: str


class SummarizeResponse(BaseModel):
    summary: str
    technologies: list[str]
    structure: str
    repo_metadata: Optional[Dict[str, Any]] = None
    repo_languages: Optional[Dict[str, int]] = None
    debug: Optional[Dict[str, Any]] = None