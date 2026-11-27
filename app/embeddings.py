from google import genai

from app.config import (
    PROJECT_ID,
    LOCATION,
    EMBEDDING_MODEL
)


client = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION
)


def generate_embeddings(texts):

    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts
    )

    return [
        embedding.values
        for embedding in response.embeddings
    ]


def generate_query_embedding(text):

    return generate_embeddings([text])[0]