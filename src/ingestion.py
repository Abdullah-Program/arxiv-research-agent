"""
ingestion.py
------------
Handles: PDF loading → text splitting → embedding generation
Returns chunks (List[Document]) and embeddings (np.ndarray) ready for vectorstore
"""

# NOTE: Heavy imports (sentence-transformers, pypdf) are done LAZILY inside
# functions so that importing this module does NOT trigger long startup times.

import os
import numpy as np
from pathlib import Path
from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


# ── Constants (change here if needed) ────────────────────────────────────────
EMBEDDING_MODEL = "all-MiniLM-L6-v2"   # free, local, 384-dim
CHUNK_SIZE      = 1000
CHUNK_OVERLAP   = 200
PAPERS_DIR      = Path(__file__).resolve().parent.parent / "data" / "papers"


# ── Embedding Model (singleton so it loads once per process) ─────────────────
_embed_model = None

def get_embedding_model():
    """Lazily load SentenceTransformer once and reuse."""
    global _embed_model
    if _embed_model is None:
        print(f"[ingestion] Loading embedding model: {EMBEDDING_MODEL}")
        # Lazy import — only loaded when first needed, not at module import time
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415
        _embed_model = SentenceTransformer(EMBEDDING_MODEL)
        print(f"[ingestion] Embedding dim: {_embed_model.get_sentence_embedding_dimension()}")
    return _embed_model


# ── PDF Loading ───────────────────────────────────────────────────────────────
def load_pdf(pdf_path: str | Path) -> List["Document"]:
    """
    Load a single PDF file using pypdf (avoids heavy langchain_community chain).
    Each page becomes one Document with metadata:
      source, source_file, page, file_type
    """
    # Lazy imports — keep module-level imports minimal for fast startup
    from pypdf import PdfReader                          # noqa: PLC0415
    from langchain_core.documents import Document        # noqa: PLC0415

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    docs   = []
    for page_num, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        doc  = Document(
            page_content=text,
            metadata={
                "source":      str(pdf_path),
                "source_file": pdf_path.name,
                "page":        page_num,
                "file_type":   "pdf",
            },
        )
        docs.append(doc)

    print(f"[ingestion] Loaded '{pdf_path.name}' → {len(docs)} pages")
    return docs


def load_all_pdfs(directory: str | Path = PAPERS_DIR) -> list:
    """
    Recursively load every PDF in a directory.
    Returns combined list of all page Documents.
    """
    pdf_dir = Path(directory)
    if not pdf_dir.exists():
        print(f"[ingestion] Creating papers directory: {pdf_dir}")
        pdf_dir.mkdir(parents=True, exist_ok=True)
        return []

    pdf_files = list(pdf_dir.glob("**/*.pdf"))
    if not pdf_files:
        print(f"[ingestion] No PDFs found in {pdf_dir}")
        return []

    print(f"[ingestion] Found {len(pdf_files)} PDFs to load")
    all_docs = []
    for pdf_file in pdf_files:
        try:
            all_docs.extend(load_pdf(pdf_file))
        except Exception as e:
            print(f"[ingestion] ✗ Skipping {pdf_file.name}: {e}")

    print(f"[ingestion] Total pages loaded: {len(all_docs)}")
    return all_docs


# ── Text Splitting ────────────────────────────────────────────────────────────
def split_documents(
    documents,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
):
    """
    Split documents into smaller chunks.
    Preserves all original metadata + adds chunk_index.
    """
    # Lazy import — langchain_text_splitters is fine to import here
    from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: PLC0415

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_documents(documents)

    # Tag each chunk with its position
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i

    print(f"[ingestion] Split {len(documents)} pages → {len(chunks)} chunks")
    return chunks


# ── Embedding Generation ──────────────────────────────────────────────────────
def generate_embeddings(texts: List[str]) -> np.ndarray:
    """
    Generate embeddings for a list of strings.
    Returns numpy array of shape (len(texts), embedding_dim).
    """
    model      = get_embedding_model()
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)
    print(f"[ingestion] Embeddings shape: {embeddings.shape}")
    return embeddings


# ── Main Pipeline Function (used by tools.py) ────────────────────────────────
def ingest_pdfs(
    directory: str | Path = PAPERS_DIR,
) -> Tuple[list, np.ndarray]:
    """
    Full ingestion pipeline:
      load PDFs → split → embed

    Returns:
        chunks     : List[Document]  — text chunks with metadata
        embeddings : np.ndarray      — shape (n_chunks, 384)

    Used by tools.py → ingest_papers_tool
    """
    docs       = load_all_pdfs(directory)
    if not docs:
        return [], np.array([])

    chunks     = split_documents(docs)
    texts      = [c.page_content for c in chunks]
    embeddings = generate_embeddings(texts)

    return chunks, embeddings


def ingest_single_pdf(
    pdf_path: str | Path,
) -> Tuple[list, np.ndarray]:
    """
    Ingest a single PDF file.
    Used by api.py for file-upload endpoint.
    """
    docs       = load_pdf(pdf_path)
    chunks     = split_documents(docs)
    texts      = [c.page_content for c in chunks]
    embeddings = generate_embeddings(texts)
    return chunks, embeddings


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    chunks, embeddings = ingest_pdfs()
    print(f"\nResult: {len(chunks)} chunks, embeddings shape: {embeddings.shape}")
    if chunks:
        print(f"Sample chunk metadata: {chunks[0].metadata}")
        print(f"Sample content: {chunks[0].page_content[:200]}")
