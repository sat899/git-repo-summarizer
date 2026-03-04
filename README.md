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
  -d '{"github_url": "https://github.com/psf/requests"}'
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
  - Calls the GitHub API to fetch:
    - Repository metadata (`/repos/{owner}/{repo}`).
    - Language breakdown (`/repos/{owner}/{repo}/languages`).
    - The README (`/repos/{owner}/{repo}/readme`).
    - The full Git tree for the default branch (`/git/trees/{sha}?recursive=1`).
  - Selects a small sample of representative text/code files from the tree and fetches their contents using the Contents API.
- **LLM summarizer** (`src/llm.py`):
  - Builds a single prompt containing:
    - The repository URL.
    - README content.
    - Repository metadata (pretty‑printed JSON).
    - Repository languages (pretty‑printed JSON).
    - A few sampled files (each prefixed with `FILE: path` followed by its contents).
  - Sends this prompt to the OpenAI API and expects strict JSON with `summary`, `technologies`, and `structure`.
- **API route** (`src/routes.py`):
  - Validates the URL and handles GitHub / LLM errors.
  - Orchestrates GitHub data fetch + context building + LLM call.
  - Returns a `SummarizeResponse` object containing only `summary`, `technologies`, and `structure`.

## Approach and Choices

I used the OpenAI API since I already had credits. I chose `gpt-5-mini` since it offers strong performance, including the ability to set its reasoning level, at a reasonable cost.

For repository contents, the current strategy is:

- **Always include**:
  - The README, if present (primary high‑level description).
  - Basic repository metadata (description, default branch, stars, topics, etc.).
  - Language statistics to help the model infer the tech stack.
- **Sample additional files** from the Git tree:
  - Only regular files (`type == "blob"`).
  - Skip obviously noisy paths such as `node_modules/`, `.git/`, `.github/`, `dist/`, `build/`, `__pycache__/`, and `.venv/`.
  - Skip very large files (currently > 20 KB) to avoid blowing up context.
  - Only consider common text / code extensions (`.py`, `.md`, `.rst`, `.txt`, `.js`, `.ts`).
  - Take up to a small fixed number of files (currently 5) as a simple first‑pass heuristic.
- **Context management**:
  - All of the above (README, metadata, languages, sampled files) are concatenated into a single prompt string.
  - The response schema remains fixed: the API only returns `summary`, `technologies`, and `structure`, even though the LLM sees richer context.