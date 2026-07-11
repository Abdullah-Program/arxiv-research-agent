"""
api.py
------
FastAPI backend for ArXiv Research Agent.
"""

import json
import shutil
import sys
import os
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from ingestion import ingest_pdfs, ingest_single_pdf, PAPERS_DIR
from vectorstore import get_vectorstore
from graph import ask_graph as ask_agent, graph
import history_db
import analytics_db
from ingestion import get_embedding_model

app = FastAPI(
    title="ArXiv Research Agent API",
    description="Agentic RAG system for AI/ML research papers",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def warmup_models():
    """Pre-load embedding model so first query is fast."""
    try:
        get_embedding_model()
        print("[api] Embedding model warmed up.")
    except Exception as e:
        print(f"[api] Embedding warmup skipped: {e}")


class QueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = 5
    session_id: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    steps: int
    question: str
    node_logs: Optional[dict] = None
    follow_up_questions: Optional[list] = None
    confidence_score: Optional[float] = None
    diagram: Optional[str] = None

class IngestResponse(BaseModel):
    message: str
    papers: list[str]
    total_chunks: int

class MessageInsertRequest(BaseModel):
    role: str
    text: str
    sources: Optional[list[str]] = None
    timestamp: Optional[str] = None
    node_logs: Optional[dict] = None


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
    vs = get_vectorstore()
    papers = vs.list_papers()
    return {"papers": papers, "count": len(papers), "total_chunks": vs.count()}


@app.post("/ingest", response_model=IngestResponse)
def ingest_all_papers():
    try:
        vs = get_vectorstore()
        chunks, embeddings = ingest_pdfs(PAPERS_DIR)
        if not chunks:
            raise HTTPException(status_code=400, detail=f"No PDFs found in {PAPERS_DIR}.")
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
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")
    try:
        PAPERS_DIR.mkdir(parents=True, exist_ok=True)
        save_path = PAPERS_DIR / file.filename
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
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
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        result = ask_agent(request.question)
        if request.session_id:
            import datetime
            ts = datetime.datetime.now().strftime("%I:%M:%S %p")
            history_db.add_message(request.session_id, "user", request.question, timestamp=ts)
            history_db.add_message(
                request.session_id, "ai", result["answer"],
                sources=result["sources"], timestamp=ts, node_logs=result.get("node_logs"),
            )
        return QueryResponse(
            answer=result["answer"],
            sources=result["sources"],
            steps=result["steps"],
            question=request.question,
            node_logs=result.get("node_logs"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/query/stream")
async def query_stream(question: str, session_id: Optional[str] = None):
    if not question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    # NOTE: We do NOT block on empty DB here — the retrieve_node handles it
    # by auto-fetching from arXiv when no documents are found.

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            initial_state = {"original_query": question}
            final_answer    = ""
            final_sources   = []
            final_logs      = {}
            final_follow_ups = []
            final_confidence = 0.0
            final_diagram   = ""
            final_chunks    = []
            final_retries   = 0
            needs_rag       = True

            for event in graph.stream(initial_state, stream_mode="updates"):
                for node_name, update in event.items():

                    # Extract full documents BEFORE serialize (for citation cards)
                    if "documents" in update and isinstance(update["documents"], list):
                        final_chunks = [
                            {
                                "content": d.get("content", ""),
                                "source":  d.get("source", ""),
                                "page":    d.get("page", "?"),
                                "score":   round(d.get("score", 0.0), 3),
                            }
                            for d in update["documents"]
                        ]
                        # FIX 2: populate final_sources from chunks
                        final_sources = list({c["source"] for c in final_chunks if c["source"]})

                    if "answer" in update:
                        final_answer = update["answer"]
                    if "node_logs" in update:
                        final_logs.update(update["node_logs"])
                    if "follow_up_questions" in update:
                        final_follow_ups = update["follow_up_questions"]
                    if "confidence_score" in update:
                        final_confidence = update["confidence_score"]
                    if "diagram" in update:
                        final_diagram = update["diagram"]
                    if "retry_count" in update:
                        final_retries = update["retry_count"]
                    if node_name == "router" and "needs_rag" in update:
                        needs_rag = bool(update["needs_rag"])

                    payload = _serialize_update(node_name, update)
                    yield f"data: {json.dumps(payload)}\n\n"

            # Final enriched event — includes arxiv_status for auto-fetch banner
            retriever_prompt  = final_logs.get("retriever", {}).get("prompt", "")
            fallback_output   = final_logs.get("arxiv_fallback", {}).get("output", "")
            arxiv_fetched = (
                "Successfully downloaded" in retriever_prompt or
                "Successfully downloaded" in fallback_output
            )
            yield f"data: {json.dumps({'node': '__result__', 'data': {'follow_up_questions': final_follow_ups, 'confidence_score': round(final_confidence, 3), 'diagram': final_diagram, 'chunks': final_chunks, 'arxiv_fetched': arxiv_fetched, 'sources': final_sources}})}\n\n"

            # Analytics logging — FIX 3: robust parsing with json.loads fallback
            try:
                grade_raw = final_logs.get("grader", {}).get("output", "")
                try:
                    grade_parsed = json.loads(grade_raw)
                    grade = grade_parsed.get("grade", None)
                except Exception:
                    grade = "relevant" if "relevant" in grade_raw else "irrelevant" if "irrelevant" in grade_raw else None

                halu_raw = final_logs.get("halucheck", {}).get("output", "")
                try:
                    halu_parsed = json.loads(halu_raw)
                    halu = halu_parsed.get("verdict", "not_applicable")
                except Exception:
                    halu = "grounded" if "grounded" in halu_raw else "hallucinated" if "hallucinated" in halu_raw else "not_applicable"

                analytics_db.log_query(
                    query=question,
                    grade=grade,
                    hallucination_check=halu,
                    confidence_score=final_confidence,
                    docs_found=len(final_chunks),
                    retry_count=final_retries,
                    needs_rag=needs_rag,
                )
            except Exception as ae:
                print(f"[api] Analytics log error: {ae}")

            # Save to history
            if session_id:
                try:
                    import datetime
                    ts = datetime.datetime.now().strftime("%I:%M:%S %p")
                    history_db.add_message(session_id, "user", question, timestamp=ts)
                    history_db.add_message(
                        session_id, "ai", final_answer,
                        sources=final_sources, timestamp=ts, node_logs=final_logs,
                    )
                except Exception as db_err:
                    print(f"[api] DB save error: {db_err}")

            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'node': 'error', 'data': {'message': str(e)}})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/sessions")
def get_sessions():
    return history_db.list_sessions()

@app.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: str):
    return history_db.get_session_messages(session_id)

@app.post("/sessions")
def create_new_session(title: str):
    session_id = history_db.create_session(title)
    return {"session_id": session_id}

@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    history_db.delete_session(session_id)
    return {"status": "success"}

@app.get("/analytics")
def get_analytics():
    return analytics_db.get_stats()

@app.get("/search/chunks")
def search_chunks(query: str, source: str = None, top_k: int = 5):
    try:
        vs = get_vectorstore()
        results = vs.hybrid_search(query, top_k=top_k)
        chunks = [
            {
                "content": r["content"],
                "source":  r["metadata"].get("source_file", "unknown"),
                "page":    r["metadata"].get("page", "?"),
                "score":   round(r.get("similarity_score", 0.0), 3),
            }
            for r in results
            if (source is None or r["metadata"].get("source_file", "") == source)
        ]
        return {"chunks": chunks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _serialize_update(node_name: str, update: dict) -> dict:
    safe = {}
    for k, v in update.items():
        if k == "documents" and isinstance(v, list):
            safe[k] = {
                "count":   len(v),
                "sources": list({d.get("source", "?") for d in v}),
                "preview": v[0]["content"][:120] + "..." if v else "",
            }
        elif k == "node_logs" and isinstance(v, dict):
            safe["node_log"] = v.get(node_name, {})
        elif k == "arxiv_status":
            safe["arxiv_status"] = v
        else:
            safe[k] = v
    return {"node": node_name, "data": safe}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
