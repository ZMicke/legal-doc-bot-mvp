from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.models import ClaimRequest, Document
from app.database.session import get_db
from app.services.claim_generator import generate_delay_claim_text
from app.services.contract_analyzer import (
    analyze_contract_text,
    detect_delay_violation,
)
from app.services.llm.provider import LLMError, improve_claim_with_llm
from app.services.rag.law_retriever import retrieve_law_articles_with_fallback

from fastapi.responses import FileResponse
from pathlib import Path

from app.services.docx_generator import clean_markdown, generate_claim_docx

router = APIRouter(prefix="/claims", tags=["Claims"])


class ClaimManualFields(BaseModel):
    violation_date: str | None = None
    violation_description: str | None = None
    response_deadline: str | None = None
    penalty_amount: str | None = None

    recipient_name: str | None = None
    recipient_address: str | None = None
    sender_name: str | None = None
    sender_address: str | None = None


class ClaimGenerateRequest(BaseModel):
    file_id: str
    user_request: str
    manual_fields: ClaimManualFields | None = None
    use_llm: bool = True


@router.post("/generate-delay-claim")
async def generate_delay_claim(
    request: ClaimGenerateRequest,
    db: Session = Depends(get_db),
):
    document = (
        db.query(Document)
        .filter(Document.file_id == request.file_id)
        .first()
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Документ с таким file_id не найден",
        )

    contract_analysis = analyze_contract_text(document.extracted_text)
    violation = detect_delay_violation(contract_analysis)

    rag_query = f"""
    {request.user_request}

    Предмет договора:
    {contract_analysis.get("subject")}

    Сроки:
    {contract_analysis.get("deadlines")}

    Ответственность:
    {contract_analysis.get("liability")}

    Претензионный порядок:
    {contract_analysis.get("claim_procedure")}
    """

    law_result = retrieve_law_articles_with_fallback(rag_query)
    law_articles = law_result["items"]

    manual_fields = (
        request.manual_fields.model_dump()
        if request.manual_fields
        else {}
    )

    draft_claim = generate_delay_claim_text(
        contract_text=document.extracted_text,
        user_request=request.user_request,
        law_articles=law_articles,
        contract_analysis=contract_analysis,
        violation=violation,
        manual_fields=manual_fields,
    )

    llm_error = None

    if request.use_llm:
        try:
            final_claim = improve_claim_with_llm(
                draft_claim=draft_claim,
                contract_analysis=contract_analysis,
                law_articles=law_articles,
                user_request=request.user_request,
                manual_fields=manual_fields,
            )
        except LLMError as error:
            final_claim = draft_claim
            llm_error = str(error)
    else:
        final_claim = draft_claim

    final_claim = clean_markdown(final_claim)
    docx_path = generate_claim_docx(final_claim)

    claim_request = ClaimRequest(
        file_id=request.file_id,
        user_request=request.user_request,
        result_text=final_claim,
        docx_path=docx_path,
    )
    

    db.add(claim_request)
    db.commit()
    db.refresh(claim_request)

    return {
        "message": "Претензия успешно сформирована",
        "claim_request_id": claim_request.id,
        "file_id": request.file_id,
        "contract_analysis": contract_analysis,
        "violation": violation,
        "manual_fields": manual_fields,
        "law_articles": law_articles,
        "web_fallback_used": law_result.get("web_fallback_used", False),
        "web_error": law_result.get("web_error"),
        "vector_error": law_result.get("vector_error"),
        "use_llm": request.use_llm,
        "llm_error": llm_error,
        "draft_claim": draft_claim,
        "claim_text": final_claim,
        "docx_path": docx_path,
        "download_url": f"/claims/{claim_request.id}/download-docx",
    }



@router.get("/history")
async def get_claims_history(
    db: Session = Depends(get_db),
):
    claims = (
        db.query(ClaimRequest)
        .order_by(ClaimRequest.created_at.desc())
        .all()
    )

    return {
        "count": len(claims),
        "items": [
            {
                "id": claim.id,
                "file_id": claim.file_id,
                "user_request": claim.user_request,
                "created_at": claim.created_at,
                "has_docx": bool(claim.docx_path),
                "download_url": (
                    f"/claims/{claim.id}/download-docx"
                    if claim.docx_path
                    else None
                ),
                "preview": (
                    claim.result_text[:500]
                    if claim.result_text
                    else None
                ),
            }
            for claim in claims
        ],
    }


@router.delete("/history")
async def clear_claims_history(
    db: Session = Depends(get_db),
):
    claims = db.query(ClaimRequest).all()
    deleted_count = len(claims)
    deleted_files_count = 0

    for claim in claims:
        if not claim.docx_path:
            continue

        try:
            file_path = Path(claim.docx_path)
            if file_path.exists() and file_path.is_file():
                file_path.unlink()
                deleted_files_count += 1
        except OSError:
            pass

    db.query(ClaimRequest).delete(synchronize_session=False)
    db.commit()

    return {
        "message": "История претензий очищена",
        "deleted_count": deleted_count,
        "deleted_files_count": deleted_files_count,
    }


@router.get("/{claim_request_id}")
async def get_claim_by_id(
    claim_request_id: int,
    db: Session = Depends(get_db),
):
    claim = (
        db.query(ClaimRequest)
        .filter(ClaimRequest.id == claim_request_id)
        .first()
    )

    if claim is None:
        raise HTTPException(
            status_code=404,
            detail="Претензия не найдена",
        )

    return {
        "id": claim.id,
        "file_id": claim.file_id,
        "user_request": claim.user_request,
        "result_text": claim.result_text,
        "docx_path": claim.docx_path,
        "download_url": (
            f"/claims/{claim.id}/download-docx"
            if claim.docx_path
            else None
        ),
        "created_at": claim.created_at,
    }


@router.get("/{claim_request_id}/download-docx")
async def download_claim_docx(
    claim_request_id: int,
    db: Session = Depends(get_db),
):
    claim_request = (
        db.query(ClaimRequest)
        .filter(ClaimRequest.id == claim_request_id)
        .first()
    )

    if claim_request is None:
        raise HTTPException(
            status_code=404,
            detail="Претензия не найдена",
        )

    if not claim_request.docx_path:
        raise HTTPException(
            status_code=404,
            detail="DOCX-файл для этой претензии не был создан",
        )

    file_path = Path(claim_request.docx_path)

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Файл DOCX не найден на сервере",
        )

    return FileResponse(
        path=str(file_path),
        filename=f"claim_{claim_request_id}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
