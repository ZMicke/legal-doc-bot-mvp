import requests

from app.config import settings
import time
import logging
import json
from datetime import datetime
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LOG_DIR = "/app/logs/model_comparison"
os.makedirs(LOG_DIR, exist_ok=True)



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
    customer_name = contract_analysis.get("customer_name", "Заказчик")
    contractor_name = contract_analysis.get("contractor_name", "Исполнитель")
    contract_number = contract_analysis.get("contract_number", "номер не указан")
    contract_date = contract_analysis.get("contract_date", "дата не указана")
    subject = contract_analysis.get("subject", "не указано")
    deadlines = contract_analysis.get("deadlines", "не указаны")
    liability = contract_analysis.get("liability", "не указана")

    return f"""
Ты — юридический помощник предприятия. Отредактируй черновик претензии.

## ПРАВИЛА:

1. **Названия сторон**:
   - Заказчик: {customer_name}
   - Исполнитель: {contractor_name}
   
   ЗАПРЕЩЕНО вставлять в документ текст "а оказать услуги по маркетинговому аудиту" или другие фрагменты из описания услуг вместо названия компании.

2. **Форматирование**:
   - НЕ используй ** __ ## # * _ ---
   - Тире пиши как "—"
   - Заголовки без Markdown, просто с новой строки

3. **Ручные поля (НЕ ИЗМЕНЯТЬ)**:
   sender_name: {manual_fields.get('sender_name', '[не указано]')}
   recipient_name: {manual_fields.get('recipient_name', '[не указано]')}
   sender_address: {manual_fields.get('sender_address', '[не указано]')}
   recipient_address: {manual_fields.get('recipient_address', '[не указано]')}
   violation_date: {manual_fields.get('violation_date', '[не указано]')}
   penalty_amount: {manual_fields.get('penalty_amount', '[не указано]')}
   response_deadline: {manual_fields.get('response_deadline', '10')}

4. **Правовые основания**: Используй ТОЛЬКО статьи из списка ниже. Не добавляй свои.

5. **Ответ**: Верни ТОЛЬКО текст претензии. Начинай с заголовка "ПРЕТЕНЗИЯ". Без пояснений.

## Данные из анализа договора:
- Номер договора: {contract_number}
- Дата договора: {contract_date}
- Предмет: {subject}
- Сроки: {deadlines}
- Ответственность: {liability}

## Классификация претензии:
{claim_classification}

## Запрос пользователя:
{user_request}

## Найденные правовые основания:
{law_articles}

## Черновик претензии:
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

    logger.info(f"Промпт для LLM (первые 500 символов):\n{prompt[:500]}...")
    logger.info(f"Длина промпта: {len(prompt)} символов")

    start_time = time.time()

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

    logger.info(f"Запрос к Ollama: {json.dumps(payload, ensure_ascii=False)[:500]}...")

    url = f"{settings.OLLAMA_BASE_URL}/api/chat"

    try:
        response = requests.post(url, json=payload, timeout=180)

        logger.info(f"Статус ответа: {response.status_code}")
        logger.info(f"Длина ответа: {len(response.text)} символов")
        response.raise_for_status()
    except requests.RequestException as error:
        logger.error(f"Ошибка: {error}")
        raise LLMError(f"Ошибка Ollama: {error}")

    data = response.json()
    total_time = time.time() - start_time
    
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "model": settings.OLLAMA_MODEL,
        "total_duration": total_time,
        "prompt_eval_duration": data.get("prompt_eval_duration", 0) / 1e9,  # в секундах
        "eval_duration": data.get("eval_duration", 0) / 1e9,
        "prompt_length": len(prompt),
        "response_length": len(data["message"]["content"]),
        "prompt_tokens": data.get("prompt_eval_count", 0),
        "response_tokens": data.get("eval_count", 0),
        "tokens_per_second": data.get("eval_count", 0) / (data.get("eval_duration", 1) / 1e9) if data.get("eval_duration") else 0,
    }
    log_file = f"{LOG_DIR}/metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"МЕТРИКИ ДЛЯ МОДЕЛИ: {settings.OLLAMA_MODEL}")
    print(f"{'='*60}")
    print(f"Полное время: {total_time:.2f} сек")
    print(f"Время генерации: {log_entry['eval_duration']:.2f} сек")
    print(f"Токенов на входе: {log_entry['prompt_tokens']}")
    print(f"Токенов на выходе: {log_entry['response_tokens']}")
    print(f"Скорость: {log_entry['tokens_per_second']:.1f} токенов/сек")
    print(f"Длина ответа: {log_entry['response_length']} символов")
    print(f"{'='*60}\n")

    answer = data["message"]["content"]
    logger.info(f"Ответ модели (первые 300 символов):\n{answer[:300]}...")

    

    try:
        return data["message"]["content"], answer
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
    
    if isinstance(result, tuple):
        print(f"ВНИМАНИЕ: LLM вернул кортеж, берем первый элемент")
        result = result[0] if result else ""

    else:
        raise LLMError(f"Неизвестный LLM_PROVIDER: {settings.LLM_PROVIDER}")
    
    
    return result



