import json
from datetime import datetime

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, engine, get_db
from app.demo_context import context_for
from app.models import Borrower, Call, Escalation, Upload
from app.schemas import BorrowerOut, CallOut, CompleteMockCall, CreateCallJob, EscalationOut, UploadResult
from app.services import assess_conversation, log_event, validate_csv
from app.telephony import get_voice_provider, validate_twilio_webhook
from app.realtime import bridge_twilio_to_realtime, ws_url

Base.metadata.create_all(bind=engine)
settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"], allow_credentials=True)


def borrower_payload(borrower: Borrower) -> dict:
    payload = BorrowerOut.model_validate(borrower).model_dump()
    payload["profile_context"] = context_for(borrower.borrower_id)
    return payload


def call_payload(call: Call) -> dict:
    payload = CallOut.model_validate(call).model_dump()
    borrower = call.borrower
    payload.update({
        "borrower_name": borrower.borrower_name,
        "borrower_reference": borrower.borrower_id,
        "profile_context": context_for(borrower.borrower_id),
    })
    return payload


@app.get("/health")
def health():
    return {"status": "ok", "voice_provider": settings.voice_provider, "live_calls_enabled": settings.live_calls_enabled}


@app.get("/api/voice/status")
def voice_status():
    """Return non-secret readiness information for the live AI demo."""
    provider_ready = all([
        settings.voice_provider == "twilio",
        settings.live_calls_enabled,
        settings.twilio_account_sid,
        settings.twilio_auth_token,
        settings.twilio_from_number,
    ])
    public_url_ready = bool(settings.public_base_url) and "abc123.ngrok-free.app" not in settings.public_base_url
    return {
        "provider_ready": provider_ready,
        "live_ai_enabled": settings.live_ai_voice_enabled,
        "public_url_configured": bool(settings.public_base_url),
        "public_url_ready": public_url_ready,
        "live_call_ready": provider_ready and settings.live_ai_voice_enabled and public_url_ready,
        "realtime_model": settings.openai_realtime_model if settings.live_ai_voice_enabled else None,
        "demo_only": True,
    }


@app.post("/api/uploads", response_model=UploadResult, status_code=201)
async def upload_borrowers(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a CSV file.")
    valid, errors = validate_csv(await file.read())
    upload = Upload(filename=file.filename, accepted_rows=len(valid), rejected_rows=len(errors), errors_json=json.dumps(errors))
    db.add(upload)
    for data in valid:
        existing = db.scalar(select(Borrower).where(Borrower.borrower_id == data["borrower_id"]))
        if existing:
            errors.append({"row": None, "error": f"Duplicate borrower_id: {data['borrower_id']}"})
            upload.accepted_rows -= 1
            upload.rejected_rows += 1
            continue
        db.add(Borrower(**data))
    upload.errors_json = json.dumps(errors)
    log_event(db, "upload_processed", "upload", "pending", {"filename": file.filename, "accepted": upload.accepted_rows, "rejected": upload.rejected_rows})
    db.commit()
    db.refresh(upload)
    return UploadResult(id=upload.id, filename=upload.filename, accepted_rows=upload.accepted_rows, rejected_rows=upload.rejected_rows, errors=errors)


@app.get("/api/borrowers", response_model=list[BorrowerOut])
def list_borrowers(db: Session = Depends(get_db)):
    return [borrower_payload(borrower) for borrower in db.scalars(select(Borrower).order_by(Borrower.created_at.desc()))]


@app.post("/api/call-jobs", response_model=CallOut, status_code=201)
def create_call_job(payload: CreateCallJob, db: Session = Depends(get_db)):
    borrower = db.scalar(select(Borrower).where(Borrower.borrower_id == payload.borrower_id))
    if not borrower:
        raise HTTPException(404, "Borrower not found.")
    if not borrower.consent_to_contact or not borrower.permitted_to_call:
        raise HTTPException(409, "Call cannot be queued: contact consent or permission is missing.")
    call = Call(borrower_id=borrower.id, status="queued", provider=settings.voice_provider)
    borrower.status = "call_queued"
    db.add(call)
    db.flush()
    log_event(db, "call_queued", "call", call.id, {"provider": settings.voice_provider, "borrower_id": borrower.borrower_id})
    if settings.voice_provider == "twilio" and settings.live_calls_enabled:
        try:
            placed_call = get_voice_provider(settings).place_outbound_call(borrower.phone_number, call.id)
            call.provider_call_sid, call.status = placed_call.sid, placed_call.status
            log_event(db, "live_call_requested", "call", call.id, {"provider": "twilio", "provider_call_sid": placed_call.sid})
        except (ValueError, Exception) as exc:
            call.status, borrower.status = "failed", "call_failed"
            log_event(db, "live_call_failed", "call", call.id, {"error": str(exc)})
            db.commit()
            raise HTTPException(502, "The telephony provider could not start the call. Check the audit log and provider console.")
    db.commit()
    db.refresh(call)
    return call_payload(call)


@app.post("/api/calls/{call_id}/complete-mock", response_model=CallOut)
def complete_mock_call(call_id: int, payload: CompleteMockCall, db: Session = Depends(get_db)):
    if call := db.get(Call, call_id):
        if call.provider != "mock":
            raise HTTPException(409, "Mock completion is unavailable for a live-provider call.")
    else:
        raise HTTPException(404, "Call not found.")
    if call.status == "completed":
        raise HTTPException(409, "Call is already completed.")
    assessment = assess_conversation(payload.transcript, payload.outcome)
    call.status, call.outcome, call.transcript = "completed", payload.outcome, payload.transcript
    call.summary, call.score, call.assessment_label, call.completed_at = assessment.summary, assessment.score, assessment.label, datetime.utcnow()
    call.borrower.status = assessment.label
    if assessment.escalation_reason:
        db.add(Escalation(call_id=call.id, reason=assessment.escalation_reason, severity=assessment.severity))
    log_event(db, "call_completed", "call", call.id, {"outcome": payload.outcome, "score": assessment.score, "label": assessment.label})
    db.commit()
    db.refresh(call)
    return call_payload(call)


@app.get("/api/calls/{call_id}", response_model=CallOut)
def get_call(call_id: int, db: Session = Depends(get_db)):
    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(404, "Call not found.")
    return call_payload(call)


@app.get("/api/calls", response_model=list[CallOut])
def list_calls(db: Session = Depends(get_db)):
    return [call_payload(call) for call in db.scalars(select(Call).order_by(Call.created_at.desc()).limit(20))]


async def require_valid_twilio_webhook(request: Request) -> None:
    form = await request.form()
    params = {str(key): str(value) for key, value in form.items()}
    signature = request.headers.get("X-Twilio-Signature")
    path_and_query = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    if not validate_twilio_webhook(settings, path_and_query, params, signature):
        raise HTTPException(403, "Invalid telephony webhook signature.")


@app.post("/api/telephony/twilio/voice")
async def twilio_voice_instructions(call_id: int, request: Request, db: Session = Depends(get_db)):
    """Return a minimal, privacy-preserving call flow before a live AI stream is connected."""
    await require_valid_twilio_webhook(request)
    call = db.get(Call, call_id)
    if not call or call.provider != "twilio":
        raise HTTPException(404, "Call not found.")
    if settings.live_ai_voice_enabled:
        try:
            settings.validate_live_ai_settings()
        except ValueError as exc:
            raise HTTPException(503, str(exc)) from exc
        media_url = ws_url(settings.public_base_url)
        return_response = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response><Connect><Stream url="{media_url}"><Parameter name="call_id" value="{call.id}" /></Stream></Connect></Response>'''
        from fastapi.responses import Response
        return Response(content=return_response, media_type="application/xml")
    base_url = settings.public_base_url.rstrip("/")
    org = settings.organisation_name.replace("&", "and")
    return_response = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response><Gather input="dtmf" numDigits="1" timeout="8" action="{base_url}/api/telephony/twilio/gather?call_id={call_id}" method="POST"><Say voice="alice" language="en-US">Hello. This is {org} calling about a service update. We will not share account details without verification. If this is a convenient time to receive a callback from our team, press 1. To opt out of automated calls, press 9.</Say></Gather><Say language="en-US">We did not receive a selection. Thank you. Goodbye.</Say></Response>'''
    from fastapi.responses import Response
    return Response(content=return_response, media_type="application/xml")


@app.websocket("/api/telephony/twilio/media")
async def twilio_media_stream(websocket: WebSocket):
    await bridge_twilio_to_realtime(websocket, settings)


@app.post("/api/telephony/twilio/gather")
async def twilio_gather(call_id: int, request: Request, Digits: str = Form(""), db: Session = Depends(get_db)):
    await require_valid_twilio_webhook(request)
    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(404, "Call not found.")
    if Digits == "9":
        call.borrower.permitted_to_call, call.borrower.status = False, "opted_out"
        call.outcome, call.status = "opted_out", "completed"
        log_event(db, "automated_call_opt_out", "call", call.id, {})
    elif Digits == "1":
        call.outcome, call.status = "requested_callback", "completed"
        log_event(db, "callback_requested", "call", call.id, {})
    else:
        call.outcome, call.status = "other", "completed"
    call.completed_at = datetime.utcnow()
    db.commit()
    from fastapi.responses import Response
    return Response(content="<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response><Say language=\"en-US\">Thank you. Goodbye.</Say></Response>", media_type="application/xml")


@app.post("/api/telephony/twilio/status")
async def twilio_status(call_id: int, request: Request, db: Session = Depends(get_db)):
    """Persist signed Twilio progress callbacks."""
    await require_valid_twilio_webhook(request)
    form = await request.form()
    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(404, "Call not found.")
    provider_status = str(form.get("CallStatus", ""))
    provider_sid = str(form.get("CallSid", ""))
    if provider_sid:
        call.provider_call_sid = provider_sid
    if provider_status:
        call.status = provider_status
    if provider_status in {"completed", "busy", "failed", "no-answer", "canceled"}:
        call.completed_at = datetime.utcnow()
        if not call.outcome:
            call.outcome = provider_status
    log_event(db, "telephony_status", "call", call.id, {"provider": "twilio", "status": provider_status, "sid": provider_sid})
    db.commit()
    return {"ok": True}


@app.post("/api/telephony/twilio/stream-status")
async def twilio_stream_status(call_id: int, request: Request, db: Session = Depends(get_db)):
    """Persist Twilio Media Stream lifecycle events for live-demo diagnostics."""
    await require_valid_twilio_webhook(request)
    form = await request.form()
    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(404, "Call not found.")
    log_event(db, "media_stream_status", "call", call_id, {
        "event": str(form.get("StreamEvent", "")),
        "stream_sid": str(form.get("StreamSid", "")),
        "error": str(form.get("StreamError", "")),
    })
    db.commit()
    return {"ok": True}


@app.get("/api/escalations", response_model=list[EscalationOut])
def list_escalations(db: Session = Depends(get_db)):
    return list(db.scalars(select(Escalation).order_by(Escalation.created_at.desc())))


@app.get("/api/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    return {
        "borrowers": db.scalar(select(func.count()).select_from(Borrower)) or 0,
        "queued_calls": db.scalar(select(func.count()).select_from(Call).where(Call.status == "queued")) or 0,
        "completed_calls": db.scalar(select(func.count()).select_from(Call).where(Call.status == "completed")) or 0,
        "open_escalations": db.scalar(select(func.count()).select_from(Escalation).where(Escalation.status == "open")) or 0,
    }


app.mount("/", StaticFiles(directory="app/static", html=True), name="dashboard")
