import requests

from app.config import settings


class LLMError(Exception):
    pass


def build_claim_improvement_prompt(
    draft_claim: str,
    contract_analysis: dict,
    law_articles: list[dict],
    user_request: str,
    manual_fields: dict | None = None,
    claim_classification: dict | None = None,
) -> str:
    manual_fields = manual_fields or {}
    claim_classification = claim_classification or {}

    return f"""
Ты юридический помощник предприятия.

Сформируй итоговую претензию строго в соответствии с claim_type и claim_title.
Если claim_type=payment_delay, не используй формулировки про оказание услуг, если это прямо не следует из договора.
Если claim_type отличается от services_delay, не превращай документ в претензию по оказанию услуг.

Результат — только текст официального документа без Markdown.
Не добавляй комментарии, пояснения, вступления вроде "Вот исправленный вариант".

КРИТИЧЕСКИ ВАЖНО:
1. Не меняй тип претензии и заголовок по смыслу.
2. Не выдумывай адреса, даты, суммы, реквизиты, номера договоров и обстоятельства.
3. Не меняй ручные поля пользователя: sender_name, sender_address, recipient_name, recipient_address, violation_date, penalty_amount, response_deadline.
4. Не добавляй статьи закона, которых нет в law_articles.
5. Не используй markdown-разметку, таблицы и декоративные элементы.
6. Сохрани структуру официального документа и деловой тон.

Классификация претензии:
{claim_classification}

Ручные поля пользователя:
{manual_fields}

Запрос пользователя:
{user_request}

Анализ договора:
{contract_analysis}

Найденные правовые основания:
{law_articles}

Черновик претензии:
{draft_claim}
"""


def call_openrouter(prompt: str) -> str:
    if not settings.OPENROUTER_API_KEY:
        raise LLMError("OPENROUTER_API_KEY не указан")

    payload = {
        "model": settings.OPENROUTER_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ты юридический помощник. Верни только текст официальной претензии "
                    "без Markdown, без смены темы и без изменения фактов."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise LLMError(f"Ошибка OpenRouter: {error}")

    data = response.json()

    try:
        return data["choices"][0]["message"]["content"]
    except KeyError:
        raise LLMError("OpenRouter вернул неожиданный формат ответа")


def call_ollama(prompt: str) -> str:
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ты юридический помощник. Верни только текст официальной претензии "
                    "без Markdown, без смены темы и без изменения фактов."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.1},
    }

    url = f"{settings.OLLAMA_BASE_URL}/api/chat"

    try:
        response = requests.post(url, json=payload, timeout=180)
        response.raise_for_status()
    except requests.RequestException as error:
        raise LLMError(f"Ошибка Ollama: {error}")

    data = response.json()

    try:
        return data["message"]["content"]
    except KeyError:
        raise LLMError("Ollama вернула неожиданный формат ответа")


def improve_claim_with_llm(
    draft_claim: str,
    contract_analysis: dict,
    law_articles: list[dict],
    user_request: str,
    manual_fields: dict | None = None,
    claim_classification: dict | None = None,
) -> str:
    prompt = build_claim_improvement_prompt(
        draft_claim=draft_claim,
        contract_analysis=contract_analysis,
        law_articles=law_articles,
        user_request=user_request,
        manual_fields=manual_fields,
        claim_classification=claim_classification,
    )

    provider = settings.LLM_PROVIDER.lower().strip()

    if provider == "openrouter":
        return call_openrouter(prompt)

    if provider == "ollama":
        return call_ollama(prompt)

    raise LLMError(f"Неизвестный LLM_PROVIDER: {settings.LLM_PROVIDER}")
