from __future__ import annotations

from fingoose_training.reasoning_chain import compile_reasoning_chain


def test_empty_industry_chain_compiles_seven_explicit_gap_nodes() -> None:
    chain = compile_reasoning_chain(
        "INDUSTRY_IMPACT",
        scope={"event_industry_mapping_id": "industry-empty", "mechanism_chain": {"nodes": [], "edges": []}},
        evidence_registry=[],
    )
    nodes = chain["reasoning_chain"]["nodes"]

    assert len(nodes) == 7
    assert nodes[0]["status"] == "EVIDENCE_MISSING"
    assert nodes[-1]["status"] == "CALCULATED_ONLY"
    assert chain["reasoning_chain"]["closure_gate"]["status"] == "OPEN"


def test_empty_company_chain_keeps_business_exposure_gap_node() -> None:
    chain = compile_reasoning_chain(
        "COMPANY_IMPACT",
        scope={"mapping_id": "company-empty", "mechanism_chain": {"nodes": [], "edges": []}},
        evidence_registry=[],
    )

    assert any(
        node["node_type"] == "COMPANY_BUSINESS_EXPOSURE"
        for node in chain["reasoning_chain"]["nodes"]
    )
