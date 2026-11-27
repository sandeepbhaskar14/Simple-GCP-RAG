# main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.ingestion import ingest_document
from app.retrieval import retrieve_chunks
from app.generation import generate_answer


app = FastAPI(title="Simple GCP RAG")


class QuestionRequest(BaseModel):

    question: str


@app.get("/")
def home():

    return {
        "message": "Simple GCP RAG API is running"
    }


# INGESTION ENDPOINT

@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):

    try:

        file_bytes = await file.read()

        result = ingest_document(
            file_bytes,
            file.filename
        )

        return {
            "status": "success",
            "message": "Document ingested successfully",
            **result
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# RETRIEVAL + GENERATION ENDPOINT

@app.post("/ask")
def ask(request: QuestionRequest):

    try:

        # 1. Retrieve relevant chunks

        chunks = retrieve_chunks(
            request.question,
            top_k=5
        )

        if not chunks:
            return {
                "question": request.question,
                "answer": "No documents have been ingested yet.",
                "sources": []
            }

        # 2. Generate answer

        answer = generate_answer(
            request.question,
            chunks
        )

        return {
            "question": request.question,
            "answer": answer,
            "sources": [
                {
                    "filename": chunk["filename"],
                    "chunk_number": chunk["chunk_number"],
                    "distance": chunk["distance"]
                }
                for chunk in chunks
            ]
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )