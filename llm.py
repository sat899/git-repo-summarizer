import json
from typing import Any, Dict
from openai import OpenAI
from schemas import SummarizeResponse

client = OpenAI()

def summarize_repository(repo_url: str, readme_text: str) -> SummarizeResponse:
    """
    Calls the LLM with the repo URL + README text and expects
    a JSON object with summary, technologies, structure.
    """
    system_prompt = (
        "You are an assistant that summarizes GitHub repositories.\n"
        "Given the repository URL and its README content, produce a short JSON "
        "object with keys: summary (string), technologies (list of strings), "
        "structure (string). Respond ONLY with a JSON object, no extra text."
    )

    user_content = (
        f"Repository URL: {repo_url}\n\n"
        f"README content:\n\n{readme_text}\n"
    )

    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )

    content = completion.choices[0].message.content
    data: Dict[str, Any] = json.loads(content)

    return SummarizeResponse(
        summary=data.get("summary", ""),
        technologies=data.get("technologies") or [],
        structure=data.get("structure", ""),
    )