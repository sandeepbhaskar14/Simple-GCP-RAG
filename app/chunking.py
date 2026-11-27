"""File-aware chunking for PDF, DOCX, TXT, and CSV documents."""
from __future__ import annotations
import csv
import io
import re
from typing import Dict, Iterable, List
from docx import Document

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150
DEFAULT_CSV_ROWS_PER_CHUNK = 20
_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

def _merge_splits(parts: Iterable[str], separator: str, chunk_size: int, overlap: int) -> List[str]:
    chunks, current, current_length = [], [], 0
    for raw_part in parts:
        part = raw_part.strip()
        if not part:
            continue
        proposed = current_length + (len(separator) if current else 0) + len(part)
        if proposed > chunk_size and current:
            combined = separator.join(current).strip()
            if combined:
                chunks.append(combined)
            # Keep overlap where possible, but never let overlap make the next
            # chunk exceed chunk_size.
            while current and (
                current_length > overlap
                or current_length + len(separator) + len(part) > chunk_size
            ):
                removed = current.pop(0)
                current_length -= len(removed)
                if current:
                    current_length -= len(separator)
        if len(part) > chunk_size:
            if current:
                chunks.append(separator.join(current).strip())
                current, current_length = [], 0
            step = max(1, chunk_size - overlap)
            chunks.extend(part[i:i + chunk_size].strip() for i in range(0, len(part), step))
            continue
        if current:
            current_length += len(separator)
        current.append(part)
        current_length += len(part)
    if current:
        combined = separator.join(current).strip()
        if combined:
            chunks.append(combined)
    result = []
    for chunk in chunks:
        if chunk and (not result or chunk != result[-1]):
            result.append(chunk)
    return result

def recursive_split_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE,
                         overlap: int = DEFAULT_CHUNK_OVERLAP,
                         separators: List[str] | None = None) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Require chunk_size > overlap >= 0.")
    separators = list(separators or _SEPARATORS)
    def split_level(value: str, remaining: List[str]) -> List[str]:
        if len(value) <= chunk_size:
            return [value]
        if not remaining:
            step = chunk_size - overlap
            return [value[i:i + chunk_size] for i in range(0, len(value), step)]
        separator = remaining[0]
        parts = value.split(separator) if separator else list(value)
        good = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            good.extend([part] if len(part) <= chunk_size else split_level(part, remaining[1:]))
        return _merge_splits(good, separator, chunk_size, overlap)
    return split_level(text, separators)

def chunk_pdf(file_bytes: bytes, filename: str, chunk_size: int = DEFAULT_CHUNK_SIZE,
              overlap: int = DEFAULT_CHUNK_OVERLAP) -> List[Dict]:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(file_bytes))
    output = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        for part_index, part in enumerate(recursive_split_text(text, chunk_size, overlap)):
            output.append({"content": part, "metadata": {
                "filename": filename, "file_type": "pdf", "page": page_number,
                "page_chunk": part_index}})
    return output

def chunk_docx(file_bytes: bytes, filename: str, chunk_size: int = DEFAULT_CHUNK_SIZE,
               overlap: int = DEFAULT_CHUNK_OVERLAP) -> List[Dict]:
    document = Document(io.BytesIO(file_bytes))
    sections, heading_stack, current_paragraphs, current_path = [], {}, [], []
    def flush():
        nonlocal current_paragraphs
        body = "\n\n".join(current_paragraphs).strip()
        if body:
            sections.append({"body": body, "heading": current_path[-1] if current_path else None,
                             "heading_path": list(current_path)})
        current_paragraphs = []
    for paragraph in document.paragraphs:
        value = paragraph.text.strip()
        if not value:
            continue
        match = re.match(r"Heading\s+([1-9])$", (paragraph.style.name or "").strip(), re.I)
        if match:
            flush()
            level = int(match.group(1))
            heading_stack[level] = value
            for deeper in list(heading_stack):
                if deeper > level:
                    del heading_stack[deeper]
            current_path = [heading_stack[key] for key in sorted(heading_stack)]
        else:
            current_paragraphs.append(value)
    flush()
    if not sections:
        plain = "\n\n".join(p.text.strip() for p in document.paragraphs if p.text.strip())
        if plain:
            sections = [{"body": plain, "heading": None, "heading_path": []}]
    output = []
    for section_index, section in enumerate(sections):
        prefix = " > ".join(section["heading_path"])
        text = (prefix + "\n\n" if prefix else "") + section["body"]
        for part_index, part in enumerate(recursive_split_text(text, chunk_size, overlap)):
            output.append({"content": part, "metadata": {
                "filename": filename, "file_type": "docx", "section": section_index,
                "section_chunk": part_index, "heading": section["heading"],
                "heading_path": section["heading_path"]}})
    return output

def chunk_txt(file_bytes: bytes, filename: str, chunk_size: int = DEFAULT_CHUNK_SIZE,
              overlap: int = DEFAULT_CHUNK_OVERLAP) -> List[Dict]:
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("TXT files must be UTF-8 encoded.") from exc
    return [{"content": part, "metadata": {"filename": filename, "file_type": "txt",
             "chunk_part": index}}
            for index, part in enumerate(recursive_split_text(text, chunk_size, overlap))]

def chunk_csv(file_bytes: bytes, filename: str,
              rows_per_chunk: int = DEFAULT_CSV_ROWS_PER_CHUNK) -> List[Dict]:
    if rows_per_chunk <= 0:
        raise ValueError("rows_per_chunk must be greater than zero.")
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV files must be UTF-8 encoded.") from exc
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames
    if not headers:
        raise ValueError("CSV must contain a header row.")
    rows = list(reader)
    output = []
    for group_index, start in enumerate(range(0, len(rows), rows_per_chunk)):
        group = rows[start:start + rows_per_chunk]
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(group)
        output.append({"content": buffer.getvalue().strip(), "metadata": {
            "filename": filename, "file_type": "csv", "row_start": start + 1,
            "row_end": start + len(group), "row_count": len(group),
            "columns": headers, "group": group_index}})
    return output

def chunk_document(file_bytes: bytes, filename: str) -> List[Dict]:
    from pathlib import Path
    extension = Path(filename).suffix.lower()
    if extension == ".pdf":
        return chunk_pdf(file_bytes, filename)
    if extension == ".docx":
        return chunk_docx(file_bytes, filename)
    if extension == ".txt":
        return chunk_txt(file_bytes, filename)
    if extension == ".csv":
        return chunk_csv(file_bytes, filename)
    raise ValueError("Unsupported file type. Allowed: PDF, DOCX, TXT, CSV.")
