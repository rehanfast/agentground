"""
backend/app/database.py
Dual-engine database setup.

Prerequisites (one-time, run as root):
    sudo mysql
    GRANT ALL PRIVILEGES ON `agentground`.* TO 'agent_user'@'localhost';
    GRANT ALL PRIVILEGES ON `agentground_%`.* TO 'agent_user'@'localhost';
    FLUSH PRIVILEGES;

After that, DB_USER handles everything — no separate admin user needed.

Bootstrap order (automatic, zero manual SQL after grants are set):
  1. Connect with no database selected → CREATE DATABASE IF NOT EXISTS agentground.
  2. Connect to agentground → create users + sessions tables.
  3. Per-user DBs created at registration via create_user_database().
"""

import os
from functools import lru_cache
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "agentground")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASSWORD", "")

# ── Declarative bases ─────────────────────────────────────────────────────────
MasterBase = declarative_base()
AppBase    = declarative_base()


# ── DDL helper (uses app user — must have CREATE privilege on agentground_*) ──
def _ddl(sql: str) -> None:
    """
    Run a DDL statement (CREATE/DROP DATABASE) using a no-database connection.
    Requires the app user to have been granted the CREATE privilege:
        GRANT ALL PRIVILEGES ON `agentground_%`.* TO '<user>'@'localhost';
    """
    root_url = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/"
    engine = create_engine(root_url, echo=False, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
    except Exception as exc:
        msg = str(exc)
        # Surface a clear, actionable error instead of a raw SQLAlchemy trace.
        if "1044" in msg or "1045" in msg or "Access denied" in msg:
            raise RuntimeError(
                f"MySQL user '{DB_USER}' lacks the CREATE DATABASE privilege.\n\n"
                "Run this once as root, then restart Streamlit:\n\n"
                "    sudo mysql\n"
                f"    GRANT ALL PRIVILEGES ON `{DB_NAME}`.* TO '{DB_USER}'@'localhost';\n"
                f"    GRANT ALL PRIVILEGES ON `{DB_NAME}_%`.* TO '{DB_USER}'@'localhost';\n"
                "    FLUSH PRIVILEGES;\n\n"
                f"Original error: {exc}"
            ) from exc
        raise
    finally:
        engine.dispose()


# ── Bootstrap: create master DB if missing ────────────────────────────────────
_ddl(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4")

# ── Master engine ─────────────────────────────────────────────────────────────
MASTER_URL    = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
master_engine = create_engine(MASTER_URL, echo=False, pool_pre_ping=True)
MasterSession = sessionmaker(bind=master_engine, autoflush=False, autocommit=False)


# ── Per-user engines ──────────────────────────────────────────────────────────
@lru_cache(maxsize=64)
def _get_user_engine(db_name: str):
    url = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{db_name}"
    return create_engine(url, echo=False, pool_pre_ping=True)


# ── Session factories ─────────────────────────────────────────────────────────
def get_master_session():
    return MasterSession()


def get_session(db_name: str | None = None):
    if db_name:
        return sessionmaker(
            bind=_get_user_engine(db_name), autoflush=False, autocommit=False
        )()
    return MasterSession()


# ── Helpers ───────────────────────────────────────────────────────────────────
def user_db_name(username: str) -> str:
    safe = "".join(c for c in username.lower() if c.isalnum() or c == "_")
    return f"agentground_{safe}"


# ── Per-user lifecycle ────────────────────────────────────────────────────────
def create_user_database(username: str) -> None:
    db = user_db_name(username)
    _ddl(f"CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4")
    from backend.app import models  # noqa: registers AppBase models
    AppBase.metadata.create_all(bind=_get_user_engine(db))
    _seed_tools(db)


def _seed_tools(db_name: str) -> None:
    from backend.app.models import Tool
    session = get_session(db_name)
    try:
        if session.query(Tool).count() == 0:
            session.add_all([
                Tool(name="Terminal",
                     description=(
                         "Whitelisted shell commands in the agent workspace. "
                         "Permitted: ls, echo, pwd, cat, mkdir, date, whoami, "
                         "head, tail, wc, find, grep. Path traversal blocked."
                     ),
                     is_builtin=True),
                Tool(name="Web Search",
                     description=(
                         "Tavily Search API — max 3 results. "
                         "Requires TAVILY_API_KEY in .env."
                     ),
                     is_builtin=True),
                Tool(name="File Read/Write",
                     description="Read/write plain text files in the agent workspace.",
                     is_builtin=True),
            ])
            session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def drop_user_database(username: str) -> None:
    _get_user_engine.cache_clear()
    _ddl(f"DROP DATABASE IF EXISTS `{user_db_name(username)}`")


# ── Master schema ─────────────────────────────────────────────────────────────
def init_master_db() -> None:
    from backend.app import models  # noqa
    MasterBase.metadata.create_all(bind=master_engine)


init_master_db()
