import os
from unittest.mock import Mock, patch

# Ensure the OpenAI client can be constructed during import
os.environ.setdefault("OPENAI_API_KEY", "test-key")

from src.llm import MODEL, select_files, summarize_repository


@patch("src.llm.client")
def test_select_files_happy_path(mock_client: Mock) -> None:
    mock_completion = Mock()
    mock_completion.choices = [
        Mock(message=Mock(content='{"files": ["a.py", "b.py", "README.md"]}'))
    ]
    mock_client.chat.completions.create.return_value = mock_completion

    files = select_files(
        tree_text="a.py\nb.py\nREADME.md",
        readme_text="# README",
        repo_languages={"Python": 1234},
        max_files=2,
    )

    assert files == ["a.py", "b.py"]
    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == MODEL
    assert call_kwargs["response_format"] == {"type": "json_object"}


@patch("src.llm.client")
def test_select_files_handles_non_list_response(mock_client: Mock) -> None:
    mock_completion = Mock()
    mock_completion.choices = [Mock(message=Mock(content='{"files": "not-a-list"}'))]
    mock_client.chat.completions.create.return_value = mock_completion

    files = select_files(tree_text="file.py", readme_text="# README")
    assert files == []


@patch("src.llm.client")
def test_summarize_repository_basic(mock_client: Mock) -> None:
    mock_completion = Mock()
    mock_completion.choices = [
        Mock(
            message=Mock(
                content='{"summary": "A project.", "technologies": ["Python"], "structure": "Simple."}'
            )
        )
    ]
    mock_client.chat.completions.create.return_value = mock_completion

    result = summarize_repository(
        repo_url="https://github.com/owner/repo",
        readme_text="# README",
        tree_text="file.py",
        repo_languages={"Python": 100},
        files_context="FILE: file.py\nprint('hi')",
    )

    assert result.summary == "A project."
    assert result.technologies == ["Python"]
    assert result.structure == "Simple."
    # llm_input should contain key pieces of context
    assert "Repository URL: https://github.com/owner/repo" in result.llm_input
    assert "README content:" in result.llm_input
    assert "Repository file tree:" in result.llm_input
    assert "Selected source files:" in result.llm_input

