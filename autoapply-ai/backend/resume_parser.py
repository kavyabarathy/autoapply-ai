import io
import re

from docx import Document
from pypdf import PdfReader

SKILLS = [
    "python", "java", "javascript", "typescript", "c++", "c#", "golang", "rust", "sql",
    "react", "node.js", "express", "fastapi", "flask", "django", "spring", "tailwind",
    "html", "css", "mongodb", "postgresql", "mysql", "redis", "celery", "docker",
    "kubernetes", "aws", "gcp", "azure", "git", "linux", "rest", "graphql",
    "machine learning", "nlp", "pandas", "numpy", "pytorch", "tensorflow",
    "playwright", "selenium", "langchain", "openai", "ci/cd", "agile",
    "verilog", "vhdl", "fpga", "assembly", "computer architecture",
]


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    if name.endswith(".docx"):
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs).strip()
    if name.endswith(".txt"):
        return data.decode("utf-8", errors="ignore").strip()
    raise ValueError("Unsupported file type. Upload a PDF, DOCX or TXT file.")


def extract_keywords(text: str) -> list[str]:
    lowered = text.lower()
    found = []
    for skill in SKILLS:
        pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
        if re.search(pattern, lowered):
            found.append(skill)
    return found
