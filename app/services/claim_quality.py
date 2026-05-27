import re


ARTICLE_PATTERN = re.compile(r"ст\.\s*\d+(?:\.\d+)?\s*ГК\s*РФ", re.IGNORECASE)


def check_manual_fields_preserved(claim_text: str, manual_fields: dict) -> tuple[bool, list[str]]:
    warnings = []
    important_fields = [
        "sender_name",
        "sender_address",
        "recipient_name",
        "recipient_address",
        "violation_date",
        "penalty_amount",
        "response_deadline",
    ]

    for field in important_fields:
        value = manual_fields.get(field)
        if value and str(value).strip() and str(value).strip() not in claim_text:
            warnings.append(f"LLM могла изменить или удалить поле {field}")

    return len(warnings) == 0, warnings


def detect_unexpected_articles(claim_text: str, law_articles: list[dict]) -> list[str]:
    allowed_articles = {
        str(item.get("article") or "").lower()
        for item in law_articles
        if item.get("article")
    }
    found_articles = {
        match.group(0).replace("  ", " ").strip()
        for match in ARTICLE_PATTERN.finditer(claim_text)
    }

    return [
        article
        for article in sorted(found_articles)
        if article.lower() not in allowed_articles
    ]


def evaluate_claim_quality(
    claim_text: str,
    manual_fields: dict,
    law_articles: list[dict],
    claim_classification: dict,
) -> dict:
    warnings = []
    manual_preserved, manual_warnings = check_manual_fields_preserved(claim_text, manual_fields)
    warnings.extend(manual_warnings)

    unexpected_articles = detect_unexpected_articles(claim_text, law_articles)
    if unexpected_articles:
        warnings.append("В тексте обнаружены статьи, отсутствующие в RAG")

    if "**" in claim_text:
        warnings.append("В тексте обнаружены markdown-символы")

    claim_type = claim_classification.get("claim_type")
    services_mentions = claim_text.lower().count("оказания услуг") + claim_text.lower().count("услуг")
    forbidden_topic_shift_detected = claim_type != "services_delay" and services_mentions >= 3

    if forbidden_topic_shift_detected:
        warnings.append(
            f"Тип претензии {claim_type}, но текст содержит много формулировок про оказание услуг"
        )

    quality_metrics = {
        "has_markdown": "**" in claim_text or "__" in claim_text,
        "has_unexpected_articles": len(unexpected_articles) > 0,
        "preserves_manual_fields": manual_preserved,
        "document_length": len(claim_text),
        "paragraphs_count": len(claim_text.split('\n\n')),
        "warnings_count": len(warnings),
    }

    return {
        **quality_metrics,
        "manual_fields_preserved": manual_preserved,
        "forbidden_topic_shift_detected": forbidden_topic_shift_detected,
        "unexpected_articles": unexpected_articles,
        "warnings": warnings,
    }
