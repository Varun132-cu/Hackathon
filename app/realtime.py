"""Bidirectional Twilio Media Streams to a consented, synthetic-data Realtime demo."""

import asyncio
import json
import ssl

import websockets
from fastapi import WebSocket

from app.config import Settings
from app.database import SessionLocal
from app.demo_context import context_for
from app.models import Call, Escalation
from app.services import assess_conversation, log_event


def ws_url(public_base_url: str) -> str:
    return public_base_url.rstrip("/").replace("https://", "wss://", 1) + "/api/telephony/twilio/media"


def build_instructions(*, borrower_name: str, borrower_id: str, emi_amount: float, days_past_due: int, organisation_name: str) -> str:
    """Create a privacy-conscious script for a synthetic, consented test account only."""
    context = context_for(borrower_id)
    return f"""You are a warm, concise AI voice assistant for a synthetic DebtAssist demo.
You are speaking only to the developer's own consented test phone. This is not a production collection call.
Speak exclusively in clear, natural US English. Never switch to Portuguese or any other language unless the caller explicitly asks you to.
This is a purpose-specific repayment-outreach conversation, not a general assistant. Never open with a generic offer such as "How can I help you today?" and do not answer unrelated questions (including medical, legal, or financial-advice questions). Briefly acknowledge the concern, explain that you cannot advise on it, then return to identity verification or offer a human callback.

Start: "Hello, this is the DebtAssist demo assistant from {organisation_name}. Is this {borrower_name}, and is now an okay time to talk?"
Do not reveal account details until they confirm they are {borrower_name}. If they do not confirm, say you cannot discuss the account and end the call.

After confirmation, say this is a synthetic demo account created for {context['purpose']}. Explain calmly that its monthly installment is INR {emi_amount:,.0f} and it is {days_past_due} days past due. Ask an open question such as: "Would you like to share what has made payment difficult, or would a short callback be better?"
The synthetic profile also suggests {context['life_context']} and a preference for {context['contact_preference']}. Treat this only as a gentle cue, never as a fact to challenge the caller with. You may offer {context['next_step']} when appropriate. Profile note: {context['recent_note']}

Conversation flow:
1. On the first turn, say the Start sentence exactly, then stop and listen.
2. Until identity is confirmed, ask only for confirmation. If the caller asks an unrelated question, acknowledge it briefly, say you cannot help with that topic, and repeat the identity question.
3. After confirmation, explain the synthetic account context once and ask the open question.
4. For each later caller turn, respond directly to what they said. If they give a payment date or callback time, repeat it back accurately and ask one concise confirmation question. Do not repeat the opening greeting or account explanation.
5. Once a date/time is confirmed, thank them, say it will be recorded for follow-up, and close naturally.

Interpret caller replies using this map:
- Confirmation such as "yes", "speaking", or "this is {borrower_name}": move to step 3 immediately.
- A payment commitment with a date such as "Friday", "next week", or "after salary": acknowledge it and ask for the most specific date/time they can comfortably confirm.
- A callback request: offer the synthetic profile's preferred window only as an option, then repeat the caller's chosen time back for confirmation.
- A hardship or inability-to-pay statement: acknowledge it without pressure, stop asking for payment, and offer a human follow-up or callback.
- A question about the amount or overdue status after identity confirmation: answer only with the synthetic EMI amount and days past due given above, then return to one voluntary next-step question.
- An ambiguous answer such as "maybe", "I don't know", or "later": ask one short clarifying question: whether a callback time or a future payment date would be easier.
- If a spoken date, day, amount, or time is unclear or conflicts with what the caller said, never guess or invent a value. Say, "I want to make sure I record that correctly," then ask the caller to repeat the specific date or time.
- A confirmed time or date: close the conversation. Do not ask another repayment question.

Listen without interruption. Do not shame, threaten, promise legal consequences, claim authority, negotiate loan terms, request card/bank details, or take payment. You may invite one voluntary next step only: {context['next_step']}. If the caller gives a date or time, repeat it back for confirmation and say the team will record it for follow-up.

If the caller asks to stop, opts out, mentions distress/hardship, disputes the account, uses abusive language, or asks for a human, immediately acknowledge it, say a human follow-up will be arranged where appropriate, do not continue repayment discussion, and end the call.
Keep turns short, natural, and non-judgmental. Never invent facts beyond this synthetic context."""


def infer_outcome(transcript: str) -> str:
    text = transcript.lower()
    if any(term in text for term in ("do not call", "don't call", "stop calling", "opt out")):
        return "opted_out"
    if any(term in text for term in ("dispute", "not my loan", "wrong account", "lawyer")):
        return "disputed"
    if any(term in text for term in ("human agent", "speak to a person", "manager", "representative")):
        return "human_transfer"
    if any(term in text for term in ("call me back", "callback", "call back")):
        return "requested_callback"
    if any(term in text for term in ("will pay", "i'll pay", "i will pay", "pay on", "payment on")):
        return "promise_to_pay"
    return "other"


def tls12_context() -> ssl.SSLContext:
    """Avoid the TLS 1.3 handshake stall observed on this demo workstation."""
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_2
    return context


async def bridge_twilio_to_realtime(websocket: WebSocket, settings: Settings) -> None:
    """Forward G.711 μ-law frames in both directions and persist the conversation result."""
    settings.validate_live_ai_settings()
    await websocket.accept()
    call_id: int | None = None
    stream_sid: str | None = None
    instructions: str | None = None
    transcript: list[str] = []
    realtime_url = f"wss://api.openai.com/v1/realtime?model={settings.openai_realtime_model}"
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}

    try:
        async with websockets.connect(realtime_url, additional_headers=headers, ssl=tls12_context()) as ai_socket:
            while not stream_sid:
                event = json.loads(await websocket.receive_text())
                if event.get("event") != "start":
                    continue
                stream_sid = event["start"]["streamSid"]
                parameters = event["start"].get("customParameters", {})
                call_id = int(parameters.get("call_id", "0"))
                provider_sid = event["start"].get("callSid")
                with SessionLocal() as db:
                    call = db.get(Call, call_id)
                    if not call or call.provider != "twilio" or call.provider_call_sid != provider_sid:
                        await websocket.close(code=1008)
                        return
                    borrower = call.borrower
                    instructions = build_instructions(
                        borrower_name=borrower.borrower_name,
                        borrower_id=borrower.borrower_id,
                        emi_amount=borrower.emi_amount,
                        days_past_due=borrower.days_past_due,
                        organisation_name=settings.organisation_name,
                    )
                    log_event(db, "ai_media_stream_started", "call", call_id, {
                        "stream_sid": stream_sid,
                        "synthetic_demo": borrower.borrower_id.startswith("SYN-"),
                        "profile_context": context_for(borrower.borrower_id),
                    })
                    db.commit()
            await ai_socket.send(json.dumps({"type": "session.update", "session": {
                "type": "realtime",
                "instructions": instructions,
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcmu"},
                        "transcription": {"model": "gpt-4o-mini-transcribe", "language": "en"},
                        # Server VAD automatically commits each finished caller turn and
                        # creates the next response from the full session instructions.
                        "turn_detection": {"type": "server_vad", "silence_duration_ms": 800, "create_response": True, "interrupt_response": True},
                    },
                    "output": {"format": {"type": "audio/pcmu"}, "voice": "marin"},
                },
            }}))
            while True:
                session_event = json.loads(await ai_socket.recv())
                if session_event.get("type") == "session.updated":
                    break
                if session_event.get("type") == "error":
                    raise RuntimeError(session_event.get("error", {}).get("message", "Realtime session update failed"))
            # Do not provide per-response instructions here: Realtime treats them as
            # an override of the session instructions, which would discard the
            # borrower-specific conversation state above.
            await ai_socket.send(json.dumps({"type": "response.create"}))

            async def from_twilio() -> None:
                while True:
                    message = json.loads(await websocket.receive_text())
                    if message.get("event") == "media":
                        await ai_socket.send(json.dumps({"type": "input_audio_buffer.append", "audio": message["media"]["payload"]}))
                    elif message.get("event") == "stop":
                        return

            async def from_ai() -> None:
                while True:
                    event = json.loads(await ai_socket.recv())
                    event_type = event.get("type")
                    if event_type == "response.output_audio.delta":
                        await websocket.send_text(json.dumps({"event": "media", "streamSid": stream_sid, "media": {"payload": event["delta"]}}))
                    elif event_type == "response.output_audio_transcript.done":
                        transcript.append("Agent: " + event.get("transcript", ""))
                    elif event_type == "conversation.item.input_audio_transcription.completed":
                        transcript.append("Caller: " + event.get("transcript", ""))
                    elif event_type == "input_audio_buffer.speech_started":
                        await websocket.send_text(json.dumps({"event": "clear", "streamSid": stream_sid}))
                    elif event_type == "error":
                        raise RuntimeError(event.get("error", {}).get("message", "Realtime conversation error"))

            done, pending = await asyncio.wait(
                [asyncio.create_task(from_twilio()), asyncio.create_task(from_ai())],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            # Surface a failed bridge task instead of silently treating it as a normal hang-up.
            # The outer handler records a safe diagnostic against this call.
            for task in done:
                task.result()
    except Exception as exc:
        if call_id:
            with SessionLocal() as db:
                log_event(db, "ai_media_stream_error", "call", call_id, {
                    "error": str(exc)[:500],
                    "stream_sid": stream_sid or "",
                })
                db.commit()
        raise
    finally:
        if call_id:
            with SessionLocal() as db:
                call = db.get(Call, call_id)
                if call and transcript:
                    full_transcript = "\n".join(transcript)
                    outcome = infer_outcome(full_transcript)
                    assessment = assess_conversation(full_transcript, outcome)
                    call.transcript = full_transcript
                    call.outcome = outcome
                    call.summary = assessment.summary
                    call.score = assessment.score
                    call.assessment_label = assessment.label
                    call.status = "completed"
                    if outcome == "opted_out":
                        call.borrower.permitted_to_call = False
                        call.borrower.status = "opted_out"
                    else:
                        call.borrower.status = assessment.label
                    if assessment.escalation_reason and not call.escalation:
                        db.add(Escalation(call_id=call.id, reason=assessment.escalation_reason, severity=assessment.severity))
                    log_event(db, "ai_media_stream_ended", "call", call_id, {"outcome": outcome, "score": assessment.score, "transcript_lines": len(transcript)})
                    db.commit()
