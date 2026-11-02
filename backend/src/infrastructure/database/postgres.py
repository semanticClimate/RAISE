"""
PostgreSQL Storage Manager & 3-Tier Database Fallback
======================================================
Manages persistent relational storage for chat sessions, message histories,
document metadata, ingestion pipelines, and user feedback.

3-Tier Sequential Fallback Architecture:
  1. Local PostgreSQL (localhost:5432)
  2. Cloud PostgreSQL (Aiven / Neon / Supabase / AWS RDS)
  3. Python In-Memory SQLite Database (sqlite:///:memory:)

Assembled modularly from specialized mixins:
  - ChatStoreMixin: message persistence, sliding window queries, history sync
  - SessionDrawerMixin: active session document drawer attachments
  - DocumentStoreMixin: document metadata and ingestion progress tracking
  - FeedbackStoreMixin: answer quality ratings and telemetry metrics
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from src.storage.interfaces import ISessionStore
from .mixins import (
    ChatStoreMixin,
    DocumentStoreMixin,
    FeedbackStoreMixin,
    SessionDrawerMixin,
)

logger = logging.getLogger("raise.infrastructure.database.postgres")

__all__ = ["PostgresManager", "PostgresDatabase", "get_database_engine"]

_GLOBAL_PG_INSTANCE: Optional[PostgresManager] = None
_GLOBAL_PG_LOCK = threading.Lock()
_HAS_LOGGED_PG_CONNECTION = False


def get_database_engine(
    local_url: Optional[str] = None,
    cloud_url: Optional[str] = None,
    memory_url: str = "sqlite:///:memory:",
) -> Engine:
    """
    Creates and returns a SQLAlchemy Engine following a sequential 3-tier fallback:
      Tier 1: Localhost PostgreSQL
      Tier 2: Cloud PostgreSQL
      Tier 3: Python In-Memory SQLite Database (sqlite:///:memory:)
    """
    global _HAS_LOGGED_PG_CONNECTION

    # 1. Resolve connection URLs
    if not local_url:
        local_url = os.getenv("LOCAL_DB_URL") or os.getenv("DATABASE_URL")
        if not local_url:
            u = os.getenv("POSTGRES_USER", "raise_user")
            p = os.getenv("POSTGRES_PASSWORD", "raise_password")
            h = os.getenv("POSTGRES_HOST", "localhost")
            pt = os.getenv("POSTGRES_PORT", "5432")
            db = os.getenv("POSTGRES_DB", "raise_db")
            local_url = f"postgresql://{u}:{p}@{h}:{pt}/{db}"

    cloud_url = cloud_url or os.getenv("CLOUD_DB_URL") or os.getenv("POSTGRES_CLOUD_URL") or os.getenv("DATABASE_CLOUD_URL")

    # Tier 1: Attempt Local PostgreSQL
    try:
        engine = create_engine(
            local_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=5,
            connect_args={"connect_timeout": 2},
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        if not _HAS_LOGGED_PG_CONNECTION:
            logger.info("Connected to PostgreSQL at Localhost (%s)", local_url.split("@")[-1] if "@" in local_url else local_url)
            _HAS_LOGGED_PG_CONNECTION = True
        return engine
    except (OperationalError, Exception) as exc:
        logger.debug("Local PostgreSQL connection failed: %s. Falling back to Cloud...", exc)

    # Tier 2: Attempt Cloud PostgreSQL
    if cloud_url:
        try:
            engine = create_engine(
                cloud_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=5,
                connect_args={"connect_timeout": 4},
            )
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            if not _HAS_LOGGED_PG_CONNECTION:
                logger.info("Connected to PostgreSQL at Cloud")
                _HAS_LOGGED_PG_CONNECTION = True
            return engine
        except (OperationalError, Exception) as exc:
            logger.debug("Cloud PostgreSQL connection failed: %s. Falling back to In-Memory SQLite...", exc)
    else:
        logger.debug("Cloud PostgreSQL URL not configured. Falling back to In-Memory SQLite...")

    # Tier 3: Local SQLite Database (persistent file-backed by default, or memory if in test environment)
    import sys
    is_testing = os.getenv("TESTING", "").lower() in ("true", "1") or "pytest" in sys.modules
    sqlite_path = os.getenv("SQLITE_DB_PATH")
    if not sqlite_path and not is_testing and memory_url == "sqlite:///:memory:":
        data_dir = os.path.join(os.getcwd(), "data")
        try:
            os.makedirs(data_dir, exist_ok=True)
            sqlite_path = os.path.join(data_dir, "raise_local.db")
        except Exception:
            sqlite_path = None

    if sqlite_path and memory_url == "sqlite:///:memory:":
        norm_path = sqlite_path.replace(os.sep, "/")
        actual_url = f"sqlite:///{norm_path}"
    else:
        actual_url = memory_url

    engine = create_engine(actual_url)
    if not _HAS_LOGGED_PG_CONNECTION:
        if "sqlite:///:memory:" in actual_url:
            logger.info("Connected to In-Memory SQLite Database")
        else:
            logger.info("Connected to Persistent Local SQLite Database (%s)", actual_url)
        _HAS_LOGGED_PG_CONNECTION = True
    return engine


class PostgresManager(
    ChatStoreMixin,
    SessionDrawerMixin,
    DocumentStoreMixin,
    FeedbackStoreMixin,
    ISessionStore,
):
    """
    Manages long-term chat sessions, message logs, and document metadata in PostgreSQL.
    Follows a 3-tier fallback (Localhost -> Cloud -> In-Memory SQLite) and operates
    as a thread-safe singleton to eliminate duplicate connection initializations.
    """

    _instance: Optional[PostgresManager] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        # Return existing singleton when instantiated with default arguments
        if not args and not kwargs and cls._instance is not None:
            return cls._instance
        with cls._lock:
            if not args and not kwargs and cls._instance is not None:
                return cls._instance
            instance = super().__new__(cls)
            if not args and not kwargs:
                cls._instance = instance
            return instance

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        dbname: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        if getattr(self, "_initialized", False):
            return

        self.host = host or os.getenv("POSTGRES_HOST", "localhost")
        self.port = int(port or os.getenv("POSTGRES_PORT", "5432"))
        self.dbname = dbname or os.getenv("POSTGRES_DB", "raise_db")
        self.user = user or os.getenv("POSTGRES_USER", "raise_user")
        self.password = password or os.getenv("POSTGRES_PASSWORD", "raise_password")

        self.tier: str = "memory"
        self.is_connected: bool = False
        self._pool = None
        self.engine: Optional[Engine] = None

        self._memory_chat: Dict[str, List[Dict[str, Any]]] = {}
        self._memory_docs: Dict[str, Dict[str, Any]] = {}
        self._memory_doc_status: Dict[str, Dict[str, Any]] = {}
        self._memory_feedback: List[Dict[str, Any]] = []
        self._memory_sessions: Dict[str, Dict[str, Any]] = {}

        self._connect_and_init()
        self._initialized = True

    def _init_pool(self, target_host: str, target_port: int, target_db: str, target_user: str, target_pass: str):
        try:
            from psycopg2 import pool
            if self._pool is None:
                self._pool = pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=30,
                    host=target_host,
                    port=target_port,
                    dbname=target_db,
                    user=target_user,
                    password=target_pass,
                    connect_timeout=2,
                )
        except Exception as e:
            logger.debug("ThreadedConnectionPool init skipped/failed: %s", e)

    def _get_connection(self):
        if not self.is_connected:
            return None

        now = time.time()
        if (now - getattr(self, "_last_pg_probe", 0)) < 3.0:
            if self._pool:
                try:
                    return self._pool.getconn()
                except Exception:
                    pass
        self._last_pg_probe = now

        probe_host = "127.0.0.1" if self.host in ("localhost", "127.0.0.1") else self.host
        try:
            import socket
            with socket.create_connection((probe_host, self.port), timeout=0.05):
                pass
        except Exception:
            return None

        try:
            if not self._pool:
                self._init_pool(self.host, self.port, self.dbname, self.user, self.password)
            if self._pool:
                return self._pool.getconn()
            import psycopg2
            return psycopg2.connect(
                host=self.host,
                port=self.port,
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                connect_timeout=2,
            )
        except Exception as e:
            logger.debug("PostgreSQL connection attempt failed: %s", e)
            return None

    def _release_connection(self, conn):
        if not conn:
            return
        try:
            if self._pool:
                self._pool.putconn(conn)
            else:
                conn.close()
        except Exception as e:
            logger.debug("Error releasing PostgreSQL connection: %s", e)

    def _connect_and_init(self):
        # 1. Initialize SQLAlchemy Engine via 3-Tier Fallback
        self.engine = get_database_engine()

        # 2. Probe psycopg2 connection for direct fast connection pooling
        conn = None
        probe_host = "127.0.0.1" if self.host in ("localhost", "127.0.0.1") else self.host
        try:
            import socket
            with socket.create_connection((probe_host, self.port), timeout=0.1):
                self._init_pool(self.host, self.port, self.dbname, self.user, self.password)
                if self._pool:
                    conn = self._pool.getconn()
                    self.tier = "local"
                    self.is_connected = True
        except Exception:
            conn = None

        # 3. If local direct connection failed, probe Cloud URL
        if not conn:
            cloud_url = os.getenv("CLOUD_DB_URL") or os.getenv("POSTGRES_CLOUD_URL") or os.getenv("DATABASE_CLOUD_URL")
            if cloud_url:
                try:
                    parsed = urlparse(cloud_url)
                    c_host = parsed.hostname or "localhost"
                    c_port = parsed.port or 5432
                    c_user = parsed.username or "postgres"
                    c_pass = parsed.password or ""
                    c_db = (parsed.path or "/postgres").lstrip("/")
                    self._init_pool(c_host, c_port, c_db, c_user, c_pass)
                    if self._pool:
                        conn = self._pool.getconn()
                        self.tier = "cloud"
                        self.is_connected = True
                except Exception as c_err:
                    logger.debug("Direct Cloud pool connection failed: %s", c_err)

        if not conn:
            self.tier = "memory"
            self.is_connected = False
            return

        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(100) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    mode VARCHAR(20) DEFAULT 'fast',
                    sources JSONB DEFAULT '[]'::jsonb,
                    citations JSONB DEFAULT '[]'::jsonb,
                    duration_sec DOUBLE PRECISION DEFAULT 0.0,
                    turn_index INT DEFAULT 0,
                    message_hash VARCHAR(64),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS citations JSONB DEFAULT '[]'::jsonb;
                ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS duration_sec DOUBLE PRECISION DEFAULT 0.0;
                ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS latency_sec NUMERIC DEFAULT 0.0;
                ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS turn_index INT DEFAULT 0;
                ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS message_hash VARCHAR(64);
                CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_messages(session_id);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_messages_hash ON chat_messages(session_id, message_hash);
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS document_metadata (
                    id VARCHAR(100) PRIMARY KEY,
                    filename VARCHAR(255) NOT NULL,
                    library VARCHAR(100) DEFAULT 'default',
                    chunks_count INT DEFAULT 0,
                    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    is_protected BOOLEAN DEFAULT FALSE,
                    can_delete BOOLEAN DEFAULT TRUE,
                    owner VARCHAR(100) DEFAULT 'user'
                );
                ALTER TABLE document_metadata ADD COLUMN IF NOT EXISTS is_protected BOOLEAN DEFAULT FALSE;
                ALTER TABLE document_metadata ADD COLUMN IF NOT EXISTS can_delete BOOLEAN DEFAULT TRUE;
                ALTER TABLE document_metadata ADD COLUMN IF NOT EXISTS owner VARCHAR(100) DEFAULT 'user';
                CREATE INDEX IF NOT EXISTS idx_doc_library ON document_metadata(library);
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS session_metadata (
                    id VARCHAR(255) PRIMARY KEY,
                    title VARCHAR(500) NOT NULL,
                    attached_docs JSONB DEFAULT '[]'::jsonb,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                ALTER TABLE session_metadata ADD COLUMN IF NOT EXISTS attached_docs JSONB DEFAULT '[]'::jsonb;
                CREATE TABLE IF NOT EXISTS message_history (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(255) REFERENCES session_metadata(id) ON DELETE CASCADE,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_msg_session ON message_history(session_id);
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id VARCHAR(100) PRIMARY KEY,
                    filename VARCHAR(255) NOT NULL,
                    status VARCHAR(50) DEFAULT 'processing',
                    phase VARCHAR(50) DEFAULT 'uploading',
                    progress_percent INT DEFAULT 0,
                    detail TEXT DEFAULT '',
                    error_message TEXT DEFAULT NULL,
                    pages_processed INT DEFAULT 0,
                    chunks_extracted INT DEFAULT 0,
                    file_size_bytes BIGINT DEFAULT 0,
                    library VARCHAR(100) DEFAULT 'default',
                    is_protected BOOLEAN DEFAULT FALSE,
                    can_delete BOOLEAN DEFAULT TRUE,
                    owner VARCHAR(100) DEFAULT 'user',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_protected BOOLEAN DEFAULT FALSE;
                ALTER TABLE documents ADD COLUMN IF NOT EXISTS can_delete BOOLEAN DEFAULT TRUE;
                ALTER TABLE documents ADD COLUMN IF NOT EXISTS owner VARCHAR(100) DEFAULT 'user';
                CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_feedback (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(100) NOT NULL,
                    query TEXT,
                    rating VARCHAR(50) NOT NULL,
                    reason TEXT,
                    message_id VARCHAR(100),
                    client_ip VARCHAR(45),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                ALTER TABLE chat_feedback ADD COLUMN IF NOT EXISTS client_ip VARCHAR(45);
                CREATE INDEX IF NOT EXISTS idx_feedback_session ON chat_feedback(session_id);
            """)
            conn.commit()
            cur.close()
            self._release_connection(conn)
            self.is_connected = True
        except Exception as e:
            logger.error("Error initializing PostgreSQL schema: %s", e)
            self.is_connected = False


PostgresDatabase = PostgresManager
