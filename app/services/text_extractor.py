from pathlib import Path

from docx import Document
from pypdf import PdfReader


def extract_text_from_txt(file_path: str) -> str:
    path = Path(file_path)

    return path.read_text(encoding="utf-8")


def extract_text_from_docx(file_path: str) -> str:
    document = Document(file_path)

    paragraphs = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            paragraphs.append(text)

    return "\n".join(paragraphs)


def extract_text_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)

    pages_text = []

    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages_text.append(text)

    return "\n".join(pages_text)


def extract_text(file_path: str) -> str:
    path = Path(file_path)
    extension = path.suffix.lower()

    if extension == ".txt":
        return extract_text_from_txt(file_path)

    if extension == ".docx":
        return extract_text_from_docx(file_path)

    if extension == ".pdf":
        return extract_text_from_pdf(file_path)

    raise ValueError("Неподдерживаемый формат файла")