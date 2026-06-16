"""
German Immigration RAG Assistant — Lite Backend
Works without Docker/Qdrant. Requires only: ANTHROPIC_API_KEY
Run: uvicorn main_lite:app --reload --port 8000
"""
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid, os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load .env from prototype/ folder (one level up from backend/)
load_dotenv(Path(__file__).parent.parent / ".env")

from services.ocr_service import OCRService
from services.document_service import DocumentService
from services import rag_service_lite as rag

app = FastAPI(title="Immigration RAG Assistant", version="1.0.0-lite")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:3001", "http://127.0.0.1:3001",
        "http://localhost:3002", "http://127.0.0.1:3002",
    ],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

ocr_service = OCRService()
doc_service = DocumentService()


class FeedbackRequest(BaseModel):
    analysis_id: str
    rating: int
    comment: Optional[str] = None


@app.get("/api/v1/health")
async def health():
    api_key_set = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return {
        "status": "ok",
        "api_key_configured": api_key_set,
        "mode": "lite (in-memory RAG, no Qdrant needed)",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/api/v1/upload")
async def upload_document(file: UploadFile = File(...)):
    allowed = ["application/pdf", "image/jpeg", "image/png", "image/tiff", "image/jpg"]
    if file.content_type not in allowed:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}. Use PDF, JPG, or PNG.")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(400, "File exceeds 10 MB limit.")

    doc_id = str(uuid.uuid4())
    tmp = f"/tmp/{doc_id}_{file.filename}"
    with open(tmp, "wb") as f:
        f.write(contents)

    try:
        ocr_result = ocr_service.process(tmp, file.content_type)
    except Exception as e:
        raise HTTPException(500, f"OCR failed: {e}")
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    doc_service.create_document(
        doc_id=doc_id, filename=file.filename,
        ocr_text=ocr_result["text"], doc_type=ocr_result["doc_type"],
        deadlines=ocr_result["deadlines"], entities=ocr_result["entities"],
    )
    return {
        "document_id": doc_id,
        "filename": file.filename,
        "doc_type": ocr_result["doc_type"],
        "extracted_text_preview": ocr_result["text"][:400],
        "detected_deadlines": ocr_result["deadlines"],
        "detected_entities": ocr_result["entities"],
        "status": "ready_for_analysis"
    }


@app.post("/api/v1/analyze/{doc_id}")
async def analyze_document(doc_id: str):
    doc = doc_service.get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found.")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(500, "ANTHROPIC_API_KEY not set. Add it to your .env file.")
    try:
        result = await rag.analyze(
            doc_id=doc_id, ocr_text=doc["ocr_text"],
            doc_type=doc["doc_type"], deadlines=doc["deadlines"],
        )
    except Exception as e:
        raise HTTPException(500, f"Analysis failed: {e}")
    return result


@app.get("/api/v1/documents")
async def list_documents():
    return doc_service.list_documents()


@app.get("/api/v1/documents/{doc_id}")
async def get_document(doc_id: str):
    doc = doc_service.get_document(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found.")
    return doc


@app.post("/api/v1/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    doc_service.save_feedback(feedback.analysis_id, feedback.rating, feedback.comment)
    return {"status": "recorded", "analysis_id": feedback.analysis_id}
