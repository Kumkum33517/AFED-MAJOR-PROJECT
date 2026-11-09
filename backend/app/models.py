"""Database tables. Keep in step with supabase/schema.sql."""
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

ROLES = ("Admin", "Analyst", "Reviewer", "Viewer")
ALERT_STATUSES = ("Pending", "Confirmed", "Dismissed", "Escalated")
CASE_STATUSES = ("Open", "Investigating", "Closed")
SEEDED_COMMENT = "Simulated review from seed data"  # marks decisions that came from the synthetic labels, not a person


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="Viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|completed|failed
    stage: Mapped[str] = mapped_column(String(80), default="Queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(255), default="")
    rows: Mapped[int] = mapped_column(Integer, default=0)
    new_rows: Mapped[int] = mapped_column(Integer, default=0)
    alerts_count: Mapped[int] = mapped_column(Integer, default=0)
    model_version: Mapped[Optional[str]] = mapped_column(String(40))
    # none_as_null: plain JSON stores None as the JSON value null, which `IS NOT NULL` then matches.
    metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON(none_as_null=True))
    error: Mapped[Optional[str]] = mapped_column(Text)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class Event(Base):
    """One invoice. The input columns, then what the latest run computed for it."""
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    vendor_id: Mapped[str] = mapped_column(String(120), index=True)
    vendor_name: Mapped[Optional[str]] = mapped_column(String(255))
    amount: Mapped[float] = mapped_column(Float)
    invoice_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    invoice_number: Mapped[Optional[str]] = mapped_column(String(120))
    category: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    department: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    approver_id: Mapped[Optional[str]] = mapped_column(String(120))
    created_by: Mapped[Optional[str]] = mapped_column(String(120))
    approval_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    processing_days: Mapped[Optional[float]] = mapped_column(Float)
    bank_account: Mapped[Optional[str]] = mapped_column(String(80))
    vendor_created: Mapped[Optional[datetime]] = mapped_column(DateTime)
    po_amount: Mapped[Optional[float]] = mapped_column(Float)
    is_anomaly: Mapped[Optional[int]] = mapped_column(Integer)
    anomaly_type: Mapped[Optional[str]] = mapped_column(String(60))
    # Scored by the pipeline
    baseline_source: Mapped[Optional[str]] = mapped_column(String(10))
    baseline_amount: Mapped[Optional[float]] = mapped_column(Float)
    expected_amount: Mapped[Optional[float]] = mapped_column(Float)
    amt_z: Mapped[Optional[float]] = mapped_column(Float)
    amt_ratio: Mapped[Optional[float]] = mapped_column(Float)
    freq_z: Mapped[Optional[float]] = mapped_column(Float)
    proc_z: Mapped[Optional[float]] = mapped_column(Float)
    risk: Mapped[Optional[float]] = mapped_column(Float, index=True)
    level: Mapped[Optional[str]] = mapped_column(String(10), index=True)
    flags: Mapped[list[str]] = mapped_column(JSON, default=list)


class EntityBaseline(Base):
    """Latest baseline per vendor, for profile pages. Per-event baselines live on the events."""
    __tablename__ = "entity_baselines"
    __table_args__ = (UniqueConstraint("entity_type", "entity_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20), default="vendor")
    entity_id: Mapped[str] = mapped_column(String(120), index=True)
    entity_name: Mapped[Optional[str]] = mapped_column(String(255))
    category: Mapped[Optional[str]] = mapped_column(String(120))
    baseline_source: Mapped[str] = mapped_column(String(10), default="vendor")
    median_amount: Mapped[Optional[float]] = mapped_column(Float)
    p25_amount: Mapped[Optional[float]] = mapped_column(Float)
    p75_amount: Mapped[Optional[float]] = mapped_column(Float)
    median_gap_days: Mapped[Optional[float]] = mapped_column(Float)
    median_processing_days: Mapped[Optional[float]] = mapped_column(Float)
    history_len: Mapped[int] = mapped_column(Integer, default=0)
    usual_bank_account: Mapped[Optional[str]] = mapped_column(String(80))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_id: Mapped[str] = mapped_column(String(120), index=True)
    vendor_name: Mapped[Optional[str]] = mapped_column(String(255))
    window_start: Mapped[datetime] = mapped_column(DateTime)
    window_end: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="Open", index=True)
    assignee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    notes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    assignee: Mapped[Optional[User]] = relationship()
    alerts: Mapped[list["Alert"]] = relationship(back_populates="case")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = {"sqlite_autoincrement": True}  # a reused id would inherit a deleted alert's audit history
    id: Mapped[int] = mapped_column(primary_key=True)
    event_pk: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), unique=True)
    vendor_id: Mapped[str] = mapped_column(String(120), index=True)
    risk: Mapped[float] = mapped_column(Float, index=True)
    level: Mapped[str] = mapped_column(String(10), index=True)
    a_score: Mapped[float] = mapped_column(Float)  # A: Isolation Forest percentile, cubed
    d_score: Mapped[float] = mapped_column(Float)  # D: entity deviation
    f_score: Mapped[float] = mapped_column(Float)  # F: rule score
    lstm_score: Mapped[Optional[float]] = mapped_column(Float)  # LSTM error percentile, display only; NULL if torch is absent
    flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    facts: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    explanation: Mapped[str] = mapped_column(Text, default="")
    explanation_provider: Mapped[str] = mapped_column(String(20), default="template")
    status: Mapped[str] = mapped_column(String(20), default="Pending", index=True)
    assignee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), index=True)
    run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"))
    model_version: Mapped[Optional[str]] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    event: Mapped[Event] = relationship()
    assignee: Mapped[Optional[User]] = relationship()
    case: Mapped[Optional[Case]] = relationship(back_populates="alerts")


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(20))  # Confirmed|Dismissed|Escalated
    label: Mapped[Optional[int]] = mapped_column(Integer)  # 1 confirmed, 0 dismissed, NULL escalated
    reason: Mapped[str] = mapped_column(String(120), default="")
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Setting(Base):
    """Single row (id = 1) holding the pipeline settings as JSON."""
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read", "user_id", "read"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(30))  # critical_alert|assignment|run_completed|password_reset
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str] = mapped_column(String(200), default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str] = mapped_column(String(30), default="")
    entity_id: Mapped[str] = mapped_column(String(80), default="")
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    user: Mapped[Optional[User]] = relationship()
