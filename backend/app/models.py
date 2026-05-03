"""
backend/app/models.py
ORM models for AgentGround.
  MasterBase → central 'agentground' DB (users, sessions)
  AppBase    → per-user 'agentground_<username>' DB (everything else)
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime,
    Enum, JSON, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from backend.app.database import MasterBase, AppBase


# ── Master DB ─────────────────────────────────────────────────────────────────

class User(MasterBase):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    username      = Column(String(50),  nullable=False, unique=True)
    email         = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    created_at    = Column(DateTime, nullable=False, default=datetime.utcnow)


class Session(MasterBase):
    __tablename__ = "sessions"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    token      = Column(String(64), nullable=False, unique=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


# ── Per-user App DB ───────────────────────────────────────────────────────────

class Environment(AppBase):
    __tablename__ = "environments"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)

    agents = relationship("Agent", back_populates="environment",
                          cascade="all, delete-orphan")
    runs   = relationship("Run",   back_populates="environment",
                          cascade="all, delete-orphan")


class Tool(AppBase):
    __tablename__ = "tools"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    is_builtin  = Column(Boolean, nullable=False, default=True)
    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)

    agent_tools = relationship("AgentTool", back_populates="tool",
                               cascade="all, delete-orphan")


class Agent(AppBase):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("environment_id", "name", name="uq_agent_name_per_env"),
    )

    id             = Column(Integer, primary_key=True, autoincrement=True)
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="CASCADE"),
                            nullable=False)
    name           = Column(String(100), nullable=False)
    api_url        = Column(String(500), nullable=False)
    model_name     = Column(String(100), nullable=False, default="gpt-4")
    system_prompt  = Column(Text, nullable=False)
    created_at     = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at     = Column(DateTime, nullable=False, default=datetime.utcnow,
                            onupdate=datetime.utcnow)

    environment = relationship("Environment", back_populates="agents")
    agent_tools = relationship("AgentTool", back_populates="agent",
                               cascade="all, delete-orphan")
    audit_logs  = relationship("AuditLog", back_populates="agent",
                               cascade="all, delete-orphan")


class AgentTool(AppBase):
    __tablename__ = "agent_tools"
    __table_args__ = (
        UniqueConstraint("agent_id", "tool_id", name="uq_agent_tool"),
    )

    id         = Column(Integer, primary_key=True, autoincrement=True)
    agent_id   = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"),
                        nullable=False)
    tool_id    = Column(Integer, ForeignKey("tools.id", ondelete="CASCADE"),
                        nullable=False)
    scope      = Column(Enum("private", "shared"), nullable=False, default="private")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    agent = relationship("Agent", back_populates="agent_tools")
    tool  = relationship("Tool",  back_populates="agent_tools")


class Run(AppBase):
    __tablename__ = "runs"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="CASCADE"),
                            nullable=False)
    status         = Column(
        Enum("pending", "running", "stopped", "completed", "failed"),
        nullable=False, default="pending"
    )
    started_at  = Column(DateTime, nullable=True)
    ended_at    = Column(DateTime, nullable=True)
    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)
    # Stores run configuration so previous runs can be re-loaded into the form.
    # Schema: {agent_ids, initial_message, max_calls, timeout_secs, rpm_limit}
    config      = Column(JSON, nullable=True)

    environment = relationship("Environment", back_populates="runs")
    audit_logs  = relationship("AuditLog", back_populates="run",
                               cascade="all, delete-orphan")


class AuditLog(AppBase):
    __tablename__ = "audit_logs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    run_id      = Column(Integer, ForeignKey("runs.id",   ondelete="CASCADE"),
                         nullable=False)
    agent_id    = Column(Integer, ForeignKey("agents.id", ondelete="CASCADE"),
                         nullable=False)
    step_number = Column(Integer, nullable=False)
    action_type = Column(String(50), nullable=False)
    payload     = Column(JSON, nullable=True)
    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)

    run   = relationship("Run",   back_populates="audit_logs")
    agent = relationship("Agent", back_populates="audit_logs")


# ── Per-user settings ─────────────────────────────────────────────────────────

class UserSetting(AppBase):
    """Key-value store for per-user application settings."""
    __tablename__ = "user_settings"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    key        = Column(String(100), nullable=False, unique=True)
    value      = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow,
                        onupdate=datetime.utcnow)


class ModelConfig(AppBase):
    """
    User-configured LLM model registry.
    Stores provider, endpoint, multiple API keys (rotated), and an
    intelligence rank so the Auto Mode master agent can pick the best
    available model for each sub-agent task.
    """
    __tablename__ = "model_configs"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    # Display name — e.g. "Gemini 1.5 Flash (free)"
    display_name      = Column(String(200), nullable=False, unique=True)
    # Provider tag: openai | google | xai | deepseek | ollama | other
    provider          = Column(String(50),  nullable=False, default="openai")
    # Exact model_id sent in API requests — e.g. "gemini-1.5-flash"
    model_id          = Column(String(200), nullable=False)
    # OpenAI-compatible base URL (Google uses its compat endpoint too)
    api_url           = Column(String(500), nullable=False)
    # JSON array of API keys: ["key1", "key2"]
    # Keys are rotated round-robin; exhausted keys are cooled down.
    api_keys          = Column(JSON, nullable=False, default=list)
    # Lower = smarter (1 is best). Used by Auto Mode for model selection.
    intelligence_rank = Column(Integer, nullable=False, default=99)
    # Whether this model is on a free tier (used by Auto Mode prioritisation)
    is_free_tier      = Column(Boolean, nullable=False, default=False)
    # Disable without deleting
    is_active         = Column(Boolean, nullable=False, default=True)
    notes             = Column(Text, nullable=True)
    created_at        = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at        = Column(DateTime, nullable=False, default=datetime.utcnow,
                               onupdate=datetime.utcnow)
