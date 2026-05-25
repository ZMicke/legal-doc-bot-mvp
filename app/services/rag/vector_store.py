from uuid import uuid4

from app.config import settings
from app.services.rag.text_chunker import split_text_into_chunks


_model = None
_vector_error = None


def get_vector_error() -> str | None:
    return _vector_error


def set_vector_error(error: Exception) -> None:
    global _vector_error
    _vector_error = str(error)


def clear_vector_error() -> None:
    global _vector_error
    _vector_error = None


def get_embedding_model():
    global _model

    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.EMBEDDING_MODEL)

    return _model


def embed_passages(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()

    prepared_texts = [f"passage: {text}" for text in texts]

    embeddings = model.encode(
        prepared_texts,
        normalize_embeddings=True,
    )

    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    model = get_embedding_model()

    embedding = model.encode(
        f"query: {query}",
        normalize_embeddings=True,
    )

    return embedding.tolist()


def get_chroma_collection():
    import chromadb

    client = chromadb.PersistentClient(path=settings.CHROMA_DIR)

    return client.get_or_create_collection(
        name="legal_knowledge"
    )


def add_text_to_vector_store(
    title: str,
    source_type: str,
    content: str,
    source_url: str | None = None,
) -> int:
    clear_vector_error()

    try:
        collection = get_chroma_collection()
    except Exception as error:
        set_vector_error(error)
        return 0

    chunks = split_text_into_chunks(content)

    if not chunks:
        return 0

    ids = []
    metadatas = []

    for index, chunk in enumerate(chunks):
        ids.append(str(uuid4()))
        metadatas.append({
            "title": title,
            "source_type": source_type,
            "source_url": source_url or "",
            "chunk_index": index,
        })

    try:
        embeddings = embed_passages(chunks)
    except Exception as error:
        set_vector_error(error)
        return 0

    try:
        collection.add(
            ids=ids,
            documents=chunks,
            metadatas=metadatas,
            embeddings=embeddings,
        )
    except Exception as error:
        set_vector_error(error)
        return 0

    return len(chunks)


def search_vector_store(
    query: str,
    top_k: int = 5,
) -> list[dict]:
    clear_vector_error()

    try:
        collection = get_chroma_collection()
        query_embedding = embed_query(query)

        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )
    except Exception as error:
        set_vector_error(error)
        return []

    items = []

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    for document, metadata, distance in zip(documents, metadatas, distances):
        items.append({
            "source": "vector_db",
            "title": metadata.get("title"),
            "article": None,
            "text": document,
            "source_url": metadata.get("source_url") or None,
            "source_type": metadata.get("source_type"),
            "score": float(1 - distance),
        })

    return items

def clear_vector_store() -> None:
    import chromadb

    client = chromadb.PersistentClient(path=settings.CHROMA_DIR)

    try:
        client.delete_collection(name="legal_knowledge")
    except Exception:
        pass

    client.get_or_create_collection(name="legal_knowledge")
