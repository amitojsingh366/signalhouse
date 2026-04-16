"""Lightweight SQL migration engine for additive DB schema updates."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

MIGRATION_FILE_PATTERN = re.compile(r"^\d{4}_[a-z0-9_]+\.sql$")


def _migration_dir() -> Path:
    return Path(__file__).resolve().parent


def _list_sql_migrations() -> list[Path]:
    """Return numbered SQL migrations sorted by filename order."""
    files = sorted(_migration_dir().glob("*.sql"))
    migrations: list[Path] = []
    for file in files:
        if MIGRATION_FILE_PATTERN.match(file.name):
            migrations.append(file)
    return migrations


def _split_sql_statements(sql: str) -> list[str]:
    """Split a SQL script into single statements for asyncpg execution."""
    statements: list[str] = []
    current: list[str] = []
    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    in_block_comment = False
    i = 0

    while i < len(sql):
        char = sql[i]
        next_char = sql[i + 1] if i + 1 < len(sql) else ""

        if in_line_comment:
            current.append(char)
            if char == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            current.append(char)
            if char == "*" and next_char == "/":
                current.append(next_char)
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if in_single_quote:
            current.append(char)
            if char == "'" and next_char == "'":
                current.append(next_char)
                i += 2
                continue
            if char == "'":
                in_single_quote = False
            i += 1
            continue

        if in_double_quote:
            current.append(char)
            if char == '"' and next_char == '"':
                current.append(next_char)
                i += 2
                continue
            if char == '"':
                in_double_quote = False
            i += 1
            continue

        if char == "-" and next_char == "-":
            current.append(char)
            current.append(next_char)
            in_line_comment = True
            i += 2
            continue

        if char == "/" and next_char == "*":
            current.append(char)
            current.append(next_char)
            in_block_comment = True
            i += 2
            continue

        if char == "'":
            current.append(char)
            in_single_quote = True
            i += 1
            continue

        if char == '"':
            current.append(char)
            in_double_quote = True
            i += 1
            continue

        if char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            i += 1
            continue

        current.append(char)
        i += 1

    trailing = "".join(current).strip()
    if trailing:
        statements.append(trailing)

    return statements


async def run_migrations(conn: AsyncConnection) -> None:
    """Run all unapplied SQL migrations in filename order."""
    await conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                name VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    )

    result = await conn.execute(text("SELECT name FROM schema_migrations"))
    applied = {row[0] for row in result}

    for migration_file in _list_sql_migrations():
        name = migration_file.name
        if name in applied:
            continue

        sql = migration_file.read_text(encoding="utf-8").strip()
        for statement in _split_sql_statements(sql):
            await conn.execute(text(statement))

        await conn.execute(
            text(
                "INSERT INTO schema_migrations (name, applied_at) "
                "VALUES (:name, :applied_at)"
            ),
            {"name": name, "applied_at": datetime.now(UTC)},
        )
