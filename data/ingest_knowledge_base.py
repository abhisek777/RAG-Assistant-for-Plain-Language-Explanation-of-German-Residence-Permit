"""
Knowledge Base Ingestion Script
Chunks, embeds, and indexes official German immigration documents into Qdrant.

Usage:
    python ingest_knowledge_base.py --source_dir ./sources/ --collection immigration_knowledge_base

Sources to add to ./sources/:
  - AufenthG.txt       (German Residence Act — copy from gesetze-im-internet.de)
  - AufenthV.txt       (Residence Ordinance)
  - BAMF_guidance.txt  (BAMF official guidance PDFs, extracted text)
  - BfA_info.txt       (Federal Foreign Office information)
"""

import os
import uuid
import argparse
from pathlib import Path
from typing import Generator

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

COLLECTION_NAME = "immigration_knowledge_base"
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
CHUNK_SIZE = 512       # tokens (approximate by characters: ~4 chars/token)
CHUNK_OVERLAP = 50
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")

# Document metadata map: filename → (source_name, doc_type, url)
SOURCE_METADATA = {
    "AufenthG.txt": ("Aufenthaltsgesetz (AufenthG)", "law", "https://www.gesetze-im-internet.de/aufenthg_2004/"),
    "AufenthV.txt": ("Aufenthaltsverordnung (AufenthV)", "ordinance", "https://www.gesetze-im-internet.de/aufenthv/"),
    "BAMF_guidance.txt": ("BAMF Official Guidance", "guidance", "https://www.bamf.de"),
    "BfA_info.txt": ("Federal Foreign Office — Visa Information", "info", "https://www.auswaertiges-amt.de/en/visa-service"),
}


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE * 4, overlap: int = CHUNK_OVERLAP * 4) -> Generator[str, None, None]:
    """Sliding window chunking by character count (proxy for tokens)."""
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        # Try to break at a sentence boundary
        if end < len(text):
            for sep in ['. ', '.\n', '\n\n', '\n']:
                idx = text.rfind(sep, start, end)
                if idx > start + chunk_size // 2:
                    end = idx + len(sep)
                    break
        yield text[start:end].strip()
        start = end - overlap


def ingest(source_dir: str):
    print(f"Initialising embedder: {EMBEDDING_MODEL}")
    embedder = SentenceTransformer(EMBEDDING_MODEL)

    print(f"Connecting to Qdrant at {QDRANT_URL}")
    client = QdrantClient(url=QDRANT_URL)

    # Recreate collection
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in existing:
        print(f"Deleting existing collection: {COLLECTION_NAME}")
        client.delete_collection(COLLECTION_NAME)

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
    )
    print(f"Created collection: {COLLECTION_NAME}")

    total_chunks = 0
    source_path = Path(source_dir)

    for filename, (source_name, doc_type, url) in SOURCE_METADATA.items():
        filepath = source_path / filename
        if not filepath.exists():
            print(f"  SKIP (not found): {filename}")
            continue

        print(f"Processing: {filename}")
        text = filepath.read_text(encoding="utf-8")
        chunks = list(chunk_text(text))
        print(f"  Chunks: {len(chunks)}")

        points = []
        for i, chunk in enumerate(chunks):
            # e5 models require "passage: " prefix for documents
            embedding = embedder.encode(f"passage: {chunk}", normalize_embeddings=True).tolist()
            point_id = str(uuid.uuid4())
            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "text": chunk,
                    "source_name": source_name,
                    "doc_type": doc_type,
                    "url": url,
                    "filename": filename,
                    "chunk_index": i,
                    "section": _extract_section(chunk),
                }
            ))

        # Batch upsert
        batch_size = 50
        for i in range(0, len(points), batch_size):
            client.upsert(collection_name=COLLECTION_NAME, points=points[i:i+batch_size])

        total_chunks += len(chunks)
        print(f"  Indexed {len(chunks)} chunks from {filename}")

    print(f"\nIngestion complete. Total chunks indexed: {total_chunks}")


def _extract_section(text: str) -> str:
    """Try to extract a section/paragraph number from chunk text."""
    import re
    match = re.search(r'§\s*\d+[a-z]?\s+\w+', text[:100])
    return match.group(0) if match else ""


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source_dir", default="./sources", help="Directory containing source text files")
    args = parser.parse_args()
    ingest(args.source_dir)
