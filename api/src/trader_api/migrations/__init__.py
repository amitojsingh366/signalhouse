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
        if sql:
            await conn.execute(text(sql))

        await conn.execute(
            text(
                "INSERT INTO schema_migrations (name, applied_at) "
                "VALUES (:name, :applied_at)"
            ),
            {"name": name, "applied_at": datetime.now(UTC)},
        )
