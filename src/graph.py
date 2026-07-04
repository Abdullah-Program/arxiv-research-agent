"""
graph.py — Explicit LangGraph StateGraph for self-correcting Agentic RAG.

Replaces agent.py's create_react_agent (ReAct tool-calling loop) with an
explicit graph so each decision point — route / grade / rewrite /
hallucination-check — is a visible, independently testable node instead of
being buried inside the agent's tool-calling loop. This also unlocks
node-by-node event streaming for the SSE endpoint planned in NEXT STEPS.

Pipeline
--------

    START
      |
      v
   router --------------------------+
      | needs_rag=True              | needs_rag=False
      v                              v
  retriever                   generate_direct
      |                              |
      v                              v
   grader                           END
      | relevant     | irrelevant
      v              v
  generator        rewriter --(loop back)--> retriever
      |
      v
  halucheck
      | grounded          | hallucinated
      v                    v
     END                rewriter --(loop back)--> retriever

Retry safety: `retry_count` is incremented exactly once per pass through
`rewriter`, whether triggered by the grader or by halucheck. Both
conditional edges check `retry_count >= MAX_RETRIES` and fall through to a
terminal path instead of looping again, so the graph is guaranteed to
terminate within a bounded number of steps.

Interfaces this file depends on (unchanged, kept as-is):
    vectorstore.get_vectorstore() -> VectorStore
        .semantic_search(query, top_k=5) -> List[Dict] with keys:
            content, metadata ({"source_file", "page", ...}), similarity_score
        .count() -> int

    tools.py's ingest_papers_tool / list_papers_tool are NOT imported here —
    per the brief they stay outside the graph as standalone utilities used
    by api.py's /ingest and /papers routes.
"""

import os
import sys
from pathlib import Path
from typing import List, Literal

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

# ── Load env + fix path (mirrors agent.py) ───────────────────────────────────
load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from state import RAGState
from vectorstore import get_vectorstore


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MAX_RETRIES = 2
TOP_K = 5

# Cheap/fast model for structured yes/no-ish decisions (router, grader,
# hallucination check). The larger model is reserved for actual answer
# generation. Splitting these saves latency and Groq free-tier rate limits,
# since the 8b model has far more headroom than the 70b model.
ROUTER_MODEL = os.environ.get("ROUTER_MODEL", "llama-3.1-8b-instant")
GENERATOR_MODEL = os.environ.get("GENERATOR_MODEL", "llama-3.3-70b-versatile")


def _require_api_key() -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in .env file")
    return api_key


def _router_llm(temperature: float = 0.0) -> ChatGroq:
    return ChatGroq(model=ROUTER_MODEL, temperature=temperature, api_key=_require_api_key())


def _generator_llm(temperature: float = 0.1) -> ChatGroq:
    return ChatGroq(
        model=GENERATOR_MODEL, temperature=temperature, max_tokens=2048, api_key=_require_api_key()
    )


# ---------------------------------------------------------------------------
# Structured-output schemas for the "cheap decision" nodes. Using
# with_structured_output keeps router/grader/halucheck deterministic and
# easy to branch on, instead of parsing free-text yes/no answers.
# ---------------------------------------------------------------------------

class RouteDecision(BaseModel):
    needs_rag: bool = Field(
        description=(
            "True if answering the query requires looking up information in "
            "the ingested arxiv paper knowledge base. False if it's a "
            "greeting, small talk, general knowledge, or a question about "
            "how to use the assistant itself."
        )
    )


class GradeDecision(BaseModel):
    grade: Literal["relevant", "irrelevant"] = Field(
        description=(
            "'relevant' if the retrieved documents contain information that "
            "helps answer the query, 'irrelevant' if they're empty, "
            "off-topic, or too vague."
        )
    )


class HallucinationDecision(BaseModel):
    verdict: Literal["grounded", "hallucinated"] = Field(
        description=(
            "'grounded' if every factual claim in the answer is supported by "
            "the provided documents, 'hallucinated' if the answer makes "
            "claims not present in or contradicted by the documents."
        )
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_context(documents: List[dict]) -> str:
    """Render retrieved chunks the same way tools.py's retrieve_context_tool
    did, so prompts/citations look identical to the pre-graph behavior."""
    if not documents:
        return "(no documents retrieved)"
    blocks = []
    for d in documents:
        blocks.append(f"[Source: {d['source']} | Page: {d['page']}]\n{d['content']}")
    return "\n\n---\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def router_node(state: RAGState) -> dict:
    """Decide whether the query needs retrieval at all."""
    llm = _router_llm().with_structured_output(RouteDecision)
    decision: RouteDecision = llm.invoke(
        [
            (
                "system",
                "You are a routing classifier for an arxiv research "
                "assistant. Decide if the user's question requires "
                "searching a knowledge base of ingested arxiv papers, or "
                "if it can be answered directly (e.g. greetings, general "
                "knowledge, math, or questions about how to use the "
                "assistant).",
            ),
            ("user", state["original_query"]),
        ]
    )
    return {
        "query": state["original_query"],
        "needs_rag": decision.needs_rag,
        "retry_count": 0,
    }


def retrieve_node(state: RAGState) -> dict:
    """Pull candidate chunks from ChromaDB for the current query."""
    vs = get_vectorstore()
    if vs.count() == 0:
        return {"documents": []}

    results = vs.semantic_search(state["query"], top_k=TOP_K)
    documents = [
        {
            "content": r["content"],
            "source": r["metadata"].get("source_file", "unknown"),
            "page": r["metadata"].get("page", "?"),
            "score": r["similarity_score"],
        }
        for r in results
    ]
    return {"documents": documents}


def grade_node(state: RAGState) -> dict:
    """Grade whether the retrieved documents actually address the query."""
    llm = _router_llm().with_structured_output(GradeDecision)
    context = _format_context(state.get("documents", []))
    decision: GradeDecision = llm.invoke(
        [
            (
                "system",
                "You grade retrieved documents for relevance to a query. "
                "Respond 'irrelevant' if the documents are empty, off-topic, "
                "or too vague to answer the query.",
            ),
            ("user", f"Query: {state['query']}\n\nDocuments:\n{context}"),
        ]
    )
    return {"grade": decision.grade}


def rewrite_node(state: RAGState) -> dict:
    """Rewrite the query for better retrieval, informed by the original intent."""
    llm = _router_llm(temperature=0.3)
    response = llm.invoke(
        [
            (
                "system",
                "You rewrite search queries to improve retrieval from an "
                "arxiv paper vector database. The previous query either "
                "failed to retrieve relevant results, or the resulting "
                "answer wasn't well-grounded. Produce a single improved "
                "query — more specific, with better keywords/terminology. "
                "Respond with ONLY the rewritten query, no explanation.",
            ),
            (
                "user",
                f"Original question: {state['original_query']}\n"
                f"Last query tried: {state['query']}",
            ),
        ]
    )
    new_query = response.content.strip()
    return {
        "query": new_query,
        "retry_count": state.get("retry_count", 0) + 1,
    }


def generate_node(state: RAGState) -> dict:
    """Generate a grounded answer from the retrieved (and graded) documents."""
    llm = _generator_llm()
    context = _format_context(state.get("documents", []))
    response = llm.invoke(
        [
            (
                "system",
                "You are an expert AI research assistant specializing in "
                "machine learning and AI papers. Answer the user's question "
                "using ONLY the information in the provided documents. Cite "
                "sources like: (Source: paper_name.pdf, Page X). If the "
                "documents don't fully answer the question, say so plainly "
                "rather than filling gaps with outside knowledge. Be "
                "concise but thorough.",
            ),
            (
                "user",
                f"Question: {state['original_query']}\n\nDocuments:\n{context}",
            ),
        ]
    )
    return {"answer": response.content}


def generate_direct_node(state: RAGState) -> dict:
    """Answer directly, without retrieval, for queries the router deemed non-RAG."""
    llm = _generator_llm()
    response = llm.invoke(
        [
            (
                "system",
                "You are an expert AI research assistant. Answer the user's "
                "question directly and concisely; no document lookup was "
                "needed for this one.",
            ),
            ("user", state["original_query"]),
        ]
    )
    return {"answer": response.content, "hallucination_check": "not_applicable"}


def halucheck_node(state: RAGState) -> dict:
    """Check whether the generated answer is actually grounded in the documents."""
    llm = _router_llm().with_structured_output(HallucinationDecision)
    context = _format_context(state.get("documents", []))
    decision: HallucinationDecision = llm.invoke(
        [
            (
                "system",
                "You check whether an answer is fully supported by the "
                "given documents. Flag 'hallucinated' if the answer "
                "contains claims the documents don't support.",
            ),
            (
                "user",
                f"Documents:\n{context}\n\nAnswer to check:\n{state['answer']}",
            ),
        ]
    )
    return {"hallucination_check": decision.verdict}


# ---------------------------------------------------------------------------
# Conditional edge routers
# ---------------------------------------------------------------------------

def route_after_router(state: RAGState) -> str:
    return "retriever" if state.get("needs_rag") else "generate_direct"


def route_after_grade(state: RAGState) -> str:
    if state.get("grade") == "relevant":
        return "generator"
    if state.get("retry_count", 0) >= MAX_RETRIES:
        # Out of retries: proceed with best-effort generation instead of
        # looping forever. halucheck downstream will still flag a bad answer.
        return "generator"
    return "rewriter"


def route_after_halucheck(state: RAGState) -> str:
    if state.get("hallucination_check") in ("grounded", "not_applicable"):
        return "end"
    if state.get("retry_count", 0) >= MAX_RETRIES:
        # Out of retries: return the (possibly imperfect) answer rather than
        # looping forever.
        return "end"
    return "rewriter"


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_graph():
    builder = StateGraph(RAGState)

    builder.add_node("router", router_node)
    builder.add_node("retriever", retrieve_node)
    builder.add_node("grader", grade_node)
    builder.add_node("rewriter", rewrite_node)
    builder.add_node("generator", generate_node)
    builder.add_node("generate_direct", generate_direct_node)
    builder.add_node("halucheck", halucheck_node)

    builder.add_edge(START, "router")

    builder.add_conditional_edges(
        "router",
        route_after_router,
        {"retriever": "retriever", "generate_direct": "generate_direct"},
    )

    builder.add_edge("retriever", "grader")

    builder.add_conditional_edges(
        "grader",
        route_after_grade,
        {"generator": "generator", "rewriter": "rewriter"},
    )

    builder.add_edge("rewriter", "retriever")

    builder.add_edge("generator", "halucheck")

    builder.add_conditional_edges(
        "halucheck",
        route_after_halucheck,
        {"end": END, "rewriter": "rewriter"},
    )

    builder.add_edge("generate_direct", END)

    return builder.compile()


graph = build_graph()


# ---------------------------------------------------------------------------
# ask_graph() — drop-in replacement for agent.py's ask_agent(), so api.py
# needs a one-line swap: `from agent import ask_agent` -> `from graph import ask_graph as ask_agent`
# ---------------------------------------------------------------------------

def ask_graph(query: str, chat_history: list = None) -> dict:
    """
    Run the graph for a single query and return the same shape api.py
    already expects from agent.ask_agent(): {"answer", "sources", "steps"}.

    chat_history is accepted for signature compatibility with ask_agent but
    is not yet threaded into RAGState — multi-turn context is a follow-on
    enhancement, not part of this graph conversion.
    """
    initial_state: RAGState = {"original_query": query}

    final_state = initial_state
    steps = 0
    for event in graph.stream(initial_state, stream_mode="updates"):
        for _node_name, update in event.items():
            steps += 1
            final_state = {**final_state, **update}

    documents = final_state.get("documents", [])
    sources = sorted({f"{d['source']}" for d in documents})

    return {
        "answer": final_state.get("answer", ""),
        "sources": sources,
        "steps": steps,
    }


# ---------------------------------------------------------------------------
# Standalone terminal test (NEXT STEPS item 1)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "What is the attention mechanism in transformers?"

    initial_state: RAGState = {"original_query": query}

    print(f"\n=== Query: {query} ===\n")
    for event in graph.stream(initial_state, stream_mode="updates"):
        for node_name, update in event.items():
            print(f"--- node: {node_name} ---")
            for k, v in update.items():
                preview = str(v)
                if len(preview) > 300:
                    preview = preview[:300] + "... [truncated]"
                print(f"  {k}: {preview}")
            print()
