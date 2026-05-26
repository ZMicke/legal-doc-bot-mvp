import json
from pathlib import Path

from app.services.rag.knowledge_store import load_custom_knowledge
from app.services.rag.vector_store import get_vector_error, search_vector_store
from app.services.web_legal_search import web_legal_fallback


LAW_PATH = Path("app/knowledge/law_gk.json")

CLAIM_TYPE_REQUIRED_ARTICLES = {
    "services_delay": ["ст. 309 ГК РФ", "ст. 314 ГК РФ", "ст. 330 ГК РФ", "ст. 779 ГК РФ"],
    "payment_delay": ["ст. 309 ГК РФ", "ст. 310 ГК РФ", "ст. 314 ГК РФ", "ст. 395 ГК РФ"],
    "delivery_delay": ["ст. 309 ГК РФ", "ст. 314 ГК РФ", "ст. 330 ГК РФ", "ст. 506 ГК РФ", "ст. 521 ГК РФ"],
    "defective_goods": ["ст. 309 ГК РФ", "ст. 469 ГК РФ", "ст. 475 ГК РФ", "ст. 518 ГК РФ"],
    "refund": ["ст. 309 ГК РФ", "ст. 310 ГК РФ", "ст. 1102 ГК РФ"],
    "custom": ["ст. 309 ГК РФ", "ст. 310 ГК РФ"],
}


def load_law_base() -> list[dict]:
    if not LAW_PATH.exists():
        return []

    with LAW_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def score_text(query: str, text: str) -> int:
    query_words = {
        word.strip(".,:;()[]{}\"'").lower()
        for word in query.split()
        if len(word.strip(".,:;()[]{}\"'")) >= 4
    }
    text_lower = text.lower()

    return sum(1 for word in query_words if word in text_lower)


def normalize_law_item(item: dict, source: str = "base_law") -> dict:
    return {
        "source": source,
        "title": item.get("title"),
        "article": item.get("article"),
        "text": item.get("text") or item.get("content"),
        "source_url": item.get("source_url"),
        "source_type": item.get("source_type"),
    }


def normalize_custom_item(item: dict) -> dict:
    return {
        "source": "custom_knowledge",
        "title": item.get("title"),
        "article": item.get("article"),
        "text": item.get("content"),
        "source_url": item.get("source_url"),
        "source_type": item.get("source_type"),
    }


def article_key(item: dict) -> str:
    return " | ".join(
        str(item.get(key) or "").strip().lower()
        for key in ("source", "article", "title", "source_url")
    )


def unique_items(items: list[dict]) -> list[dict]:
    result = []
    seen = set()

    for item in items:
        key = article_key(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)

    return result


def required_articles_for_claim(
    claim_type: str | None,
    required_articles: list[str] | None = None,
) -> list[str]:
    result = list(CLAIM_TYPE_REQUIRED_ARTICLES.get(claim_type or "custom", []))

    for article in required_articles or []:
        if article not in result:
            result.append(article)

    return result


def add_required_articles(
    items: list[dict],
    base_law: list[dict],
    required_articles: list[str],
) -> list[dict]:
    existing_articles = {
        str(item.get("article") or "").lower()
        for item in items
    }

    for article in required_articles:
        if article.lower() in existing_articles:
            continue

        found = next(
            (
                item
                for item in base_law
                if str(item.get("article") or "").lower() == article.lower()
            ),
            None,
        )

        if found:
            normalized = normalize_law_item(found)
            normalized["score"] = 999
            normalized["mandatory"] = True
            items.append(normalized)

    return items


def retrieve_law_articles(
    query: str,
    claim_type: str | None = None,
    required_articles: list[str] | None = None,
    top_k: int = 8,
) -> list[dict]:
    result = retrieve_law_articles_with_fallback(
        query=query,
        claim_type=claim_type,
        required_articles=required_articles,
        top_k=top_k,
        use_web=False,
    )
    return result["items"]


def retrieve_law_articles_with_fallback(
    query: str,
    claim_type: str | None = None,
    required_articles: list[str] | None = None,
    top_k: int = 8,
    use_web: bool = True,
) -> dict:
    base_law = load_law_base()
    custom_knowledge = load_custom_knowledge()
    required = required_articles_for_claim(claim_type, required_articles)

    candidates = []

    for item in base_law:
        text_for_search = " ".join([
            item.get("article", ""),
            item.get("title", ""),
            " ".join(item.get("keywords", [])),
            item.get("text", ""),
        ])
        score = score_text(query, text_for_search)

        if score > 0:
            normalized = normalize_law_item(item)
            normalized["score"] = score
            candidates.append(normalized)

    for item in custom_knowledge:
        text_for_search = " ".join([
            item.get("title", ""),
            item.get("source_type", ""),
            item.get("content", ""),
            item.get("source_url", "") or "",
        ])
        score = score_text(query, text_for_search)

        if score > 0:
            normalized = normalize_custom_item(item)
            normalized["score"] = score
            candidates.append(normalized)

    candidates.extend(search_vector_store(query, top_k=top_k))
    candidates.sort(key=lambda item: item.get("score", 0), reverse=True)
    candidates = unique_items(candidates)

    relevant_count = len(candidates)
    candidates = add_required_articles(candidates, base_law, required)

    web_fallback_used = False
    web_error = None

    if use_web and relevant_count < 2:
        web_result = web_legal_fallback(query)
        web_fallback_used = bool(web_result.get("used"))
        web_error = web_result.get("web_error")
        candidates.extend(web_result.get("items", []))
        candidates = unique_items(candidates)
        candidates = add_required_articles(candidates, base_law, required)

    candidates.sort(
        key=lambda item: (item.get("mandatory", False), item.get("score", 0)),
        reverse=True,
    )

    return {
        "items": candidates[:top_k],
        "web_fallback_used": web_fallback_used,
        "web_error": web_error,
        "vector_error": get_vector_error(),
        "required_articles": required,
    }
