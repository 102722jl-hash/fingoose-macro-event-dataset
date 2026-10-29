from __future__ import annotations

from fingoose_training.reasoning_chain import compile_reasoning_chain


def test_company_source_node_types_fall_back_to_source_fact_semantics() -> None:
    chain = compile_reasoning_chain(
        "COMPANY_IMPACT",
        scope={
            "mapping_id": "company-source-fallback",
            "nodes": [
                {
                    "node_id": "event-fact",
                    "node_type": "EVENT_FACT",
                    "statement_zh": "事件事实。",
                    "evidence_ids": ["event-missing"],
                },
                {
                    "node_id": "business-exposure",
                    "node_type": "COMPANY_BUSINESS_EXPOSURE",
                    "statement_zh": "公司业务暴露。",
                    "evidence_ids": ["company-source"],
                    "premise_node_ids": ["event-fact"],
                },
            ],
        },
        evidence_registry=[
            {
                "evidence_id": "company-source",
                "original_quote": "Company business disclosure.",
                "locator": "page=3",
                "source_url": "https://example.com/company",
            }
        ],
    )
    status = {
        node["node_id"]: node["status"]
        for node in chain["reasoning_chain"]["nodes"]
    }

    assert status["event-fact"] == "EVIDENCE_MISSING"
    assert status["business-exposure"] == "VERIFIED_SOURCE"
    assert chain["reasoning_chain"]["closure_gate"]["status"] == "OPEN"
