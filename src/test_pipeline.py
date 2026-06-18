from ingestion import ingest_pdfs
from vectorstore import get_vectorstore

# Step 1: PDFs load + chunk + embed
chunks, embeddings = ingest_pdfs()

# Step 2: ChromaDB mein save karo
vs = get_vectorstore()
vs.add_documents(chunks, embeddings)

# Step 3: Test search
results = vs.semantic_search("what is attention mechanism", top_k=3)
for r in results:
    print(f"\nRank {r['rank']} | Score: {r['similarity_score']}")
    print(f"Source: {r['metadata']['source_file']}")
    print(f"Content: {r['content'][:200]}")
