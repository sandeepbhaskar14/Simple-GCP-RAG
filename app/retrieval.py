from app.database import get_connection
from app.embeddings import generate_query_embedding


def retrieve_chunks(question, top_k=5):
    """Return nearest chunks with page, heading, or row-group metadata."""
    query_embedding = generate_query_embedding(question)
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, document_id, filename, content, chunk_number, metadata,
                       embedding <=> %s::vector AS distance
                FROM document_chunks
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (query_embedding, query_embedding, top_k),
            )
            rows = cursor.fetchall()

    return [
        {
            "id": row[0],
            "document_id": str(row[1]),
            "filename": row[2],
            "content": row[3],
            "chunk_number": row[4],
            "metadata": row[5] or {},
            "distance": float(row[6]),
        }
        for row in rows
    ]
