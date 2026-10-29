from __future__ import annotations

from fingoose_training.reasoning_chain import compile_reasoning_chain


def test_hidden_validation_nodes_and_edges_are_not_compiled() -> None:
    scope = {
        "event_id": "event-03",
        "nodes": [
            {
                "node_id": "public-node",
                "node_type": "EVENT_FACT",
                "statement_class": "RESEARCH_INFERENCE",
                "statement_zh": "公开研究节点。",
            },
            {
                "node_id": "hidden-node",
                "node_type": "VALIDATION",
                "statement_class": "RESEARCH_INFERENCE",
                "statement_zh": "隐藏验证节点。",
                "visibility": "HIDDEN_VALIDATION",
            },
        ],
        "edges": [
            {"from_node_id": "public-node", "to_node_id": "hidden-node"}
        ],
    }

    chain = compile_reasoning_chain(
        "EVENT_ANALYSIS", scope=scope, evidence_registry=[]
    )
    graph = chain["reasoning_chain"]

    assert [node["node_id"] for node in graph["nodes"]] == ["public-node"]
    assert graph["edges"] == []
    assert "hidden" not in str(chain).lower()
