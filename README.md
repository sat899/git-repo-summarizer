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
- **Two-pass LLM** (`src/llm.py`):
  - **Pass 1 (file selection)**: The first LLM selects the most relevant files from the repo tree. It receives the README, languages, and the full file tree, and returns a JSON list of file paths in priority order. We then apply deterministic filters (blocklist, must exist in tree, per-file size cap) and fetch file contents in that order until the total content budget is reached.
  - **Pass 2 (summarization)**: The second LLM is responsible for summarizing the information contained in the files selected by the first LLM and for generating a response that adheres to the required output structure. It receives the repository URL, README (capped), languages, the same file tree, and the contents of the selected files (within budget). It returns strict JSON with `summary`, `technologies`, and `structure`.
- **API route** (`src/routes.py`):
  - Validates the URL; caps README at 30k characters; enforces a 200k-character total budget for file contents when fetching, truncating the last file if needed.
  - Handles GitHub and LLM errors with appropriate status codes.
  - Returns a `SummarizeResponse` with `summary`, `technologies`, and `structure` (and optionally `llm_input` when `?debug=true`).

## Approach and Choices

I used the OpenAI API and chose `gpt-5-mini` for strong performance and a 400k-token context window at reasonable cost.

**Functionality:** The endpoint returns `summary`, `technologies`, and `structure` in strict JSON format (enforced via `response_format={"type": "json_object"}` in `src/llm.py`). The two-pass LLM design ensures the summarizer sees both high-level context (tree, README, languages) and detailed file contents chosen for relevance.

**Repository processing:** Files are filtered using a blocklist (`src/github_client.py`: `_should_skip_path`) that excludes noise (lock files, binaries, build artifacts, `node_modules/`, etc.) and a per-file size cap (50 KB). The first LLM selects files by relevance rather than a fixed heuristic, receiving the full tree (up to 1000 entries), README, and languages but no file contents. Its output is validated before fetching.

**Context management:** README is capped at 30k characters (`src/routes.py`). The tree is limited to 1000 entries (`src/github_client.py`: `format_tree_for_prompt`). File contents are accumulated up to a 200k-character budget; when reached, the last file is truncated or fetching stops. This keeps the summarization prompt within the 400k-token window while adapting to repo size (many small files or fewer large ones).

**Prompt engineering:** The file-selection LLM (`src/llm.py`: `select_files`) is instructed to prioritize entry points, config, and key modules, and to skip lock files and generated code. The summarizer (`summarize_repository`) is told to keep `structure` concise (a few lines), preventing verbose output. Both prompts enforce JSON-only responses.

**Code quality & error handling:** The codebase is modular (`src/github_client.py`, `src/llm.py`, `src/routes.py`, `src/schemas.py`) with unit tests (`tests/test_github.py`, `tests/test_llm.py`). Errors are handled with specific HTTP status codes: 400 (invalid URL), 403 (private repo or rate limit, with reset time if available), 404 (not found), 422 (empty repo), 502 (LLM/GitHub failures), 503 (network errors). API keys are read from environment variables (`.env`), never hardcoded.

**Trade-offs and challenges:** We rely entirely on the first LLM's judgment for file selection; if it picks poorly (ignoring key modules or choosing noise), the summary suffers. The blocklist and budget caps mitigate worst cases but don't guarantee optimal choice. An alternative would be single-pass with static heuristics (faster, more predictable) or multi-turn agentic exploration (flexible but complex). Latency comes from multiple sources: GitHub API calls (languages, README, tree, then individual files), followed by two sequential LLM calls. Even with async/await for the GitHub requests, they run one after another, and file fetching is done in a loop. The summarization call receives up to 200k characters of code plus tree and README, which can take several seconds even with `gpt-5-mini`'s speed.

**Future directions:** An **agentic approach** could replace the dual-LLM design: give the model tools (list directories, read files, search symbols) and let it iteratively explore until satisfied. This trades simplicity for flexibility but adds complexity (tool reliability, multi-turn cost, potential loops). For production, **structured outputs** (JSON schema enforcement) would reduce parsing fragility, and **response caching** (GitHub data, LLM selections) would cut costs and latency. Better **guardrails** (hallucination detection, rate-limit backoff, timeouts) would improve reliability. On infrastructure, **Docker/Kubernetes** with horizontal scaling and async task queues would handle load. Finally, deeper modularization (service layers, dependency injection, repository patterns) would ease testing and extension as complexity grows.