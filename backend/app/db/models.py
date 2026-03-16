from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, JSON,
    ForeignKey, Enum as SAEnum, Boolean, Index
)
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func
import enum


class Base(DeclarativeBase):
    pass


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EventType(str, enum.Enum):
    PULL_REQUEST = "pull_request"
    PUSH = "push"
    ISSUES = "issues"
    PING = "ping"


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    github_url = Column(String(512), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    owner = Column(String(255), nullable=False)
    default_branch = Column(String(100), default="main")
    indexed_at = Column(DateTime(timezone=True), nullable=True)
    health_score = Column(Float, default=100.0)
    is_active = Column(Boolean, default=True)
    webhook_configured = Column(Boolean, default=False)
    total_files_indexed = Column(Integer, default=0)
    indexing_status = Column(String(50), default="pending")  # pending, indexing, complete, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    events = relationship("Event", back_populates="repository", cascade="all, delete-orphan")
    pull_requests = relationship("PullRequest", back_populates="repository", cascade="all, delete-orphan")
    health_history = relationship("HealthHistory", back_populates="repository", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_repositories_owner_name", "owner", "name"),)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(100), nullable=False)
    github_delivery_id = Column(String(255), unique=True, nullable=True)
    payload = Column(JSON, nullable=False)
    raw_headers = Column(JSON, nullable=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    processing_status = Column(String(50), default="pending")  # pending, processing, complete, failed
    error_message = Column(Text, nullable=True)
    celery_task_id = Column(String(255), nullable=True)

    repository = relationship("Repository", back_populates="events")

    __table_args__ = (
        Index("ix_events_repo_id_received_at", "repo_id", "received_at"),
        Index("ix_events_processing_status", "processing_status"),
    )


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    github_pr_number = Column(Integer, nullable=False)
    title = Column(String(512), nullable=False)
    author = Column(String(255), nullable=False)
    author_avatar_url = Column(String(512), nullable=True)
    github_pr_url = Column(String(512), nullable=False)
    base_branch = Column(String(255), nullable=True)
    head_branch = Column(String(255), nullable=True)
    risk_level = Column(SAEnum(RiskLevel), nullable=True)
    debt_score = Column(Float, nullable=True)
    blast_radius_count = Column(Integer, default=0)
    files_changed = Column(Integer, default=0)
    lines_added = Column(Integer, default=0)
    lines_removed = Column(Integer, default=0)
    analysis_json = Column(JSON, nullable=True)
    github_comment_id = Column(Integer, nullable=True)
    labels_applied = Column(JSON, default=list)
    analysis_status = Column(String(50), default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    merged_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    is_stale = Column(Boolean, default=False)

    repository = relationship("Repository", back_populates="pull_requests")
    notifications = relationship("Notification", back_populates="pull_request", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_pr_repo_id_number", "repo_id", "github_pr_number", unique=True),
        Index("ix_pr_risk_level", "risk_level"),
        Index("ix_pr_created_at", "created_at"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    pr_id = Column(Integer, ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False)
    channel = Column(String(50), nullable=False)  # slack, email
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    content = Column(Text, nullable=False)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)

    pull_request = relationship("PullRequest", back_populates="notifications")


class HealthHistory(Base):
    __tablename__ = "health_history"

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    score = Column(Float, nullable=False)
    calculated_at = Column(DateTime(timezone=True), server_default=func.now())
    metrics_json = Column(JSON, nullable=True)

    repository = relationship("Repository", back_populates="health_history")

    __table_args__ = (Index("ix_health_history_repo_id_calculated_at", "repo_id", "calculated_at"),)
