from datetime import date

from app.services.template_renderer import render_template


TEMPLATE_PATH = "app/templates/delay_claim_template.txt"


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


def get_manual_or_default(
    manual_fields: dict,
    key: str,
    default_value: str,
) -> str:
    return clean_value(manual_fields.get(key), default_value)


def generate_delay_claim_text(
    contract_text: str,
    user_request: str,
    law_articles: list[dict],
    contract_analysis: dict,
    violation: dict,
    manual_fields: dict | None = None,
) -> str:
    manual_fields = manual_fields or {}

    violation_description = get_manual_or_default(
        manual_fields,
        "violation_description",
        violation.get(
            "summary",
            "обязательства по договору исполнены ненадлежащим образом",
        ),
    )

    violation_date = get_manual_or_default(
        manual_fields,
        "violation_date",
        "дата нарушения не указана",
    )

    penalty_amount = get_manual_or_default(
        manual_fields,
        "penalty_amount",
        "размер неустойки требует уточнения",
    )

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
        "contract_number": normalize_contract_value(
            contract_analysis.get("contract_number"),
            "номер договора не определен",
        ),
        "contract_date": normalize_contract_value(
            contract_analysis.get("contract_date"),
            "дата договора не определена",
        ),
        "contract_subject": normalize_contract_value(
            contract_analysis.get("subject"),
            "Не найдено",
        ),
        "contract_deadline": normalize_contract_value(
            contract_analysis.get("deadlines"),
            "Не найдено",
        ),
        "violation_date": violation_date,
        "violation_description": violation_description,
        "contract_evidence": normalize_contract_value(
            contract_analysis.get("deadlines"),
            "Не найдено",
        ),
        "law_basis": format_law_basis(law_articles),
        "response_deadline": get_manual_or_default(
            manual_fields,
            "response_deadline",
            "10",
        ),
        "penalty_amount": penalty_amount,
        "claim_date": date.today().strftime("%d.%m.%Y"),
    }

    return render_template(TEMPLATE_PATH, context)
