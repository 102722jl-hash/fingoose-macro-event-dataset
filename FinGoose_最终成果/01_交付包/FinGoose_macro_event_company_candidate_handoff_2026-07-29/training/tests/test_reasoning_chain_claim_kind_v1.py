from __future__ import annotations

from fingoose_training.reasoning_chain import compile_reasoning_chain


def test_claim_kind_source_fact_without_quote_is_evidence_missing() -> None:
    chain = compile_reasoning_chain(
        "INDUSTRY_IMPACT",
        scope={
            "event_industry_mapping_id": "industry-claim-kind",
            "nodes": [
                {
                    "node_id": "source-node",
                    "node_type": "EVENT_FACT",
                    "claim_kind": "SOURCE_FACT",
                    "statement_zh": "来源事实。",
                    "evidence_ids": ["partial-source"],
                }
            ],
        },
        evidence_registry=[
            {
                "evidence_id": "partial-source",
                "locator": {"type": "html_text", "value": "定位"},
                "source_url": "https://example.com/source",
            }
        ],
    )

    assert chain["reasoning_chain"]["nodes"][0]["status"] == "EVIDENCE_MISSING"
    assert chain["reasoning_chain"]["closure_gate"]["status"] == "OPEN"
