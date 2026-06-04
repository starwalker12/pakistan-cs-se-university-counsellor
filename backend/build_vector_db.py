"""
Pakistan CS & SE University Counsellor — Build Vector Database

Reads processed university documents, generates embeddings using
sentence-transformers, and stores them in Chroma (local vector DB).

Usage (future phase):
  python build_vector_db.py
"""

import os
import json

CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "data", "processed")


def build():
    """Placeholder — will load docs, embed, and index into Chroma."""
    os.makedirs(CHROMA_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    print("Vector DB build — placeholder.")
    print(f"  Chroma dir: {CHROMA_DIR}")
    print(f"  Processed data dir: {PROCESSED_DIR}")
    print("  Full implementation will be added in Phase 2.")


if __name__ == "__main__":
    build()
