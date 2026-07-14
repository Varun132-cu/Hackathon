# DebtAssist MVP

A consent-aware repayment reminder backend with CSV import, mock-call processing, explainable engagement scoring, and human-intervention flags. It does **not** make real calls.

## Run locally

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/` for the dashboard or `http://127.0.0.1:8000/docs` for the interactive API.

## Try the workflow

1. Upload `sample_borrowers.csv` to `POST /api/uploads`.
2. Queue an eligible borrower through `POST /api/call-jobs` with `{"borrower_id":"BR-1001"}`.
3. Complete the simulated call using `POST /api/calls/{call_id}/complete-mock`:

```json
{"outcome":"promise_to_pay","transcript":"I can make the payment on Friday. Please send a payment link."}
```

Use a transcript such as `"This is a scam, I need to speak to a human agent"` to verify an escalation.

The SQLite database (`debtassist.db`) is created automatically for local development. Use PostgreSQL and managed secrets before deployment.

## Controlled Twilio pilot

The default mode is `VOICE_PROVIDER=mock`; it cannot call a real phone. For a controlled test only, configure `.env` with `VOICE_PROVIDER=twilio`, `LIVE_CALLS_ENABLED=true`, an HTTPS `PUBLIC_BASE_URL`, a Twilio account SID/auth token, and a verified or purchased `TWILIO_FROM_NUMBER`. Start with staff-owned, consented test numbers. The initial live flow is a short DTMF callback/opt-out IVR; it deliberately does not expose loan information or make AI decisions.

Before enabling a production campaign, add an approved calling-hours/frequency policy, DLT/TSP compliance for the target market, authentication/RBAC, PostgreSQL migrations, and a human review path. The Twilio callbacks in this build validate provider signatures using the configured public URL. Do not use the local SQLite setup for production.

## Live AI voice demo to your own phone

After the controlled Twilio pilot works, add `LIVE_AI_VOICE_ENABLED=true`, `OPENAI_API_KEY`, and an enabled `OPENAI_REALTIME_MODEL` to `.env`. The call then uses Twilio's bidirectional Media Stream to relay G.711 μ-law audio directly to and from the Realtime API; there is no audio conversion layer. Keep the API key on the server and test only with your own phone number.

The call flow is `Twilio → wss://your-domain/api/telephony/twilio/media → Realtime API → Twilio`. The public endpoint must support both HTTPS and secure WebSockets (`wss`). This demo uses a constrained script and saves returned caller/agent transcripts to the call record; it is not ready for borrower calls.
