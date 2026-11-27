"""HTTP client for the GCP RAG FastAPI backend.

Save as dialog/services/gcp_requests.py. Keep your original
dialog/services/handle_requests.py for the chat/history service.

Backend routes (all need `Authorization: Bearer <Firebase ID token>`
and a verified email, except /health):
  GET    /health
  GET    /auth/me
  POST   /documents/upload-url          body: {file_name, content_type}
  PUT    <signed GCS URL>               headers: response["required_headers"]
  POST   /documents/{id}/confirm        no body
  GET    /documents
  GET    /documents/{id}
  GET    /documents/{id}/status
  DELETE /documents/{id}                204

Env: GCP_API_BASE_URL (default http://127.0.0.1:8000). Use your Cloud Run
URL once deployed.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List
from urllib.parse import quote

import requests

API_BASE_URL = os.getenv("GCP_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
DEFAULT_TIMEOUT = (10, 60)
MAX_FILE_SIZE = 25 * 1024 * 1024  # matches backend MAX_DOCUMENT_SIZE_BYTES

# Must match the backend's ALLOWED_TYPES. The content type is derived from the
# extension instead of the browser's guess (browsers report .csv as
# application/vnd.ms-excel on some systems), and the same value is used for the
# upload-url request and the GCS PUT, because the backend compares them.
CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".csv": "text/csv",
}
ALLOWED_EXTS = set(CONTENT_TYPES)


class APIRequestError(RuntimeError):
    """An API request failed or returned an unexpected response."""


def _headers(token: str) -> Dict[str, str]:
    if not token or not token.strip():
        raise APIRequestError("A Firebase ID token is required.")
    return {"Authorization": f"Bearer {token.strip()}", "Accept": "application/json"}


def _request(method: str, path: str, token: str, **kwargs: Any) -> Any:
    headers = {**_headers(token), **kwargs.pop("headers", {})}
    timeout = kwargs.pop("timeout", DEFAULT_TIMEOUT)
    try:
        response = requests.request(
            method, f"{API_BASE_URL}{path}", headers=headers, timeout=timeout, **kwargs
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        resp = exc.response
        if resp is None:
            raise APIRequestError(str(exc)) from exc
        try:
            body = resp.json().get("detail", resp.text[:500])
        except (ValueError, AttributeError):
            body = resp.text[:500]
        hint = " (token may be expired; Firebase ID tokens last 1 hour)" if resp.status_code == 401 else ""
        raise APIRequestError(f"API returned HTTP {resp.status_code}: {body}{hint}") from exc
    except requests.RequestException as exc:
        raise APIRequestError(f"Cannot reach {API_BASE_URL}: {exc}") from exc

    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return {"raw_response": response.text}


def _doc_path(document_id: str, suffix: str = "") -> str:
    return f"/documents/{quote(str(document_id), safe='')}{suffix}"


# ── Public / auth ──────────────────────────────────────────────────────────────
def check_health() -> Dict[str, Any]:
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=(5, 10))
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise APIRequestError(f"Health check failed for {API_BASE_URL}: {exc}") from exc


def get_me(token: str) -> Dict[str, Any]:
    result = _request("GET", "/auth/me", token)
    if not isinstance(result, dict):
        raise APIRequestError("Unexpected /auth/me response.")
    return result


# ── Upload flow ────────────────────────────────────────────────────────────────
def create_upload_url(token: str, file_name: str, content_type: str) -> Dict[str, Any]:
    result = _request(
        "POST", "/documents/upload-url", token,
        json={"file_name": file_name, "content_type": content_type},
    )
    if not isinstance(result, dict) or not result.get("document_id") or not result.get("upload_url"):
        raise APIRequestError("Unexpected /documents/upload-url response.")
    return result


def put_file_to_signed_url(upload_url: str, file_bytes: bytes, headers: Dict[str, str]) -> None:
    """PUT bytes to GCS with exactly the headers the URL was signed with.

    Never attach the Firebase bearer token here.
    """
    try:
        response = requests.put(upload_url, data=file_bytes, headers=headers, timeout=(10, 180))
        response.raise_for_status()
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "unknown"
        detail = exc.response.text[:500] if exc.response is not None else str(exc)
        raise APIRequestError(f"Cloud Storage upload failed (HTTP {code}): {detail}") from exc
    except requests.RequestException as exc:
        raise APIRequestError(f"Cloud Storage upload failed: {exc}") from exc


def confirm_upload(token: str, document_id: str) -> Dict[str, Any]:
    return _request("POST", _doc_path(document_id, "/confirm"), token)


def upload_document(token: str, uploaded_file: Any) -> Dict[str, Any]:
    """upload-url -> PUT to GCS -> confirm. Returns document_id and confirmation."""
    file_name = os.path.basename(uploaded_file.name)
    suffix = os.path.splitext(file_name)[1].lower()
    content_type = CONTENT_TYPES.get(suffix)
    if content_type is None:
        raise APIRequestError(
            f"Unsupported file type: {suffix or '(no extension)'}. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTS))}"
        )

    file_bytes = uploaded_file.getvalue()
    if not file_bytes:
        raise APIRequestError("The selected file is empty.")
    if len(file_bytes) > MAX_FILE_SIZE:
        raise APIRequestError("File exceeds the 25 MB limit.")

    info = create_upload_url(token, file_name, content_type)
    document_id = str(info["document_id"])
    put_headers = info.get("required_headers") or {"Content-Type": content_type}

    try:
        put_file_to_signed_url(info["upload_url"], file_bytes, put_headers)
        confirmation = confirm_upload(token, document_id)
    except APIRequestError:
        # Don't leave an orphaned "pending" row behind (best effort).
        try:
            delete_document(token, document_id)
        except APIRequestError:
            pass
        raise

    return {"document_id": document_id, "confirmation": confirmation}


# ── Read / delete ──────────────────────────────────────────────────────────────
def list_documents(token: str) -> List[Dict[str, Any]]:
    result = _request("GET", "/documents", token)
    if not isinstance(result, list):
        raise APIRequestError("Unexpected /documents response; expected a list.")
    return result


def get_document(token: str, document_id: str) -> Dict[str, Any]:
    result = _request("GET", _doc_path(document_id), token)
    if not isinstance(result, dict):
        raise APIRequestError("Unexpected document response.")
    return result


def get_document_status(token: str, document_id: str) -> Dict[str, Any]:
    result = _request("GET", _doc_path(document_id, "/status"), token)
    if not isinstance(result, dict):
        raise APIRequestError("Unexpected document status response.")
    return result


def delete_document(token: str, document_id: str) -> None:
    _request("DELETE", _doc_path(document_id), token)