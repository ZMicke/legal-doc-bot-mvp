from pathlib import Path

from uuid import uuid4
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.url_loader import load_text_from_url

from app.services.rag.knowledge_store import (
    add_knowledge_item,
    load_custom_knowledge,
)
from app.services.text_extractor import extract_text
from app.services.rag.knowledge_store import reindex_custom_knowledge

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base"])


class KnowledgeItemRequest(BaseModel):
    title: str
    source_type: str
    content: str
    source_url: str | None = None

class KnowledgeUrlRequest(BaseModel):
    title: str
    source_type: str
    source_url: str


@router.post("/add")
async def add_item(item: KnowledgeItemRequest):
    saved_item = add_knowledge_item(
        title=item.title,
        source_type=item.source_type,
        content=item.content,
        source_url=item.source_url,
    )

    return {
        "message": "Материал добавлен в базу знаний",
        "item": saved_item,
    }


@router.post("/upload-file")
async def upload_knowledge_file(
    title: str = Form(...),
    source_type: str = Form(...),
    file: UploadFile = File(...),
):
    allowed_extensions = [".pdf", ".docx", ".txt"]
    file_ext = Path(file.filename or "").suffix.lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Разрешены только файлы PDF, DOCX или TXT",
        )

    temp_dir = Path("uploads/knowledge")
    temp_dir.mkdir(parents=True, exist_ok=True)

    temp_path = temp_dir / f"{uuid4()}_{file.filename}"

    with temp_path.open("wb") as buffer:
        buffer.write(await file.read())

    try:
        extracted_text = extract_text(str(temp_path))
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось извлечь текст из файла: {error}",
        )

    saved_item = add_knowledge_item(
        title=title,
        source_type=source_type,
        content=extracted_text,
        source_url=None,
    )

    return {
        "message": "Файл загружен и добавлен в базу знаний",
        "filename": file.filename,
        "item": saved_item,
        "text_preview": extracted_text[:1000],
        "text_length": len(extracted_text),
    }


@router.get("/list")
async def list_items():
    items = load_custom_knowledge()

    return {
        "count": len(items),
        "items": items,
    }


@router.post("/add-url")
async def add_knowledge_from_url(item: KnowledgeUrlRequest):
    try:
        extracted_text = load_text_from_url(item.source_url)
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось загрузить текст по ссылке: {error}",
        )

    saved_item = add_knowledge_item(
        title=item.title,
        source_type=item.source_type,
        content=extracted_text,
        source_url=item.source_url,
    )

    return {
        "message": "Материал по ссылке добавлен в базу знаний",
        "item": saved_item,
        "text_preview": extracted_text[:1000],
        "text_length": len(extracted_text),
    }

@router.post("/reindex")
async def reindex_knowledge():
    result = reindex_custom_knowledge()

    return {
        "message": "База знаний успешно переиндексирована в ChromaDB",
        "result": result,
    }

