"""Grounded answer generation with validated, conditional document citations."""
import json
import re

from google import genai
from app.config import PROJECT_ID, LOCATION, LLM_MODEL

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
NOT_FOUND_ANSWER = "I couldn't find sufficient information about this in the available documents."


def generate_answer(question, retrieved_chunks, history=None):
    """Generate an answer and return only citations the model ties to evidence."""
    history = history or []
    source_map = {}
    context_blocks = []

    for index, chunk in enumerate(retrieved_chunks or [], start=1):
        source_id = f"S{index}"
        source_map[source_id] = chunk
        metadata = chunk.get("metadata") or {}
        context_blocks.append(
            f"[{source_id}] File: {chunk.get('filename', 'unknown')}; "
            f"Metadata: {json.dumps(metadata, ensure_ascii=False)}\n"
            f"{chunk.get('content', '')}"
        )

    context = "\n\n".join(context_blocks) or "(No document passages were retrieved.)"
    history_text = "\n".join(
        f"{item.get('role', 'user').upper()}: {item.get('content', '')}"
        for item in history[-10:]
        if item.get("role") in {"user", "assistant"}
    ) or "(No previous conversation.)"

    prompt = f"""
You are a careful conversational RAG assistant.

Use document passages as the authoritative source for claims about uploaded
documents. You may use conversation history to resolve follow-up references,
but do not present unsupported document claims as facts.

If document passages do not support an answer, say that you could not find
sufficient information in the available documents. Do not invent details.

Return ONLY valid JSON:
{{
  "answer": "the user-facing answer",
  "grounded": true,
  "source_ids": ["S1"]
}}

Rules:
- grounded=true only when the answer is directly supported by document passages.
- source_ids may contain only IDs shown in the document context.
- If documents do not support the answer, set grounded=false and source_ids=[].
- If the answer relies only on conversation history, set grounded=false and source_ids=[].
- Never invent source IDs, filenames, page numbers, headings, or row numbers.
- Be concise and answer the user's actual question.

Recent conversation:
{history_text}

Document context:
{context}

Current question:
{question}
"""
    response = client.models.generate_content(model=LLM_MODEL, contents=prompt)
    raw = (response.text or "").strip()

    try:
        cleaned = re.sub(r"^\`\`\`(?:json)?\s*|\s*\`\`\`$", "", raw, flags=re.IGNORECASE)
        payload = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        # Fail closed: malformed model output must never emit document citations.
        return {"answer": NOT_FOUND_ANSWER, "grounded": False, "sources": []}

    answer = str(payload.get("answer") or NOT_FOUND_ANSWER).strip()
    requested_ids = payload.get("source_ids") or []
    valid_ids = list(dict.fromkeys(
        source_id for source_id in requested_ids
        if isinstance(source_id, str) and source_id in source_map
    ))

    grounded = payload.get("grounded") is True and bool(valid_ids)
    if not grounded:
        return {"answer": answer, "grounded": False, "sources": []}

    sources = []
    for source_id in valid_ids:
        chunk = source_map[source_id]
        metadata = chunk.get("metadata") or {}
        sources.append({
            "source_id": source_id,
            "document_id": chunk.get("document_id"),
            "filename": chunk.get("filename"),
            "chunk_number": chunk.get("chunk_number"),
            "distance": chunk.get("distance"),
            "page": metadata.get("page"),
            "heading": metadata.get("heading"),
            "heading_path": metadata.get("heading_path"),
            "row_start": metadata.get("row_start"),
            "row_end": metadata.get("row_end"),
            "text": chunk.get("content"),
        })

    return {"answer": answer, "grounded": True, "sources": sources}
