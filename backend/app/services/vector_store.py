import os
import json
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.core.logging import get_logger
from app.utils.chunker import CodeChunk

logger = get_logger(__name__)

# Lazy imports for heavy dependencies
_chroma_client = None
_embedding_model = None


def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        import chromadb
        os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    return _chroma_client


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def get_collection_name(repo_id: int) -> str:
    return f"repo_{repo_id}"


def get_or_create_collection(repo_id: int):
    client = get_chroma_client()
    collection_name = get_collection_name(repo_id)
    try:
        return client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as e:
        logger.error(f"Failed to get/create collection {collection_name}: {e}")
        raise


def embed_texts(texts: List[str]) -> List[List[float]]:
    model = get_embedding_model()
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=False)
    return embeddings.tolist()


def index_chunks(repo_id: int, chunks: List[CodeChunk], batch_size: int = 100) -> int:
    """Index code chunks into ChromaDB. Returns count of indexed chunks."""
    if not chunks:
        return 0

    collection = get_or_create_collection(repo_id)
    indexed = 0

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        ids = [c.chunk_id for c in batch]
        texts = [c.content for c in batch]
        metadatas = [
            {
                "file_path": c.file_path,
                "language": c.language,
                "chunk_type": c.chunk_type,
                "name": c.name,
                "start_line": c.start_line,
                "end_line": c.end_line,
            }
            for c in batch
        ]

        try:
            embeddings = embed_texts(texts)
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
            indexed += len(batch)
        except Exception as e:
            logger.error(f"Failed to index batch {i} for repo {repo_id}: {e}")

    return indexed


def semantic_search(
    repo_id: int,
    query: str,
    n_results: int = 10,
    where: Optional[Dict] = None,
) -> List[Dict[str, Any]]:
    """Run semantic similarity search against a repo's indexed chunks."""
    try:
        collection = get_or_create_collection(repo_id)
        query_embedding = embed_texts([query])[0]

        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(n_results, max(1, collection.count())),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = collection.query(**kwargs)

        output = []
        if results["ids"] and results["ids"][0]:
            for j, chunk_id in enumerate(results["ids"][0]):
                output.append({
                    "chunk_id": chunk_id,
                    "content": results["documents"][0][j],
                    "metadata": results["metadatas"][0][j],
                    "similarity": 1 - results["distances"][0][j],
                })
        return output
    except Exception as e:
        logger.error(f"Semantic search failed for repo {repo_id}: {e}")
        return []


def delete_repo_collection(repo_id: int) -> bool:
    """Delete all indexed data for a repository."""
    try:
        client = get_chroma_client()
        client.delete_collection(get_collection_name(repo_id))
        return True
    except Exception as e:
        logger.error(f"Failed to delete collection for repo {repo_id}: {e}")
        return False


def delete_file_chunks(repo_id: int, file_path: str) -> int:
    """Remove all chunks for a specific file from the index."""
    try:
        collection = get_or_create_collection(repo_id)
        results = collection.get(where={"file_path": file_path})
        if results["ids"]:
            collection.delete(ids=results["ids"])
            return len(results["ids"])
        return 0
    except Exception as e:
        logger.error(f"Failed to delete file chunks for {file_path}: {e}")
        return 0


def get_collection_stats(repo_id: int) -> Dict[str, Any]:
    """Get statistics about the indexed collection."""
    try:
        collection = get_or_create_collection(repo_id)
        count = collection.count()
        return {"total_chunks": count, "repo_id": repo_id}
    except Exception as e:
        logger.error(f"Failed to get collection stats: {e}")
        return {"total_chunks": 0, "repo_id": repo_id}
