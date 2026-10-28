"""PostgreSQL schema for chunks and saved research runs."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    collection_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    chunk_index INTEGER NOT NULL,
    document TEXT NOT NULL,
    embedding JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS chunks_collection_idx ON chunks (collection_name);

CREATE TABLE IF NOT EXISTS research_runs (
    id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    stopped_reason TEXT NOT NULL,
    markdown TEXT NOT NULL DEFAULT '',
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def connect(database_url: str):
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(database_url, row_factory=dict_row)


def apply_schema(database_url: str) -> None:
    with connect(database_url) as conn:
        conn.execute(SCHEMA_SQL)
        conn.commit()


def save_research_run(
    database_url: str,
    *,
    run_id: str,
    topic: str,
    stopped_reason: str,
    markdown: str,
    result: dict[str, Any],
) -> None:
    apply_schema(database_url)
    with connect(database_url) as conn:
        conn.execute(
            """
            INSERT INTO research_runs (id, topic, stopped_reason, markdown, result)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            """,
            (run_id, topic, stopped_reason, markdown, json.dumps(result)),
        )
        conn.commit()


def load_research_run(database_url: str, run_id: str) -> dict[str, Any] | None:
    apply_schema(database_url)
    with connect(database_url) as conn:
        row = conn.execute(
            """
            SELECT id, topic, stopped_reason, markdown, result
            FROM research_runs
            WHERE id = %s
            """,
            (run_id,),
        ).fetchone()
    return dict(row) if row else None
