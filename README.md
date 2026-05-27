# Legal Document Bot MVP

Корпоративный web-сервис для анализа договоров и подготовки претензий по просрочке оказания услуг. Пользователь загружает договор, backend извлекает текст, сохраняет документ в PostgreSQL, ищет правовые основания через RAG/ChromaDB, при необходимости использует web fallback, формирует претензию и отдаёт DOCX.

## Архитектура

- `backend`: FastAPI, SQLAlchemy, PostgreSQL, генерация DOCX, RAG и LLM-интеграции.
- `frontend`: обычные `HTML/CSS/JS`, раздаётся через nginx.
- `postgres`: PostgreSQL 16 внутри Docker Compose.
- `uploads/`: загруженные договоры.
- `generated/`: сгенерированные DOCX.
- `chroma_db/`: постоянное хранилище ChromaDB.

Основной endpoint генерации: `POST /claims/generate`. Он поддерживает типы претензий `auto`, `services_delay`, `payment_delay`, `delivery_delay`, `defective_goods`, `refund`, `custom`. Старый endpoint `POST /claims/generate-delay-claim` сохранён для обратной совместимости и использует тип `services_delay`.

## Запуск Через Docker Compose

1. Подготовьте `.env`:

```powershell
Copy-Item .env.example .env
```

2. Запустите проект:

```powershell
docker compose up --build
```

Для фонового запуска:

```powershell
docker compose up --build -d
```

После запуска:

- Frontend: `http://127.0.0.1:5500`
- Backend Swagger: `http://127.0.0.1:8000/docs`
- Healthcheck: `http://127.0.0.1:8000/health`

## Подготовка .env

Для Docker используйте:

```env
APP_NAME=Legal Document Bot MVP
DATABASE_URL=postgresql+psycopg2://postgres:postgres@postgres:5432/legal_bot
UPLOAD_DIR=uploads
GENERATED_DIR=generated
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=
OPENROUTER_MODEL=google/gemini-2.5-flash-lite
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:7b
CHROMA_DIR=chroma_db
EMBEDDING_MODEL=intfloat/multilingual-e5-base
WEB_FALLBACK_URLS=
```

Для локального запуска без Docker замените `DATABASE_URL` на:

```env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/legal_bot
```

## Проверка Backend

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
```

Ожидаемый ответ:

```json
{
  "status": "ok",
  "database": "ok",
  "app": "Legal Document Bot MVP"
}
```

Swagger доступен по адресу `http://127.0.0.1:8000/docs`.

## Проверка Frontend

Откройте `http://127.0.0.1:5500`.

Проверьте сценарий:

1. Загрузить договор.
2. Получить `file_id`.
3. Сгенерировать претензию.
4. Скачать DOCX.
5. Открыть историю.
6. Очистить историю.
7. Добавить ссылку в RAG.
8. Загрузить файл в RAG.
9. Обновить список RAG.
10. Переиндексировать RAG.
11. Открыть вкладку `Диагностика LLM` и проверить тип претензии, найденные статьи, время RAG/LLM и предупреждения качества.

## Работа С PostgreSQL

PostgreSQL запускается сервисом `postgres`:

```powershell
docker compose ps
docker compose logs -f postgres
```

Подключение из контейнерной сети:

```text
postgresql+psycopg2://postgres:postgres@postgres:5432/legal_bot
```

Backend при старте создаёт таблицы и безопасно добавляет колонку `claim_requests.docx_path`, если старая таблица была создана без неё.

## Работа С LLM

### OpenRouter

В `.env`:

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=ваш_ключ
OPENROUTER_MODEL=google/gemini-2.5-flash-lite
```

### Ollama

Установите Ollama на хосте и скачайте модель:

```powershell
ollama pull qwen2.5:7b
```

В `.env`:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:7b
```

Если LLM недоступна, генерация не падает: backend возвращает черновик и заполняет `llm_error`.

## Универсальная Генерация И Trace

`POST /claims/generate` принимает `claim_type`:

- `auto`: определить тип автоматически;
- `services_delay`: просрочка оказания услуг;
- `payment_delay`: неоплата или задолженность;
- `delivery_delay`: просрочка поставки;
- `defective_goods`: некачественный товар;
- `refund`: возврат денежных средств;
- `custom`: свободная претензия.

Ответ содержит `trace`: шаги выполнения, классификацию, найденные статьи, время RAG/LLM, общее время и предупреждения качества. Эти данные отображаются во frontend на вкладке `Диагностика LLM`.

## Работа С RAG

Во frontend есть блок `База знаний RAG`:

- добавить ссылку: `POST /knowledge/add-url`;
- загрузить документ: `POST /knowledge/upload-file`;
- посмотреть список: `GET /knowledge/list`;
- переиндексировать: `POST /knowledge/reindex`.

Если ChromaDB или `sentence-transformers` недоступны, приложение продолжает работать через JSON-поиск, а подробность возвращается в `vector_error`.

## Где Хранятся Файлы

- `uploads/`: договоры и временные RAG-файлы.
- `generated/`: DOCX-претензии.
- `chroma_db/`: индекс ChromaDB.
- PostgreSQL volume `legal_bot_pgdata`: таблицы документов и истории.

Эти директории подключены в `docker-compose.yml` как bind volumes, поэтому данные сохраняются между перезапусками контейнеров.

## Типовые Ошибки

- Backend не подключается к БД: проверьте `docker compose logs -f backend` и `docker compose logs -f postgres`; внутри Docker `DATABASE_URL` должен использовать host `postgres`.
- Frontend не видит backend: проверьте, что backend доступен на `http://127.0.0.1:8000/health`.
- CORS: в `app/main.py` включены `allow_origins=["*"]`, `allow_methods=["*"]`, `allow_headers=["*"]`.
- `docx_path column does not exist`: перезапустите backend; стартовая инициализация добавляет колонку автоматически.
- ChromaDB/sentence-transformers долго устанавливаются: это ожидаемо при первой сборке, образ скачивает ML-зависимости.
- OpenRouter 401: проверьте `OPENROUTER_API_KEY`.
- Ollama недоступна: проверьте `ollama run qwen2.5:7b` на хосте и `OLLAMA_BASE_URL=http://host.docker.internal:11434`.

## Разворачивание На Предприятии

Перед запуском:

- проверить Docker и Docker Compose;
- проверить доступ к интернету для OpenRouter или заранее выбрать Ollama;
- уточнить, разрешены ли внешние LLM API;
- подготовить тестовые договоры;
- проверить генерацию DOCX;
- проверить пополнение и переиндексацию RAG;
- проверить логи контейнеров.

Команды:

```powershell
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres
```

Остановка:

```powershell
docker compose down
```

Полная очистка PostgreSQL volume:

```powershell
docker compose down -v
```
