import json
from pathlib import Path
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import ClaimRequest, Document
from app.database.session import get_db
from app.services.claim_classifier import ALLOWED_CLAIM_TYPES, classify_claim
from app.services.claim_generator import generate_claim_text
from app.services.claim_quality import evaluate_claim_quality
from app.services.contract_analyzer import analyze_contract_text, detect_delay_violation
from app.services.docx_generator import clean_markdown, generate_claim_docx
from app.services.llm.provider import LLMError, improve_claim_with_llm
from app.services.rag.law_retriever import retrieve_law_articles_with_fallback


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
    claim_type: str = "auto"
    manual_fields: ClaimManualFields | None = None
    use_llm: bool = True


def elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)


def add_step(trace: dict, name: str, duration_ms: int) -> None:
    trace["steps"].append({"name": name, "duration_ms": duration_ms})


async def generate_claim_pipeline(
    request: ClaimGenerateRequest,
    db: Session,
    forced_claim_type: str | None = None,
) -> dict:
    total_start = perf_counter()
    trace = {"steps": []}

    step_start = perf_counter()
    document = db.query(Document).filter(Document.file_id == request.file_id).first()
    add_step(trace, "document_loaded", elapsed_ms(step_start))

    if document is None:
        raise HTTPException(status_code=404, detail="Документ с таким file_id не найден")

    manual_fields = request.manual_fields.model_dump() if request.manual_fields else {}
    selected_claim_type = forced_claim_type or request.claim_type or "auto"
    if selected_claim_type not in ALLOWED_CLAIM_TYPES:
        selected_claim_type = "auto"

    step_start = perf_counter()
    contract_analysis = analyze_contract_text(document.extracted_text)
    violation = detect_delay_violation(contract_analysis)
    add_step(trace, "contract_analysis", elapsed_ms(step_start))

    step_start = perf_counter()
    classification = classify_claim(
        user_request=request.user_request,
        contract_analysis=contract_analysis,
        requested_claim_type=selected_claim_type,
    )
    add_step(trace, "claim_classification", elapsed_ms(step_start))

    rag_query = f"""
    {request.user_request}

    Тип претензии: {classification.get("claim_type")}
    Фокус: {classification.get("legal_focus")}

    Предмет договора:
    {contract_analysis.get("subject")}

    Сроки:
    {contract_analysis.get("deadlines")}

    Ответственность:
    {contract_analysis.get("liability")}

    Претензионный порядок:
    {contract_analysis.get("claim_procedure")}
    """

    step_start = perf_counter()
    law_result = retrieve_law_articles_with_fallback(
        query=rag_query,
        claim_type=classification.get("claim_type"),
        required_articles=classification.get("recommended_articles", []),
    )
    law_articles = law_result["items"]
    rag_duration_ms = elapsed_ms(step_start)
    add_step(trace, "rag_search", rag_duration_ms)

    step_start = perf_counter()
    draft_claim = generate_claim_text(
        contract_text=document.extracted_text,
        user_request=request.user_request,
        law_articles=law_articles,
        contract_analysis=contract_analysis,
        claim_classification=classification,
        manual_fields=manual_fields,
    )
    add_step(trace, "draft_generation", elapsed_ms(step_start))

    llm_error = None
    llm_used = False
    llm_duration_ms = 0
    final_claim = draft_claim

    step_start = perf_counter()
    if request.use_llm:
        llm_used = True
        try:
            final_claim = improve_claim_with_llm(
                draft_claim=draft_claim,
                contract_analysis=contract_analysis,
                law_articles=law_articles,
                user_request=request.user_request,
                manual_fields=manual_fields,
                claim_classification=classification,
            )
        except LLMError as error:
            final_claim = draft_claim
            llm_error = str(error)
    llm_duration_ms = elapsed_ms(step_start)
    add_step(trace, "llm_refinement", llm_duration_ms)

    final_claim = clean_markdown(final_claim)

    quality_checks = evaluate_claim_quality(
        claim_text=final_claim,
        manual_fields=manual_fields,
        law_articles=law_articles,
        claim_classification=classification,
    )

    step_start = perf_counter()
    docx_path = generate_claim_docx(final_claim)
    add_step(trace, "docx_generation", elapsed_ms(step_start))

    total_duration_ms = elapsed_ms(total_start)

    trace.update({
        "llm": {
            "provider": settings.LLM_PROVIDER,
            "model": settings.OPENROUTER_MODEL if settings.LLM_PROVIDER == "openrouter" else settings.OLLAMA_MODEL,
            "duration_ms": llm_duration_ms,
            "used": llm_used,
            "error": llm_error,
        },
        "classification": {
            "claim_type": classification.get("claim_type"),
            "claim_title": classification.get("claim_title"),
            "confidence": classification.get("confidence"),
            "explanation": classification.get("explanation"),
        },
        "rag": {
            "duration_ms": rag_duration_ms,
            "articles_count": len(law_articles),
            "required_articles": law_result.get("required_articles", []),
            "sources": [
                {
                    "source": item.get("source"),
                    "article": item.get("article"),
                    "title": item.get("title"),
                    "source_url": item.get("source_url"),
                }
                for item in law_articles
            ],
        },
        "quality_checks": quality_checks,
        "total_duration_ms": total_duration_ms,
    })

    claim_request = ClaimRequest(
        file_id=request.file_id,
        user_request=request.user_request,
        result_text=final_claim,
        docx_path=docx_path,
        trace_json=json.dumps(trace, ensure_ascii=False),
    )

    db.add(claim_request)
    db.commit()
    db.refresh(claim_request)

    return {
        "message": "Претензия успешно сформирована",
        "claim_request_id": claim_request.id,
        "file_id": request.file_id,
        "claim_type": classification.get("claim_type"),
        "claim_title": classification.get("claim_title"),
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
        "trace": trace,
    }


@router.post("/generate")
async def generate_claim(
    request: ClaimGenerateRequest,
    db: Session = Depends(get_db),
):
    return await generate_claim_pipeline(request, db)


@router.post("/generate-delay-claim")
async def generate_delay_claim(
    request: ClaimGenerateRequest,
    db: Session = Depends(get_db),
):
    return await generate_claim_pipeline(request, db, forced_claim_type="services_delay")


@router.get("/history")
async def get_claims_history(db: Session = Depends(get_db)):
    claims = db.query(ClaimRequest).order_by(ClaimRequest.created_at.desc()).all()

    return {
        "count": len(claims),
        "items": [
            {
                "id": claim.id,
                "file_id": claim.file_id,
                "user_request": claim.user_request,
                "created_at": claim.created_at,
                "has_docx": bool(claim.docx_path),
                "download_url": f"/claims/{claim.id}/download-docx" if claim.docx_path else None,
                "preview": claim.result_text[:500] if claim.result_text else None,
                "trace": json.loads(claim.trace_json) if claim.trace_json else None,
            }
            for claim in claims
        ],
    }


@router.delete("/history")
async def clear_claims_history(db: Session = Depends(get_db)):
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
async def get_claim_by_id(claim_request_id: int, db: Session = Depends(get_db)):
    claim = db.query(ClaimRequest).filter(ClaimRequest.id == claim_request_id).first()

    if claim is None:
        raise HTTPException(status_code=404, detail="Претензия не найдена")

    return {
        "id": claim.id,
        "file_id": claim.file_id,
        "user_request": claim.user_request,
        "result_text": claim.result_text,
        "docx_path": claim.docx_path,
        "download_url": f"/claims/{claim.id}/download-docx" if claim.docx_path else None,
        "created_at": claim.created_at,
        "trace": json.loads(claim.trace_json) if claim.trace_json else None,
    }


@router.get("/{claim_request_id}/download-docx")
async def download_claim_docx(claim_request_id: int, db: Session = Depends(get_db)):
    claim_request = db.query(ClaimRequest).filter(ClaimRequest.id == claim_request_id).first()

    if claim_request is None:
        raise HTTPException(status_code=404, detail="Претензия не найдена")

    if not claim_request.docx_path:
        raise HTTPException(status_code=404, detail="DOCX-файл для этой претензии не был создан")

    file_path = Path(claim_request.docx_path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл DOCX не найден на сервере")

    return FileResponse(
        path=str(file_path),
        filename=f"claim_{claim_request_id}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
