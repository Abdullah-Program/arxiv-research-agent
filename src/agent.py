"""
agent.py
--------
LangGraph ReAct agent that uses tools from tools.py.
LLM: Groq (llama-3.3-70b-versatile)

Flow:
    User Query → Agent thinks → picks tool → gets result → thinks again → final answer
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load env + fix path ───────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage

from tools import TOOLS


# ── LLM Setup ─────────────────────────────────────────────────────────────────
def get_llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in .env file")

    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.1,          # low temp = more factual answers
        max_tokens=2048,
        api_key=api_key,
    )


# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an expert AI research assistant specializing in machine learning and AI papers.

You have access to a knowledge base of ArXiv research papers. Your job is to answer questions accurately using the papers.

RULES:
1. ALWAYS use retrieve_context_tool before answering any research question
2. Use list_papers_tool when asked what papers are available
3. Use ingest_papers_tool when asked to add/update papers
4. Base your answers on the retrieved context — cite the source paper and page
5. If context doesn't contain enough info, say so clearly
6. Be concise but thorough — explain concepts clearly

Answer format:
- Give a clear direct answer
- Cite sources like: (Source: paper_name.pdf, Page X)
- If multiple sources, mention all
"""


# ── Agent Setup ───────────────────────────────────────────────────────────────
def get_agent():
    """
    Create and return a LangGraph ReAct agent.
    Used by api.py and app.py.
    """
    llm   = get_llm()
    agent = create_react_agent(
        model=llm,
        tools=TOOLS,
        prompt=SYSTEM_PROMPT,
    )
    return agent


# ── Main invoke function (used by api.py) ─────────────────────────────────────
def ask_agent(query: str, chat_history: list = None) -> dict:
    """
    Send a query to the agent and get back answer + sources.

    Args:
        query        : User's question
        chat_history : List of previous messages (optional)

    Returns:
        {
            "answer"  : str,
            "sources" : List[str],
            "steps"   : int   (how many tool calls agent made)
        }
    """
    agent = get_agent()

    # Build messages
    messages = []
    if chat_history:
        messages.extend(chat_history)
    messages.append(HumanMessage(content=query))

    # Run agent
    result = agent.invoke({"messages": messages})

    # Extract final answer
    final_message = result["messages"][-1]
    answer = final_message.content if hasattr(final_message, "content") else str(final_message)

    # Count tool calls (steps agent took)
    steps = sum(
        1 for m in result["messages"]
        if hasattr(m, "type") and m.type == "tool"
    )

    # Extract sources from tool messages
    sources = []
    for m in result["messages"]:
        if hasattr(m, "type") and m.type == "tool":
            content = m.content if hasattr(m, "content") else ""
            # Parse source files from tool output
            for line in content.split("\n"):
                if "Source:" in line and ".pdf" in line:
                    # Extract filename
                    parts = line.split("|")
                    for part in parts:
                        if "Source:" in part:
                            src = part.replace("[Source:", "").replace("Source:", "").strip()
                            if src and src not in sources:
                                sources.append(src)

    return {
        "answer":  answer,
        "sources": sources,
        "steps":   steps,
    }


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing agent...\n")
    print("Query: What is the attention mechanism in transformers?\n")

    result = ask_agent("What is the attention mechanism in transformers?")

    print(f"Answer:\n{result['answer']}")
    print(f"\nSources: {result['sources']}")
    print(f"Agent took {result['steps']} tool call(s)")