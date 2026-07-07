from pathlib import Path
import fitz  # PyMuPDF


def extract_pdf(file_path: str) -> str:
    """Extract full text from a PDF file using PyMuPDF."""
    doc = fitz.open(file_path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if text.strip():
            pages.append(f"[Page {i + 1}]\n{text}")
    doc.close()
    return "\n\n".join(pages)


def extract_pdf_with_metadata(file_path: str) -> tuple[str, dict]:
    """Extract text and document metadata from PDF."""
    doc = fitz.open(file_path)
    meta = doc.metadata
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if text.strip():
            pages.append(f"[Page {i + 1}]\n{text}")
    doc.close()
    return "\n\n".join(pages), meta
