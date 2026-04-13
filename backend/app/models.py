"""
backend/app/models.py
SQLAlchemy ORM models mirroring database/schema.sql exactly.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime,
    Enum, JSON, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from backend.app.database import Base


class Environment(Base):
    __tablename__ = "environments"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    agents = relationship("Agent", back_populates="environment",
                          cascade="all, delete-orphan")
    runs   = relationship("Run",   back_populates="environment",
                          cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Environment id={self.id} name={self.name!r}>"


class Tool(Base):
    __tablename__ = "tools"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    is_builtin  = Column(Boolean, nullable=False, default=True)
    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)

    agent_tools = relationship("AgentTool", back_populates="tool",
                               cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tool id={self.id} name={self.name!r}>"


class Agent(Base):
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

    def __repr__(self):
        return f"<Agent id={self.id} name={self.name!r}>"


class AgentTool(Base):
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

    def __repr__(self):
        return f"<AgentTool agent={self.agent_id} tool={self.tool_id} scope={self.scope}>"


class Run(Base):
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

    environment = relationship("Environment", back_populates="runs")
    audit_logs  = relationship("AuditLog", back_populates="run",
                               cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Run id={self.id} status={self.status}>"


class AuditLog(Base):
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
