from google import genai

from app.config import (
    PROJECT_ID,
    LOCATION,
    LLM_MODEL
)


client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION
)


def generate_answer(question, retrieved_chunks):

    # Combine retrieved chunks into context

    context = "\n\n".join(
        [
            chunk["content"]
            for chunk in retrieved_chunks
        ]
    )

    prompt = f"""
    You are a helpful RAG assistant.

    Answer the question using ONLY the provided context.

    If the answer is not available in the context,
    clearly say that I could not find in the documents.

    Context:
    {context}

    Question:
    {question}

    Answer:
    """

    response = client.models.generate_content(
        model=LLM_MODEL,
        contents=prompt
    )

    return response.text