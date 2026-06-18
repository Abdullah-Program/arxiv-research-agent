"""
vectorstore.py
--------------
Manages ChromaDB persistent vector store.
Provides: add_documents(), semantic_search(), list_papers(), delete_collection()
Used by: tools.py, api.py
"""

import os
import uuid
import numpy as np
from pathlib import Path
from typing import List, Dict, Any

import chromadb

from ingestion import get_embedding_model   # reuse same model instance
# Document is imported lazily inside methods to avoid heavy startup chain


# ── Constants ─────────────────────────────────────────────────────────────────
VECTOR_STORE_DIR = Path(__file__).resolve().parent.parent / "data" / "vector_store"
COLLECTION_NAME  = "arxiv_papers"


# ── VectorStore Class ─────────────────────────────────────────────────────────
class VectorStore:
    """
    ChromaDB-backed vector store for research paper chunks.

    Public API used by tools.py / api.py:
        vs = VectorStore()
        vs.add_documents(chunks, embeddings)
        results = vs.semantic_search(query, top_k=5)
        papers  = vs.list_papers()
    """

    def __init__(
        self,
        collection_name: str = COLLECTION_NAME,
        persist_directory: str | Path = VECTOR_STORE_DIR,
    ):
        self.collection_name  = collection_name
        self.persist_directory = Path(persist_directory)
        self.client     = None
        self.collection = None
        self._init()

    # ── Setup ──────────────────────────────────────────────────────────────────
    def _init(self):
        """Initialize ChromaDB client and get/create collection."""
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory)
        )
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "ArXiv paper embeddings for RAG"},
        )
        print(f"[vectorstore] Collection '{self.collection_name}' ready.")
        print(f"[vectorstore] Existing docs: {self.collection.count()}")

    # ── Write ──────────────────────────────────────────────────────────────────
    def add_documents(
        self,
        documents,
        embeddings: np.ndarray,
    ) -> int:
        """
        Store chunks + their embeddings in ChromaDB.

        Args:
            documents  : List[Document] from ingestion.py
            embeddings : np.ndarray shape (n, 384)

        Returns:
            Number of chunks added.
        """
        if len(documents) != len(embeddings):
            raise ValueError("documents and embeddings length mismatch")

        ids, metas, texts, vecs = [], [], [], []

        for i, (doc, emb) in enumerate(zip(documents, embeddings)):
            doc_id = f"doc_{uuid.uuid4().hex[:8]}_{i}"
            ids.append(doc_id)

            meta = dict(doc.metadata)
            meta["content_length"] = len(doc.page_content)
            metas.append(meta)

            texts.append(doc.page_content)
            vecs.append(emb.tolist())

        # ChromaDB add (handles duplicates via unique IDs)
        self.collection.add(
            ids=ids,
            embeddings=vecs,
            metadatas=metas,
            documents=texts,
        )

        added = len(documents)
        print(f"[vectorstore] Added {added} chunks. Total: {self.collection.count()}")
        return added

    # ── Read ───────────────────────────────────────────────────────────────────
    def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.0,
        source_filter: str | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for chunks semantically similar to query.

        Args:
            query           : Natural language query
            top_k           : Max results to return
            score_threshold : Min similarity score (0.0 = return all)
            source_filter   : Filter by source_file name (optional)

        Returns:
            List of dicts — each has:
                content, metadata, similarity_score, distance, rank
        """
        # Embed the query using same model
        model         = get_embedding_model()
        query_vector  = model.encode([query])[0].tolist()

        # Build optional where filter
        where = {"source_file": source_filter} if source_filter else None

        try:
            results = self.collection.query(
                query_embeddings=[query_vector],
                n_results=min(top_k, self.collection.count()) or 1,
                where=where,
            )
        except Exception as e:
            print(f"[vectorstore] Query error: {e}")
            return []

        retrieved = []
        if results["documents"] and results["documents"][0]:
            for rank, (doc_id, content, meta, dist) in enumerate(
                zip(
                    results["ids"][0],
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                ),
                start=1,
            ):
                score = 1.0 - dist  # ChromaDB returns cosine distance
                if score >= score_threshold:
                    retrieved.append(
                        {
                            "id":               doc_id,
                            "content":          content,
                            "metadata":         meta,
                            "similarity_score": round(score, 4),
                            "distance":         round(dist, 4),
                            "rank":             rank,
                        }
                    )

        print(f"[vectorstore] Query '{query[:50]}...' → {len(retrieved)} results")
        return retrieved

    # ── Utility ────────────────────────────────────────────────────────────────
    def list_papers(self) -> List[str]:
        """
        Return unique paper filenames currently in the store.
        Used by api.py GET /papers endpoint.
        """
        if self.collection.count() == 0:
            return []

        all_meta = self.collection.get(include=["metadatas"])["metadatas"]
        papers   = sorted({m.get("source_file", "unknown") for m in all_meta})
        return papers

    def count(self) -> int:
        """Total chunks stored."""
        return self.collection.count()

    def delete_collection(self):
        """
        Wipe entire collection (useful for re-ingesting fresh).
        Recreates empty collection after deletion.
        """
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "ArXiv paper embeddings for RAG"},
        )
        print(f"[vectorstore] Collection reset. Count: {self.collection.count()}")

    def __repr__(self):
        return (
            f"VectorStore(collection='{self.collection_name}', "
            f"docs={self.collection.count()}, "
            f"path='{self.persist_directory}')"
        )


# ── Singleton getter (used by tools.py and api.py) ────────────────────────────
_vectorstore_instance: VectorStore | None = None

def get_vectorstore() -> VectorStore:
    """
    Return a single shared VectorStore instance.
    Avoids re-opening ChromaDB on every tool call.
    """
    global _vectorstore_instance
    if _vectorstore_instance is None:
        _vectorstore_instance = VectorStore()
    return _vectorstore_instance


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    vs = get_vectorstore()
    print(vs)
    print("Papers:", vs.list_papers())

    # Test search if data exists
    if vs.count() > 0:
        results = vs.semantic_search("attention mechanism transformer", top_k=3)
        for r in results:
            print(f"\nRank {r['rank']} | Score: {r['similarity_score']}")
            print(f"Source: {r['metadata'].get('source_file')} | Page: {r['metadata'].get('page')}")
            print(f"Content: {r['content'][:200]}...")
