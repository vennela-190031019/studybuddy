"""
Turns an uploaded PDF or pasted text into clean text, and (if it's long)
splits it into chunks small enough to comfortably fit in a prompt.

Chunking here is intentionally simple — paragraph-based with a max size —
which is enough for lecture notes / textbook chapters. If you later want
to handle much longer documents, this is the piece you'd swap for a vector
store (Chroma/FAISS) + embeddings-based retrieval, same idea as DocuChat.
"""
from io import BytesIO
from pypdf import PdfReader


def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages).strip()


def chunk_text(text: str, max_chars: int = 6000) -> list[str]:
    """
    Splits text into chunks under max_chars, breaking on paragraph
    boundaries where possible so we don't cut a sentence in half.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = f"{current}\n\n{para}".strip()
        else:
            if current:
                chunks.append(current)
            current = para

    if current:
        chunks.append(current)

    return chunks or [text[:max_chars]]
