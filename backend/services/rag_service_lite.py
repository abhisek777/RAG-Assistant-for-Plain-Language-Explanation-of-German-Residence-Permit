"""
RAG Service — Lite version (no Qdrant, in-memory BM25 + Claude API)
Works with just ANTHROPIC_API_KEY set. No Docker required.
"""
import os, json, re
from datetime import datetime
from typing import Any
import anthropic
from rank_bm25 import BM25Okapi

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
IN_SCOPE_TYPES = {"appointment_letter", "documentation_request", "extension_notice"}

# ── Inline knowledge base (official German immigration info) ─────────────────
KNOWLEDGE_BASE = [
    {
        "id": "aufenthg_26",
        "source_name": "German Residence Act (AufenthG) § 26",
        "section": "Duration of Residence Permits",
        "url": "https://www.gesetze-im-internet.de/aufenthg_2004/__26.html",
        "text": "The residence permit is issued for a limited period. The immigration authority (Ausländerbehörde) sets the duration. Before the permit expires, an extension application (Verlängerungsantrag) must be submitted. Late applications may affect legal residence status. Applicants must appear in person at the Ausländerbehörde."
    },
    {
        "id": "aufenthg_81",
        "source_name": "German Residence Act (AufenthG) § 81",
        "section": "Application for Residence Title",
        "url": "https://www.gesetze-im-internet.de/aufenthg_2004/__81.html",
        "text": "A residence permit may be extended upon application. The application must be filed before the current permit expires. If the application is submitted in time, the legal residence is maintained during the review period (Fiktionsbescheinigung). Required documents must be submitted completely."
    },
    {
        "id": "bamf_extension",
        "source_name": "BAMF — Extending a Residence Permit",
        "section": "Extension Procedure",
        "url": "https://www.bamf.de/EN/Themen/MigrationAufenthalt/ZuwandererDrittstaaten/Migrathek/Aufenthaltstitel/aufenthaltstitel-node.html",
        "text": "To extend a residence permit, submit the application at your local Ausländerbehörde. Bring: valid passport, current residence permit, proof of sufficient income (Einkommensnachweis), proof of accommodation (Wohnungsnachweis), health insurance confirmation, and any additionally requested documents. Processing times vary by city — apply at least 6–8 weeks before expiry."
    },
    {
        "id": "bamf_appointment",
        "source_name": "BAMF — Appointment at the Ausländerbehörde",
        "section": "Appointment Procedure",
        "url": "https://www.bamf.de/EN/Themen/MigrationAufenthalt/ZuwandererDrittstaaten/Migrathek/aufenthaltstitel-node.html",
        "text": "You have been invited to attend a personal appointment (persönliche Vorsprache) at the immigration authority. You must appear in person on the stated date and time. Bring all required documents. If you cannot attend, contact the Ausländerbehörde immediately to reschedule — missing the appointment without notice may delay your application."
    },
    {
        "id": "bamf_docs_request",
        "source_name": "BAMF — Documentation Requirements",
        "section": "Required Documents",
        "url": "https://www.bamf.de/EN/Themen/MigrationAufenthalt/ZuwandererDrittstaaten/Migrathek/Dokumente/dokumente-node.html",
        "text": "The immigration authority has requested additional documents (Nachforderung) to process your application. You must submit the requested documents within the stated deadline. Missing the deadline may result in rejection of your application. Commonly requested documents include: proof of income, employment contract, enrollment certificate, health insurance, rental agreement, and passport copies."
    },
    {
        "id": "aufenthaltsv_general",
        "source_name": "Residence Ordinance (AufenthV)",
        "section": "General Provisions on Required Documents",
        "url": "https://www.gesetze-im-internet.de/aufenthv/",
        "text": "Applicants must provide all documents requested by the Ausländerbehörde. Documents in languages other than German must be accompanied by a certified translation. Biometric photographs must meet current specifications. The authority may request additional documents if necessary to assess the application."
    },
    {
        "id": "bfa_deadline",
        "source_name": "Federal Foreign Office — Deadlines",
        "section": "Importance of Deadlines",
        "url": "https://www.auswaertiges-amt.de/en/visa-service",
        "text": "Deadlines in German immigration procedures are legally binding. Missing a deadline (Fristversäumnis) can result in loss of legal residence status, obligation to leave the country, or rejection of an application. If you cannot meet a deadline, contact the responsible authority (Ausländerbehörde) immediately and explain your situation in writing."
    },
    {
        "id": "plain_language_rights",
        "source_name": "Rights and Obligations — Plain Language Guide",
        "section": "Understanding Your Document",
        "url": "https://www.bamf.de/EN/Themen/MigrationAufenthalt/ZuwandererDrittstaaten/migrathek-node.html",
        "text": "German immigration documents are official letters from the Ausländerbehörde (immigration authority). They contain important information about your residence status, required actions, and deadlines. Read the document carefully. Note all deadlines. Gather all requested documents. If you do not understand the document, seek assistance from a recognised advice centre (Beratungsstelle) or a qualified immigration lawyer (Fachanwalt für Ausländerrecht)."
    },
]

# Pre-tokenise for BM25
_tokenised = [doc["text"].lower().split() for doc in KNOWLEDGE_BASE]
_bm25 = BM25Okapi(_tokenised)

LEGAL_ADVICE_TRIGGERS = [
    "what should i do legally", "will i be deported", "will i win",
    "can they reject", "is it legal to", "my rights", "sue",
    "appeal my case", "legal strategy", "what are my chances",
    "will the judge", "should i fight", "legal advice"
]

GUARD_RAIL_RESPONSE = {
    "summary": "This question requires legal advice which this system cannot provide.",
    "explanation": "Your query appears to ask for legal advice or a prediction about a legal outcome. This system is designed only to explain documents in plain language. Please consult a licensed immigration lawyer (Fachanwalt für Ausländerrecht) or contact your local Ausländerbehörde.",
    "deadlines": [],
    "required_actions": [
        "Consult a licensed immigration lawyer (Fachanwalt für Ausländerrecht).",
        "Contact your Ausländerbehörde for official guidance."
    ],
    "confidence_rationale": "Guard rail triggered — legal advice boundary.",
    "disclaimer": "This system does not provide legal advice.",
    "guard_rail_triggered": True
}

SYSTEM_PROMPT = """You are an AI assistant that explains German immigration administrative documents in plain language.

CRITICAL RULES:
1. ONLY explain what is in the document and retrieved sources. Do not add information from outside.
2. Do NOT provide legal advice, predict outcomes, or make administrative decisions.
3. Use plain language at B1 CEFR level — short sentences, simple words.
4. Always include the legal disclaimer.
5. Respond with valid JSON matching the schema provided."""

RAG_PROMPT = """Explain this German immigration document to a non-expert user.

DOCUMENT TYPE: {doc_type}
DETECTED DEADLINES: {deadlines}

OFFICIAL SOURCES RETRIEVED:
{context}

DOCUMENT TEXT:
{doc_text}

Reply ONLY with this JSON:
{{
  "summary": "2-3 sentence plain-language summary",
  "explanation": "200-300 word plain-language explanation (B1 CEFR level)",
  "deadlines": [{{"date": "DD.MM.YYYY or description", "description": "what must happen", "urgency": "high|normal"}}],
  "required_actions": ["Action 1", "Action 2"],
  "confidence_rationale": "One sentence on why you are confident based on retrieved sources.",
  "disclaimer": "This is a plain-language explanation only. It does not constitute legal advice. For legal decisions, consult a licensed immigration lawyer (Fachanwalt für Ausländerrecht) or contact the Ausländerbehörde directly."
}}"""


def _retrieve(query: str, top_k: int = 5) -> list[dict]:
    tokens = query.lower().split()
    scores = _bm25.get_scores(tokens)
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
    results = []
    for idx, score in ranked:
        doc = KNOWLEDGE_BASE[idx].copy()
        doc["score"] = round(float(score), 3)
        results.append(doc)
    return results


def _guard(text: str) -> bool:
    lower = text.lower()
    return any(t in lower for t in LEGAL_ADVICE_TRIGGERS)


async def analyze(doc_id: str, ocr_text: str, doc_type: str, deadlines: list) -> dict:
    if doc_type not in IN_SCOPE_TYPES:
        return {
            "document_id": doc_id, "doc_type": doc_type, "out_of_scope": True,
            "message": (
                f"Document type '{doc_type}' is outside the system scope. "
                "This assistant handles: (1) Residence permit appointment letters, "
                "(2) Requests for additional documentation, "
                "(3) Residence permit extension notices. "
                "For other documents, please contact your Ausländerbehörde or a qualified immigration lawyer."
            ),
            "retrieved_sources": [], "confidence_score": 0.0,
        }

    if _guard(ocr_text):
        r = dict(GUARD_RAIL_RESPONSE)
        r["document_id"] = doc_id
        r["retrieved_sources"] = []
        r["confidence_score"] = 0.0
        return r

    passages = _retrieve(ocr_text[:1500], top_k=5)
    context = "\n\n".join(
        f"[Source {i+1}] {p['source_name']} — {p['section']}\n{p['text']}"
        for i, p in enumerate(passages)
    )

    user_prompt = RAG_PROMPT.format(
        doc_type=doc_type.replace("_", " ").title(),
        deadlines=json.dumps(deadlines, ensure_ascii=False) if deadlines else "None detected",
        context=context,
        doc_text=ocr_text[:2000],
    )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}]
    )
    raw = response.content[0].text.strip()

    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        analysis = json.loads(raw)
    except json.JSONDecodeError:
        analysis = {
            "summary": "Document explained below.",
            "explanation": raw,
            "deadlines": deadlines,
            "required_actions": [],
            "confidence_rationale": "Generated from retrieved official sources.",
            "disclaimer": "This is a plain-language explanation only. It does not constitute legal advice."
        }

    scores = [p["score"] for p in passages]
    confidence = round(min(sum(scores) / len(scores) / 10, 0.99), 2) if scores else 0.5

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
                    "similarity_score": p["score"],
                    "relevance_label": "High" if p["score"] > 5 else "Medium" if p["score"] > 2 else "Low"
                }
                for i, p in enumerate(passages)
            ],
            "reasoning_summary": f"Explanation based on {len(passages)} official sources. Most relevant: '{passages[0]['source_name']}'." if passages else "No sources retrieved.",
            "guard_rail_triggered": False,
            "model_used": "claude-haiku-4-5-20251001",
            "retrieval_method": "bm25-in-memory",
        },
        "timestamp": datetime.utcnow().isoformat(),
    }
