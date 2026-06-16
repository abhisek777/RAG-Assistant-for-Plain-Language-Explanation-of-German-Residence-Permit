# DocAssist — Explainable RAG Assistant for German Immigration Documents

**MSc AI Thesis — IU International University of Applied Sciences**  
**Author:** Kalpana Abhiseka Maddi  
**Title:** Design and Evaluation of an Explainable RAG Assistant for Plain-Language Explanation of German Residence Permit and Immigration-Related Administrative Documents

---

## What This System Does

DocAssist takes a German immigration document uploaded by the user, extracts its text via OCR, retrieves the most relevant passages from a curated knowledge base of official German immigration law using BM25 retrieval, and generates a plain-language explanation using the Anthropic Claude API — grounded in verifiable official sources.

Three document types are in scope:
- **Terminschreiben** — appointment letters from the Ausländerbehörde
- **Nachforderungen** — requests for additional documentation
- **Verlängerungsbescheide** — residence permit extension notices

Every explanation includes the retrieved source passages and their relevance scores, so users can see what the explanation is based on. A mandatory legal boundary disclaimer is appended to every response.

**What the system does NOT do:** provide legal advice, predict outcomes, make administrative decisions, or replace qualified immigration lawyers.

---

## System Architecture

```
User uploads document (PDF / JPG / PNG)
        │
        ▼
  OCR Service (Tesseract)
        │ extracted text
        ▼
  BM25 Retrieval (rank_bm25)
        │ top-5 passages from knowledge base
        ▼
  Claude API (Anthropic) — prompt-conditioned generation
        │ plain-language explanation + citations
        ▼
  Frontend (Next.js) — structured 3-panel output
        │ Overview · Key Points · Required Actions · Sources
```

---

## Running the Prototype

### Option A — Lite Version (recommended, no Docker needed)

Uses BM25 retrieval only — no Qdrant or Postgres required.

```bash
# 1. Clone and set up
git clone https://github.com/abhisek777/RAG-Assistant-for-Plain-Language-Explanation-of-German-Residence-Permit.git
cd RAG-Assistant-for-Plain-Language-Explanation-of-German-Residence-Permit

# 2. Set your Anthropic API key
cp .env.example .env
# Edit .env and add your key: ANTHROPIC_API_KEY=sk-ant-...

# 3. Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements_lite.txt
uvicorn main_lite:app --reload --port 8000

# 4. Frontend (new terminal tab)
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**

### Option B — Full Version (with Docker)

```bash
# Prerequisites: Docker, Python 3.11+, Node.js 18+, Tesseract OCR
# brew install tesseract tesseract-lang  (macOS)

docker-compose up -d
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000
cd ../frontend && npm install && npm run dev
```

---

## Project Structure

```
├── backend/
│   ├── main.py                    # FastAPI app (full version)
│   ├── main_lite.py               # FastAPI app (lite — BM25 only)
│   ├── requirements.txt           # Full dependencies
│   ├── requirements_lite.txt      # Lite dependencies
│   └── services/
│       ├── ocr_service.py         # OCR text extraction
│       ├── rag_service.py         # BM25 retrieval + Claude API
│       ├── rag_service_lite.py    # Lite RAG service
│       └── document_service.py    # Document handling
├── frontend/
│   ├── app/                       # Next.js app router
│   └── components/
│       └── DocumentAnalysis.tsx   # Main UI component
├── data/
│   └── ingest_knowledge_base.py   # Knowledge base ingestion script
├── evaluation/
│   └── ragas_evaluate.py          # Evaluation script
├── docker-compose.yml
├── .env.example                   # Environment variable template
└── README.md
```

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/upload` | POST | Upload document (PDF/image) |
| `/api/v1/analyze/{doc_id}` | POST | Run RAG pipeline and return explanation |
| `/api/v1/health` | GET | Health check |
| `/docs` | GET | Interactive API documentation (Swagger UI) |

---

## Knowledge Base

The knowledge base covers official German immigration regulatory texts. Add source files to `data/sources/`:

- `AufenthG.txt` — Aufenthaltsgesetz (Residence Act): https://www.gesetze-im-internet.de/aufenthg_2004/
- `AufenthV.txt` — Aufenthaltsverordnung: https://www.gesetze-im-internet.de/aufenthv/
- `BeschV.txt` — Beschäftigungsverordnung: https://www.gesetze-im-internet.de/beschv_2013/
- `BAMF_guidance.txt` — BAMF guidance documents: https://www.bamf.de

Then run: `python data/ingest_knowledge_base.py --source_dir ./data/sources`

---

## Legal Boundary

This system is an academic research prototype. It provides **informational plain-language explanations only** — not legal advice. Every API response includes a mandatory disclaimer. The system does not advise on individual situations, predict legal outcomes, or make administrative decisions on behalf of users.
