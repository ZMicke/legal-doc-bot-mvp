import json
from pathlib import Path
from uuid import uuid4

from app.services.rag.vector_store import (
    add_text_to_vector_store,
    clear_vector_store,
    get_vector_error,
)


KNOWLEDGE_PATH = Path("app/knowledge/custom_knowledge.json")


def ensure_knowledge_file():
    KNOWLEDGE_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not KNOWLEDGE_PATH.exists():
        KNOWLEDGE_PATH.write_text("[]", encoding="utf-8")


def load_custom_knowledge() -> list[dict]:
    ensure_knowledge_file()

    with KNOWLEDGE_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_custom_knowledge(items: list[dict]) -> None:
    ensure_knowledge_file()

    with KNOWLEDGE_PATH.open("w", encoding="utf-8") as file:
        json.dump(items, file, ensure_ascii=False, indent=2)


def add_knowledge_item(
    title: str,
    source_type: str,
    content: str,
    source_url: str | None = None,
) -> dict:
    items = load_custom_knowledge()

    item = {
        "id": str(uuid4()),
        "title": title,
        "source_type": source_type,
        "source_url": source_url,
        "content": content,
    }

    items.append(item)
    save_custom_knowledge(items)
    chunks_count = add_text_to_vector_store(
        title=title,
        source_type=source_type,
        content=content,
        source_url=source_url,
    )

    item["vector_chunks_count"] = chunks_count
    item["vector_error"] = get_vector_error()
    save_custom_knowledge(items)

    return item

def reindex_custom_knowledge() -> dict:
    items = load_custom_knowledge()

    vector_error = None

    try:
        clear_vector_store()
    except Exception as error:
        vector_error = str(error)

    total_chunks = 0
    reindexed_items = []

    for item in items:
        chunks_count = add_text_to_vector_store(
            title=item.get("title", "Без названия"),
            source_type=item.get("source_type", "custom"),
            content=item.get("content", ""),
            source_url=item.get("source_url"),
        )

        item["vector_chunks_count"] = chunks_count
        item["vector_error"] = get_vector_error()
        total_chunks += chunks_count
        reindexed_items.append(item)

    save_custom_knowledge(items)

    return {
        "items_count": len(items),
        "total_chunks": total_chunks,
        "vector_error": vector_error or get_vector_error(),
        "items": reindexed_items,
    }
