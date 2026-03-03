## git-repo-summarizer

Simple service that takes a public GitHub repository URL and returns a human‑readable summary of:

- What the project does
- The main technologies used
- The basic project structure

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
git clone <this-repo-url>
cd git-repo-summarizer
```

2. **Create a `.env` file**

In the project root:

```bash
echo OPENAI_API_KEY=sk-... > .env
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

Streamlit will print a URL (typically `http://localhost:8501`). Open it in your browser.

In the UI:

- Enter a public GitHub repo URL (e.g. `https://github.com/psf/requests`)
- Click **Summarize**
- The summary, technologies, and structure will appear below the button.

## How it works (high level)

- **Input**: `github_url` pointing to a public GitHub repository.
- **GitHub client** (`src/github_client.py`):
  - Parses the URL into `(owner, repo)`.
  - Calls the GitHub API to fetch the repository README.
- **LLM summarizer** (`src/llm.py`):
  - Sends the repo URL + README content to the OpenAI API with a structured prompt.
  - Expects JSON with `summary`, `technologies`, and `structure`.
  - The example uses `gpt-5-mini` for a good balance between cost and quality. You can change the model name in `src/llm.py` if you prefer a different model.
- **API route** (`src/routes.py`):
  - Validates the URL and handles GitHub / LLM errors.
  - Returns a `SummarizeResponse` object in the format defined in `requirements.md`.

Currently, the context sent to the LLM is just the README; more advanced repo processing (e.g., sampling source files, configs, directory trees) can be added on top of this basic flow.