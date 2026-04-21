"""
backend/app/database.py
Provides the SQLAlchemy engine and session factory.
Run this file directly to auto-create all tables:
    python backend/app/database.py
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "agentground")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_session():
    """Return a new SQLAlchemy session. Caller must close it."""
    return SessionLocal()


def init_db():
    """Auto-create all tables from ORM models (alternative to schema.sql)."""
    from backend.app import models  # noqa: F401 — import to register models
    Base.metadata.create_all(bind=engine)
    print("All tables created (or already exist).")


if __name__ == "__main__":
    init_db()
