"""
German Immigration RAG Assistant — FastAPI Backend
MSc AI Thesis: Explainable RAG for Immigration Documents
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import uuid
import os
from datetime import datetime

from services.ocr_service import OCRService
from services.rag_service import RAGService
from services.document_service import DocumentService

app = FastAPI(
    title="Immigration RAG Assistant API",
    description="Explainable RAG for German Immigration Documents",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ocr_service = OCRService()
rag_service = RAGService()
doc_service = DocumentService()


class FeedbackRequest(BaseModel):
    analysis_id: str
    rating: int  # 1–5
    comment: Optional[str] = None


@app.post("/api/v1/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and OCR a document. Returns document_id and extracted text."""
    allowed_types = ["application/pdf", "image/jpeg", "image/png", "image/tiff"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File exceeds 10MB limit.")

    doc_id = str(uuid.uuid4())

    # Save file temporarily
    tmp_path = f"/tmp/{doc_id}_{file.filename}"
    with open(tmp_path, "wb") as f:
        f.write(contents)

    # OCR processing
    try:
        ocr_result = ocr_service.process(tmp_path, file.content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")
    finally:
        os.remove(tmp_path)

    # Store document record
    doc_record = doc_service.create_document(
        doc_id=doc_id,
        filename=file.filename,
        ocr_text=ocr_result["text"],
        doc_type=ocr_result["doc_type"],
        deadlines=ocr_result["deadlines"],
        entities=ocr_result["entities"],
    )

    return {
        "document_id": doc_id,
        "filename": file.filename,
        "doc_type": ocr_result["doc_type"],
        "extracted_text_preview": ocr_result["text"][:500],
        "detected_deadlines": ocr_result["deadlines"],
        "status": "ready_for_analysis"
    }


@app.post("/api/v1/analyze/{doc_id}")
async def analyze_document(doc_id: str):
    """Run full RAG pipeline on a processed document."""
    doc = doc_service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    try:
        result = await rag_service.analyze(
            doc_id=doc_id,
            ocr_text=doc["ocr_text"],
            doc_type=doc["doc_type"],
            deadlines=doc["deadlines"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    return result


@app.get("/api/v1/documents")
async def list_documents():
    """List all documents (prototype: no auth)."""
    return doc_service.list_documents()


@app.get("/api/v1/documents/{doc_id}")
async def get_document(doc_id: str):
    doc = doc_service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@app.post("/api/v1/feedback")
async def submit_feedback(feedback: FeedbackRequest):
    doc_service.save_feedback(
        analysis_id=feedback.analysis_id,
        rating=feedback.rating,
        comment=feedback.comment
    )
    return {"status": "feedback recorded", "analysis_id": feedback.analysis_id}


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
