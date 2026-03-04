import json
from typing import Any, Dict, List, Optional

from openai import OpenAI

from src.schemas import SummarizeResponse


client = OpenAI()

MODEL = "gpt-5-mini"


def select_files(
    tree_text: str,
    readme_text: str,
    repo_languages: Optional[Dict[str, int]] = None,
    max_files: int = 10,
) -> List[str]:
    """
    LLM pass 1: given the file tree, README, and languages, ask the LLM
    to pick the most informative files for understanding the project.

    Returns a list of file paths.
    """
    system_prompt = (
        "You are a code analyst. Given a repository's file tree, README, "
        "and language breakdown, select the files that would be most useful "
        "for understanding what this project does, how it is structured, and "
        "what technologies it uses.\n\n"
        "Rules:\n"
        f"- Return at most {max_files} file paths.\n"
        "- Prefer source code entry points, config files, and key modules.\n"
        "- Skip lock files, generated code, test fixtures, and vendored dependencies.\n"
        "- Do NOT select the README (it is already provided separately).\n"
        "- Respond ONLY with a JSON object: {\"files\": [\"path/to/file\", ...]}"
    )

    context_parts = [
        "README content:",
        readme_text,
    ]

    if repo_languages is not None:
        context_parts.extend(
            [
                "",
                "Repository languages:",
                json.dumps(repo_languages, indent=2),
            ]
        )

    context_parts.extend(
        [
            "",
            "Repository file tree:",
            tree_text,
        ]
    )

    user_content = "\n".join(context_parts)

    completion = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )

    data = json.loads(completion.choices[0].message.content)
    files = data.get("files", [])
    if not isinstance(files, list):
        return []
    return [f for f in files if isinstance(f, str)][:max_files]


def summarize_repository(
    repo_url: str,
    readme_text: str,
    tree_text: str,
    repo_languages: Optional[Dict[str, int]] = None,
    files_context: Optional[str] = None,
) -> SummarizeResponse:
    """
    LLM pass 2: given the repo URL, README, file tree, languages, and
    selected file contents, produce the final summary JSON.
    """
    system_prompt = (
        "You are an assistant that summarizes GitHub repositories.\n"
        "You are given the repository URL, its README, the full file tree, "
        "language statistics, and the contents of key source files.\n"
        "Produce a JSON object with keys: "
        "summary (string), technologies (list of strings), structure (string).\n"
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
                "Repository languages:",
                json.dumps(repo_languages, indent=2),
            ]
        )

    context_parts.extend(
        [
            "",
            "Repository file tree:",
            tree_text,
        ]
    )

    if files_context:
        context_parts.extend(
            [
                "",
                "Selected source files:",
                files_context,
            ]
        )

    user_content = "\n".join(context_parts)

    completion = client.chat.completions.create(
        model=MODEL,
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