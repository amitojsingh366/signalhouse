"""Add separate daily mute columns for notifications and calls."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

MIGRATION_NAME = "20260416_split_notification_channel_mutes"


async def upgrade(conn: AsyncConnection) -> None:
    """Add channel-specific daily mute columns to device registrations."""
    await conn.execute(
        text(
            "ALTER TABLE device_registrations "
            "ADD COLUMN IF NOT EXISTS daily_disabled_notifications_date VARCHAR(10)"
        )
    )
    await conn.execute(
        text(
            "ALTER TABLE device_registrations "
            "ADD COLUMN IF NOT EXISTS daily_disabled_calls_date VARCHAR(10)"
        )
    )
