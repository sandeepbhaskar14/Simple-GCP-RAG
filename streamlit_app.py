
import html

import streamlit as st

from dialog.services import handle_requests as rag_api
from dialog.styles import build_css


# ─────────────────────────────────────────────────────────────────────────────
# Page configuration
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI Assistant",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─────────────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────────────

DEFAULTS = {
    "messages": [],
    "theme": "Dark",
    "font_size": "Default",
    "compact": False,
    "sidebar_open": True,
    "last_upload": None,
    "upload_nonce": 0,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

ss = st.session_state


# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────

st.markdown(
    build_css(
        ss.theme,
        ss.font_size,
        ss.compact,
        ss.sidebar_open,
    ),
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

FILE_TYPES = ["pdf", "txt"]


# ─────────────────────────────────────────────────────────────────────────────
# Backend
# ─────────────────────────────────────────────────────────────────────────────

def check_backend():
    try:
        health = rag_api.check_health()
        return True, health.get("message", "FastAPI is running")
    except rag_api.APIRequestError as exc:
        return False, str(exc)


# ─────────────────────────────────────────────────────────────────────────────
# Document upload
# ─────────────────────────────────────────────────────────────────────────────

def upload_document(uploaded_file):

    if uploaded_file is None:
        return None

    try:
        with st.spinner(
            f"Uploading and processing {uploaded_file.name}..."
        ):
            result = rag_api.upload_document(uploaded_file)

        ss.last_upload = result

        st.success(
            f"Document uploaded successfully: {uploaded_file.name}"
        )

        return result

    except rag_api.APIRequestError as exc:

        st.error(f"Document upload failed: {exc}")

        return None


def render_upload_result(result):

    if not result:
        return

    with st.expander("Latest upload details"):

        st.json(result)


# ─────────────────────────────────────────────────────────────────────────────
# New chat
# ─────────────────────────────────────────────────────────────────────────────

def new_chat():

    ss.messages = []



# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

def sidebar():

    with st.sidebar:

        # Header
        with st.container():

            c1, c2 = st.columns([5, 1], vertical_alignment="center")

            c1.markdown(
                '<div class="brand">'
                '<div class="logo"></div>'
                'AI Assistant'
                '</div>',
                unsafe_allow_html=True,
            )

            if c2.button(
                "",
                icon=":material/chevron_left:",
                key="collapse_sidebar",
                help="Collapse sidebar",
            ):
                ss.sidebar_open = False
                st.rerun()

        # New chat
        st.button(
            "New Chat",
            key="new_chat",
            on_click=new_chat,
            use_container_width=True,
            help="Start a new conversation",
        )

        st.divider()

        # AI mode
        st.markdown(
            '<div class="side-heading">AI MODE</div>',
            unsafe_allow_html=True,
        )

        st.markdown("**GCP RAG Assistant**")

        st.caption(
            "Ask questions using your uploaded documents."
        )

        st.divider()

        # Document upload
        st.markdown(
            '<div class="side-heading">DOCUMENTS</div>',
            unsafe_allow_html=True,
        )

        uploaded_file = st.file_uploader(
            "Upload PDF or TXT",
            type=FILE_TYPES,
            key=f"document_uploader_{ss.upload_nonce}",
        )

        if st.button(
            "Upload and Ingest",
            type="primary",
            use_container_width=True,
            disabled=uploaded_file is None,
        ):

            result = upload_document(uploaded_file)

            if result:
                ss.upload_nonce += 1
                st.rerun()

        if ss.last_upload:

            with st.expander("Latest document"):

                filename = ss.last_upload.get(
                    "filename",
                    "Uploaded document",
                )

                st.write(filename)

        st.divider()

        # Conversation information
        st.markdown(
            '<div class="side-heading">CURRENT SESSION</div>',
            unsafe_allow_html=True,
        )

        st.caption(
            f"{len(ss.messages) // 2} conversation turns"
        )

        st.caption(
            "Conversation history is stored in this Streamlit session."
        )

        # Sidebar expand/collapse
        if not ss.sidebar_open:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Message rendering
# ─────────────────────────────────────────────────────────────────────────────

def render_sources(sources):

    if not sources:
        return

    with st.expander(
        f"View retrieved sources ({len(sources)})"
    ):

        for index, source in enumerate(sources, start=1):

            filename = source.get(
                "filename",
                "Unknown document",
            )

            chunk_number = source.get(
                "chunk_number",
                "N/A",
            )

            distance = source.get("distance")

            st.markdown(
                f"**{index}. {html.escape(str(filename))}**"
            )

            st.caption(
                f"Chunk: {chunk_number}"
            )

            if distance is not None:

                st.caption(
                    f"Cosine distance: {float(distance):.4f}"
                )

            if source.get("text"):
                st.write(source["text"])

            if index < len(sources):
                st.divider()


def render_messages():

    for message in ss.messages:

        with st.chat_message(message["role"]):

            st.markdown(message["content"])

            if message["role"] == "assistant":

                render_sources(
                    message.get("sources", [])
                )


# ─────────────────────────────────────────────────────────────────────────────
# Submit question
# ─────────────────────────────────────────────────────────────────────────────

def submit_prompt(prompt):

    question = (prompt.text or "").strip()

    attached_file = (
        prompt.files[0]
        if prompt.files
        else None
    )

    # Optional document upload before asking
    if attached_file:

        result = upload_document(attached_file)

        if not result:
            return False

        st.toast(
            f"Document ingested: {attached_file.name}"
        )

    # Allow document-only uploads
    if not question:
        if attached_file:
            return True

        st.toast("Please enter a question.")
        return False

    try:

        with st.spinner(
            "Searching documents and generating answer..."
        ):

            result = rag_api.ask_question(question)

        answer = result.get(
            "answer",
            "The backend returned no answer.",
        )

        sources = result.get(
            "sources",
            [],
        )

        # Save user message
        user_content = question

        if attached_file:
            user_content += (
                f"\n\n📎 Uploaded document: {attached_file.name}"
            )

        ss.messages.append({
            "role": "user",
            "content": user_content,
        })

        # Save assistant response
        ss.messages.append({
            "role": "assistant",
            "content": answer,
            "sources": sources,
        })

        return True

    except rag_api.APIRequestError as exc:

        st.error(
            f"RAG request failed: {exc}"
        )

        return False


# ─────────────────────────────────────────────────────────────────────────────
# Chat area
# ─────────────────────────────────────────────────────────────────────────────

def chat_area():

    if not ss.messages:

        st.markdown(
            '<div class="welcome">'
            '<h1>Ask your documents</h1>'
            '<p>Upload documents and ask questions about their contents.</p>'
            '</div>',
            unsafe_allow_html=True,
        )

    else:

        render_messages()

    prompt = st.chat_input(
        "Ask your documents...",
        accept_file=True,
        file_type=FILE_TYPES,
        key="rag_composer",
    )

    if prompt:
        if submit_prompt(prompt):
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Application entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():

    # Sidebar
    sidebar()

    if not ss.sidebar_open:
        if st.button(
            "",
            icon=":material/chevron_right:",
            key="expand_sidebar",
            help="Open sidebar",
        ):
            ss.sidebar_open = True
            st.rerun()

    # Backend status
    backend_ok, backend_message = check_backend()

    if backend_ok:

        st.caption(
            f"🟢 GCP RAG Backend · {backend_message}"
        )

    else:

        st.error(
            f"Backend unavailable: {backend_message}"
        )

        if st.button("Retry connection"):
            st.rerun()

    # Main chat
    chat_area()


if __name__ == "__main__":
    main()
