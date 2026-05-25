from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Legal Document Bot MVP"

    DATABASE_URL: str = "postgresql+psycopg2://postgres:0000@localhost:5432/legal_bot"

    UPLOAD_DIR: str = "uploads"

    LLM_PROVIDER: str = "openrouter"

    OPENROUTER_API_KEY: str | None = None
    OPENROUTER_MODEL: str = "google/gemini-2.5-flash-lite"
    GENERATED_DIR: str = "generated"

    CHROMA_DIR: str = "chroma_db"
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-base"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"

    WEB_FALLBACK_URLS: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
