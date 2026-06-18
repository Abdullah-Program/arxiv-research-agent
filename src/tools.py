"""
tools.py
--------
LangGraph tools that the agent uses.
Imports directly from ingestion.py and vectorstore.py.

Tools:
    - ingest_papers_tool  : Load PDFs → embed → store in ChromaDB
    - retrieve_context_tool: Search ChromaDB for relevant chunks
    - list_papers_tool    : List all ingested papers
"""

import sys
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

# ── Add src to path so imports work ──────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from ingestion import ingest_pdfs, ingest_single_pdf
from vectorstore import get_vectorstore


# ── Tool 1: Ingest Papers ─────────────────────────────────────────────────────
@tool
def ingest_papers_tool(
    directory: Annotated[str, "Path to folder containing PDF files. Leave empty for default data/papers/"] = ""
) -> str:
    """
    Load all PDF papers from a directory, create embeddings, and store in ChromaDB.
    Use this when the user wants to add or update papers in the knowledge base.
    """
    try:
        vs = get_vectorstore()

        # Use default papers dir if not specified
        from ingestion import PAPERS_DIR
        target_dir = Path(directory) if directory else PAPERS_DIR

        chunks, embeddings = ingest_pdfs(target_dir)

        if not chunks:
            return f"No PDFs found in {target_dir}. Please add PDF files first."

        added = vs.add_documents(chunks, embeddings)
        papers = vs.list_papers()

        return (
            f"Successfully ingested {len(papers)} papers with {added} chunks.\n"
            f"Papers in knowledge base: {', '.join(papers)}"
        )

    except Exception as e:
        return f"Error during ingestion: {str(e)}"


# ── Tool 2: Retrieve Context ──────────────────────────────────────────────────
@tool
def retrieve_context_tool(
    query: Annotated[str, "The question or topic to search for in the research papers"],
    top_k: Annotated[int, "Number of relevant chunks to retrieve (default 5)"] = 5,
) -> str:
    """
    Search the ChromaDB vector store for chunks relevant to the query.
    Use this to find information from ingested research papers before answering.
    Always use this tool before answering research questions.
    """
    try:
        vs = get_vectorstore()

        if vs.count() == 0:
            return "Knowledge base is empty. Please ingest papers first using ingest_papers_tool."

        results = vs.semantic_search(query, top_k=top_k)

        if not results:
            return f"No relevant content found for: '{query}'"

        # Format results for the agent
        formatted = []
        for r in results:
            source = r["metadata"].get("source_file", "unknown")
            page   = r["metadata"].get("page", "?")
            score  = r["similarity_score"]
            content = r["content"]

            formatted.append(
                f"[Source: {source} | Page: {page} | Score: {score}]\n{content}"
            )

        return "\n\n---\n\n".join(formatted)

    except Exception as e:
        return f"Error during retrieval: {str(e)}"


# ── Tool 3: List Papers ───────────────────────────────────────────────────────
@tool
def list_papers_tool() -> str:
    """
    List all research papers currently stored in the knowledge base.
    Use this when the user asks what papers are available.
    """
    try:
        vs = get_vectorstore()
        papers = vs.list_papers()
        count  = vs.count()

        if not papers:
            return "No papers ingested yet. Use ingest_papers_tool to add papers."

        paper_list = "\n".join(f"  {i+1}. {p}" for i, p in enumerate(papers))
        return f"Knowledge base has {count} chunks from {len(papers)} papers:\n{paper_list}"

    except Exception as e:
        return f"Error listing papers: {str(e)}"


# ── All tools (imported by agent.py) ─────────────────────────────────────────
TOOLS = [ingest_papers_tool, retrieve_context_tool, list_papers_tool]


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing tools...\n")

    print("1. List papers:")
    print(list_papers_tool.invoke({}))

    print("\n2. Retrieve context:")
    print(retrieve_context_tool.invoke({"query": "what is attention mechanism", "top_k": 2}))