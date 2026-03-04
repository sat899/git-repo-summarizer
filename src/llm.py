import json
from typing import Any, Dict, Optional

from openai import OpenAI

from src.schemas import SummarizeResponse


client = OpenAI()


def summarize_repository(
    repo_url: str,
    readme_text: str,
    repo_languages: Optional[Dict[str, int]] = None,
    files_context: Optional[str] = None,
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

    if repo_languages is not None:
        context_parts.extend(
            [
                "",
                "Repository languages (JSON):",
                json.dumps(repo_languages, indent=2),
            ]
        )

    if files_context:
        context_parts.extend(
            [
                "",
                "Sampled repository files:",
                files_context,
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

    content = completion.choices[0].message.content
    data: Dict[str, Any] = json.loads(content)

    return SummarizeResponse(
        summary=data.get("summary", ""),
        technologies=data.get("technologies") or [],
        structure=data.get("structure", ""),
        llm_input=user_content,
    )