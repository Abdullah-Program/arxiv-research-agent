<div align="center">

# ⬡ ResearchForge AI
### Self-Correcting Agentic RAG for AI/ML Research Papers

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-8_nodes-FF6B6B?style=flat-square)](https://langchain-ai.github.io/langgraph/)
[![Groq](https://img.shields.io/badge/Groq-70B_LLM-F55036?style=flat-square)](https://groq.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react)](https://react.dev)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_DB-FF6B35?style=flat-square)](https://trychroma.com)

**This is NOT a simple chatbot. It's an autonomous agent that verifies its own answers.**

</div>

---

## 🧠 What Makes This "Agentic"

Most RAG apps: `Query → Retrieve → Generate → Answer` *(fixed pipeline, no self-correction)*

ResearchForge AI:
```
Query
  │
  ▼
[ROUTER] ── "is this a comparison?" ──► [COMPARE_NODE] ──► Table Answer
  │ needs retrieval
  ▼
[RETRIEVER] ── Hybrid Search (BM25 + Dense Vectors + RRF Fusion)
  │
  ▼
[GRADER] ── "are these docs actually relevant?"
  │ NO ──► [REWRITER] ── improves query ──► retry (max 2x)
  │ YES
  ▼
[GENERATOR] ── llama-3.3-70b ── answer + Mermaid diagram + follow-up questions
  │
  ▼
[HALUCHECK] ── "is the answer grounded in the docs?"
  │ HALLUCINATED ──► [REWRITER] ──► retry
  │ GROUNDED
  ▼
Answer ✓ + Confidence Score
```

**3 autonomous decision nodes + self-correcting retry loop = Agentic RAG**

---

## ✨ Features

| Backend | Frontend |
|---|---|
| 8-node LangGraph StateGraph | Cyberpunk 3-panel UI (Sidebar + Chat + Pipeline) |
| Hybrid Search (BM25 + Dense + RRF) | Live pipeline trace — nodes glow in real-time |
| Hallucination detection | Citation drawer — exact source chunks with score bars |
| Confidence score (0-100%) | Mermaid.js architecture diagrams auto-render |
| Auto Mermaid diagram generation | Follow-up question chips |
| Follow-up question generation | Grounding score SVG ring |
| Comparison mode (X vs Y → table) | Node timing (+0ms, +312ms, ...) |
| ArXiv auto-fetch ("fetch arxiv 1706.03762") | Dual model badge (70B ★ on generator) |
| Session history (SQLite) | Analytics dashboard (KPI cards, charts) |
| Analytics tracking | Chat history with session management |
| Node observability (prompt/input/output/latency) | Export session as JSON |

---

## 🚀 Quick Start

### 1. Clone & Setup
```bash
git clone https://github.com/YOUR_USERNAME/researchforge-ai
cd researchforge-ai
echo "GROQ_API_KEY=gsk_your_key_here" > .env
```
Get free API key at [console.groq.com](https://console.groq.com)

### 2. Install
```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

### 3. Run (Windows)
```bash
# Double-click start.bat
# OR:
start.bat
```
Opens 2 terminals + browser automatically.

### 4. Manual
```bash
# Terminal 1
cd src && python api.py        # → http://localhost:8000

# Terminal 2
cd frontend && npm run dev     # → http://localhost:5173
```

### 5. Docker
```bash
docker-compose up --build
```

### 6. Ingest Papers
- Go to **Documents** page → drag-drop any PDF
- OR click `INGEST_ALL` (ingests from `data/papers/`)
- OR chat: `fetch arxiv 1706.03762` (auto-downloads from arXiv)

---

## 💬 Try These Queries

```
"Explain the attention mechanism in transformers"     → Full RAG + citations
"Compare BERT vs GPT architecture"                    → Comparison table
"Explain the architecture of BERT"                    → RAG + Mermaid diagram
"fetch arxiv 2005.11401"                              → Auto-download + ingest
"hello"                                               → Direct answer (no RAG)
```

---

## 🏗️ Architecture

```
Browser (React + Vite :5173)
  │  EventSource /query/stream  (SSE — node-by-node events)
  ▼
FastAPI (:8000)
  │
  ├── LangGraph StateGraph (8 nodes)
  │     └── Groq LLM API (8b + 70b models)
  │
  ├── ChromaDB (vector store)
  │     └── all-MiniLM-L6-v2 (embeddings)
  │
  ├── SQLite history.db   (chat sessions)
  └── SQLite analytics.db (query logs)
```

---

## 📁 Structure

```
researchforge-ai/
├── src/
│   ├── graph.py          # LangGraph 8-node pipeline (CORE)
│   ├── state.py          # RAGState TypedDict
│   ├── api.py            # FastAPI + SSE endpoints
│   ├── vectorstore.py    # ChromaDB + BM25 hybrid search
│   ├── ingestion.py      # PDF → chunks → embeddings
│   ├── history_db.py     # SQLite session persistence
│   ├── analytics_db.py   # SQLite analytics
│   └── arxiv_helper.py   # arXiv auto-fetch
├── frontend/src/
│   ├── App.jsx           # Main app + SSE handler
│   └── components/       # 9 React components
├── data/papers/          # PDF storage
├── .env                  # GROQ_API_KEY
├── start.bat             # One-click Windows launcher
└── docker-compose.yml
```

---

## 🔑 Environment

```bash
GROQ_API_KEY=gsk_...
ROUTER_MODEL=llama-3.1-8b-instant        # optional
GENERATOR_MODEL=llama-3.3-70b-versatile  # optional
```

---

## 🎨 Design System

```css
--accent: #00f0ff  /* Cyan */    --success: #00ff66  /* Green */
--purple: #ff00ff  /* Magenta */ --warning: #ffaa00  /* Amber */
--yellow: #f0ff00  /* Yellow */  --danger:  #ff0055  /* Red */
Fonts: Orbitron · Share Tech Mono · Rajdhani
```

---

<div align="center">
Built by Abdullah Haider | LangGraph + Groq + ChromaDB + React
</div>
