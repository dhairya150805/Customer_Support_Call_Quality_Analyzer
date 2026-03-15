import chromadb
from chromadb.utils import embedding_functions
import os
from dotenv import load_dotenv

load_dotenv()

# ─── ChromaDB persistent client ─────────────────────────────────────────────
CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_store")

chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

# Use Gemini embeddings via the google-genai embedding model
# ChromaDB's built-in default embedding function (sentence-transformers) is used
# as a lightweight local option — swap for Gemini embeddings if desired
embedding_fn = embedding_functions.DefaultEmbeddingFunction()

COLLECTION_NAME = "support_complaints"


def get_collection():
    """Get or create the support complaints collection."""
    return chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )


def add_documents(documents: list[dict]):
    """
    Add documents to the vector store.
    Each document: {"id": str, "text": str, "metadata": dict}
    """
    collection = get_collection()
    collection.add(
        ids=[doc["id"] for doc in documents],
        documents=[doc["text"] for doc in documents],
        metadatas=[doc.get("metadata", {}) for doc in documents],
    )
    print(f"✅ Added {len(documents)} documents to vector store.")


def search_documents(query: str, n_results: int = 5) -> list[dict]:
    """
    Search the vector store for the most relevant documents.
    Returns a list of {'text': ..., 'metadata': ...} dicts.
    """
    collection = get_collection()
    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    if results and results["documents"]:
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            hits.append({"text": doc, "metadata": meta, "distance": dist})
    return hits
