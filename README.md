# 🔬 ArXiv Research Agent

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/badge/LangGraph-ReAct-purple?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Groq-llama--3.3--70b-orange?style=for-the-badge" />
  <img src="https://img.shields.io/badge/ChromaDB-Vector_Store-green?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Streamlit-UI-red?style=for-the-badge&logo=streamlit" />
</p>

> **Agentic RAG system** that lets you chat with AI/ML research papers using LangGraph ReAct agents, Groq LLM, and ChromaDB vector store.

---

## ✨ Features

- 🤖 **Agentic RAG** — LangGraph ReAct agent decides *when* and *how* to retrieve context
- ⚡ **Groq LLM** — Sub-second inference with `llama-3.3-70b-versatile`
- 🗄️ **ChromaDB** — Persistent local vector store with cosine similarity search
- 📄 **PDF Ingestion** — Upload any research paper and chat with it instantly
- 🧠 **Local Embeddings** — `all-MiniLM-L6-v2` via sentence-transformers (no API cost)
- 🌐 **FastAPI Backend** — REST API with `/query`, `/ingest`, `/papers` endpoints
- 💬 **Streamlit UI** — Clean chat interface with source citations

---

## 🏗️ Architecture

```
User Query
    │
    ▼
Streamlit UI (app.py)
    │
    ▼
LangGraph ReAct Agent (agent.py)
    │
    ├── [Tool: retrieve_context] → ChromaDB semantic search
    │                                    │
    │                              sentence-transformers
    │                              (all-MiniLM-L6-v2 embeddings)
    │
    └── [Tool: list_papers] → List available papers
    │
    ▼
Groq LLM (llama-3.3-70b-versatile)
    │
    ▼
Answer + Citations
```

---

## 🚀 Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/YOUR_USERNAME/arxiv-research-agent.git
cd arxiv-research-agent
uv sync   # or: pip install -e .
```

### 2. Set API Key
```bash
# Create .env file
echo "GROQ_API_KEY=your_key_here" > .env
```
Get your free key at [console.groq.com](https://console.groq.com)

### 3. Add Papers
Put PDF files in `data/papers/` folder.

### 4. Run
```bash
# Standalone Streamlit (recommended)
uv run streamlit run app.py

# OR: FastAPI + Streamlit (2 terminals)
uv run python src/api.py          # Terminal 1
uv run streamlit run app.py       # Terminal 2
```

### 5. Ingest Papers
Click **"Ingest from data/papers/"** in the sidebar → start chatting!

---

## 🐳 Run with Docker (Recommended for Production)

No need to install Python or any dependencies manually.

```bash
# 1. Build and start both services
docker-compose up --build

# 2. Open browser
# Streamlit UI  → http://localhost:8501
# FastAPI docs  → http://localhost:8000/docs

# 3. Stop everything
docker-compose down
```

> Make sure `.env` file with `GROQ_API_KEY` is in the project root.

---

## 📁 Project Structure

```
arxiv-research-agent/
├── app.py              # Streamlit UI (standalone)
├── pyproject.toml      # Dependencies (uv)
├── data/
│   └── papers/         # Put your PDFs here
└── src/
    ├── agent.py         # LangGraph ReAct agent
    ├── tools.py         # Agent tools (retrieve, list)
    ├── vectorstore.py   # ChromaDB wrapper
    ├── ingestion.py     # PDF → chunks → embeddings
    └── api.py           # FastAPI REST backend
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Groq — llama-3.3-70b-versatile |
| Agent Framework | LangGraph (ReAct pattern) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Vector Store | ChromaDB (persistent) |
| PDF Parsing | pypdf |
| Backend API | FastAPI + Uvicorn |
| Frontend | Streamlit |
| Package Manager | uv |

---

## 📜 Sample Papers Included

- **Attention Is All You Need** (Transformers, 2017)
- **BERT** — Pre-training of Deep Bidirectional Transformers
- **GPT** — Language Models are Few-Shot Learners
- **Denoising Diffusion Probabilistic Models**

## 📸 SnapShot
<img width="1919" height="1036" alt="image" src="https://github.com/user-attachments/assets/6f131a87-9e23-4e23-b7ef-1fd30fe0584c" />

---

## 📄 License

MIT License — feel free to use and modify.

## 🌐 Live Demo
👉 https://arxiv-research-agent-vcsa8qizikqspclkfjzvcm.streamlit.app/
