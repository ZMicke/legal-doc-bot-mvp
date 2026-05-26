ALLOWED_CLAIM_TYPES = {
    "auto",
    "services_delay",
    "payment_delay",
    "delivery_delay",
    "defective_goods",
    "refund",
    "custom",
}


CLAIM_TYPE_CONFIG = {
    "services_delay": {
        "claim_title": "ПРЕТЕНЗИЯ о нарушении срока оказания услуг",
        "legal_focus": "нарушение срока оказания услуг",
        "required_contract_sections": ["subject", "deadlines", "liability", "claim_procedure"],
        "recommended_articles": ["ст. 309 ГК РФ", "ст. 314 ГК РФ", "ст. 330 ГК РФ", "ст. 779 ГК РФ"],
    },
    "payment_delay": {
        "claim_title": "ПРЕТЕНЗИЯ о погашении задолженности",
        "legal_focus": "неисполнение денежного обязательства",
        "required_contract_sections": ["subject", "deadlines", "liability"],
        "recommended_articles": ["ст. 309 ГК РФ", "ст. 310 ГК РФ", "ст. 314 ГК РФ", "ст. 395 ГК РФ"],
    },
    "delivery_delay": {
        "claim_title": "ПРЕТЕНЗИЯ о нарушении срока поставки товара",
        "legal_focus": "нарушение срока поставки товара",
        "required_contract_sections": ["subject", "deadlines", "liability"],
        "recommended_articles": ["ст. 309 ГК РФ", "ст. 314 ГК РФ", "ст. 330 ГК РФ", "ст. 506 ГК РФ", "ст. 521 ГК РФ"],
    },
    "defective_goods": {
        "claim_title": "ПРЕТЕНЗИЯ о поставке товара ненадлежащего качества",
        "legal_focus": "передача товара ненадлежащего качества",
        "required_contract_sections": ["subject", "liability", "claim_procedure"],
        "recommended_articles": ["ст. 309 ГК РФ", "ст. 469 ГК РФ", "ст. 475 ГК РФ", "ст. 518 ГК РФ"],
    },
    "refund": {
        "claim_title": "ПРЕТЕНЗИЯ о возврате денежных средств",
        "legal_focus": "возврат денежных средств",
        "required_contract_sections": ["subject", "liability", "claim_procedure"],
        "recommended_articles": ["ст. 309 ГК РФ", "ст. 310 ГК РФ", "ст. 1102 ГК РФ"],
    },
    "custom": {
        "claim_title": "ПРЕТЕНЗИЯ",
        "legal_focus": "нарушение договорных обязательств",
        "required_contract_sections": ["subject", "liability", "claim_procedure"],
        "recommended_articles": ["ст. 309 ГК РФ", "ст. 310 ГК РФ"],
    },
}


CLAIM_KEYWORDS = {
    "services_delay": ["услуг", "оказан", "просрочк", "срок оказания", "исполнитель"],
    "payment_delay": ["неуплат", "не оплат", "неоплат", "задолж", "долг", "погаш", "денежн"],
    "delivery_delay": ["поставк", "недопостав", "просрочк постав", "товар не постав"],
    "defective_goods": ["брак", "некачествен", "ненадлежащего качества", "дефект", "недостатк"],
    "refund": ["возврат", "вернуть денеж", "денежных средств", "неосновательн"],
}


def classify_claim(
    user_request: str,
    contract_analysis: dict,
    requested_claim_type: str = "auto",
) -> dict:
    requested_claim_type = (requested_claim_type or "auto").strip()

    if requested_claim_type not in ALLOWED_CLAIM_TYPES:
        requested_claim_type = "auto"

    if requested_claim_type != "auto":
        config = CLAIM_TYPE_CONFIG[requested_claim_type]
        return {
            "claim_type": requested_claim_type,
            "claim_title": config["claim_title"],
            "legal_focus": config["legal_focus"],
            "required_contract_sections": config["required_contract_sections"],
            "recommended_articles": config["recommended_articles"],
            "confidence": 1.0,
            "explanation": "Тип претензии выбран пользователем.",
        }

    searchable_text = " ".join([
        user_request or "",
        str(contract_analysis.get("subject", "")),
        str(contract_analysis.get("deadlines", "")),
        str(contract_analysis.get("liability", "")),
    ]).lower()

    scores = {
        claim_type: sum(1 for keyword in keywords if keyword in searchable_text)
        for claim_type, keywords in CLAIM_KEYWORDS.items()
    }

    best_type = max(scores, key=scores.get)
    best_score = scores[best_type]

    if best_score == 0:
        best_type = "custom"
        confidence = 0.35
        explanation = "Не найдено устойчивых признаков конкретного типа претензии."
    else:
        confidence = min(0.95, 0.45 + best_score * 0.18)
        explanation = f"Тип определен по ключевым признакам запроса и договора: score={best_score}."

    config = CLAIM_TYPE_CONFIG[best_type]

    return {
        "claim_type": best_type,
        "claim_title": config["claim_title"],
        "legal_focus": config["legal_focus"],
        "required_contract_sections": config["required_contract_sections"],
        "recommended_articles": config["recommended_articles"],
        "confidence": confidence,
        "explanation": explanation,
    }
