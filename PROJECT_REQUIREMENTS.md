# DebtAssist Voice Agent — Product & Technical Requirements

## 1. Purpose

DebtAssist helps a bank or NBFC manage **consented, policy-compliant repayment reminder calls**. An authorised team uploads eligible borrower accounts; the system schedules a courteous voice outreach, records the interaction outcome, scores repayment likelihood, and routes sensitive conversations to a human agent.

This product is a servicing and reminder tool. It must not use threatening, deceptive, discriminatory, or coercive language, and it must always respect applicable debt-collection, privacy, consent, and calling-hour regulations.

## 2. Primary workflow

1. An authorised operations user signs in to the dashboard.
2. They upload a CSV/XLSX of eligible accounts.
3. The system validates mandatory fields, deduplicates records, and rejects accounts without contact consent or an allowed calling window.
4. Eligible accounts are queued for an outbound call through a telephony provider.
5. The voice agent verifies the recipient using a minimal, privacy-preserving check before discussing account details.
6. The agent listens for the customer’s situation and offers approved options: payment reminder, payment-link/SMS follow-up, promise-to-pay capture, callback request, or transfer to a human agent.
7. Each call generates a transcript/summary, outcome, sentiment and risk assessment, next action, and audit log entry.
8. Abusive language, distress, threats, vulnerability signals, disputes, or repeated failed contact attempts are flagged for human review.

## 3. User roles

- **Admin** — manages users, templates, compliance settings, and provider credentials.
- **Collections manager** — uploads lists, reviews queues, outcomes, and escalation workload.
- **Human agent** — handles only assigned escalations and logs follow-up.
- **Auditor/read-only** — views immutable activity and call records without changing them.

## 4. MVP features

### A. Account-list upload

- CSV upload in the first release; XLSX support is optional.
- Downloadable template and clear row-level validation errors.
- Required columns:
  - `borrower_id`
  - `borrower_name`
  - `phone_number` (E.164 format)
  - `loan_account_id`
  - `emi_amount`
  - `days_past_due`
  - `consent_to_contact`
  - `permitted_to_call`
- Optional columns: `due_date`, `prior_contact_count`, `preferred_language`, `allowed_call_start`, `allowed_call_end`, `notes`.
- Store upload source, uploader, timestamp, accepted/rejected row counts, and error reasons.

### B. Calling and conversation workflow

- Queue only records with explicit consent, permitted calling status, a valid number, and an in-hours schedule.
- Use an approved provider such as Twilio, Exotel, Plivo, or a bank-approved telephony vendor.
- Start with a clear identity and purpose, then request permission to continue.
- Do not reveal loan details until the recipient has passed the configured verification check.
- Keep language calm, concise, and non-judgmental.
- Capture structured outcomes: `paid`, `promise_to_pay`, `requested_callback`, `wrong_number`, `disputed`, `unreachable`, `refused`, `human_transfer`, `other`.
- Send payment links/messages only when the customer has consented and an approved channel is configured.

### C. Dashboard

- Overview cards: uploaded accounts, queued calls, completed calls, promise-to-pay total, escalations.
- Account table with search, status filters, risk score, last outcome, and next-action date.
- Call detail: timestamp, duration, provider status, transcript/summary, outcome, score breakdown, redacted recording link (if enabled), and audit trail.
- Escalation queue with reason, severity, owner, and resolution notes.
- Import report with downloadable rejected rows.

### D. Scoring and escalation

Create an explainable 0–100 **engagement/repayment score**, not an automated enforcement decision. Example inputs:

- positive: confirmed payment, credible promise-to-pay, requested payment link;
- neutral: callback request, short/unclear interaction;
- negative: repeated non-contact, refusal, dispute, or payment hardship;
- escalation signals: abusive/profane speech, hostile tone, threats, self-harm/distress indicators, vulnerability, complaint/legal dispute, or a request for a human.

Escalation must create a `human_intervention_required` record immediately. A human must review any high-severity flag before further automated outreach.

## 5. Conversation policy

- Ask once whether it is a convenient time; offer a callback.
- Never shame, threaten, impersonate a government body, misrepresent consequences, contact unauthorised third parties, or persist after an opt-out request.
- Honour do-not-call, dispute, hardship, language preference, and human-agent requests immediately.
- State that the call may be recorded/transcribed where required by law and policy.
- Use approved scripts and response templates; all prompt/template versions must be auditable.

Example opening:

> Hello, I’m calling from [Organisation] regarding a service update. Is this a convenient time to speak? Before I share any account information, I’ll need to verify that I’m speaking with the account holder.

## 6. Compliance, privacy, and safety requirements

- Obtain and retain a lawful basis and contact consent; enforce local calling windows and frequency caps.
- Use least-privilege role-based access control and MFA for staff accounts.
- Encrypt data in transit and at rest; redact phone numbers, identifiers, payment data, and transcripts in non-production views.
- Keep immutable audit events for uploads, queue decisions, calls, score changes, escalations, and manual actions.
- Define retention/deletion rules for recordings and transcripts; support account data export/deletion requests where applicable.
- Separate tenant/bank data and never train shared models on customer data without explicit written approval.
- Allow a kill switch to pause all outbound calls.
- Require human approval for policy changes, automated message templates, payment arrangements outside approved bounds, and escalated cases.

## 7. Technical architecture (MVP)

- **Web app:** React/Vite dashboard.
- **API:** Python FastAPI.
- **Database:** PostgreSQL.
- **Background jobs:** Redis + Celery/RQ for upload processing, scheduling, and webhook work.
- **Telephony:** provider adapter behind a `VoiceProvider` interface; local mock provider for development.
- **AI layer:** provider adapter for transcription, structured call summary, approved-response generation, and safety classification. Keep human-readable prompts/version IDs with each interaction.
- **Storage:** encrypted object storage for import files and optional recordings.
- **Observability:** structured logs, error monitoring, metrics, and audit-event table.

## 8. Initial data model

- `users`, `roles`, `organisations`
- `uploads`, `upload_rows`
- `borrowers`, `loan_accounts`, `contact_preferences`
- `call_jobs`, `calls`, `call_events`, `call_transcripts`
- `assessments` (score, labels, rationale, model/prompt version)
- `escalations`, `human_followups`
- `audit_events`

## 9. API outline

- `POST /api/uploads` — import borrower list.
- `GET /api/uploads/{id}` — import progress/errors.
- `GET /api/borrowers` and `GET /api/borrowers/{id}` — dashboard data.
- `POST /api/call-jobs` — enqueue an eligible call (internal/admin action).
- `POST /api/telephony/webhooks/*` — provider status and conversation events.
- `GET /api/escalations` / `PATCH /api/escalations/{id}` — human-review queue.
- `GET /api/dashboard/summary` — aggregate metrics.

## 10. Delivery plan

1. Bootstrap API, database schema, local mock telephony, and dashboard shell.
2. Implement secure CSV upload/validation, borrower records, and audit events.
3. Build the call-job queue, provider adapter, webhook ingestion, and mock call simulator.
4. Add structured conversation assessment, scoring, and escalation rules.
5. Build dashboard tables, account detail, import report, and escalation workflow.
6. Add authentication, RBAC, rate/call-frequency rules, observability, tests, and deployment configuration.
7. Complete compliance/security review before connecting production telephone numbers or real customer data.

## 11. Definition of done for the MVP

- A manager can upload a valid CSV and see accepted/rejected results.
- Only eligible accounts can be queued.
- A simulated/provider call produces a persisted outcome, summary, and assessment.
- Abusive/hostile, distress, dispute, and human-agent-request signals create visible escalation records.
- The dashboard shows call history, score explanations, and human-review status.
- Tests cover validation, eligibility, scoring, and escalation rules.
- No real calls are enabled until compliance approval and provider credentials are configured.
