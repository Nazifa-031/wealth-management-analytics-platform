"""
Step 2: Build Vector Index - embeddings + ChromaDB, batched to stay under
ChromaDB's max batch size (this was the actual cause of "retrieved 0 chunks"
in your last run - collection.add() crashed partway through, so the store
never got populated).
"""

import json
import os
import chromadb
from sentence_transformers import SentenceTransformer

DOCUMENTS_DIR = "documents"
CHROMA_DIR = "chroma_store"
COLLECTION_NAME = "client_portfolios"
BATCH_SIZE = 2000  # comfortably under ChromaDB's default max (~5461)


def main():
    manifest_path = os.path.join(DOCUMENTS_DIR, "_manifest.json")
    if not os.path.exists(manifest_path):
        raise SystemExit("No documents found. Run 01_prepare_documents.py first.")

    with open(manifest_path) as f:
        manifest = json.load(f)

    print("Loading embedding model (first run downloads it)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    texts = [item["text"] for item in manifest]
    ids = [item["chunk_id"] for item in manifest]
    metadatas = [item["metadata"] for item in manifest]

    print(f"Embedding {len(texts)} chunks...")
    embeddings = model.encode(texts, show_progress_bar=True).tolist()

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(COLLECTION_NAME)

    total = len(ids)
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        collection.add(
            ids=ids[start:end],
            embeddings=embeddings[start:end],
            documents=texts[start:end],
            metadatas=metadatas[start:end],
        )
        print(f"  Added batch {start}-{end} of {total}")

    print(f"Stored {total} embeddings in '{CHROMA_DIR}/' (collection: {COLLECTION_NAME})")


if __name__ == "__main__":
    main()