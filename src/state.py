"""
state.py — Shared state definition for the self-correcting Agentic RAG graph.

This replaces the create_react_agent message-list state with an explicit,
typed state that's threaded through every node in graph.py. Each node reads
the fields it needs and returns a dict of only the fields it updates —
LangGraph shallow-merges that into the running state.

`total=False` because no single node populates every field on its first hit
(e.g. `grade` doesn't exist until after the grader node runs).
"""

from typing import Any, Dict, List, TypedDict


class RAGState(TypedDict, total=False):
    # --- input / query tracking ---
    query: str
    # The query currently used for retrieval. Starts equal to
    # `original_query`, overwritten by the rewriter node on retries.

    original_query: str
    # The user's original, unmodified question. The generator always
    # answers this, even after N query rewrites.

    # --- retrieval ---
    documents: List[Dict[str, Any]]
    # Retrieved chunks from vectorstore.VectorStore.semantic_search(), kept
    # as dicts (not raw langchain Documents) so state stays JSON-serializable
    # for the future SSE endpoint. Each dict has the shape:
    #   {"content": str, "source": str, "page": int | str, "score": float}
    # `source`/`page` are pulled from the chunk's metadata so citations
    # survive all the way to the final answer, matching how api.py's
    # QueryResponse.sources currently works.

    grade: str
    # Grader's verdict on `documents` relative to `query`.
    # One of: "relevant" | "irrelevant"

    # --- generation ---
    answer: str
    # The generated answer text (from either `generator` or `generate_direct`).

    hallucination_check: str
    # One of: "grounded" | "hallucinated" | "not_applicable"
    # "not_applicable" is set by generate_direct, since there are no source
    # documents to check groundedness against.

    # --- control flow ---
    retry_count: int
    # Shared counter, incremented once per pass through `rewriter` regardless
    # of whether the rewrite was triggered by a bad grade or a failed
    # hallucination check. Capped by MAX_RETRIES in graph.py to guarantee
    # the graph terminates.

    needs_rag: bool
    # Router's decision: does this query require retrieval from the arxiv
    # paper knowledge base, or can it be answered directly (chit-chat,
    # general knowledge, "what papers do you support", etc.)?
