"""
api.py
------
FastAPI backend for ArXiv Research Agent.

Endpoints:
    POST /ingest        - Ingest all PDFs from data/papers/
    POST /ingest/upload - Upload and ingest a single PDF
    POST /query         - Ask a question to the agent
    GET  /papers        - List all ingested papers
    GET  /health        - Health check
"""

import sys
import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# ── Path fix ──────────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from ingestion import ingest_pdfs, ingest_single_pdf, PAPERS_DIR
from vectorstore import get_vectorstore
from agent import ask_agent


# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="ArXiv Research Agent API",
    description="Agentic RAG system for AI/ML research papers",
    version="1.0.0",
)

# Allow Streamlit to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response Models ─────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = 5

class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    steps: int
    question: str

class IngestResponse(BaseModel):
    message: str
    papers: list[str]
    total_chunks: int


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    vs = get_vectorstore()
    return {
        "status": "ok",
        "chunks_in_db": vs.count(),
        "papers": vs.list_papers(),
    }


@app.get("/papers")
def list_papers():
    """List all ingested papers in the knowledge base."""
    vs = get_vectorstore()
    papers = vs.list_papers()
    return {
        "papers": papers,
        "count": len(papers),
        "total_chunks": vs.count(),
    }


@app.post("/ingest", response_model=IngestResponse)
def ingest_all_papers():
    """
    Ingest all PDFs from data/papers/ folder.
    Call this once after adding new PDFs.
    """
    try:
        vs     = get_vectorstore()
        chunks, embeddings = ingest_pdfs(PAPERS_DIR)

        if not chunks:
            raise HTTPException(
                status_code=400,
                detail=f"No PDFs found in {PAPERS_DIR}. Add PDFs first."
            )

        vs.add_documents(chunks, embeddings)
        papers = vs.list_papers()

        return IngestResponse(
            message=f"Successfully ingested {len(chunks)} chunks from {len(papers)} papers",
            papers=papers,
            total_chunks=vs.count(),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/upload", response_model=IngestResponse)
async def upload_and_ingest(file: UploadFile = File(...)):
    """
    Upload a single PDF and ingest it into the knowledge base.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

    try:
        # Save uploaded file to papers directory
        PAPERS_DIR.mkdir(parents=True, exist_ok=True)
        save_path = PAPERS_DIR / file.filename

        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Ingest the single PDF
        vs = get_vectorstore()
        chunks, embeddings = ingest_single_pdf(save_path)
        vs.add_documents(chunks, embeddings)

        papers = vs.list_papers()

        return IngestResponse(
            message=f"Uploaded and ingested '{file.filename}' with {len(chunks)} chunks",
            papers=papers,
            total_chunks=vs.count(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=QueryResponse)
def query_agent(request: QueryRequest):
    """
    Ask a question — agent retrieves context and answers using Groq LLM.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        vs = get_vectorstore()
        if vs.count() == 0:
            raise HTTPException(
                status_code=400,
                detail="Knowledge base is empty. Please ingest papers first via POST /ingest"
            )

        result = ask_agent(request.question)

        return QueryResponse(
            answer=result["answer"],
            sources=result["sources"],
            steps=result["steps"],
            question=request.question,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Run directly ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)