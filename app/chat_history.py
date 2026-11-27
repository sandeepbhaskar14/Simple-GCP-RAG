"""PostgreSQL persistence for conversations and messages."""
from psycopg.types.json import Jsonb
from app.database import get_connection


def create_chat(title="New chat"):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO chats (title) VALUES (%s) RETURNING id, title, created_at, updated_at",
                (title,),
            )
            row = cursor.fetchone()
    return {"id": str(row[0]), "title": row[1], "created_at": row[2], "updated_at": row[3]}


def list_chats(limit=50):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.title, c.created_at, c.updated_at,
                       (SELECT COUNT(*) FROM chat_messages m WHERE m.chat_id = c.id)
                FROM chats c ORDER BY c.updated_at DESC LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()
    return [
        {"id": str(row[0]), "title": row[1], "created_at": row[2],
         "updated_at": row[3], "message_count": row[4]}
        for row in rows
    ]


def get_chat(chat_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, title, created_at, updated_at FROM chats WHERE id = %s::uuid",
                (chat_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            cursor.execute(
                """
                SELECT role, content, sources, created_at
                FROM chat_messages WHERE chat_id = %s::uuid
                ORDER BY created_at, id
                """,
                (chat_id,),
            )
            messages = cursor.fetchall()
    return {
        "id": str(row[0]), "title": row[1], "created_at": row[2],
        "updated_at": row[3],
        "messages": [
            {"role": item[0], "content": item[1], "sources": item[2] or [],
             "created_at": item[3]}
            for item in messages
        ],
    }


def get_recent_messages(chat_id, limit=10):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT role, content FROM chat_messages
                WHERE chat_id = %s ORDER BY created_at DESC, id DESC LIMIT %s
                """,
                (chat_id, limit),
            )
            rows = cursor.fetchall()
    return [{"role": row[0], "content": row[1]} for row in reversed(rows)]


def add_message(chat_id, role, content, sources=None):
    if role not in {"user", "assistant"}:
        raise ValueError("Message role must be 'user' or 'assistant'.")
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO chat_messages (chat_id, role, content, sources)
                VALUES (%s, %s, %s, %s)
                """,
                (chat_id, role, content, Jsonb(sources or [])),
            )
            if role == "user":
                cursor.execute(
                    """
                    UPDATE chats
                    SET title = CASE WHEN title = 'New chat' THEN LEFT(%s, 80)
                                     ELSE title END,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s::uuid
                    """,
                    (content, chat_id),
                )
            else:
                cursor.execute(
                    "UPDATE chats SET updated_at = CURRENT_TIMESTAMP WHERE id = %s::uuid",
                    (chat_id,),
                )


def delete_chat(chat_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM chats WHERE id = %s RETURNING id", (chat_id,))
            return cursor.fetchone() is not None
