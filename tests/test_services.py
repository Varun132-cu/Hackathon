from app.services import assess_conversation, validate_csv


def test_valid_csv_is_accepted():
    csv_data = b"""borrower_id,borrower_name,phone_number,loan_account_id,emi_amount,days_past_due,consent_to_contact,permitted_to_call\nBR-1,Asha,+919876543210,LN-1,1000,2,true,true\n"""
    valid, errors = validate_csv(csv_data)
    assert len(valid) == 1
    assert errors == []


def test_invalid_phone_is_rejected():
    csv_data = b"""borrower_id,borrower_name,phone_number,loan_account_id,emi_amount,days_past_due,consent_to_contact,permitted_to_call\nBR-1,Asha,9876543210,LN-1,1000,2,true,true\n"""
    valid, errors = validate_csv(csv_data)
    assert valid == []
    assert "E.164" in errors[0]["error"]


def test_abusive_conversation_requires_human_review():
    assessment = assess_conversation("You are a fraud. Put me through to a human agent.", "refused")
    assert assessment.label == "human_intervention_required"
    assert assessment.escalation_reason == "abusive_language"


def test_payment_promise_scores_positively():
    assessment = assess_conversation("I will make the payment this Friday.", "promise_to_pay")
    assert assessment.score == 80
    assert assessment.escalation_reason is None
