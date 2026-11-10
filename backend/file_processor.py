"""
File processing utilities: text extraction from PDF, DOCX, TXT, MD, CSV, JSON.
Chunking for large documents.
"""
import io
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

MAX_CHUNK_CHARS = 6000  # safe context window for smaller LLMs
MAX_EXTRACT_CHARS = 20000


def extract_text(filename: str, content: bytes) -> str:
    """Extract readable text from uploaded file bytes based on extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    try:
        if ext in ("txt", "md"):
            return content.decode("utf-8", errors="replace")[:MAX_EXTRACT_CHARS]

        elif ext == "pdf":
            return _extract_pdf(content)

        elif ext == "docx":
            return _extract_docx(content)

        elif ext == "csv":
            return _extract_csv(content)

        elif ext == "json":
            return _extract_json(content)

        else:
            # Attempt UTF-8 decode as fallback
            text = content.decode("utf-8", errors="replace")
            return text[:MAX_EXTRACT_CHARS]

    except Exception as exc:
        logger.warning(f"[FileProcessor] Extract error for {filename}: {exc}")
        return f"[Could not extract text from {filename}: {exc}]"


def _extract_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages.append(text)
            if sum(len(p) for p in pages) > MAX_EXTRACT_CHARS:
                break
        return "\n\n".join(pages)[:MAX_EXTRACT_CHARS]
    except ImportError:
        return "[PDF extraction requires pypdf. Install it: pip install pypdf]"


def _extract_docx(content: bytes) -> str:
    try:
        import docx
        doc = docx.Document(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)[:MAX_EXTRACT_CHARS]
    except ImportError:
        return "[DOCX extraction requires python-docx. Install it: pip install python-docx]"


def _extract_csv(content: bytes) -> str:
    import csv
    text = content.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = []
    for i, row in enumerate(reader):
        rows.append(" | ".join(row))
        if i > 200:
            rows.append("... (truncated)")
            break
    return "\n".join(rows)[:MAX_EXTRACT_CHARS]


def _extract_json(content: bytes) -> str:
    try:
        data = json.loads(content.decode("utf-8", errors="replace"))
        return json.dumps(data, indent=2)[:MAX_EXTRACT_CHARS]
    except json.JSONDecodeError:
        return content.decode("utf-8", errors="replace")[:MAX_EXTRACT_CHARS]


def chunk_text(text: str, chunk_size: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split text into overlapping chunks for retrieval."""
    if not text:
        return []
    chunks = []
    step = chunk_size - 500  # 500-char overlap
    for i in range(0, len(text), step):
        chunks.append(text[i : i + chunk_size])
        if i + chunk_size >= len(text):
            break
    return chunks


def build_document_context(extracted_text: str, user_query: str, max_chars: int = 3000) -> str:
    """Select the most relevant chunk(s) for the user query (simple keyword match)."""
    if not extracted_text:
        return ""
    chunks = chunk_text(extracted_text)
    if not chunks:
        return ""

    query_words = set(user_query.lower().split())

    def score(chunk):
        lower = chunk.lower()
        return sum(1 for w in query_words if w in lower)

    ranked = sorted(chunks, key=score, reverse=True)
    selected = []
    total = 0
    for chunk in ranked:
        if total + len(chunk) > max_chars:
            break
        selected.append(chunk)
        total += len(chunk)

    return "\n\n---\n\n".join(selected)
