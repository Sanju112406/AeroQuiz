"""
rag/ingest.py
─────────────
Ingest aircraft maintenance manuals (PDFs) into ChromaDB vector store.

Usage:
    python rag/ingest.py --manuals-dir ./manuals
    python rag/ingest.py --file ./manuals/AMM-747.pdf
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from pypdf import PdfReader
from tqdm import tqdm
import chromadb
from chromadb.config import Settings

# ── Embedding backend ────────────────────────────────────────────────────────
EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "local")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chromadb")

CHUNK_SIZE = 800       # characters per chunk
CHUNK_OVERLAP = 150    # overlap between chunks


def get_embedding_function():
    """Return embedding function based on configured backend."""
    if EMBEDDING_BACKEND == "openai":
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        return OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        )
    else:
        # Local sentence-transformers — no API key needed
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        return SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )


def extract_text_from_pdf(pdf_path: Path) -> list[dict]:
    """Extract text from PDF, returning list of {page, text} dicts."""
    reader = PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append({"page": i + 1, "text": text})
    return pages


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def ingest_pdf(pdf_path: Path, collection) -> int:
    """Ingest a single PDF into the vector collection. Returns chunk count."""
    manual_name = pdf_path.stem
    pages = extract_text_from_pdf(pdf_path)

    all_chunks = []
    all_ids = []
    all_metadata = []

    for page_data in pages:
        page_num = page_data["page"]
        chunks = chunk_text(page_data["text"])

        for chunk_idx, chunk in enumerate(chunks):
            chunk_id = f"{manual_name}__p{page_num}__c{chunk_idx}"
            all_chunks.append(chunk)
            all_ids.append(chunk_id)
            all_metadata.append({
                "manual": manual_name,
                "page": page_num,
                "chunk_index": chunk_idx,
                "source": str(pdf_path),
            })

    # Upsert in batches of 100
    batch_size = 100
    for i in range(0, len(all_chunks), batch_size):
        collection.upsert(
            documents=all_chunks[i:i+batch_size],
            ids=all_ids[i:i+batch_size],
            metadatas=all_metadata[i:i+batch_size],
        )

    return len(all_chunks)


def main():
    parser = argparse.ArgumentParser(description="Ingest aircraft manuals into RAG vector store")
    parser.add_argument("--manuals-dir", type=Path, default=Path("./manuals"),
                        help="Directory containing PDF manuals")
    parser.add_argument("--file", type=Path, help="Ingest a single PDF file")
    parser.add_argument("--reset", action="store_true",
                        help="Delete existing collection before ingesting")
    args = parser.parse_args()

    # ── Connect to ChromaDB ──────────────────────────────────────────────────
    persist_dir = Path(CHROMA_PERSIST_DIR)
    persist_dir.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(persist_dir))
    embedding_fn = get_embedding_function()

    if args.reset:
        try:
            client.delete_collection("aircraft_manuals")
            print("⚠️  Existing collection deleted.")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name="aircraft_manuals",
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )

    # ── Collect PDFs ─────────────────────────────────────────────────────────
    if args.file:
        pdfs = [args.file]
    else:
        pdfs = list(args.manuals_dir.glob("**/*.pdf"))

    if not pdfs:
        print("❌ No PDF files found. Drop manuals into ./manuals/ and re-run.")
        sys.exit(1)

    print(f"📚 Found {len(pdfs)} manual(s) to ingest...")

    total_chunks = 0
    for pdf_path in tqdm(pdfs, desc="Ingesting manuals"):
        chunks = ingest_pdf(pdf_path, collection)
        print(f"   ✅ {pdf_path.name}: {chunks} chunks")
        total_chunks += chunks

    print(f"\n🎉 Done! {total_chunks} total chunks indexed in ChromaDB.")
    print(f"   📂 Vector store: {persist_dir.resolve()}")
    print(f"   📊 Collection size: {collection.count()} documents")


if __name__ == "__main__":
    main()
