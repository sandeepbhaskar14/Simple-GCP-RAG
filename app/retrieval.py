
from app.database import get_connection
from app.embeddings import generate_query_embedding


def retrieve_chunks(question, top_k=5):

    # 1. Generate query embedding
    query_embedding = generate_query_embedding(question)

    # 2. Retrieve similar chunks using pgvector
    with get_connection() as conn:

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    filename,
                    content,
                    chunk_number,
                    embedding <=> %s::vector AS distance
                FROM document_chunks
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (
                    query_embedding,
                    query_embedding,
                    top_k
                )
            )

            results = cursor.fetchall()

    # 3. Return retrieved chunks
    return [
        {
            "filename": row[0],
            "content": row[1],
            "chunk_number": row[2],
            "distance": float(row[3])
        }
        for row in results
    ]
