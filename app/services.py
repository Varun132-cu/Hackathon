import csv
import io
import json
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import AuditEvent

REQUIRED_COLUMNS = {
    "borrower_id", "borrower_name", "phone_number", "loan_account_id", "emi_amount",
    "days_past_due", "consent_to_contact", "permitted_to_call",
}
PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")
ESCALATION_TERMS = {
    "abusive_language": ["idiot", "stupid", "fraud", "scam", "fuck", "shit", "bastard"],
    "distress": ["suicide", "self harm", "kill myself", "cannot go on"],
    "dispute": ["dispute", "not my loan", "wrong account", "legal notice", "lawyer"],
    "human_request": ["human agent", "speak to a person", "manager", "representative"],
}


def as_bool(value: str | None) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def validate_csv(contents: bytes) -> tuple[list[dict], list[dict]]:
    try:
        text = contents.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
    except (UnicodeDecodeError, csv.Error) as exc:
        return [], [{"row": 0, "error": f"Invalid CSV: {exc}"}]
    headers = set(reader.fieldnames or [])
    missing = sorted(REQUIRED_COLUMNS - headers)
    if missing:
        return [], [{"row": 0, "error": f"Missing required columns: {', '.join(missing)}"}]
    valid, errors = [], []
    for row_number, row in enumerate(reader, start=2):
        row_errors = []
        for field in REQUIRED_COLUMNS:
            if not str(row.get(field, "")).strip():
                row_errors.append(f"{field} is required")
        if row.get("phone_number") and not PHONE_RE.fullmatch(row["phone_number"].strip()):
            row_errors.append("phone_number must be E.164, e.g. +919876543210")
        try:
            emi_amount = float(row.get("emi_amount", ""))
            if emi_amount < 0:
                row_errors.append("emi_amount cannot be negative")
        except ValueError:
            row_errors.append("emi_amount must be numeric")
            emi_amount = 0
        try:
            days_past_due = int(row.get("days_past_due", ""))
            if days_past_due < 0:
                row_errors.append("days_past_due cannot be negative")
        except ValueError:
            row_errors.append("days_past_due must be an integer")
            days_past_due = 0
        if row_errors:
            errors.append({"row": row_number, "error": "; ".join(row_errors)})
            continue
        valid.append({
            "borrower_id": row["borrower_id"].strip(), "borrower_name": row["borrower_name"].strip(),
            "phone_number": row["phone_number"].strip(), "loan_account_id": row["loan_account_id"].strip(),
            "emi_amount": emi_amount, "days_past_due": days_past_due,
            "consent_to_contact": as_bool(row["consent_to_contact"]),
            "permitted_to_call": as_bool(row["permitted_to_call"]),
            "prior_contact_count": int(row.get("prior_contact_count") or 0),
        })
    return valid, errors


def log_event(db: Session, event_type: str, entity_type: str, entity_id: int | str, detail: dict) -> None:
    db.add(AuditEvent(event_type=event_type, entity_type=entity_type, entity_id=str(entity_id), detail=json.dumps(detail)))


@dataclass
class Assessment:
    score: int
    label: str
    summary: str
    escalation_reason: str | None = None
    severity: str = "medium"


def assess_conversation(transcript: str, outcome: str) -> Assessment:
    normalized = transcript.lower()
    for reason, terms in ESCALATION_TERMS.items():
        if any(term in normalized for term in terms):
            severity = "high" if reason == "distress" else "medium"
            return Assessment(20, "human_intervention_required", "Sensitive conversation requires human review.", reason, severity)
    score = 50
    if outcome == "paid":
        score = 95
    elif outcome == "promise_to_pay":
        score = 80
    elif outcome == "requested_callback":
        score = 60
    elif outcome in {"refused", "unreachable"}:
        score = 30
    elif outcome == "disputed":
        return Assessment(25, "human_intervention_required", "Account dispute requires human review.", "dispute")
    return Assessment(score, "engaged" if score >= 60 else "follow_up", f"Call outcome recorded as {outcome}.")
