"""
RAISE Relational Database Asynchronous Models & Engine Factory
==============================================================
Purpose:
  Defines SQLModel ORM models and asynchronous connection factory for PostgreSQL
  using asyncpg per system-architecture.md Section 5.

Models:
  - `SessionMetadata`: Stores conversation session titles, UUIDs, and timestamps.
  - `MessageHistory`: Persists historical multi-turn dialog sequences linked to sessions.
  - `get_async_engine`: Connection pool factory with health ping and connection recycling.

Author: RAISE Core Architecture Team
Maintainability: Keep under 120 lines with strict type safety.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Optional

try:
    from sqlmodel import SQLModel, Field, Relationship
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.orm import sessionmaker
    from sqlmodel.ext.asyncio.session import AsyncSession
    HAS_ASYNC_DB = True
except ImportError:
    HAS_ASYNC_DB = False
    SQLModel = object  # type: ignore

if HAS_ASYNC_DB:
    class SessionMetadata(SQLModel, table=True):
        """Stores user conversational session titles and configuration parameters."""
        __tablename__ = "session_metadata"

        id: str = Field(primary_key=True, index=True)
        title: str = Field(nullable=False)
        created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
        updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

        messages: List["MessageHistory"] = Relationship(back_populates="session")

    class MessageHistory(SQLModel, table=True):
        """Persists historical dialog sequences sequentially."""
        __tablename__ = "message_history"

        id: Optional[int] = Field(default=None, primary_key=True)
        session_id: str = Field(foreign_key="session_metadata.id", index=True)
        role: str = Field(nullable=False)
        content: str = Field(nullable=False)
        timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

        session: Optional[SessionMetadata] = Relationship(back_populates="messages")
else:
    SessionMetadata = None  # type: ignore
    MessageHistory = None  # type: ignore


def get_async_engine(
    user: str = "raise_user",
    password: str = "raise_password",
    host: str = "localhost",
    port: int = 5432,
    dbname: str = "raise_db"
):
    """
    Creates an asynchronous engine using asyncpg per system-architecture.md Section 5.1.
    """
    if not HAS_ASYNC_DB:
        return None
    async_db_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"
    return create_async_engine(
        async_db_url,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=False
    )
