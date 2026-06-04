"""
DigiCounsellor — Test RAG Search

Loads Chroma DB and searches for example questions.
Prints top results with university name, text preview, and source URL.

Usage:
  python backend/test_rag_search.py
"""

import os
from sentence_transformers import SentenceTransformer
import chromadb

BASE_DIR = os.path.dirname(__file__)
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")
COLLECTION_NAME = "pakistan_university_admissions"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def search(query, top_k=5):
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"{'='*60}")

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_collection(COLLECTION_NAME)

    model = SentenceTransformer(EMBEDDING_MODEL)
    query_embedding = model.encode(query).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )

    if not results["ids"] or not results["ids"][0]:
        print("  No results found.")
        return

    for i in range(len(results["ids"][0])):
        chunk_id = results["ids"][0][i]
        metadata = results["metadatas"][0][i]
        text = results["documents"][0][i]
        distance = results["distances"][0][i] if results["distances"] else 0

        # Get a short preview (first 200 chars)
        preview = text[:200].replace("\n", " ").strip()

        print(f"\n  --- Result {i+1} (distance: {distance:.4f}) ---")
        print(f"  University: {metadata.get('university_name', '?')}")
        print(f"  Category:   {metadata.get('category', '?')}")
        print(f"  City:       {metadata.get('city', '?')}")
        print(f"  Source:     {metadata.get('source_url', '?')[:80]}")
        print(f"  Preview:    {preview}...")


if __name__ == "__main__":
    questions = [
        "Which universities offer CS in Lahore?",
        "What is FAST eligibility for software engineering?",
        "Which universities are good for low budget?",
        "What is the fee information for COMSATS?",
    ]

    for q in questions:
        search(q)
