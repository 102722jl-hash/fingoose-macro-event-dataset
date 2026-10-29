from __future__ import annotations

from collections import Counter
import json
from pathlib import Path


TRAINING_ROOT = Path(__file__).resolve().parents[1]


def _jsonl(name: str) -> list[dict]:
    return [
        json.loads(line)
        for line in (TRAINING_ROOT / "data" / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_real_dataset_keeps_task_distribution_and_self_contained_chains() -> None:
    samples = _jsonl("sft_dataset.jsonl")

    assert len(samples) == 157
    assert Counter(sample["task_type"] for sample in samples) == {
        "EVENT_ANALYSIS": 10,
        "INDUSTRY_IMPACT": 77,
        "COMPANY_IMPACT": 30,
        "EVENT_QA": 40,
    }
    for sample in samples:
        metadata = sample["metadata"]
        graph = metadata["reasoning_chain"]
        registry_ids = {row["evidence_id"] for row in metadata["evidence_registry"]}
        assert metadata["reasoning_chain_version"] == "v1"
        assert graph["nodes"]
        assert graph["final_node_id"] == metadata["conclusion_lineage"]["final_node_id"]
        assert set(metadata["conclusion_lineage"]["evidence_ids"]) <= registry_ids
        assert not any(
            node["status"] == "CUTOFF_BLOCKED"
            and node["node_id"] in graph["main_path_node_ids"]
            for node in graph["nodes"]
        )
        if sample["task_type"] == "INDUSTRY_IMPACT":
            assert len(graph["nodes"]) == 7
        if sample["task_type"] == "COMPANY_IMPACT":
            assert any(
                "COMPANY_BUSINESS_EXPOSURE" in node["node_type"]
                for node in graph["nodes"]
            )


def test_validation_report_exposes_public_reasoning_statistics() -> None:
    report = json.loads(
        (TRAINING_ROOT / "data" / "validation_report.json").read_text(encoding="utf-8")
    )
    stats = report["reasoning_chain_stats"]

    assert report["valid"] is True
    assert report["errors"] == []
    assert report["warnings"] == []
    assert stats["totals"]["chain_count"] == 157
    assert set(stats["by_task"]) == {
        "EVENT_ANALYSIS",
        "INDUSTRY_IMPACT",
        "COMPANY_IMPACT",
        "EVENT_QA",
    }


def test_real_dataset_closes_known_build_defects_and_keeps_causal_abstention():
    samples = _jsonl("sft_dataset.jsonl")
    non_qa = [row for row in samples if row["task_type"] != "EVENT_QA"]
    assert all(
        row["metadata"]["reasoning_chain"]["closure_gate"]["status"] == "CLOSED"
        for row in non_qa
    )

    industries = [row for row in samples if row["task_type"] == "INDUSTRY_IMPACT"]
    companies = [row for row in samples if row["task_type"] == "COMPANY_IMPACT"]
    assert len(industries) == 77
    assert len(companies) == 30
    assert all(
        (row["metadata"]["research_content"].get("market_window") or {}).get(
            "fixed_windows"
        )
        for row in industries
    )
    assert all(
        row["metadata"]["research_content"]["causal_identification"][
            "causal_conclusion"
        ]
        == "ABSTAIN"
        for row in companies
    )


def test_validation_report_exposes_market_and_causal_stats():
    report = json.loads(
        (TRAINING_ROOT / "data" / "validation_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["reasoning_chain_stats"]["totals"]["open_closure_count"] == 0
    assert report["market_completeness_stats"]["industry_total"] == 77
    assert report["market_completeness_stats"]["company_total"] == 30
    assert report["causal_identification_stats"]["IDENTIFIED"] == 0
    assert sum(report["causal_identification_stats"].values()) == 30
