from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    accepted_rows: Mapped[int] = mapped_column(Integer, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, default=0)
    errors_json: Mapped[str] = mapped_column(Text, default="[]")


class Borrower(Base):
    __tablename__ = "borrowers"

    id: Mapped[int] = mapped_column(primary_key=True)
    borrower_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    borrower_name: Mapped[str] = mapped_column(String(255))
    phone_number: Mapped[str] = mapped_column(String(32))
    loan_account_id: Mapped[str] = mapped_column(String(100), index=True)
    emi_amount: Mapped[float] = mapped_column(Float)
    days_past_due: Mapped[int] = mapped_column(Integer)
    consent_to_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    permitted_to_call: Mapped[bool] = mapped_column(Boolean, default=False)
    prior_contact_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="imported")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    calls: Mapped[list["Call"]] = relationship(back_populates="borrower")


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    borrower_id: Mapped[int] = mapped_column(ForeignKey("borrowers.id"), index=True)
    status: Mapped[str] = mapped_column(String(50), default="queued")
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assessment_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider: Mapped[str] = mapped_column(String(50), default="mock")
    provider_call_sid: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    borrower: Mapped["Borrower"] = relationship(back_populates="calls")
    escalation: Mapped["Escalation | None"] = relationship(back_populates="call", uselist=False)


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id"), unique=True)
    reason: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(30), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    call: Mapped["Call"] = relationship(back_populates="escalation")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str] = mapped_column(String(100))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
