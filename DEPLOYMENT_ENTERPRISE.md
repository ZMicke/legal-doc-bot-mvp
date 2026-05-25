# Enterprise Deployment Notes

## Минимальные Требования

- Docker.
- Docker Compose.
- 8+ GB RAM.
- 20+ GB disk.
- Интернет для OpenRouter или локальная LLM через Ollama.

## Запуск

```powershell
cp .env.example .env
docker compose up --build -d
```

## Проверка

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:5500`

## Ollama

Если используется Ollama:

```powershell
ollama pull qwen2.5:7b
ollama run qwen2.5:7b
```

В `.env`:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:7b
```

## OpenRouter

Если используется OpenRouter:

- заполните `OPENROUTER_API_KEY`;
- проверьте, что предприятие разрешает внешний API;
- проверьте журналы backend при первой генерации претензии.

## Логи

```powershell
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres
```

## Остановка

```powershell
docker compose down
```

## Полная Очистка

```powershell
docker compose down -v
```

Если нужно полностью удалить пользовательские файлы и индексы, дополнительно вручную очистите:

- `uploads/`
- `generated/`
- `chroma_db/`
