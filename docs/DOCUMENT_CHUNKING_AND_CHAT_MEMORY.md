# Document-aware chunking and persistent chat history

## Supported document formats

| Format | Strategy | Metadata |
|---|---|---|
| PDF | Extract each page separately, then recursively split within that page | page, page_chunk |
| DOCX | Group paragraphs by Heading 1-9 hierarchy, then recursively split each section | heading, heading_path, section |
| TXT | Recursive splitting preferring paragraph, line, sentence, and word boundaries | chunk_part |
| CSV | Fixed row groups; repeat the CSV header in each group | row_start, row_end, row_count, columns |

The default recursive chunk settings remain 1,000 characters with 150 characters of overlap. CSV uses 20 data rows per chunk. These are starting values and should be tuned with retrieval evaluation.

## Database migration

For an existing database, apply the migration once:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f sql/migrations/002_chunk_metadata_and_chat_history.sql
```

This adds a JSONB metadata column to document_chunks and creates chats and chat_messages. Existing embeddings and chunks are retained.

For a fresh database, sql/schema.sql includes the new schema.

## Install dependencies

```bash
pip install -r requirements.txt
```

python-docx is required for DOCX parsing. CSV uses Python's standard csv module.

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Chat memory behavior

- POST /chats creates a conversation.
- GET /chats lists conversations.
- GET /chats/{chat_id} loads all messages and saved citations.
- DELETE /chats/{chat_id} deletes a conversation and its messages.
- POST /ask accepts an optional chat_id, loads the last 10 messages, generates a response, and persists both turns.
- The model receives recent history for follow-up resolution; complete history remains in PostgreSQL.
- A history-only answer is not treated as document-grounded and has no document citations.

## Citation behavior

The generation prompt asks Gemini to return a JSON answer with grounded=true and source_ids. The backend validates every returned source ID against the retrieved passages. Sources are returned only when the model marks the answer grounded and references at least one retrieved passage. Missing or malformed grounding output fails closed with no citations.

This is model-assisted grounding, not a formal entailment guarantee. Evaluate it with a labelled question set before production.

## Security limitation to address before multi-user deployment

The current repository's active FastAPI application does not verify Firebase ID tokens or establish an authenticated user identity. Therefore these chat endpoints are currently suitable only for a trusted single-user development deployment: chat listing and loading are not yet scoped to an authenticated owner. Do not expose this branch as a multi-user service until Firebase authentication is enforced server-side and every chat/document query is filtered by the verified Firebase UID.
