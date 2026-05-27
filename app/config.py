from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Legal Document Bot MVP"

    DATABASE_URL: str = "postgresql+psycopg2://postgres:0000@localhost:5432/legal_bot"

    UPLOAD_DIR: str = "uploads"

<<<<<<< HEAD
    LLM_PROVIDER: str = "ollama"
=======
    LLM_PROVIDER: str = "openrouter"
>>>>>>> a2828f9fff27ad6b91d9c7457191682e35304ae2

    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL: str = "google/gemini-2.5-flash-lite"
    GENERATED_DIR: str = "generated"

    CHROMA_DIR: str = "chroma_db"
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-base"

<<<<<<< HEAD
    OLLAMA_BASE_URL: str = "http://10.68.98.206:11434"
    OLLAMA_MODEL: str = "yandex/YandexGPT-5-Lite-8B-instruct-GGUF:latest"
=======
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"
>>>>>>> a2828f9fff27ad6b91d9c7457191682e35304ae2

    WEB_FALLBACK_URLS: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
