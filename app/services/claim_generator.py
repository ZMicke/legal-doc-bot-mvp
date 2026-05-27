from datetime import date

from app.services.claim_classifier import CLAIM_TYPE_CONFIG
from app.services.template_renderer import render_template


TEMPLATE_PATH = "app/templates/claim_template.txt"


def clean_value(value: str | None, fallback: str) -> str:
    if value is None or str(value).strip() == "":
        return fallback
    return str(value).strip()


def normalize_contract_value(value: str | None, fallback: str) -> str:
    cleaned = clean_value(value, fallback)
    if cleaned.lower() in {"не определен", "не определена", "не указано", "не найдено"}:
        return fallback
    return cleaned


def format_law_item(item: dict) -> str:
    article = item.get("article")
    title = clean_value(item.get("title"), "правовое основание")
    text = clean_value(item.get("text"), "текст правового основания не указан")
    source_url = item.get("source_url")

    if article:
        base = f"{article} — {title}. {text}"
    else:
        base = f"{title}. {text}"

    if source_url:
        base += f"\nИсточник: {source_url}"

    return base


def format_law_basis(law_articles: list[dict]) -> str:
    if not law_articles:
        return "Подходящие правовые основания не найдены. Требуется ручная правовая проверка."

    return "\n\n".join(
        f"{index}. {format_law_item(item)}"
        for index, item in enumerate(law_articles, start=1)
    )


def get_manual_or_default(manual_fields: dict, key: str, default_value: str) -> str:
    return clean_value(manual_fields.get(key), default_value)


def claim_demands_for_type(
    claim_type: str,
    user_request: str,
    manual_fields: dict,
) -> str:
    penalty = get_manual_or_default(manual_fields, "penalty_amount", "требует уточнения")

    demands = {
        "services_delay": [
            "Устранить нарушение срока оказания услуг.",
            "Исполнить обязательства по договору в полном объеме.",
            f"Выплатить неустойку и/или возместить убытки в размере {penalty}, если применимо.",
            "Направить письменный ответ на настоящую претензию.",
        ],
        "payment_delay": [
            "Погасить задолженность по договору в полном объеме.",
            f"Уплатить проценты, неустойку и/или иные суммы ответственности в размере {penalty}, если применимо.",
            "Направить письменный ответ с указанием срока и порядка погашения задолженности.",
        ],
        "delivery_delay": [
            "Поставить товар в полном объеме в соответствии с условиями договора.",
            f"Уплатить неустойку за нарушение срока поставки в размере {penalty}, если применимо.",
            "Возместить убытки, причиненные нарушением срока поставки, если применимо.",
            "Направить письменный ответ на настоящую претензию.",
        ],
        "defective_goods": [
            "Заменить товар ненадлежащего качества либо устранить выявленные недостатки.",
            "Возместить расходы, уменьшить цену товара или выполнить иное предусмотренное законом требование, если применимо.",
            "Направить письменный ответ на настоящую претензию.",
        ],
        "refund": [
            "Возвратить денежные средства в полном объеме.",
            f"Уплатить проценты, неустойку и/или иные суммы ответственности в размере {penalty}, если применимо.",
            "Направить письменный ответ на настоящую претензию.",
        ],
        "custom": [
            f"Рассмотреть заявленные требования по существу: {clean_value(user_request, 'требования требуют уточнения')}.",
            "Исполнить обязательства по договору надлежащим образом.",
            "Направить письменный ответ на настоящую претензию.",
        ],
    }

    return "\n".join(
        f"{index}. {item}"
        for index, item in enumerate(demands.get(claim_type, demands["custom"]), start=1)
    )


def generate_claim_text(
    contract_text: str,
    user_request: str,
    law_articles: list[dict],
    contract_analysis: dict,
    claim_classification: dict,
    manual_fields: dict | None = None,
) -> str:
    manual_fields = manual_fields or {}
    claim_type = claim_classification.get("claim_type", "custom")
    claim_title = claim_classification.get("claim_title") or CLAIM_TYPE_CONFIG["custom"]["claim_title"]

    context = {
        "recipient_name": get_manual_or_default(
            manual_fields,
            "recipient_name",
            contract_analysis.get("contractor_name", "получатель не определен"),
        ),
        "recipient_address": get_manual_or_default(
            manual_fields,
            "recipient_address",
            contract_analysis.get("contractor_address", "адрес не указан"),
        ),
        "sender_name": get_manual_or_default(
            manual_fields,
            "sender_name",
            contract_analysis.get("customer_name", "отправитель не определен"),
        ),
        "sender_address": get_manual_or_default(
            manual_fields,
            "sender_address",
            contract_analysis.get("customer_address", "адрес не указан"),
        ),
        "claim_title": claim_title,
        "contract_number": normalize_contract_value(
            contract_analysis.get("contract_number"),
            "номер договора не определен",
        ),
        "contract_date": normalize_contract_value(
            contract_analysis.get("contract_date"),
            "дата договора не определена",
        ),
        "contract_subject": normalize_contract_value(contract_analysis.get("subject"), "Не найдено"),
        "violation_description": get_manual_or_default(
            manual_fields,
            "violation_description",
            clean_value(user_request, "описание нарушения требует уточнения"),
        ),
        "violation_date": get_manual_or_default(
            manual_fields,
            "violation_date",
            "дата нарушения не указана",
        ),
        "contract_evidence": "\n\n".join([
            normalize_contract_value(contract_analysis.get("deadlines"), "сроки исполнения: не найдено"),
            normalize_contract_value(contract_analysis.get("liability"), "ответственность: не найдено"),
            normalize_contract_value(contract_analysis.get("claim_procedure"), "претензионный порядок: не найдено"),
        ]),
        "law_basis": format_law_basis(law_articles),
        "claim_demands": claim_demands_for_type(claim_type, user_request, manual_fields),
        "response_deadline": get_manual_or_default(manual_fields, "response_deadline", "10"),
        "claim_date": date.today().strftime("%d.%m.%Y"),
    }

    return render_template(TEMPLATE_PATH, context)


def generate_delay_claim_text(
    contract_text: str,
    user_request: str,
    law_articles: list[dict],
    contract_analysis: dict,
    violation: dict,
    manual_fields: dict | None = None,
) -> str:
    classification = {
        **CLAIM_TYPE_CONFIG["services_delay"],
        "claim_type": "services_delay",
        "confidence": 1.0,
        "explanation": "Обратная совместимость со старым endpoint.",
    }
    return generate_claim_text(
        contract_text=contract_text,
        user_request=user_request,
        law_articles=law_articles,
        contract_analysis=contract_analysis,
        claim_classification=classification,
        manual_fields=manual_fields,
    )
