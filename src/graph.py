"""
graph.py — Explicit LangGraph StateGraph for self-correcting Agentic RAG.

Replaces agent.py's create_react_agent with an explicit graph so each
decision point (route/grade/rewrite/hallucination-check) is a visible,
independently testable node.

Pipeline:
    START → router → retriever → grader → generator → halucheck → END
                ↘ generate_direct → END        ↕ rewriter (max 2 retries)
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from state import RAGState
from vectorstore import get_vectorstore

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MAX_RETRIES = 2
TOP_K = 5

# 8b = cheap/fast for yes-no decisions | 70b = quality answers
ROUTER_MODEL    = os.environ.get("ROUTER_MODEL",    "llama-3.1-8b-instant")
GENERATOR_MODEL = os.environ.get("GENERATOR_MODEL", "llama-3.3-70b-versatile")


def _require_api_key() -> str:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise ValueError("GROQ_API_KEY not found in .env file")
    return key


def _router_llm(temperature: float = 0.0) -> ChatGroq:
    return ChatGroq(model=ROUTER_MODEL, temperature=temperature, api_key=_require_api_key())


def _generator_llm(temperature: float = 0.1) -> ChatGroq:
    return ChatGroq(model=GENERATOR_MODEL, temperature=temperature,
                    max_tokens=2048, api_key=_require_api_key())


# ---------------------------------------------------------------------------
# JSON mode helper
# llama-3.1-8b-instant is unreliable with with_structured_output() because
# it wraps fields inside a nested "parameters" key instead of root level,
# causing Groq tool-call validation errors.
# json_mode avoids the tool-call API entirely — much more reliable.
# ---------------------------------------------------------------------------

def _llm_json(llm: ChatGroq, messages: list) -> dict:
    chain = llm.bind(response_format={"type": "json_object"})
    response = chain.invoke(messages)
    text = response.content.strip()
    # strip optional ```json ... ``` wrapper some models add
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


# ---------------------------------------------------------------------------
# Context formatter
# ---------------------------------------------------------------------------

def _format_context(documents: List[dict]) -> str:
    if not documents:
        return "(no documents retrieved)"
    blocks = [
        f"[Source: {d['source']} | Page: {d['page']}]\n{d['content']}"
        for d in documents
    ]
    return "\n\n---\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def router_node(state: RAGState) -> dict:
    t0 = time.time()
    sys_prompt = (
        "You are a routing classifier for an AI research assistant. "
        "Your job: decide if the user's question needs RAG (retrieval from papers) or can be answered directly.\n\n"
        "ALWAYS return needs_rag: true for:\n"
        "- ANY question starting with 'what is', 'what are', 'explain', 'define', 'describe', 'tell me about', 'how does', 'how do', 'how is'\n"
        "- ANY technical or scientific topic: machine learning, AI, deep learning, LLM, RAG, transformers, neural networks, NLP, computer vision, supervised learning, unsupervised learning, reinforcement learning, BERT, GPT, attention, embeddings, vectors, gradient descent, backpropagation, etc.\n"
        "- ANY question about a research paper, model, algorithm, dataset, benchmark, or academic concept\n"
        "- ANY comparison between two technical concepts (vs, compare, difference, contrast)\n"
        "- ANY question about how something works, why something works, advantages/disadvantages\n\n"
        "ONLY return needs_rag: false for:\n"
        "- Pure greetings: 'hi', 'hello', 'how are you', 'thanks'\n"
        "- Questions about how to USE this assistant: 'how do I upload a file', 'what can you do'\n\n"
        "When in doubt, ALWAYS default to needs_rag: true. It is always better to retrieve than to skip retrieval.\n\n"
        'Respond ONLY with valid JSON: {"needs_rag": true} or {"needs_rag": false}'
    )
    user_prompt = state["original_query"]
    data = _llm_json(
        _router_llm(),
        [
            ("system", sys_prompt),
            ("user", user_prompt),
        ],
    )
    latency = round((time.time() - t0) * 1000, 2)
    needs_rag = bool(data.get("needs_rag", True))

    # Detect comparison intent locally (no extra LLM call)
    q_lower = state["original_query"].lower()
    compare_keywords = ["compare", "vs", "versus", "difference between", "distinguish", "contrast"]
    is_comparison = any(kw in q_lower for kw in compare_keywords)

    logs = dict(state.get("node_logs", {}))
    logs["router"] = {
        "input": user_prompt,
        "prompt": f"[System]\n{sys_prompt}\n\n[User]\n{user_prompt}",
        "output": json.dumps(data),
        "latency_ms": latency
    }

    return {
        "query":         state["original_query"],
        "needs_rag":     needs_rag,
        "is_comparison": is_comparison,
        "retry_count":   0,
        "node_logs":     logs,
    }
    
def retrieve_node(state: RAGState) -> dict:
    """Pull candidate chunks from ChromaDB using hybrid search."""
    t0 = time.time()
    vs = get_vectorstore()
    
    query = state["query"]
    original_query = state["original_query"]
    arxiv_status = "Skipped autonomous fetch"
    
    # First pass — search current knowledge base
    documents = []
    if vs.count() > 0:
        results = vs.hybrid_search(query, top_k=TOP_K)
        documents = [
            {
                "content": r["content"],
                "source":  r["metadata"].get("source_file", "unknown"),
                "page":    r["metadata"].get("page", "?"),
                "score":   r["similarity_score"],
                "rrf_score": r.get("rrf_score", 0.0),
            }
            for r in results
        ]

    # Auto-fetch from arXiv when the paper isn't in our knowledge base
    try:
        from arxiv_helper import download_and_ingest_arxiv, should_auto_fetch_arxiv, extract_search_term
        if should_auto_fetch_arxiv(original_query, documents, vs):
            arxiv_id_match = re.search(r'\b(\d{4}\.\d{4,5}(?:v\d+)?)\b', original_query)
            search_term = arxiv_id_match.group(1) if arxiv_id_match else extract_search_term(original_query)
            print(f"[retrieve_node] Auto arXiv fetch for: {search_term}")
            arxiv_status = download_and_ingest_arxiv(search_term)
            # Re-search after ingest
            if vs.count() > 0:
                results = vs.hybrid_search(query, top_k=TOP_K)
                documents = [
                    {
                        "content": r["content"],
                        "source":  r["metadata"].get("source_file", "unknown"),
                        "page":    r["metadata"].get("page", "?"),
                        "score":   r["similarity_score"],
                        "rrf_score": r.get("rrf_score", 0.0),
                    }
                    for r in results
                ]
    except Exception as e:
        arxiv_status = f"Autonomous arXiv retrieval failed: {e}"
        print(f"[retrieve_node] {arxiv_status}")

    if vs.count() == 0 and not documents:
        logs = dict(state.get("node_logs", {}))
        logs["retriever"] = {
            "input": query,
            "prompt": f"Search Query: {query}\nArXiv Ingest: {arxiv_status}",
            "output": "Database is empty.",
            "latency_ms": round((time.time() - t0) * 1000, 2)
        }
        return {"documents": [], "node_logs": logs}
        
    latency = round((time.time() - t0) * 1000, 2)
    logs = dict(state.get("node_logs", {}))
    logs["retriever"] = {
        "input": query,
        "prompt": f"Hybrid Search Query: {query}\nArXiv Status: {arxiv_status}",
        "output": f"Found {len(documents)} chunks from papers: {list({d['source'] for d in documents})}",
        "latency_ms": latency
    }
    
    return {"documents": documents, "node_logs": logs, "arxiv_status": arxiv_status}


def grade_node(state: RAGState) -> dict:
    """Grade whether retrieved docs actually address the query."""
    t0 = time.time()
    context = _format_context(state.get("documents", []))
    sys_prompt = (
        "You grade retrieved documents for relevance to a query. "
        'Respond ONLY with valid JSON: {"grade": "relevant"} or {"grade": "irrelevant"}. '
        "Use irrelevant if documents are empty, off-topic, or too vague."
    )
    user_prompt = f"Query: {state['query']}\n\nDocuments:\n{context}"
    data = _llm_json(
        _router_llm(),
        [
            ("system", sys_prompt),
            ("user", user_prompt),
        ],
    )
    grade = data.get("grade", "irrelevant")
    if grade not in ("relevant", "irrelevant"):
        grade = "irrelevant"
        
    latency = round((time.time() - t0) * 1000, 2)
    logs = dict(state.get("node_logs", {}))
    logs["grader"] = {
        "input": f"Query: {state['query']}",
        "prompt": f"[System]\n{sys_prompt}\n\n[User]\n{user_prompt}",
        "output": json.dumps(data),
        "latency_ms": latency
    }
    return {"grade": grade, "node_logs": logs}


def rewrite_node(state: RAGState) -> dict:
    """Rewrite the query for better retrieval."""
    t0 = time.time()
    llm = _router_llm(temperature=0.3)
    sys_prompt = (
        "You rewrite search queries to improve retrieval from an "
        "arxiv paper vector database. The previous query either failed "
        "to retrieve relevant results, or the answer wasn't grounded. "
        "Produce ONE improved query — more specific, better keywords. "
        "Respond with ONLY the rewritten query, no explanation."
    )
    user_prompt = (
        f"Original question: {state['original_query']}\n"
        f"Last query tried:  {state['query']}"
    )
    response = llm.invoke(
        [
            ("system", sys_prompt),
            ("user", user_prompt),
        ]
    )
    rewritten_query = response.content.strip()
    latency = round((time.time() - t0) * 1000, 2)
    
    logs = dict(state.get("node_logs", {}))
    logs["rewriter"] = {
        "input": f"Original: {state['original_query']} | Last tried: {state['query']}",
        "prompt": f"[System]\n{sys_prompt}\n\n[User]\n{user_prompt}",
        "output": rewritten_query,
        "latency_ms": latency
    }
    
    return {
        "query":       rewritten_query,
        "retry_count": state.get("retry_count", 0) + 1,
        "node_logs":   logs,
    }


def generate_node(state: RAGState) -> dict:
    """Generate a grounded answer from retrieved documents, plus follow-ups, diagram, confidence."""
    t0 = time.time()
    context = _format_context(state.get("documents", []))
    sys_prompt = (
        "You are an expert AI research assistant specializing in ML papers. "
        "Answer using ONLY the provided documents. "
        "Cite sources like: (Source: paper_name.pdf, Page X). "
        "If documents don't fully answer the question, say so plainly."
    )
    user_prompt = f"Question: {state['original_query']}\n\nDocuments:\n{context}"
    response = _generator_llm().invoke(
        [
            ("system", sys_prompt),
            ("user", user_prompt),
        ]
    )
    answer = response.content
    latency = round((time.time() - t0) * 1000, 2)

    # --- Follow-up questions ---
    follow_up_questions = []
    try:
        fu_prompt = (
            "Based on this Q&A, generate exactly 3 short follow-up questions a researcher might ask next. "
            'Respond ONLY with valid JSON: {"questions": ["q1", "q2", "q3"]}'
        )
        fu_data = _llm_json(
            _router_llm(),
            [
                ("system", fu_prompt),
                ("user", f"Q: {state['original_query']}\nA: {answer[:500]}"),
            ],
        )
        follow_up_questions = fu_data.get("questions", [])[:3]
    except Exception:
        pass

    # --- Diagram generation (Mermaid) ---
    diagram = ""
    diagram_keywords = [
        "how does", "explain", "architecture", "pipeline", "workflow", "process",
        "flow", "work", "mechanism", "step", "stages", "compare", "difference"
    ]
    q_lower = state['original_query'].lower()
    if any(kw in q_lower for kw in diagram_keywords):
        try:
            diag_prompt = (
                "You are a Mermaid.js diagram expert. Given the question and answer, "
                "create a concise Mermaid flowchart or graph diagram that visually explains the concept. "
                "Output ONLY the raw Mermaid code (no markdown fences, no explanation). "
                "Keep it short: max 10-12 nodes. Use LR direction for pipelines, TD for hierarchies. "
                "If the topic doesn't have a clear visual structure, output the single word: NONE"
            )
            diag_response = _router_llm(temperature=0.1).invoke(
                [
                    ("system", diag_prompt),
                    ("user", f"Question: {state['original_query']}\nAnswer summary: {answer[:600]}"),
                ]
            )
            raw = diag_response.content.strip()
            raw = re.sub(r"^```(?:mermaid)?\s*", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"\s*```$", "", raw)
            if raw and raw.upper() != "NONE" and len(raw) > 20:
                diagram = raw
        except Exception:
            pass

    logs = dict(state.get("node_logs", {}))
    logs["generator"] = {
        "input": f"Question: {state['original_query']}",
        "prompt": f"[System]\n{sys_prompt}\n\n[User]\n{user_prompt}",
        "output": answer,
        "latency_ms": latency
    }

    return {
        "answer": answer,
        "follow_up_questions": follow_up_questions,
        "diagram": diagram,
        "node_logs": logs,
    }


def generate_direct_node(state: RAGState) -> dict:
    """Answer directly without retrieval (router said no RAG needed)."""
    t0 = time.time()
    sys_prompt = (
        "You are an expert AI research assistant. "
        "Answer the question directly and concisely."
    )
    user_prompt = state["original_query"]
    response = _generator_llm().invoke(
        [
            ("system", sys_prompt),
            ("user", user_prompt),
        ]
    )
    answer = response.content
    latency = round((time.time() - t0) * 1000, 2)

    # --- Follow-up questions for direct answers ---
    follow_up_questions = []
    try:
        fu_prompt = (
            "Based on this Q&A, generate exactly 3 short follow-up questions a researcher might ask next. "
            'Respond ONLY with valid JSON: {"questions": ["q1", "q2", "q3"]}'
        )
        fu_data = _llm_json(
            _router_llm(),
            [
                ("system", fu_prompt),
                ("user", f"Q: {state['original_query']}\nA: {answer[:500]}"),
            ],
        )
        follow_up_questions = fu_data.get("questions", [])[:3]
    except Exception:
        pass

    # --- Mermaid diagram for direct answers (explain / how does / what is) ---
    diagram = ""
    diagram_triggers = [
        "how does", "how do", "explain", "what is", "what are",
        "architecture", "pipeline", "workflow", "process", "mechanism",
        "difference between", "compare", "vs ", "versus",
        "diagram", "flowchart", "describe the",
    ]
    if any(kw in state["original_query"].lower() for kw in diagram_triggers):
        try:
            diag_sys = (
                "You are a Mermaid.js expert. Create a clear, concise Mermaid flowchart diagram. "
                "Rules:\n"
                "1. Output ONLY raw Mermaid code — NO markdown fences, NO explanation\n"
                "2. Max 12 nodes. Use LR for flows/pipelines, TD for hierarchies\n"
                "3. Use simple node labels (no parentheses inside brackets)\n"
                "4. If no clear visual structure exists, output: NONE\n"
                "Example for 'What is RAG?':\n"
                "flowchart LR\n"
                "  A[User Query] --> B[Retriever]\n"
                "  B --> C[(Vector DB)]\n"
                "  C --> D[Top-K Chunks]\n"
                "  D --> E[LLM Generator]\n"
                "  E --> F[Final Answer]"
            )
            diag_response = _router_llm(temperature=0.1).invoke([
                ("system", diag_sys),
                ("user", f"Create a diagram for: {state['original_query']}\n\nBased on this answer:\n{answer[:800]}"),
            ])
            raw = diag_response.content.strip()
            # Clean any accidental fences
            raw = re.sub(r"^```(?:mermaid)?\s*", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"\s*```$", "", raw)
            if raw and raw.upper() != "NONE" and len(raw) > 20 and ("flowchart" in raw or "graph" in raw.lower() or "sequenceDiagram" in raw):
                diagram = raw
        except Exception:
            pass

    logs = dict(state.get("node_logs", {}))
    logs["generate_direct"] = {
        "input": user_prompt,
        "prompt": f"[System]\n{sys_prompt}\n\n[User]\n{user_prompt}",
        "output": answer,
        "latency_ms": latency
    }

    return {
        "answer": answer,
        "hallucination_check": "not_applicable",
        "confidence_score": 0.82,
        "follow_up_questions": follow_up_questions,
        "diagram": diagram,
        "node_logs": logs,
    }



def halucheck_node(state: RAGState) -> dict:
    """Check whether the answer is grounded in the documents. Compute confidence score."""
    t0 = time.time()
    context = _format_context(state.get("documents", []))
    sys_prompt = (
        "You check if an answer is supported by the given documents. "
        'Respond ONLY with valid JSON: {"verdict": "grounded"} or {"verdict": "hallucinated"}. '
        "Use hallucinated if the answer makes claims the documents don't support."
    )
    user_prompt = f"Documents:\n{context}\n\nAnswer to check:\n{state['answer']}"
    data = _llm_json(
        _router_llm(),
        [
            ("system", sys_prompt),
            ("user", user_prompt),
        ],
    )
    verdict = data.get("verdict", "grounded")
    if verdict not in ("grounded", "hallucinated"):
        verdict = "grounded"

    # --- Confidence score computation ---
    # grade: relevant=+0.4, irrelevant=-0.2
    # halucheck: grounded=+0.6, hallucinated=-0.3
    # baseline: 0.0 (capped 0.0–1.0)
    grade_score = 0.4 if state.get("grade") == "relevant" else -0.2
    halu_score  = 0.6 if verdict == "grounded" else -0.3
    retry_penalty = state.get("retry_count", 0) * 0.05
    confidence = min(1.0, max(0.0, grade_score + halu_score - retry_penalty))

    latency = round((time.time() - t0) * 1000, 2)
    logs = dict(state.get("node_logs", {}))
    logs["halucheck"] = {
        "input": f"Answer to check: {state['answer'][:200]}...",
        "prompt": f"[System]\n{sys_prompt}\n\n[User]\n{user_prompt}",
        "output": json.dumps(data),
        "latency_ms": latency
    }

    return {"hallucination_check": verdict, "confidence_score": confidence, "node_logs": logs}


# ---------------------------------------------------------------------------
# Conditional edge routers
# ---------------------------------------------------------------------------

def route_after_router(state: RAGState) -> str:
    if state.get("is_comparison"):
        return "compare"
    return "retriever" if state.get("needs_rag") else "generate_direct"


def route_after_grade(state: RAGState) -> str:
    if state.get("grade") == "relevant":
        return "generator"
    if state.get("retry_count", 0) >= MAX_RETRIES:
        return "generator"   # out of retries, best-effort answer
    # On first failure (retry_count=0), try arXiv auto-fetch before rewriting
    if state.get("retry_count", 0) == 0:
        return "arxiv_fallback"
    return "rewriter"


def route_after_halucheck(state: RAGState) -> str:
    if state.get("hallucination_check") in ("grounded", "not_applicable"):
        return "end"
    if state.get("retry_count", 0) >= MAX_RETRIES:
        return "end"         # out of retries, return as-is
    return "rewriter"


# ---------------------------------------------------------------------------
# ArXiv Fallback Node — auto-fetch when grade is irrelevant on first try
# ---------------------------------------------------------------------------

def arxiv_fallback_node(state: RAGState) -> dict:
    """
    Called when grade=irrelevant and retry_count=0.
    Attempts to fetch the most relevant arXiv paper for the query,
    then the graph will re-run retriever -> grader.
    """
    t0 = time.time()
    query = state.get("original_query", state.get("query", ""))
    arxiv_status = "Skipped — query too vague for auto-fetch"

    try:
        from arxiv_helper import download_and_ingest_arxiv, extract_search_term
        search_term = extract_search_term(query)
        print(f"[arxiv_fallback] Grade=irrelevant, auto-fetching arXiv: {search_term!r}")
        arxiv_status = download_and_ingest_arxiv(search_term)
        print(f"[arxiv_fallback] Result: {arxiv_status}")
    except Exception as e:
        arxiv_status = f"ArXiv fetch failed: {e}"
        print(f"[arxiv_fallback] {arxiv_status}")

    latency = round((time.time() - t0) * 1000, 2)
    logs = dict(state.get("node_logs", {}))
    logs["arxiv_fallback"] = {
        "input":      query,
        "prompt":     f"Auto-fetch triggered for query: {query}",
        "output":     arxiv_status,
        "latency_ms": latency,
    }
    # Increment retry_count so if arXiv fails we don't loop forever
    return {
        "arxiv_status": arxiv_status,
        "retry_count":  state.get("retry_count", 0) + 1,
        "node_logs":    logs,
    }


# ---------------------------------------------------------------------------
# Comparison Node — generates structured Markdown comparison table
# ---------------------------------------------------------------------------

def compare_node(state: RAGState) -> dict:
    """Generate a structured side-by-side Markdown comparison table."""
    t0 = time.time()
    sys_prompt = (
        "You are an expert AI research assistant. The user wants a structured comparison. "
        "Generate a clear, detailed Markdown comparison table with pipe syntax (|col|col|). "
        "Include rows for: Architecture, Training Method, Key Innovation, Strengths, Weaknesses, Best Use Case. "
        "After the table, add a 2-3 sentence summary. Be factual and concise."
    )
    user_prompt = state["original_query"]

    # Also retrieve relevant docs if available
    context = ""
    try:
        vs = get_vectorstore()
        if vs.count() > 0:
            results = vs.hybrid_search(user_prompt, top_k=4)
            if results:
                context = "\n\nRelevant context from knowledge base:\n" + _format_context([
                    {"content": r["content"], "source": r["metadata"].get("source_file","?"), "page": r["metadata"].get("page","?")}
                    for r in results
                ])
    except Exception:
        pass

    response = _generator_llm().invoke([
        ("system", sys_prompt),
        ("user",   user_prompt + context),
    ])
    answer  = response.content
    latency = round((time.time() - t0) * 1000, 2)

    # Generate follow-ups
    follow_up_questions = []
    try:
        fu_data = _llm_json(
            _router_llm(),
            [
                ("system", 'Generate 3 follow-up questions. Respond ONLY with {"questions":[...]}'),
                ("user",   f"Q: {state['original_query']}\nA: {answer[:400]}"),
            ],
        )
        follow_up_questions = fu_data.get("questions", [])[:3]
    except Exception:
        pass

    logs = dict(state.get("node_logs", {}))
    logs["compare"] = {
        "input":      user_prompt,
        "prompt":     f"[System]\n{sys_prompt}\n\n[User]\n{user_prompt}",
        "output":     answer[:300] + "...",
        "latency_ms": latency,
    }
    return {
        "answer":              answer,
        "hallucination_check": "not_applicable",
        "confidence_score":    0.88,
        "follow_up_questions": follow_up_questions,
        "diagram":             "",
        "node_logs":           logs,
    }


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_graph():
    b = StateGraph(RAGState)

    b.add_node("router",          router_node)
    b.add_node("retriever",       retrieve_node)
    b.add_node("grader",          grade_node)
    b.add_node("rewriter",        rewrite_node)
    b.add_node("arxiv_fallback",  arxiv_fallback_node)   # NEW: auto-fetch on irrelevant
    b.add_node("generator",       generate_node)
    b.add_node("generate_direct", generate_direct_node)
    b.add_node("halucheck",       halucheck_node)
    b.add_node("compare",         compare_node)

    b.add_edge(START, "router")
    b.add_conditional_edges("router", route_after_router,
        {"retriever": "retriever", "generate_direct": "generate_direct", "compare": "compare"})
    b.add_edge("retriever", "grader")
    b.add_conditional_edges("grader",    route_after_grade,
        {"generator": "generator", "rewriter": "rewriter", "arxiv_fallback": "arxiv_fallback"})
    b.add_edge("arxiv_fallback", "retriever")   # after fetch, re-retrieve
    b.add_edge("rewriter", "retriever")
    b.add_edge("generator", "halucheck")
    b.add_conditional_edges("halucheck", route_after_halucheck, {"end": END, "rewriter": "rewriter"})
    b.add_edge("generate_direct", END)
    b.add_edge("compare",         END)

    return b.compile()


graph = build_graph()


# ---------------------------------------------------------------------------
# ask_graph() — drop-in for agent.py's ask_agent()
# api.py mein sirf ye ek line swap karo:
#   from agent import ask_agent  →  from graph import ask_graph as ask_agent
# ---------------------------------------------------------------------------

def ask_graph(query: str, chat_history: list = None) -> dict:
    """Returns {"answer", "sources", "steps", "node_logs", "follow_up_questions", "confidence_score", "diagram"}"""
    initial_state: RAGState = {"original_query": query}
    final_state = dict(initial_state)
    steps = 0
    for event in graph.stream(initial_state, stream_mode="updates"):
        for _, update in event.items():
            steps += 1
            final_state.update(update)
    sources = sorted({d["source"] for d in final_state.get("documents", [])})
    return {
        "answer":              final_state.get("answer", ""),
        "sources":             sources,
        "steps":               steps,
        "node_logs":           final_state.get("node_logs", {}),
        "follow_up_questions": final_state.get("follow_up_questions", []),
        "confidence_score":    final_state.get("confidence_score", 0.0),
        "diagram":             final_state.get("diagram", ""),
    }


# ---------------------------------------------------------------------------
# Terminal test — python graph.py "your question here"
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "What is the attention mechanism in transformers?"
    print(f"\n=== Query: {query} ===\n")
    for event in graph.stream({"original_query": query}, stream_mode="updates"):
        for node_name, update in event.items():
            print(f"--- node: {node_name} ---")
            for k, v in update.items():
                preview = str(v)[:300]
                print(f"  {k}: {preview}")
            print()
