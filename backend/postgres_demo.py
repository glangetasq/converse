from __future__ import annotations

import hashlib
import os

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/convo_maker")


def main() -> None:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (email, display_name)
                VALUES (%s, %s)
                ON CONFLICT (email) DO UPDATE SET display_name = EXCLUDED.display_name
                RETURNING id, email
                """,
                ("demo@convo-maker.local", "Demo User"),
            )
            user = cur.fetchone()
            if user is None:
                raise RuntimeError("Expected demo user row.")

            content = "Demo memory written from postgres_demo.py"
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            cur.execute(
                """
                INSERT INTO memory_items (
                  user_id, memory_type, content, content_hash,
                  importance_score, confidence_score, source, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, content_hash) DO UPDATE
                SET updated_at = now(),
                    metadata = EXCLUDED.metadata
                RETURNING id, content, created_at
                """,
                (
                    user["id"],
                    "demo",
                    content,
                    content_hash,
                    0.5,
                    1.0,
                    "postgres_demo.py",
                    Jsonb({"purpose": "show a Python write to Postgres"}),
                ),
            )
            written_memory = cur.fetchone()
            conn.commit()

            cur.execute(
                """
                SELECT id, memory_type, content, created_at
                FROM memory_items
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 5
                """,
                (user["id"],),
            )
            rows = cur.fetchall()

    print("Wrote memory:")
    print(written_memory)
    print("\nRecent memories:")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
