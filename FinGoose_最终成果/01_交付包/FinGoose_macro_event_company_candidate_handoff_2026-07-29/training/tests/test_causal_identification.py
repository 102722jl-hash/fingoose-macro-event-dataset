from fingoose_training.causal_identification import (
    IDENTIFIED_GATES,
    classify_causal_identification,
)


DESCRIPTIVE_GATES = {
    "market_windows_complete": True,
    "market_benchmark_complete": True,
    "industry_benchmark_complete": True,
    "continuous_trading_verified": True,
}


def test_incomplete_market_is_not_identified_and_abstains():
    result = classify_causal_identification({})
    assert result["status"] == "NOT_IDENTIFIED"
    assert result["causal_attribution_allowed"] is False
    assert result["causal_conclusion"] == "ABSTAIN"
    assert set(result["unmet_conditions"]) == set(IDENTIFIED_GATES)


def test_complete_descriptive_event_study_still_abstains():
    result = classify_causal_identification(DESCRIPTIVE_GATES)
    assert result["status"] == "DESCRIPTIVE_EVENT_STUDY"
    assert result["causal_conclusion"] == "ABSTAIN"
    assert result["causal_attribution_allowed"] is False


def test_quasi_candidate_still_abstains():
    result = classify_causal_identification({
        **DESCRIPTIVE_GATES,
        "comparison_group_defined": True,
        "pretrend_passed": True,
        "confounders_controlled": True,
    })
    assert result["status"] == "QUASI_EXPERIMENTAL_CANDIDATE"
    assert result["causal_attribution_allowed"] is False
    assert result["causal_conclusion"] == "ABSTAIN"


def test_only_all_identification_gates_allow_attribution():
    result = classify_causal_identification({gate: True for gate in IDENTIFIED_GATES})
    assert result["status"] == "IDENTIFIED"
    assert result["causal_attribution_allowed"] is True
    assert result["causal_conclusion"] == "IDENTIFIED_EFFECT"
    assert result["unmet_conditions"] == []


def test_unknown_or_truthy_non_boolean_gate_does_not_pass():
    gates = {gate: True for gate in IDENTIFIED_GATES}
    gates["robustness_passed"] = "yes"
    result = classify_causal_identification(gates)
    assert result["status"] == "QUASI_EXPERIMENTAL_CANDIDATE"
    assert result["causal_conclusion"] == "ABSTAIN"


def test_confounders_counterevidence_and_method_are_preserved_without_mutation():
    confounders = ["同期市场冲击"]
    counterevidence = ["公司独立公告"]
    result = classify_causal_identification(
        DESCRIPTIVE_GATES,
        method="DESCRIPTIVE_EVENT_STUDY",
        confounders=confounders,
        counterevidence=counterevidence,
    )
    assert result["method"] == "DESCRIPTIVE_EVENT_STUDY"
    assert result["confounders"] == confounders
    assert result["counterevidence"] == counterevidence
    assert "拒绝归因" in result["boundary_zh"]
