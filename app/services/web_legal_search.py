import re
from urllib.parse import urlparse

from app.config import settings
from app.services.rag.knowledge_store import add_knowledge_item
from app.services.url_loader import load_text_from_url


TRUSTED_DOMAINS = (
    "pravo.gov.ru",
    "consultant.ru",
    "garant.ru",
    "government.ru",
    "minjust.gov.ru",
)


def is_trusted_legal_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host == domain or host.endswith(f".{domain}") for domain in TRUSTED_DOMAINS)


def extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s,;]+", text)


def configured_urls() -> list[str]:
    urls = []

    if settings.WEB_FALLBACK_URLS:
        urls.extend(
            url.strip()
            for url in settings.WEB_FALLBACK_URLS.split(",")
            if url.strip()
        )

    return urls


def official_urls_for_query(query: str) -> list[str]:
    urls = configured_urls()
    urls.extend(extract_urls(query))

    trusted_urls = []
    seen = set()

    for url in urls:
        clean_url = url.strip().rstrip(").]")
        if clean_url in seen or not is_trusted_legal_url(clean_url):
            continue
        seen.add(clean_url)
        trusted_urls.append(clean_url)

    return trusted_urls


def web_legal_fallback(query: str) -> dict:
    urls = official_urls_for_query(query)

    if not urls:
        return {
            "used": False,
            "web_error": (
                "Нет настроенных официальных URL для web fallback. "
                "Добавьте WEB_FALLBACK_URLS в .env или передайте URL в запросе."
            ),
            "items": [],
        }

    items = []
    errors = []

    for url in urls:
        try:
            text = load_text_from_url(url)
        except Exception as error:
            errors.append(f"{url}: {error}")
            continue

        if not text.strip():
            errors.append(f"{url}: пустой текст")
            continue

        title = f"Официальный правовой источник: {urlparse(url).netloc}"
        saved_item = add_knowledge_item(
            title=title,
            source_type="web_fallback",
            content=text,
            source_url=url,
        )

        items.append({
            "source": "web_fallback",
            "title": title,
            "article": None,
            "text": text[:3000],
            "source_url": url,
            "source_type": "web_fallback",
            "score": 1,
            "knowledge_item_id": saved_item.get("id"),
        })

    return {
        "used": True,
        "web_error": "; ".join(errors) if errors else None,
        "items": items,
    }
