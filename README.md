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
  - Renders the tree as a sorted list of paths with sizes (up to 1000 entries) for the LLM.
  - After the first LLM returns file picks, validates them (blocklist, existence, per-file size cap) and returns an ordered list. The route then fetches file contents in that order until a total content budget is reached, truncating the last file if needed.
- **Two-pass LLM** (`src/llm.py`):
  - **Pass 1 (file selection)**: Receives README, languages, and the full file tree. Returns a JSON list of file paths to read, in priority order. No file contents are sent at this stage.
  - **Pass 2 (summarization)**: Receives repository URL, README (capped), languages, the same file tree, and the contents of the selected files (within budget). Returns strict JSON with `summary`, `technologies`, and `structure`.
- **API route** (`src/routes.py`):
  - Validates the URL; caps README at 30k characters; enforces a 200k-character total budget for file contents when fetching.
  - Handles GitHub and LLM errors with appropriate status codes.
  - Returns a `SummarizeResponse` with `summary`, `technologies`, and `structure` (and optionally `llm_input` when `?debug=true`).

## Approach and Choices

I used the OpenAI API and chose `gpt-5-mini` for strong performance and a 400k-token context window at reasonable cost.

**Repository content strategy:**

- **Always include** (for both LLM passes where relevant):
  - The README, truncated to 30k characters if longer.
  - Language statistics (JSON).
  - The repository file tree (paths + sizes), up to 1000 entries so the first LLM can see large repos.
- **File selection** (relevance, not a fixed count):
  - The first LLM chooses which files to read from the tree, in priority order (entry points, config, key modules; no README, lock files, or generated code).
  - We validate picks: blocklist (e.g. `node_modules/`, lock files, binaries, `.git/`, `dist/`, `build/`), must exist in tree, each file ≤ 50 KB.
  - We fetch files in the LLM’s order until a **total content budget** (200k characters) is hit; the last file may be truncated. So we can include many small files or fewer large ones without a fixed file limit.
- **Context management**:
  - Tree and README caps plus the content budget keep the summarization prompt within bounds.
  - The API response schema is fixed: `summary`, `technologies`, `structure` (and `llm_input` only in debug mode).