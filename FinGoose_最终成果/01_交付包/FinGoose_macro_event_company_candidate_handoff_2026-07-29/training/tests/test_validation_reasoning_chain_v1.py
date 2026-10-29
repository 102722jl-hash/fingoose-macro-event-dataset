from __future__ import annotations

from copy import deepcopy

import pytest

from fingoose_training.reasoning_chain import compile_reasoning_chain
from fingoose_training.validation import validate_datasets

from test_reasoning_chain_v1 import EVIDENCE, industry_scope


def _sample() -> dict:
    chain = compile_reasoning_chain("INDUSTRY_IMPACT", scope=industry_scope(), evidence_registry=EVIDENCE)
    return {
        "sample_id": "sample-industry-1", "event_id": "event-01", "task_type": "INDUSTRY_IMPACT", "split": "train",
        "messages": [{"role": "system", "content": "规则"}, {"role": "user", "content": "问题"}, {"role": "assistant", "content": "答案"}],
        "metadata": {
            "related_industry_ids": ["industry-1"], "related_company_codes": [], "evidence_ids": ["ev-1", "ev-missing"], "source_record_ids": ["industry-1"],
            "reasoning_chain_version": chain["reasoning_chain_version"], "evidence_registry": chain["evidence_registry"], "reasoning_chain": chain["reasoning_chain"], "conclusion_lineage": chain["conclusion_lineage"],
        },
    }


def _unified() -> list[dict]:
    return [{"event_id": "event-01", "industries": [{"event_industry_mapping_id": "industry-1", "mapping": {"sw1_id": "801000"}}], "companies": [], "qa": []}]


def _codes(sample: dict) -> set[str]:
    report = validate_datasets(_unified(), [sample], expected_events={"event-01"})
    return {error["code"] for error in report["errors"]}


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda sample: sample["metadata"]["reasoning_chain"]["nodes"].append(deepcopy(sample["metadata"]["reasoning_chain"]["nodes"][0])), "REASONING_NODE_DUPLICATE"),
        (lambda sample: sample["metadata"]["reasoning_chain"]["edges"].append({"from_node_id": "node-1", "to_node_id": "missing"}), "REASONING_EDGE_UNKNOWN_NODE"),
        (lambda sample: sample["metadata"]["reasoning_chain"]["edges"].append({"from_node_id": "node-7", "to_node_id": "node-1"}), "REASONING_GRAPH_CYCLE"),
        (lambda sample: sample["metadata"]["reasoning_chain"].update({"edges": [edge for edge in sample["metadata"]["reasoning_chain"]["edges"] if edge["to_node_id"] != "node-7"]}), "REASONING_FINAL_UNREACHABLE"),
        (lambda sample: sample["metadata"]["evidence_registry"][0].update({"supports_node_ids": []}), "REASONING_EVIDENCE_LINK_MISMATCH"),
        (lambda sample: sample["metadata"]["reasoning_chain"].update({"nodes": sample["metadata"]["reasoning_chain"]["nodes"][:6]}), "REASONING_INDUSTRY_NODE_COUNT"),
    ],
)
def test_validation_rejects_reasoning_chain_failures(mutate, expected) -> None:
    sample = _sample()
    mutate(sample)
    assert expected in _codes(sample)


def test_validation_rejects_missing_reasoning_schema_version() -> None:
    sample = _sample()
    del sample["metadata"]["reasoning_chain_version"]
    assert "REASONING_SCHEMA_MISSING" in _codes(sample)
