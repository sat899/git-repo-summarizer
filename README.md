## git-repo-summarizer

Simple service that takes a public GitHub repository URL and returns a human‑readable summary of what the project does, the main technologies used and the project structure.

It exposes:
- A FastAPI backend: `POST /summarize`
- A small Streamlit UI for interactive use

The LLM is accessed via the OpenAI API and is configured using the `OPENAI_API_KEY` environment variable.

## Requirements

- Python 3.10+
- `uv` (Python package/dependency manager)
- An OpenAI API key (`OPENAI_API_KEY`)

## Setup (using uv)

1. **Clone the repo & enter the directory**

```bash
git clone https://github.com/sat899/git-repo-summarizer.git
cd git-repo-summarizer
```

2. **Create a `.env` file**

In the project root:

```bash
echo OPENAI_API_KEY=... > .env
```

3. **Install dependencies with uv**

```bash
uv sync
```

This will create a virtual environment and install all dependencies defined in `pyproject.toml`.

## Running the backend (FastAPI)

From the project root:

```bash
uv run uvicorn src.main:app --reload
```

This starts the API server on `http://localhost:8000`.

### Manual test of `/summarize`

In a separate terminal:

```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/psf/requests"}' | python -m json.tool
```

You should get a JSON response like:

```json
{
  "summary": "...",
  "technologies": ["Python", "..."],
  "structure": "..."
}
```

## Running the Streamlit UI

With the backend running on `http://localhost:8000`, start the frontend from the project root:

```bash
uv run streamlit run src/streamlit_app.py
```

Streamlit will print a URL where you can access the frontend (typically `http://localhost:8501`).

In the UI:

- Enter a public GitHub repo URL (e.g. `https://github.com/psf/requests`)
- Click **Summarize**
- The summary, technologies, and structure will appear below the button.

## Running Tests

From the project root:
```bash
uv run pytest
```

## How it works

- **Input**: `github_url` pointing to a public GitHub repository.
- **GitHub client** (`src/github_client.py`):
  - Parses the URL into `(owner, repo)`.
  - Fetches from the GitHub API:
    - Language breakdown (`/repos/{owner}/{repo}/languages`).
    - The README (`/repos/{owner}/{repo}/readme`).
    - The full Git tree for the default branch (`/git/trees/{sha}?recursive=1`).
  - Renders the tree as a sorted list of paths with sizes (up to 500 entries) for the LLM. Languages, README, and tree are fetched in parallel; selected file contents are then fetched in parallel and trimmed to the content budget in priority order.
- **Two-pass LLM** (`src/llm.py`):
  - **Pass 1 (file selection)**: The first LLM selects the most relevant files from the repo tree. It receives the README, languages, and the full file tree, and returns a JSON list of file paths in priority order. We then apply deterministic filters (blocklist, must exist in tree, per-file size cap) and fetch all selected file contents in parallel, then apply the content budget in that order.
  - **Pass 2 (summarization)**: The second LLM is responsible for summarizing the information contained in the files selected by the first LLM and for generating a response that adheres to the required output structure. It receives the repository URL, README (capped), languages, the same file tree, and the contents of the selected files (within budget). It returns strict JSON with `summary`, `technologies`, and `structure`.
- **API route** (`src/routes.py`):
  - Validates the URL; caps README at 30k characters; enforces a 150k-character total budget for file contents (fetched in parallel, then trimmed in priority order).
  - Handles GitHub and LLM errors with appropriate status codes.
  - Returns a `SummarizeResponse` with `summary`, `technologies`, and `structure` (and optionally `llm_input` when `?debug=true`).
