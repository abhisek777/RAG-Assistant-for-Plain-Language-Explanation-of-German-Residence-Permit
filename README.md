# German Immigration RAG Assistant — Prototype

**MSc AI Thesis:** Design and Evaluation of an Explainable RAG Assistant for German Immigration Documents

## Quick Start

### Prerequisites
- Docker + Docker Compose
- Python 3.11+
- Node.js 18+
- Tesseract OCR (`brew install tesseract tesseract-lang`)
- ANTHROPIC_API_KEY

### 1. Set environment variables
```bash
export ANTHROPIC_API_KEY=your_key_here
```

### 2. Start infrastructure
```bash
docker-compose up -d qdrant postgres
```

### 3. Set up backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m spacy download de_core_news_lg
uvicorn main:app --reload --port 8000
```

### 4. Ingest knowledge base
```bash
cd data
# Place source text files in ./sources/ (see ingest_knowledge_base.py for details)
python ingest_knowledge_base.py --source_dir ./sources
```

### 5. Set up frontend
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

## Project Structure
```
prototype/
├── backend/
│   ├── main.py                    # FastAPI app
│   ├── requirements.txt
│   └── services/
│       ├── ocr_service.py         # OCR + NLP pipeline
│       ├── rag_service.py         # RAG + Claude API
│       └── document_service.py    # Document store
├── frontend/
│   └── components/
│       └── DocumentAnalysis.tsx   # Main 3-panel UI component
├── data/
│   └── ingest_knowledge_base.py   # KB ingestion script
├── evaluation/
│   └── ragas_evaluate.py          # RAGAS evaluation
└── docker-compose.yml
```

## API Endpoints
| Endpoint | Method | Description |
|---|---|---|
| /api/v1/upload | POST | Upload document (PDF/image) |
| /api/v1/analyze/{doc_id} | POST | Run RAG analysis |
| /api/v1/documents | GET | List documents |
| /api/v1/feedback | POST | Submit feedback |
| /api/v1/health | GET | Health check |
| /docs | GET | OpenAPI documentation |

## Evaluation
```bash
cd evaluation
python ragas_evaluate.py --test_file test_dataset.json --output results.json
```

## Knowledge Base Sources
Add these files to `data/sources/`:
- `AufenthG.txt` — from https://www.gesetze-im-internet.de/aufenthg_2004/
- `AufenthV.txt` — from https://www.gesetze-im-internet.de/aufenthv/
- `BAMF_guidance.txt` — from https://www.bamf.de (PDF text extraction)
- `BfA_info.txt` — from https://www.auswaertiges-amt.de/en/visa-service

## Important: What this system does NOT do
- Provide legal advice
- Predict legal outcomes
- Replace immigration lawyers
- Make administrative decisions
