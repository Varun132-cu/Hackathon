from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UploadResult(BaseModel):
    id: int
    filename: str
    accepted_rows: int
    rejected_rows: int
    errors: list[dict]


class BorrowerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    borrower_id: str
    borrower_name: str
    phone_number: str
    loan_account_id: str
    emi_amount: float
    days_past_due: int
    consent_to_contact: bool
    permitted_to_call: bool
    prior_contact_count: int
    status: str
    profile_context: dict[str, str] = Field(default_factory=dict)


class CreateCallJob(BaseModel):
    borrower_id: str


class CompleteMockCall(BaseModel):
    transcript: str
    outcome: str = "other"


class CallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    borrower_id: int
    status: str
    outcome: str | None
    transcript: str | None
    summary: str | None
    score: int | None
    assessment_label: str | None
    provider: str
    provider_call_sid: str | None
    created_at: datetime
    completed_at: datetime | None
    borrower_name: str | None = None
    borrower_reference: str | None = None
    profile_context: dict[str, str] = Field(default_factory=dict)


class EscalationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    call_id: int
    reason: str
    severity: str
    status: str
    created_at: datetime
