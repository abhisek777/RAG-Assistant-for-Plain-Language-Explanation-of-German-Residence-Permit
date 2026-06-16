# 🚀 Run the Immigration Document Assistant

## Prerequisites
- Python 3.10+
- Node.js 18+
- Tesseract OCR installed on your machine
  - Mac: `brew install tesseract tesseract-lang`
  - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki

---

## Step 1 — Set your API Key

```bash
cd prototype
cp .env.example .env
```

Open `.env` and replace the placeholder with your real Anthropic API key:
```
ANTHROPIC_API_KEY=sk-ant-your-real-key-here
```

---

## Step 2 — Install & start the Backend

Open a terminal in the `prototype/` folder:

```bash
cd backend

# Install Python dependencies
pip install -r requirements_lite.txt

# Download the small German spaCy model
python -m spacy download de_core_news_sm

# Start the backend (reads .env automatically)
uvicorn main_lite:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Health check: http://localhost:8000/api/v1/health

---

## Step 3 — Install & start the Frontend

Open a **second terminal** in the `prototype/` folder:

```bash
cd frontend

# Install Node dependencies
npm install

# Start the dev server
npm run dev
```

You should see:
```
▲ Next.js 14.x.x
- Local: http://localhost:3000
```

---

## Step 4 — Open the App

Go to **http://localhost:3000** in your browser.

---

## What the app does

| Step | What happens |
|------|-------------|
| Upload | Drop a PDF or image of a German immigration document |
| Processing | OCR extracts text → BM25 retrieves relevant law passages → Claude generates plain-language explanation |
| Results | Summary, deadlines, required actions, confidence score |
| Sources | Retrieved passages with relevance scores (explainability) |
| Feedback | 5-star rating + comment, stored on backend |

Supported document types:
- Appointment letters (`Terminbestätigung`)
- Documentation requests (`Dokumentenanforderung`)
- Extension notices (`Verlängerungsbescheid`)

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ANTHROPIC_API_KEY not set` | Make sure `.env` exists in `prototype/` with your key |
| `tesseract not found` | Install Tesseract (see Prerequisites above) |
| `ModuleNotFoundError: rank_bm25` | Run `pip install -r requirements_lite.txt` again |
| Frontend shows CORS error | Make sure backend is running on port 8000 |
| `npm install` fails | Make sure Node.js 18+ is installed |

---

## Architecture (lite mode)

```
Browser (Next.js 14)
    ↓ POST /api/v1/upload
FastAPI backend
    ↓ Tesseract OCR
    ↓ BM25 in-memory retrieval (no Qdrant needed)
    ↓ Claude claude-sonnet API
    ↑ JSON: summary + sources + confidence + deadlines
Browser renders results
```

No Docker, no GPU, no vector database required for this demo.
