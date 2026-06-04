"""
DigiCounsellor — Build RAG Vector Database

Reads processed admission data, creates text chunks, generates embeddings
using sentence-transformers, and stores them in Chroma.

Usage:
  python backend/build_vector_db.py
"""

import json
import os
import shutil

from sentence_transformers import SentenceTransformer
import chromadb

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

ADMISSION_DATA_PATH = os.path.join(PROCESSED_DIR, "university_admission_data.json")
CHUNKS_OUTPUT_PATH = os.path.join(PROCESSED_DIR, "university_chunks.json")

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
COLLECTION_NAME = "pakistan_university_admissions"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def load_admission_data():
    with open(ADMISSION_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def make_chunks(records):
    """
    Split each admission record into smaller text chunks.
    One chunk per category: eligibility, entry_test, merit, fee, deadline.
    """
    chunks = []
    for rec in records:
        uni_id = rec.get("university_id", "unknown")
        uni_name = rec.get("university_name", "")
        program = rec.get("program", "Multiple")
        field_type = rec.get("field_type", "")
        city = rec.get("city", "")
        source_url = rec.get("source_url", "")
        status = rec.get("status", "")

        # Category → text field mapping
        categories = [
            ("eligibility", "eligibility_text"),
            ("entry_test", "entry_test_text"),
            ("merit", "merit_text"),
            ("fee", "fee_text"),
            ("deadline", "deadline_text"),
        ]

        for cat_label, field_name in categories:
            text = rec.get(field_name, "")
            if not text or text == "Needs official verification":
                continue

            # Clean the text a bit — remove repeated navigation fragments
            lines = text.split("\n")
            cleaned_lines = [l.strip() for l in lines if l.strip()]
            cleaned = "\n".join(cleaned_lines)

            chunk_text = f"[{cat_label.upper()}] {uni_name}\n\n{cleaned}"

            chunks.append({
                "id": f"{uni_id}_{cat_label}",
                "text": chunk_text,
                "metadata": {
                    "university_id": uni_id,
                    "university_name": uni_name,
                    "program": program,
                    "field_type": field_type,
                    "city": city,
                    "category": cat_label,
                    "source_url": source_url,
                    "status": status,
                }
            })

    return chunks


def build_chroma(chunks):
    """Create embeddings and store in Chroma."""
    os.makedirs(CHROMA_DIR, exist_ok=True)

    # Remove existing Chroma data to rebuild cleanly
    for item in os.listdir(CHROMA_DIR):
        item_path = os.path.join(CHROMA_DIR, item)
        if item != ".gitkeep":
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)

    print(f"Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print(f"Creating Chroma client at: {CHROMA_DIR}")
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    texts = [c["text"] for c in chunks]
    ids = [c["id"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]

    print(f"Generating embeddings for {len(texts)} chunks...")
    embeddings = model.encode(texts, show_progress_bar=True).tolist()

    print("Adding to Chroma collection...")
    collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    return collection


def save_chunks(chunks):
    """Save chunks to JSON for inspection."""
    with open(CHUNKS_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(chunks)} chunks to {CHUNKS_OUTPUT_PATH}")


def build():
    print("=" * 50)
    print("Building RAG Vector Database")
    print("=" * 50)

    # Step 1: Load data
    print("\n[1/4] Loading admission data...")
    records = load_admission_data()
    print(f"  Loaded {len(records)} university records")

    # Step 2: Create chunks
    print("\n[2/4] Creating text chunks...")
    chunks = make_chunks(records)
    print(f"  Created {len(chunks)} chunks")

    # Step 3: Save chunks to JSON
    print("\n[3/4] Saving chunks to JSON...")
    save_chunks(chunks)

    # Step 4: Build Chroma DB
    print("\n[4/4] Building Chroma vector database...")
    build_chroma(chunks)

    print("\n" + "=" * 50)
    print("DONE")
    print(f"  Chunks: {len(chunks)}")
    print(f"  Chunks file: {CHUNKS_OUTPUT_PATH}")
    print(f"  Chroma DB: {CHROMA_DIR}")
    print(f"  Collection: {COLLECTION_NAME}")
    print(f"  Embedding model: {EMBEDDING_MODEL}")
    print("=" * 50)


if __name__ == "__main__":
    build()
