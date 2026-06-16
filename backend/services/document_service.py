"""
Document Service — in-memory store for prototype.
Replace with SQLAlchemy + PostgreSQL for production.
"""

from datetime import datetime
from typing import Optional

# In-memory store (prototype only)
_documents: dict = {}
_feedback: list = []


class DocumentService:
    def create_document(self, doc_id: str, filename: str, ocr_text: str,
                        doc_type: str, deadlines: list, entities: dict) -> dict:
        doc = {
            "doc_id": doc_id,
            "filename": filename,
            "ocr_text": ocr_text,
            "doc_type": doc_type,
            "deadlines": deadlines,
            "entities": entities,
            "uploaded_at": datetime.utcnow().isoformat(),
            "status": "processed",
            "analysis": None,
        }
        _documents[doc_id] = doc
        return doc

    def get_document(self, doc_id: str) -> Optional[dict]:
        return _documents.get(doc_id)

    def list_documents(self) -> list:
        return [
            {"doc_id": d["doc_id"], "filename": d["filename"],
             "doc_type": d["doc_type"], "uploaded_at": d["uploaded_at"],
             "status": d["status"]}
            for d in _documents.values()
        ]

    def save_analysis(self, doc_id: str, analysis: dict):
        if doc_id in _documents:
            _documents[doc_id]["analysis"] = analysis
            _documents[doc_id]["status"] = "analysed"

    def save_feedback(self, analysis_id: str, rating: int, comment: Optional[str]):
        _feedback.append({
            "analysis_id": analysis_id,
            "rating": rating,
            "comment": comment,
            "timestamp": datetime.utcnow().isoformat()
        })
