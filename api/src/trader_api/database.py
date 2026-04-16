"""PostgreSQL database connection and session management via SQLAlchemy async."""

from __future__ import annotations

import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://trader:trader@localhost:5432/trader",
)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight additive migration for notification channel-level mute controls.
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


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """Dependency for FastAPI — yields a database session."""
    async with async_session() as session:
        yield session
