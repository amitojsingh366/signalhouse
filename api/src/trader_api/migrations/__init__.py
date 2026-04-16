"""Lightweight migration engine for additive DB schema updates."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from . import m20260416_split_notification_channel_mutes

MigrationFunc = Callable[[AsyncConnection], Awaitable[None]]

MIGRATIONS: tuple[tuple[str, MigrationFunc], ...] = (
    (
        m20260416_split_notification_channel_mutes.MIGRATION_NAME,
        m20260416_split_notification_channel_mutes.upgrade,
    ),
)


async def run_migrations(conn: AsyncConnection) -> None:
    """Run all unapplied migrations in declaration order."""
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

    for name, migration in MIGRATIONS:
        if name in applied:
            continue

        await migration(conn)
        await conn.execute(
            text(
                "INSERT INTO schema_migrations (name, applied_at) "
                "VALUES (:name, :applied_at)"
            ),
            {"name": name, "applied_at": datetime.now(UTC)},
        )
