from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import claims, documents, knowledge
from app.config import settings
from app.database.init_db import ensure_database_schema
from app.database.session import engine


ensure_database_schema(engine)

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(claims.router)
app.include_router(knowledge.router)


@app.get("/")
def root():
    return {
        "message": "Legal Document Bot MVP запущен",
        "status": "ok",
    }


@app.get("/health")
def health():
    database_status = "ok"

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"

    return {
        "status": "ok",
        "database": database_status,
        "app": settings.APP_NAME,
    }
