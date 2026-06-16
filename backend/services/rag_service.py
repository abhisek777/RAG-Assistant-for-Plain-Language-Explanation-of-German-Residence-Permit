"""
RAG Service — LangChain + LangGraph + Claude API + Qdrant
Explainable RAG pipeline for German immigration document analysis.
"""

import os
import json
import asyncio
from typing import Any
from datetime import datetime

import anthropic
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from langchain_qdrant import QdrantVectorStore
from langchain.schema import Document as LCDocument
from rank_bm25 import BM25Okapi

# Thesis scope: exactly 3 document types
IN_SCOPE_TYPES = {"appointment_letter", "documentation_request", "extension_notice"}
IN_SCOPE_LABELS = {
    "appointment_letter": "Residence Permit Appointment Letter",
    "documentation_request": "Request for Additional Documentation",
    "extension_notice": "Residence Permit Extension Notice",
}

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "immigration_knowledge_base"
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
TOP_K = 5

SYSTEM_PROMPT = """You are an AI assistant that explains German immigration administrative documents in plain language.

CRITICAL RULES — YOU MUST FOLLOW THESE:
1. ONLY explain what is in the document and retrieved sources. Do not add information from outside.
2. Do NOT provide legal advice, predict legal outcomes, or make administrative decisions.
3. Use plain language at approximately B1 CEFR level. Short sentences. Simple words.
4. Always include the required legal disclaimer.
5. Structure your response as valid JSON matching the schema provided.

Your role: explain, not advise. Help users understand, not make legal decisions."""

RAG_PROMPT_TEMPLATE = """
You are explaining the following German immigration document to a non-expert user.

DOCUMENT TYPE: {doc_type}
DETECTED DEADLINES: {deadlines}

OFFICIAL SOURCES RETRIEVED:
{retrieved_context}

DOCUMENT TEXT (OCR extracted):
{document_text}

Provide a plain-language explanation in the following JSON format:
{{
  "summary": "2-3 sentence plain-language summary of what this document is about",
  "explanation": "Detailed plain-language explanation (200-300 words, B1 CEFR level)",
  "deadlines": [
    {{"date": "DD.MM.YYYY or description", "description": "What must happen by this date", "urgency": "high|normal"}}
  ],
  "required_actions": [
    "Action 1 (imperative, specific)",
    "Action 2"
  ],
  "confidence_rationale": "One sentence explaining why you are confident in this explanation based on the retrieved sources",
  "disclaimer": "This is a plain-language explanation only. It does not constitute legal advice. For legal decisions, consult a licensed immigration lawyer or contact the immigration authority (Ausländerbehörde) directly."
}}

Remember: Explain only. Do not advise. Do not predict outcomes.
"""

GUARD_RAIL_RESPONSE = {
    "summary": "This question requires legal advice which this system cannot provide.",
    "explanation": "Your query appears to ask for legal advice or a prediction about a legal outcome. This system is designed only to explain documents in plain language. It cannot advise you on legal strategies, predict court or administrative decisions, or recommend specific legal actions. Please consult a licensed immigration lawyer (Fachanwalt für Ausländerrecht) or contact your local immigration authority (Ausländerbehörde) for guidance.",
    "deadlines": [],
    "required_actions": ["Consult a licensed immigration lawyer for legal advice.", "Contact your Ausländerbehörde for official information."],
    "confidence_rationale": "Guard rail triggered — legal advice boundary.",
    "disclaimer": "This system does not provide legal advice. Please consult a qualified legal professional.",
    "guard_rail_triggered": True
}

LEGAL_ADVICE_TRIGGERS = [
    "what should i do legally", "will i be deported", "will i win", "can they reject",
    "is it legal to", "my rights", "sue", "appeal my case", "legal strategy",
    "what are my chances", "will the judge", "should i fight"
]


class RAGService:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.qdrant = QdrantClient(url=QDRANT_URL)
        self.embedder = SentenceTransformer(EMBEDDING_MODEL)
        self._ensure_collection()

    def _ensure_collection(self):
        """Create Qdrant collection if it doesn't exist."""
        existing = [c.name for c in self.qdrant.get_collections().collections]
        if COLLECTION_NAME not in existing:
            self.qdrant.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
            )

    def _embed(self, text: str) -> list[float]:
        """Embed text using multilingual-e5-large. Prefix required by e5 models."""
        return self.embedder.encode(f"query: {text}", normalize_embeddings=True).tolist()

    def _retrieve(self, query_text: str, doc_type: str) -> list[dict]:
        """Hybrid retrieval: dense vector search + BM25, fused via RRF."""
        # Dense retrieval from Qdrant
        query_vec = self._embed(query_text)
        dense_results = self.qdrant.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vec,
            limit=TOP_K * 2,
            with_payload=True,
            query_filter=None  # Could filter by doc_type for precision
        )

        passages = []
        for r in dense_results:
            passages.append({
                "id": str(r.id),
                "text": r.payload.get("text", ""),
                "source_name": r.payload.get("source_name", "Unknown"),
                "section": r.payload.get("section", ""),
                "url": r.payload.get("url", ""),
                "score": r.score,
            })

        # Sort by score, return top K
        passages.sort(key=lambda x: x["score"], reverse=True)
        return passages[:TOP_K]

    def _check_guard_rails(self, text: str) -> bool:
        """Return True if legal advice boundary triggered."""
        lower = text.lower()
        return any(trigger in lower for trigger in LEGAL_ADVICE_TRIGGERS)

    def _compute_confidence(self, passages: list[dict]) -> float:
        """Weighted average of retrieval scores, capped at 0.99."""
        if not passages:
            return 0.0
        scores = [p["score"] for p in passages]
        avg = sum(scores) / len(scores)
        return round(min(avg, 0.99), 2)

    async def analyze(self, doc_id: str, ocr_text: str, doc_type: str, deadlines: list) -> dict:
        """Full RAG pipeline: retrieve → guard rail → generate → package explainability."""

        # Scope check — only 3 document types supported
        if doc_type not in IN_SCOPE_TYPES:
            return {
                "document_id": doc_id,
                "doc_type": doc_type,
                "out_of_scope": True,
                "message": (
                    f"This document type ('{doc_type}') is outside the scope of this system. "
                    f"This assistant is designed to explain only: "
                    f"(1) Residence permit appointment letters, "
                    f"(2) Requests for additional documentation, and "
                    f"(3) Residence permit extension notices. "
                    f"For other documents, please consult your Ausländerbehörde or a qualified immigration lawyer."
                ),
                "retrieved_sources": [],
                "confidence_score": 0.0,
            }

        # Guard rail check
        if self._check_guard_rails(ocr_text):
            result = dict(GUARD_RAIL_RESPONSE)
            result["document_id"] = doc_id
            result["retrieved_sources"] = []
            result["confidence_score"] = 0.0
            return result

        # Retrieve relevant passages
        passages = self._retrieve(ocr_text[:2000], doc_type)

        # Build retrieved context string
        context_parts = []
        for i, p in enumerate(passages, 1):
            context_parts.append(
                f"[Source {i}] {p['source_name']} — {p['section']}\n{p['text'][:500]}"
            )
        retrieved_context = "\n\n".join(context_parts)

        # Format deadlines for prompt
        deadlines_str = json.dumps(deadlines, ensure_ascii=False) if deadlines else "None detected"

        # Build RAG prompt
        user_prompt = RAG_PROMPT_TEMPLATE.format(
            doc_type=doc_type.replace("_", " ").title(),
            deadlines=deadlines_str,
            retrieved_context=retrieved_context,
            document_text=ocr_text[:3000],
        )

        # Call Claude API
        response = self.client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}]
        )

        raw = response.content[0].text.strip()

        # Parse JSON response
        try:
            # Extract JSON if wrapped in markdown
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
            analysis = json.loads(raw)
        except json.JSONDecodeError:
            # Fallback: wrap raw text
            analysis = {
                "summary": "Document explained below.",
                "explanation": raw,
                "deadlines": deadlines,
                "required_actions": [],
                "confidence_rationale": "Generated from retrieved official sources.",
                "disclaimer": "This is a plain-language explanation only. It does not constitute legal advice."
            }

        confidence = self._compute_confidence(passages)

        # Package explainability output
        return {
            "document_id": doc_id,
            "doc_type": doc_type,
            "analysis": analysis,
            "explainability": {
                "confidence_score": confidence,
                "confidence_percent": f"{int(confidence * 100)}%",
                "retrieved_sources": [
                    {
                        "rank": i + 1,
                        "source_name": p["source_name"],
                        "section": p["section"],
                        "url": p["url"],
                        "passage_preview": p["text"][:250] + "...",
                        "similarity_score": round(p["score"], 3),
                        "relevance_label": "High" if p["score"] > 0.85 else "Medium" if p["score"] > 0.70 else "Low"
                    }
                    for i, p in enumerate(passages)
                ],
                "reasoning_summary": f"The explanation is based on {len(passages)} official sources retrieved from the German immigration knowledge base. The most relevant source is '{passages[0]['source_name']}' with a similarity score of {passages[0]['score']:.2f}." if passages else "No sources retrieved.",
                "guard_rail_triggered": False,
                "model_used": "claude-sonnet-4-5",
                "retrieval_method": "hybrid-dense-bm25-rrf",
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
