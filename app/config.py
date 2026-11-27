import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = os.getenv("GCP_LOCATION", "asia-south1")

BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "text-embedding-005"
)

LLM_MODEL = os.getenv(
    "LLM_MODEL", "gemini-3.5-flash-lite"
)

DATABASE_URL = os.getenv("DATABASE_URL")