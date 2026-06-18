"""
app.py
------
Streamlit UI for ArXiv Research Agent.
Standalone mode — calls agent directly (no FastAPI needed).
Can also talk to FastAPI backend if API_URL is set and running.

Deploy on Streamlit Cloud:  https://share.streamlit.io
Set GROQ_API_KEY in Streamlit Cloud → Settings → Secrets
"""

import sys
import os
from pathlib import Path

import streamlit as st

# ── Path fix for imports ──────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
SRC  = ROOT / "src"
sys.path.insert(0, str(SRC))

# Load .env if running locally
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# ── Config ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ArXiv Research Agent",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .main-header {
        font-size: 2.6rem;
        font-weight: 800;
        background: linear-gradient(135deg, #ffffff 0%, #a78bfa 50%, #60a5fa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.2rem;
        letter-spacing: -0.5px;
    }
    .sub-header {
        color: #94a3b8;
        font-size: 1rem;
        margin-bottom: 2rem;
        letter-spacing: 0.3px;
    }
    .source-tag {
        background: rgba(96, 165, 250, 0.15);
        color: #93c5fd;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.82rem;
        margin-right: 6px;
        display: inline-block;
        border: 1px solid rgba(96, 165, 250, 0.3);
    }
    .step-tag {
        background: rgba(251, 191, 36, 0.12);
        color: #fbbf24;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.82rem;
        border: 1px solid rgba(251, 191, 36, 0.25);
    }
    .stChatMessage {
        border-radius: 12px;
    }
</style>
""", unsafe_allow_html=True)


# ── Lazy-load agent (only when needed, keeps startup fast) ────────────────────
@st.cache_resource(show_spinner="Loading AI models...")
def load_agent_components():
    """Load vectorstore + embedding model once. Cached across sessions."""
    from vectorstore import get_vectorstore
    vs = get_vectorstore()
    return vs


def run_agent_query(question: str):
    """Run the LangGraph agent and return result dict."""
    from agent import ask_agent
    return ask_agent(question)


def do_ingest(papers_dir=None):
    """Run ingestion pipeline and store into vectorstore."""
    from ingestion import ingest_pdfs, PAPERS_DIR
    from vectorstore import get_vectorstore
    directory = papers_dir or PAPERS_DIR
    vs = get_vectorstore()
    chunks, embeddings = ingest_pdfs(directory)
    if not chunks:
        return None, "No PDFs found. Add PDFs to data/papers/ folder."
    vs.add_documents(chunks, embeddings)
    return vs.list_papers(), f"Ingested {len(chunks)} chunks from {len(vs.list_papers())} papers"


def do_upload_ingest(uploaded_file):
    """Save uploaded PDF and ingest it."""
    import shutil
    from ingestion import ingest_single_pdf, PAPERS_DIR
    from vectorstore import get_vectorstore

    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    save_path = PAPERS_DIR / uploaded_file.name
    with open(save_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    vs = get_vectorstore()
    chunks, embeddings = ingest_single_pdf(save_path)
    vs.add_documents(chunks, embeddings)
    return vs.list_papers(), f"Uploaded & ingested '{uploaded_file.name}' ({len(chunks)} chunks)"


# ── Initialize session state ──────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<p class="main-header">🔬 ArXiv Research Agent</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Agentic RAG · LangGraph · Groq · ChromaDB</p>', unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("📚 Knowledge Base")

    # Check API key
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        st.error("❌ GROQ_API_KEY not set!\n\nAdd it to `.env` file or Streamlit Cloud secrets.")
        st.stop()
    else:
        st.success("✅ Groq API connected")

    # Load vectorstore + show stats
    try:
        vs = load_agent_components()
        count = vs.count()
        papers = vs.list_papers()

        st.metric("Chunks in DB", count)

        if papers:
            st.markdown(f"**{len(papers)} Papers:**")
            for p in papers:
                st.markdown(f"• `{p}`")
        else:
            st.info("No papers yet. Ingest below ↓")

    except Exception as e:
        st.error(f"Vectorstore error: {e}")
        st.stop()

    st.divider()

    # Ingest from data/papers/
    st.subheader("⚡ Ingest Papers")
    if st.button("Ingest from data/papers/", use_container_width=True):
        with st.spinner("Ingesting papers... (first run downloads model)"):
            try:
                papers, msg = do_ingest()
                if papers is None:
                    st.error(msg)
                else:
                    st.success(msg)
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    # Upload a PDF
    st.subheader("📤 Upload PDF")
    uploaded = st.file_uploader("Upload a PDF", type=["pdf"])
    if uploaded and st.button("Upload & Ingest", use_container_width=True):
        with st.spinner(f"Uploading {uploaded.name}..."):
            try:
                papers, msg = do_upload_ingest(uploaded)
                st.success(msg)
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()
    if st.button("🗑 Clear Chat", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

    st.divider()
    st.caption("Built with LangGraph · Groq · ChromaDB")
    st.caption("Model: llama-3.3-70b-versatile")


# ── Main Chat UI ──────────────────────────────────────────────────────────────
st.subheader("💬 Ask the Research Agent")

# Guard: need papers in DB
if vs.count() == 0:
    st.warning("⚠️ Knowledge base is empty. Please ingest papers using the sidebar first.")
    st.stop()

# Show chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("sources"):
            cols = st.columns([3, 1])
            with cols[0]:
                for src in msg["sources"]:
                    st.markdown(f'<span class="source-tag">📄 {src}</span>', unsafe_allow_html=True)
            with cols[1]:
                st.markdown(
                    f'<span class="step-tag">🔧 {msg.get("steps", 0)} tool call(s)</span>',
                    unsafe_allow_html=True,
                )

# Chat input
question = st.chat_input("Ask about the research papers...")

if question:
    st.session_state.chat_history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Agent thinking..."):
            try:
                result = run_agent_query(question)
                answer  = result.get("answer", "No answer")
                sources = result.get("sources", [])
                steps   = result.get("steps", 0)

                st.markdown(answer)

                if sources:
                    st.markdown("**Sources:**")
                    for src in sources:
                        st.markdown(f'<span class="source-tag">📄 {src}</span>', unsafe_allow_html=True)
                st.markdown(
                    f'<span class="step-tag">🔧 {steps} tool call(s)</span>',
                    unsafe_allow_html=True,
                )

                st.session_state.chat_history.append({
                    "role":    "assistant",
                    "content": answer,
                    "sources": sources,
                    "steps":   steps,
                })

            except Exception as e:
                err_msg = str(e)
                st.error(f"Agent error: {err_msg}")