"""
rag/retriever.py
────────────────
Query ChromaDB to retrieve relevant manual chunks for quiz generation.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

import chromadb

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chromadb")
EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "local")
TOP_K = 5  # number of chunks to retrieve per query


def get_embedding_function():
    if EMBEDDING_BACKEND == "openai":
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        return OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        )
    else:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        return SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")


class ManualRetriever:
    def __init__(self):
        persist_dir = Path(CHROMA_PERSIST_DIR)
        if not persist_dir.exists():
            raise FileNotFoundError(
                f"Vector store not found at {persist_dir}. "
                "Run `python rag/ingest.py` first."
            )

        client = chromadb.PersistentClient(path=str(persist_dir))
        embedding_fn = get_embedding_function()

        self.collection = client.get_collection(
            name="aircraft_manuals",
            embedding_function=embedding_fn,
        )

    def retrieve(self, query: str, top_k: int = TOP_K, manual_filter: str = None) -> list[dict]:
        """
        Retrieve top-k relevant chunks for a given query.

        Args:
            query: Natural language query (e.g. "hydraulic system failure procedures")
            top_k: Number of chunks to return
            manual_filter: Optional — restrict to a specific manual name

        Returns:
            List of dicts with keys: text, manual, page, score
        """
        where = {"manual": manual_filter} if manual_filter else None

        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where,
        )

        chunks = []
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0]

        for doc, meta, dist in zip(docs, metas, distances):
            chunks.append({
                "text": doc,
                "manual": meta.get("manual", "Unknown"),
                "page": meta.get("page", "?"),
                "score": round(1 - dist, 3),  # cosine similarity
                "source": meta.get("source", ""),
            })

        return chunks

    def list_manuals(self) -> list[str]:
        """Return all unique manual names in the collection."""
        results = self.collection.get(include=["metadatas"])
        manuals = set()
        for meta in results["metadatas"]:
            if "manual" in meta:
                manuals.add(meta["manual"])
        return sorted(manuals)

    def list_topics(self) -> list[dict]:
        """
        Return topics grouped by manual.
        Each entry: {"manual": str, "topics": [str, ...]}
        Topics are derived from section headings stored in metadata,
        or fall back to the manual name itself.
        """
        results = self.collection.get(include=["metadatas"])
        # Group by manual, collect unique section/topic values
        manual_topics: dict[str, set] = {}
        for meta in results["metadatas"]:
            manual = meta.get("manual", "Unknown")
            section = meta.get("section") or meta.get("topic") or None
            if manual not in manual_topics:
                manual_topics[manual] = set()
            if section:
                manual_topics[manual].add(section)

        grouped = []
        for manual in sorted(manual_topics.keys()):
            topics = sorted(manual_topics[manual])
            grouped.append({"manual": manual, "topics": topics})
        return grouped

    def random_topic_chunks(self, top_k: int = TOP_K) -> list[dict]:
        """
        Return a random set of chunks (used when no specific topic is requested).
        Picks a random offset to vary quiz topics across sessions.
        """
        import random
        total = self.collection.count()
        if total == 0:
            return []

        offset = random.randint(0, max(0, total - top_k))
        results = self.collection.get(
            limit=top_k,
            offset=offset,
            include=["documents", "metadatas"],
        )

        chunks = []
        for doc, meta in zip(results["documents"], results["metadatas"]):
            chunks.append({
                "text": doc,
                "manual": meta.get("manual", "Unknown"),
                "page": meta.get("page", "?"),
                "score": 1.0,
                "source": meta.get("source", ""),
            })
        return chunks
