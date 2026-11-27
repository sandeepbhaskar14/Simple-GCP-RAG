import requests
import streamlit as st


API_BASE_URL = "http://127.0.0.1:8000"


class APIRequestError(Exception):
    """Raised when the FastAPI request fails."""
    pass


def _request(method, endpoint, timeout=180, **kwargs):
    url = f"{API_BASE_URL}{endpoint}"
    try:
        response = requests.request(method, url, timeout=timeout, **kwargs)
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()
    except requests.exceptions.Timeout:
        raise APIRequestError("Request timed out. Please try again.")
    except requests.exceptions.ConnectionError:
        raise APIRequestError(
            f"Cannot connect to FastAPI at {API_BASE_URL}. Make sure the backend is running."
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
    return _request("GET", "/")


def upload_document(uploaded_file):
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type or "application/octet-stream",
        )
    }
    return _request("POST", "/ingest", files=files, timeout=300)


def create_chat(title="New chat"):
    return _request("POST", "/chats", json={"title": title})


def list_chats():
    return _request("GET", "/chats")


def get_chat(chat_id):
    return _request("GET", f"/chats/{chat_id}")


def delete_chat(chat_id):
    return _request("DELETE", f"/chats/{chat_id}")


def ask_question(question, chat_id=None):
    payload = {"question": question}
    if chat_id:
        payload["chat_id"] = chat_id
    return _request("POST", "/ask", json=payload, timeout=180)
