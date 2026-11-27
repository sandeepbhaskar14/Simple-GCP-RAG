
import requests
import streamlit as st


API_BASE_URL = "http://127.0.0.1:8000"


class APIRequestError(Exception):
    """Raised when the FastAPI request fails."""
    pass



def _request(method, endpoint, timeout=180, **kwargs):
    url = f"{API_BASE_URL}{endpoint}"

    try:
        response = requests.request(
            method,
            url,
            timeout=timeout,
            **kwargs
        )

        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        raise APIRequestError("Request timed out. Please try again.")

    except requests.exceptions.ConnectionError:
        raise APIRequestError(
            f"Cannot connect to FastAPI at {API_BASE_URL}. "
            "Make sure the backend is running."
        )

    except requests.exceptions.HTTPError:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text

        raise APIRequestError(str(detail))

    except requests.exceptions.RequestException as exc:
        raise APIRequestError(str(exc))



def check_health():
    """Check whether FastAPI is running."""
    return _request("GET", "/")


def upload_document(uploaded_file):
    """
    Upload a document to FastAPI.

    uploaded_file is a Streamlit UploadedFile object.
    """

    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type or "application/octet-stream"
        )
    }

    return _request(
        "POST",
        "/ingest",
        files=files,
        timeout=300
    )


def ask_question(question):
    """
    Send a question to the RAG pipeline.
    """

    payload = {
        "question": question
    }

    return _request(
        "POST",
        "/ask",
        json=payload,
        timeout=180
    )
