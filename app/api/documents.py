import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import Document
from app.database.session import get_db
from app.services.text_extractor import extract_text

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    allowed_extensions = [".pdf", ".docx", ".txt"]

    file_ext = Path(file.filename or "").suffix.lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail="Разрешены только файлы PDF, DOCX или TXT"
        )

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_id = str(uuid4())
    saved_filename = f"{file_id}{file_ext}"
    saved_path = upload_dir / saved_filename

    with saved_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        extracted_text = extract_text(str(saved_path))
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось извлечь текст из документа: {error}"
        )

    document = Document(
        file_id=file_id,
        original_filename=file.filename,
        saved_path=str(saved_path),
        extracted_text=extracted_text
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return {
        "message": "Документ успешно загружен, прочитан и сохранен в БД",
        "document_db_id": document.id,
        "file_id": file_id,
        "original_filename": file.filename,
        "text_preview": extracted_text[:1000],
        "text_length": len(extracted_text)
    }
