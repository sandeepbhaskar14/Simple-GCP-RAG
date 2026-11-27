import io
import uuid

from pypdf import PdfReader

from app.storage import upload_to_gcs
from app.embeddings import generate_embeddings
from app.database import get_connection


def extract_text(file_bytes, filename):

    if filename.endswith(".pdf"):

        reader = PdfReader(io.BytesIO(file_bytes))

        text = ""

        for page in reader.pages:
            text += page.extract_text() or ""
            text += "\n"

        return text

    elif filename.endswith(".txt"):

        return file_bytes.decode("utf-8")

    else:

        raise ValueError("Only PDF and TXT files are supported")


def chunk_text(text, chunk_size=1000, overlap=150):

    chunks = []

    start = 0

    while start < len(text):

        end = start + chunk_size

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def ingest_document(file_bytes, filename):

    # 1. Upload original document to GCS

    document_id = str(uuid.uuid4())

    gcs_filename = f"{document_id}/{filename}"

    upload_to_gcs(file_bytes, gcs_filename)

    # 2. Extract text

    text = extract_text(file_bytes, filename)

    if not text.strip():
        raise ValueError("No extractable text found in document")

    # 3. Split into chunks

    chunks = chunk_text(text)

    # 4. Generate embeddings

    embeddings = generate_embeddings(chunks)

    # 5. Store chunks and embeddings in Cloud SQL

    with get_connection() as conn:

        with conn.cursor() as cursor:

            for index, (chunk, embedding) in enumerate(
                zip(chunks, embeddings)
            ):

                cursor.execute(
                    """
                    INSERT INTO document_chunks
                    (
                        document_id,
                        filename,
                        content,
                        embedding,
                        chunk_number
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        document_id,
                        filename,
                        chunk,
                        embedding,
                        index
                    )
                )

    return {
        "document_id": document_id,
        "filename": filename,
        "total_chunks": len(chunks)
    }