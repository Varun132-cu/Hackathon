"""Synthetic-only profile context used by the live demo voice agent and dashboard."""

SYNTHETIC_BORROWER_CONTEXT = {
    "SYN-DF-001": {"purpose": "a short-term medical expense", "life_context": "a temporary household cash-flow gap", "contact_preference": "a short evening callback", "recent_note": "The synthetic profile suggests the customer may need time to confirm a payment date.", "next_step": "a payment date or a callback time"},
    "SYN-DF-002": {"purpose": "professional course fees", "life_context": "a transition between learning and work", "contact_preference": "a concise weekday conversation", "recent_note": "The synthetic profile suggests a date after the next income cycle may be more realistic.", "next_step": "a realistic payment date"},
    "SYN-DF-003": {"purpose": "a household repair", "life_context": "an unexpected home expense", "contact_preference": "a calm callback rather than a long call", "recent_note": "The synthetic profile suggests a flexible callback could be helpful.", "next_step": "a callback time or payment date"},
    "SYN-DF-004": {"purpose": "a family travel expense", "life_context": "a recent family commitment", "contact_preference": "a morning callback", "recent_note": "The synthetic profile suggests the customer may prefer a short, practical conversation.", "next_step": "a suitable time to reconnect"},
    "SYN-DF-005": {"purpose": "a small business equipment purchase", "life_context": "variable self-employment income", "contact_preference": "a brief weekday follow-up", "recent_note": "The synthetic profile suggests the customer may need to align a payment date with incoming business receipts.", "next_step": "a date to review payment availability"},
    "SYN-DF-006": {"purpose": "a home furnishing expense", "life_context": "a recent household setup cost", "contact_preference": "an early-evening callback", "recent_note": "The synthetic profile suggests a small, clear next step is preferable.", "next_step": "a callback time or payment date"},
    "SYN-DF-007": {"purpose": "a vehicle repair", "life_context": "an essential transport interruption", "contact_preference": "a concise call", "recent_note": "The synthetic profile suggests the customer may be balancing repair and travel costs.", "next_step": "a realistic payment date"},
    "SYN-DF-008": {"purpose": "a family education expense", "life_context": "a planned education commitment", "contact_preference": "a respectful weekday callback", "recent_note": "The synthetic profile suggests a callback after household discussion may be useful.", "next_step": "a convenient callback time"},
    "SYN-DF-009": {"purpose": "a move-in expense", "life_context": "a recent housing transition", "contact_preference": "a short afternoon callback", "recent_note": "The synthetic profile suggests a temporary cash-flow interruption.", "next_step": "a date to check in again"},
    "SYN-DF-010": {"purpose": "a home improvement", "life_context": "a planned household project", "contact_preference": "a concise follow-up", "recent_note": "The synthetic profile suggests the customer may want to schedule a payment around planned expenses.", "next_step": "a payment date or callback time"},
    "SYN-DF-011": {"purpose": "a planned family expense", "life_context": "a near-term family commitment", "contact_preference": "an evening callback", "recent_note": "The synthetic profile suggests the customer may need a little time before confirming a date.", "next_step": "a suitable follow-up time"},
    "SYN-DF-012": {"purpose": "a personal development expense", "life_context": "an investment in career development", "contact_preference": "a short scheduled callback", "recent_note": "The synthetic profile suggests the customer may be able to give a more precise answer after checking their budget.", "next_step": "a payment date or callback time"},
}

DEFAULT_CONTEXT = {
    "purpose": "a synthetic demo loan",
    "life_context": "a synthetic test scenario",
    "contact_preference": "a convenient callback",
    "recent_note": "No additional synthetic profile note is available.",
    "next_step": "a payment date or a callback time",
}


def context_for(borrower_id: str) -> dict[str, str]:
    return SYNTHETIC_BORROWER_CONTEXT.get(borrower_id, DEFAULT_CONTEXT).copy()
