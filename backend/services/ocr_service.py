"""
OCR Service — Tesseract + PyMuPDF + spaCy NLP
Handles PDF and image documents, extracts structured information.
"""

import re
from typing import Any
import pytesseract
from PIL import Image, ImageFilter, ImageOps
import fitz  # PyMuPDF
import io

# spaCy is optional — version conflicts with Python 3.12 are handled gracefully
try:
    import spacy as _spacy
    _SPACY_AVAILABLE = True
except Exception:
    _spacy = None
    _SPACY_AVAILABLE = False


# Document type keywords (German)
# Scope limited to 3 categories per thesis exposé:
# 1. Residence permit appointment letters
# 2. Requests for additional documentation
# 3. Residence permit extension notices
DOC_TYPE_PATTERNS = {
    "appointment_letter": [
        "termin", "vorladung", "vorsprache", "erscheinen", "termineinladung",
        "laden wir sie ein", "bitte erscheinen sie", "persönliche vorsprache"
    ],
    "documentation_request": [
        "unterlagen", "nachreichen", "nachweise", "belege vorlegen",
        "nachforderung", "fehlende unterlagen", "bitte reichen sie", "einzureichen"
    ],
    "extension_notice": [
        "verlängerung", "verlängerungsantrag", "befristung",
        "verlängerung der aufenthaltserlaubnis", "aufenthaltserlaubnis verlängern",
        "ablauf der gültigkeit", "antrag auf verlängerung"
    ],
}

# Documents outside scope — inform user
OUT_OF_SCOPE_KEYWORDS = [
    "visum", "visumantrag", "abschiebung", "ausreisepflicht",
    "duldung", "abschiebungsandrohung", "einreise"
]

# German date patterns
DATE_PATTERNS = [
    r'\b(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\b',          # 15.08.2025
    r'\b(\d{1,2})\.\s*(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s*(\d{4})\b',
    r'\b(bis zum|bis spätestens|Frist:)\s+(\d{1,2}\.\d{1,2}\.\d{4})\b',
]

DEADLINE_KEYWORDS = ["bis zum", "bis spätestens", "frist", "ablauf", "spätestens", "innerhalb von", "deadline"]


class OCRService:
    def __init__(self):
        self.nlp = None
        if not _SPACY_AVAILABLE:
            print("Warning: spaCy not available (version conflict). NER entity extraction disabled.")
            return
        try:
            self.nlp = _spacy.load("de_core_news_lg")
        except OSError:
            try:
                self.nlp = _spacy.load("de_core_news_sm")
            except OSError:
                print("Warning: No German spaCy model found. Run: python3 -m spacy download de_core_news_sm")

    def process(self, file_path: str, content_type: str) -> dict[str, Any]:
        """Main entry point: extract text, detect type, extract structured info."""
        if content_type == "application/pdf":
            text = self._extract_pdf(file_path)
        else:
            text = self._extract_image(file_path)

        text = self._clean_text(text)
        doc_type = self._classify_document(text)
        deadlines = self._extract_deadlines(text)
        entities = self._extract_entities(text)

        return {
            "text": text,
            "doc_type": doc_type,
            "deadlines": deadlines,
            "entities": entities,
        }

    def _extract_pdf(self, path: str) -> str:
        """Extract text from PDF — native text first, OCR fallback."""
        doc = fitz.open(path)
        text_parts = []
        for page in doc:
            text = page.get_text("text")
            if len(text.strip()) > 50:
                text_parts.append(text)
            else:
                # Scanned page — render and OCR
                pix = page.get_pixmap(dpi=300)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                img = self._preprocess_image(img)
                ocr_text = pytesseract.image_to_string(img, lang="deu+eng", config="--psm 6")
                text_parts.append(ocr_text)
        return "\n\n".join(text_parts)

    def _extract_image(self, path: str) -> str:
        """OCR from image file with preprocessing."""
        img = Image.open(path)
        img = self._preprocess_image(img)
        return pytesseract.image_to_string(img, lang="deu+eng", config="--psm 6 --oem 3")

    def _preprocess_image(self, img: Image.Image) -> Image.Image:
        """Improve image quality for OCR: grayscale, denoise, binarise."""
        img = img.convert("L")                          # Grayscale
        img = img.filter(ImageFilter.MedianFilter(3))   # Denoise
        img = ImageOps.autocontrast(img)                # Contrast stretch
        # Binarise with Otsu threshold (via PIL point)
        threshold = 128
        img = img.point(lambda x: 0 if x < threshold else 255, "1")
        img = img.convert("L")
        return img

    def _clean_text(self, text: str) -> str:
        """Remove OCR artifacts and normalise whitespace."""
        text = re.sub(r'[^\S\n]+', ' ', text)           # collapse spaces
        text = re.sub(r'\n{3,}', '\n\n', text)          # max 2 newlines
        text = re.sub(r'[|¦]', '', text)                # OCR pipe artifacts
        # Rejoin hyphenated line breaks
        text = re.sub(r'-\n(\w)', r'\1', text)
        return text.strip()

    def _classify_document(self, text: str) -> str:
        """Classify into one of 3 in-scope types, or 'out_of_scope' / 'unknown'."""
        lower = text.lower()
        # Check for out-of-scope keywords first
        if any(kw in lower for kw in OUT_OF_SCOPE_KEYWORDS):
            scores = {dt: sum(1 for kw in kws if kw in lower) for dt, kws in DOC_TYPE_PATTERNS.items()}
            if max(scores.values()) == 0:
                return "out_of_scope"
        scores = {}
        for doc_type, keywords in DOC_TYPE_PATTERNS.items():
            scores[doc_type] = sum(1 for kw in keywords if kw in lower)
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "unknown"

    def _extract_deadlines(self, text: str) -> list[dict]:
        deadlines = []
        lower = text.lower()
        lines = text.split('\n')

        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(kw in line_lower for kw in DEADLINE_KEYWORDS):
                for pattern in DATE_PATTERNS:
                    matches = re.findall(pattern, line, re.IGNORECASE)
                    for match in matches:
                        date_str = match[-1] if isinstance(match, tuple) else match
                        context = line.strip()
                        # Get surrounding context
                        if i + 1 < len(lines):
                            context += " " + lines[i + 1].strip()
                        deadlines.append({
                            "date": date_str,
                            "context": context[:200],
                            "urgency": "high" if "abschiebung" in lower or "ausreise" in lower else "normal"
                        })
        # Remove duplicates
        seen = set()
        unique = []
        for d in deadlines:
            key = d["date"]
            if key not in seen:
                seen.add(key)
                unique.append(d)
        return unique

    def _extract_entities(self, text: str) -> dict:
        if not self.nlp:
            return {}
        doc = self.nlp(text[:10000])  # Limit for performance
        entities = {"persons": [], "organisations": [], "locations": [], "dates": []}
        for ent in doc.ents:
            if ent.label_ == "PER":
                entities["persons"].append(ent.text)
            elif ent.label_ == "ORG":
                entities["organisations"].append(ent.text)
            elif ent.label_ == "LOC":
                entities["locations"].append(ent.text)
            elif ent.label_ == "DATE":
                entities["dates"].append(ent.text)
        # Deduplicate
        return {k: list(set(v)) for k, v in entities.items()}
