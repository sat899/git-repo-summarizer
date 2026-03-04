import json
from typing import Any, Dict, Optional

from openai import OpenAI

from src.schemas import SummarizeResponse


client = OpenAI()


def summarize_repository(
    repo_url: str,
    readme_text: str,
    repo_metadata: Optional[Dict[str, Any]] = None,
    repo_languages: Optional[Dict[str, int]] = None,
) -> SummarizeResponse:
    """
    Calls the LLM with the repo URL, README text, and any additional
    repository context (metadata, languages) and expects a JSON object
    with summary, technologies, and structure.
    """
    system_prompt = (
        "You are an assistant that summarizes GitHub repositories.\n"
        "Given the repository URL, its README content, and additional "
        "repository context, produce a short JSON object with keys: "
        "summary (string), technologies (list of strings), structure (string). "
        "Respond ONLY with a JSON object, no extra text."
    )

    context_parts = [
        f"Repository URL: {repo_url}",
        "",
        "README content:",
        readme_text,
    ]

    if repo_metadata is not None:
        context_parts.extend(
            [
                "",
                "Repository metadata (JSON):",
                json.dumps(repo_metadata, indent=2),
            ]
        )

    if repo_languages is not None:
        context_parts.extend(
            [
                "",
                "Repository languages (JSON):",
                json.dumps(repo_languages, indent=2),
            ]
        )

    user_content = "\n".join(context_parts)

    completion = client.chat.completions.create(
        model="gpt-5-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )

    raw_content = completion.choices[0].message.content
    data: Dict[str, Any] = json.loads(raw_content)

    return SummarizeResponse(
        summary=data.get("summary", ""),
        technologies=data.get("technologies") or [],
        structure=data.get("structure", ""),
        repo_metadata=repo_metadata,
        repo_languages=repo_languages,
        debug={
            "llm_input": user_content,
            "llm_raw_output": raw_content,
        },
    )