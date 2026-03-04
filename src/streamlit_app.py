import httpx
import streamlit as st

API_URL = "http://localhost:8000/summarize"

st.set_page_config(page_title="Git Repo Summarizer", layout="centered")
st.title("Git Repository Summarizer")
st.write(
    "Enter the URL of a public GitHub repository and get a brief summary of "
    "what it does, the technologies it uses, and its structure."
)

github_url = st.text_input(
    "GitHub repository URL",
    placeholder="https://github.com/psf/requests",
)

summarize_clicked = st.button("Summarize")

if summarize_clicked:
    if not github_url:
        st.warning("Please enter a GitHub repository URL.")
    else:
        with st.spinner("Summarizing repository..."):
            try:
                response = httpx.post(API_URL, json={"github_url": github_url}, timeout=60)
            except httpx.RequestError as exc:
                st.error(f"Could not reach the API: {exc}")
            else:
                if response.status_code != 200:
                    try:
                        data = response.json()
                        message = data.get("detail") or data.get("message") or str(data)
                    except Exception:
                        message = response.text
                    st.error(f"API error ({response.status_code}): {message}")
                else:
                    data = response.json()

                    st.subheader("Summary")
                    st.write(data.get("summary", ""))

                    technologies = data.get("technologies") or []
                    if technologies:
                        st.subheader("Technologies")
                        st.write(", ".join(technologies))

                    structure = data.get("structure", "")
                    if structure:
                        st.subheader("Structure")
                        st.write(structure)