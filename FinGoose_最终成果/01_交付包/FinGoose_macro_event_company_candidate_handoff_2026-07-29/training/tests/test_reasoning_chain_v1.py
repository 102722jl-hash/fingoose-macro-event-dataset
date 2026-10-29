from __future__ import annotations

from copy import deepcopy

from fingoose_training.reasoning_chain import (
    compile_reasoning_chain,
    render_chain_summary,
    validate_chain_graph,
)


def industry_scope() -> dict:
    nodes = [
        {"node_id": "node-1", "node_type": "EVENT_FACT", "statement_class": "SOURCE_FACT", "statement_zh": "事件事实已经公开。", "evidence_ids": ["ev-1"]},
        {"node_id": "node-2", "node_type": "BEHAVIOR_OR_POLICY_CHANGE", "statement_class": "SOURCE_FACT", "statement_zh": "政策行为发生变化。", "evidence_ids": ["ev-missing"], "missing_evidence_ids": ["ev-missing"]},
        {"node_id": "node-3", "node_type": "OBSERVABLE_DRIVER", "statement_class": "RESEARCH_INFERENCE", "statement_zh": "可观察驱动变量变化。", "premise_node_ids": ["node-1"]},
        {"node_id": "node-4", "node_type": "INDUSTRY_OPERATING_VARIABLE", "statement_class": "RESEARCH_INFERENCE", "statement_zh": "行业经营变量变化。", "premise_node_ids": ["node-3"]},
        {"node_id": "node-5", "node_type": "INDUSTRY_REVENUE_OR_COST_VARIABLE", "statement_class": "RESEARCH_INFERENCE", "statement_zh": "行业收入或成本变化。", "premise_node_ids": ["node-2", "node-4"]},
        {"node_id": "node-6", "node_type": "DIRECTION_ASSESSMENT", "statement_class": "RESEARCH_INFERENCE", "statement_zh": "行业方向为候选判断。", "premise_node_ids": ["node-5"]},
        {"node_id": "node-7", "node_type": "PRICE_CONFOUNDER_AND_COUNTEREVIDENCE", "statement_class": "CALCULATED_FACT", "statement_zh": "行情只用于验证。", "premise_node_ids": ["node-6"]},
    ]
    return {
        "event_id": "event-01",
        "event_industry_mapping_id": "industry-1",
        "prediction_cutoff_at": "2020-03-12T23:59:59+00:00",
        "mechanism_chain": {
            "nodes": nodes,
            "edges": [{"from_node_id": f"node-{i}", "to_node_id": f"node-{i + 1}"} for i in range(1, 7)],
            "horizon_directions": {"IMMEDIATE": "NEGATIVE", "SHORT_TERM": "NEGATIVE", "MEDIUM_TERM": "MIXED"},
        },
    }


EVIDENCE = [{"evidence_id": "ev-1", "original_quote": "Official event fact.", "locator": "paragraph 3", "source_url": "https://example.com/event", "snapshot_sha256": "a" * 64, "published_at": "2020-03-11T12:00:00+00:00"}]


def test_industry_chain_has_seven_nodes_and_bidirectional_evidence() -> None:
    chain = compile_reasoning_chain("INDUSTRY_IMPACT", scope=industry_scope(), evidence_registry=EVIDENCE)
    graph = chain["reasoning_chain"]
    assert chain["reasoning_chain_version"] == "v1"
    assert len(graph["nodes"]) == 7
    assert graph["nodes"][0]["status"] == "VERIFIED_SOURCE"
    assert graph["nodes"][1]["status"] == "EVIDENCE_MISSING"
    node_ids = {node["node_id"] for node in graph["nodes"]}
    for evidence in chain["evidence_registry"]:
        for node_id in evidence["supports_node_ids"]:
            assert node_id in node_ids
            node = next(row for row in graph["nodes"] if row["node_id"] == node_id)
            assert evidence["evidence_id"] in node["evidence_ids"]


def test_missing_premise_blocks_supported_inference() -> None:
    chain = compile_reasoning_chain("INDUSTRY_IMPACT", scope=industry_scope(), evidence_registry=EVIDENCE)
    status_by_id = {node["node_id"]: node["status"] for node in chain["reasoning_chain"]["nodes"]}
    assert status_by_id["node-2"] == "EVIDENCE_MISSING"
    assert status_by_id["node-5"] == "INFERENCE_ONLY"
    assert status_by_id["node-6"] == "INFERENCE_ONLY"
    assert status_by_id["node-7"] == "CALCULATED_ONLY"


def test_post_cutoff_source_node_is_blocked() -> None:
    scope = industry_scope()
    scope["mechanism_chain"]["nodes"][0]["published_at"] = "2020-03-13T00:00:00+00:00"
    chain = compile_reasoning_chain("INDUSTRY_IMPACT", scope=scope, evidence_registry=EVIDENCE)
    assert chain["reasoning_chain"]["nodes"][0]["status"] == "CUTOFF_BLOCKED"
    assert "node-1" not in chain["reasoning_chain"]["main_path_node_ids"]


def test_graph_validation_returns_stable_codes() -> None:
    graph = compile_reasoning_chain("INDUSTRY_IMPACT", scope=industry_scope(), evidence_registry=EVIDENCE)["reasoning_chain"]
    duplicate = deepcopy(graph)
    duplicate["nodes"].append(deepcopy(duplicate["nodes"][0]))
    assert "REASONING_NODE_DUPLICATE" in validate_chain_graph(duplicate)
    unknown = deepcopy(graph)
    unknown["edges"].append({"from_node_id": "node-1", "to_node_id": "missing"})
    assert "REASONING_EDGE_UNKNOWN_NODE" in validate_chain_graph(unknown)
    cyclic = deepcopy(graph)
    cyclic["edges"].append({"from_node_id": "node-7", "to_node_id": "node-1"})
    assert "REASONING_GRAPH_CYCLE" in validate_chain_graph(cyclic)
    unreachable = deepcopy(graph)
    unreachable["edges"] = [edge for edge in unreachable["edges"] if edge["to_node_id"] != "node-7"]
    assert "REASONING_FINAL_UNREACHABLE" in validate_chain_graph(unreachable)


def test_summary_keeps_evidence_ids_and_boundary_without_full_quote() -> None:
    chain = compile_reasoning_chain("INDUSTRY_IMPACT", scope=industry_scope(), evidence_registry=EVIDENCE)
    summary = render_chain_summary(chain)
    assert "证据 ID" in summary
    assert "ev-1" in summary
    assert "证据边界" in summary
    assert "Official event fact." not in summary
