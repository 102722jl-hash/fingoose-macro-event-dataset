from audit_outputs import (
    classify_temporal_role,
    evaluate_candidate_evidence,
    validate_causal_gate,
)


def test_post_event_material_is_validation_only():
    assert classify_temporal_role(
        published_at="2026-01-03T00:00:00Z",
        anchor_at="2026-01-01T00:00:00Z",
        declared_role="POST_EVENT_VALIDATION",
    ) == "POST_EVENT_VALIDATION"


def test_post_event_material_cannot_claim_as_of_role():
    assert classify_temporal_role(
        published_at="2026-01-03T00:00:00Z",
        anchor_at="2026-01-01T00:00:00Z",
        declared_role="AS_OF_EVIDENCE",
    ) == "CUTOFF_BLOCKED"


def test_media_source_cannot_support_source_fact():
    result = evaluate_candidate_evidence(
        {
            "source_tier": "T3",
            "statement_class": "SOURCE_FACT",
            "original_quote": "reported statement",
            "locator": "paragraph 2",
            "source_url": "https://media.test/story",
            "temporal_role": "AS_OF_EVIDENCE",
        }
    )
    assert result == {"accepted": False, "reason": "SOURCE_TIER_NOT_ELIGIBLE"}


def test_nonidentified_must_abstain():
    errors = validate_causal_gate(
        {
            "status": "NOT_IDENTIFIED",
            "causal_attribution_allowed": True,
            "causal_conclusion": "CAUSED",
            "gate_results": {},
        }
    )
    assert errors == ["CAUSAL_GATE_CONTRADICTION"]
