import re


def find_section(text: str, keywords: list[str], window: int = 700) -> str:
    lower_text = text.lower()

    for keyword in keywords:
        position = lower_text.find(keyword.lower())

        if position != -1:
            start = max(position - 200, 0)
            end = min(position + window, len(text))
            return text[start:end].strip()

    return "Не найдено"


def extract_contract_number(text: str) -> str:
    patterns = [
        r"договор\s*№\s*([А-Яа-яA-Za-z0-9\-\/]+)",
        r"договор\s*N\s*([А-Яа-яA-Za-z0-9\-\/]+)",
        r"№\s*([А-Яа-яA-Za-z0-9\-\/]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return "не определен"


def extract_contract_date(text: str) -> str:
    patterns = [
        r"от\s*(\d{1,2}\.\d{1,2}\.\d{4})",
        r"от\s*(\d{1,2}\s+[а-яА-Я]+\s+\d{4}\s*г\.?)",
        r"(\d{1,2}\.\d{1,2}\.\d{4})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return "не определена"


def extract_party(text: str, role: str) -> str:
    patterns = [
        rf"{role}\s*[:\-]?\s*([А-ЯA-ZЁ][^,\n]{{5,180}})",
        rf"именуем[а-я\s]+в дальнейшем\s+[\"«]?{role}[\"»]?.{{0,80}}?([А-ЯA-ZЁ][^,\n]{{5,180}})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return " ".join(match.group(1).split())

    return "не определен"


def extract_address(text: str, role: str) -> str:
    role_position = text.lower().find(role.lower())

    if role_position == -1:
        return "не указано"

    fragment = text[role_position:role_position + 1500]

    address_patterns = [
        r"адрес\s*[:\-]?\s*([^\n]{10,200})",
        r"место нахождения\s*[:\-]?\s*([^\n]{10,200})",
        r"юридический адрес\s*[:\-]?\s*([^\n]{10,200})",
    ]

    for pattern in address_patterns:
        match = re.search(pattern, fragment, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return "не указано"


def analyze_contract_text(text: str) -> dict:
    customer = extract_party(text, "Заказчик")
    contractor = extract_party(text, "Исполнитель")

    return {
        "contract_number": extract_contract_number(text),
        "contract_date": extract_contract_date(text),

        "customer_name": customer,
        "contractor_name": contractor,
        "customer_address": extract_address(text, "Заказчик"),
        "contractor_address": extract_address(text, "Исполнитель"),

        "parties": find_section(
            text,
            ["заказчик", "исполнитель", "стороны"]
        ),
        "subject": find_section(
            text,
            ["предмет договора", "оказание услуг", "исполнитель обязуется"]
        ),
        "deadlines": find_section(
            text,
            ["срок оказания услуг", "срок выполнения", "срок исполнения", "до "]
        ),
        "liability": find_section(
            text,
            ["ответственность сторон", "неустойка", "пеня", "штраф"]
        ),
        "claim_procedure": find_section(
            text,
            ["претензионный порядок", "претензия", "досудебный порядок"]
        ),
    }


def detect_delay_violation(analysis: dict) -> dict:
    deadlines = analysis.get("deadlines", "")
    liability = analysis.get("liability", "")

    has_deadline = deadlines != "Не найдено"
    has_liability = liability != "Не найдено"

    return {
        "violation_type": "Просрочка оказания услуг",
        "has_deadline_clause": has_deadline,
        "has_liability_clause": has_liability,
        "summary": (
            "В договоре обнаружены условия о сроках оказания услуг. "
            "При наличии факта нарушения можно формировать претензию по просрочке."
            if has_deadline
            else "Условия о сроках явно не найдены. Требуется ручная проверка договора."
        )
    }
