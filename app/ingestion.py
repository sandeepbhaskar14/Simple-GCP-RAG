from pathlib import Path
import uuid

from psycopg.types.json import Jsonb

from app.chunking import chunk_document
from app.storage import upload_to_gcs
from app.embeddings import generate_embeddings
from app.database import get_connection


def ingest_document(file_bytes, filename):
    """Upload, format-aware chunk, embed, and persist a document."""
    if not file_bytes:
        raise ValueError("The uploaded file is empty.")
    filename = Path(filename or "").name
    if not filename:
        raise ValueError("A valid filename is required.")

    # Validate and chunk before uploading, avoiding GCS orphans for invalid files.
    chunks = chunk_document(file_bytes, filename)
    if not chunks:
        raise ValueError("No extractable text or rows found in document.")

    document_id = str(uuid.uuid4())
    gcs_uri = upload_to_gcs(file_bytes, f"{document_id}/{filename}")
    embeddings = generate_embeddings([item["content"] for item in chunks])
    if len(embeddings) != len(chunks):
        raise RuntimeError("Embedding count does not match chunk count.")

    with get_connection() as conn:
        with conn.cursor() as cursor:
            for index, (item, embedding) in enumerate(zip(chunks, embeddings)):
                cursor.execute(
                    """
                    INSERT INTO document_chunks
                    (document_id, filename, content, embedding, chunk_number, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (document_id, filename, item["content"], embedding, index,
                     Jsonb(item["metadata"])),
                )

    return {
        "document_id": document_id,
        "filename": filename,
        "gcs_uri": gcs_uri,
        "total_chunks": len(chunks),
        "file_type": Path(filename).suffix.lower().lstrip("."),
    }
