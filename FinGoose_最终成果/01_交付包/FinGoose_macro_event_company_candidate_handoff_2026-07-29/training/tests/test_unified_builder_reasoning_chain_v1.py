from __future__ import annotations

from fingoose_training.unified_builder import build_unified_events

from test_unified_builder import complete_source


def source_with_complete_chains() -> dict:
    source = complete_source()
    source["event_milestones"][0].update(
        {
            "sources": [{"evidence_id": "event-source-1"}],
        }
    )
    source["macro_sources"] = [
        {
            "event_id": "event-01",
            "evidence_id": "event-source-1",
            "original_quote": "Event source quote.",
            "locator": "paragraph 1",
            "source_url": "https://example.com/event",
        }
    ]
    nodes = []
    for index in range(1, 8):
        node = {
            "node_id": f"industry-node-{index}",
            "node_type": "EVENT_FACT" if index == 1 else "RESEARCH_INFERENCE",
            "statement_class": "SOURCE_FACT" if index == 1 else "RESEARCH_INFERENCE",
            "statement_zh": f"行业步骤 {index}",
            "premise_node_ids": [f"industry-node-{index - 1}"] if index > 1 else [],
        }
        if index == 1:
            node["evidence_ids"] = ["ie-1"]
        nodes.append(node)
    source["industry_mechanism_chains"][0]["nodes"] = nodes
    source["industry_mechanism_chains"][0]["edges"] = [
        {"from_node_id": f"industry-node-{index}", "to_node_id": f"industry-node-{index + 1}"}
        for index in range(1, 7)
    ]
    source["industry_evidence"][0].update(
        {
            "original_quote": "Industry source quote.",
            "locator": "section 2",
            "source_url": "https://example.com/industry",
        }
    )
    source["company_mechanism_chains"][0]["nodes"] = [
        {
            "node_id": "company-exposure",
            "node_type": "COMPANY_BUSINESS_EXPOSURE",
            "statement_class": "SOURCE_FACT",
            "statement_zh": "公司业务暴露。",
            "evidence_ids": ["ce-1"],
        }
    ]
    source["company_evidence"][0].update(
        {
            "original_quote": "Company source quote.",
            "page_or_section_locator": "page=3",
            "source_url": "https://example.com/company",
        }
    )
    source["qa_answers"][0]["evidence"] = [source["industry_evidence"][0]]
    return source


def test_unified_builder_attaches_four_canonical_chain_types() -> None:
    event = build_unified_events(source_with_complete_chains(), "test-v1")[0]

    objects = [
        event["event"],
        event["industries"][0],
        event["companies"][0],
        event["qa"][0],
    ]
    for value in objects:
        chain = value["reasoning_chain"]
        assert chain["reasoning_chain_version"] == "v1"
        assert chain["reasoning_chain"]["nodes"]
        assert chain["conclusion_lineage"]["final_node_id"]

    assert len(event["industries"][0]["reasoning_chain"]["reasoning_chain"]["nodes"]) == 7
    assert event["companies"][0]["reasoning_chain"]["parent_chain_refs"] == ["ei-1"]
    assert event["qa"][0]["reasoning_chain"]["parent_chain_refs"] == ["event-01"]
