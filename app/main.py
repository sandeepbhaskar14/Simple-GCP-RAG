from typing import Optional
from uuid import UUID

from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel, Field

from app.ingestion import ingest_document
from app.retrieval import retrieve_chunks
from app.generation import generate_answer, NOT_FOUND_ANSWER
from app.chat_history import (
    create_chat, list_chats, get_chat, get_recent_messages,
    add_message, delete_chat,
)

app = FastAPI(title="Simple GCP RAG")


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=12000)
    chat_id: Optional[UUID] = None


class CreateChatRequest(BaseModel):
    title: str = Field(default="New chat", max_length=160)


@app.get("/")
def home():
    return {"message": "Simple GCP RAG API is running"}


@app.post("/ingest")
async def ingest(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        result = ingest_document(file_bytes, file.filename)
        return {"status": "success", "message": "Document ingested successfully", **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Document ingestion failed.") from exc


@app.post("/chats")
def create_new_chat(request: CreateChatRequest):
    try:
        return create_chat(request.title)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not create chat.") from exc


@app.get("/chats")
def get_chats(limit: int = 50):
    try:
        return list_chats(max(1, min(limit, 100)))
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not load chats.") from exc


@app.get("/chats/{chat_id}")
def get_chat_by_id(chat_id: UUID):
    try:
        chat = get_chat(str(chat_id))
        if chat is None:
            raise HTTPException(status_code=404, detail="Chat not found.")
        return chat
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not load chat.") from exc


@app.delete("/chats/{chat_id}")
def remove_chat(chat_id: UUID):
    try:
        if not delete_chat(str(chat_id)):
            raise HTTPException(status_code=404, detail="Chat not found.")
        return {"status": "success", "chat_id": str(chat_id)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not delete chat.") from exc


@app.post("/ask")
def ask(request: QuestionRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        chat_id = str(request.chat_id) if request.chat_id else create_chat()["id"]
        if get_chat(chat_id) is None:
            raise HTTPException(status_code=404, detail="Chat not found.")

        # Load previous turns before storing this new question.
        history = get_recent_messages(chat_id, limit=10)
        add_message(chat_id, "user", question)

        chunks = retrieve_chunks(question, top_k=5)

        if not chunks and not history:
            result = {"answer": NOT_FOUND_ANSWER, "grounded": False, "sources": []}
        else:
            result = generate_answer(question, chunks, history=history)

        # Sources are already validated against retrieved chunk IDs by generation.py.
        add_message(chat_id, "assistant", result["answer"], result.get("sources", []))

        return {
            "chat_id": chat_id,
            "question": question,
            "answer": result["answer"],
            "grounded": result.get("grounded", False),
            "sources": result.get("sources", []),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Question processing failed.") from exc
