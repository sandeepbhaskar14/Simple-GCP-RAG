CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_chunks (
    id BIGSERIAL PRIMARY KEY,

    document_id UUID NOT NULL,
    filename TEXT NOT NULL,

    content TEXT NOT NULL,

    embedding VECTOR(768),

    chunk_number INTEGER NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);