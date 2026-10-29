from __future__ import annotations

import json

from fingoose_training.reasoning_chain import compile_reasoning_chain
from fingoose_training.sft_projector import project_sft_samples

from test_reasoning_chain_v1 import EVIDENCE, industry_scope


def _simple_scope(task_type: str, scope_id: str) -> dict:
    node_type = {"EVENT_ANALYSIS": "EVENT_FACT", "COMPANY_IMPACT": "COMPANY_BUSINESS_EXPOSURE", "EVENT_QA": "QA_SOURCE_FACT"}[task_type]
    return {
        "event_id": "event-01",
        "scope_id": scope_id,
        "prediction_cutoff_at": "2020-03-12T23:59:59+00:00",
        "nodes": [
            {"node_id": f"{scope_id}-source", "node_type": node_type, "statement_class": "SOURCE_FACT", "statement_zh": "可核对事实。", "evidence_ids": ["ev-1"]},
            {"node_id": f"{scope_id}-conclusion", "node_type": "DIRECTION_ASSESSMENT", "statement_class": "RESEARCH_INFERENCE", "statement_zh": "候选结论。", "premise_node_ids": [f"{scope_id}-source"]},
        ],
        "edges": [{"from_node_id": f"{scope_id}-source", "to_node_id": f"{scope_id}-conclusion"}],
    }


def complete_event_with_chains() -> dict:
    event_chain = compile_reasoning_chain("EVENT_ANALYSIS", scope=_simple_scope("EVENT_ANALYSIS", "event-chain"), evidence_registry=EVIDENCE)
    industry_chain = compile_reasoning_chain("INDUSTRY_IMPACT", scope=industry_scope(), evidence_registry=EVIDENCE)
    company_chain = compile_reasoning_chain("COMPANY_IMPACT", scope=_simple_scope("COMPANY_IMPACT", "company-chain"), evidence_registry=EVIDENCE, parent_chain_refs=["industry-1"])
    qa_chain = compile_reasoning_chain("EVENT_QA", scope=_simple_scope("EVENT_QA", "qa-chain"), evidence_registry=EVIDENCE, parent_chain_refs=["event-01"])
    return {
        "event_id": "event-01",
        "event": {"title_zh": "测试事件", "milestones": [], "episodes": [], "market_windows": [], "transmission_graphs": [], "reasoning_chain": event_chain},
        "industries": [{"event_industry_mapping_id": "industry-1", "mapping": {"display_name_zh": "测试行业", "sw1_id": "801000", "horizon_directions": {}}, "mechanism_chain": industry_scope()["mechanism_chain"], "market_window": {}, "evidence": EVIDENCE, "reasoning_chain": industry_chain}],
        "companies": [{"mapping_id": "company-1", "company_code": "600000.SH", "company_name": "测试公司", "mapping": {"industry_classification": {"sw1_id": "801000"}}, "mechanism_chain": {}, "direction_assessment": {}, "market_windows": [], "confounders": [], "counterevidence_reviews": [], "evidence": EVIDENCE, "reasoning_chain": company_chain}],
        "qa": [{"case_id": "qa-1", "case": {"question_zh": "发生了什么？", "task_type": "EVIDENCE_AUDIT"}, "answer": {"task_answer": {"direct_answer_zh": "候选回答"}}, "source_fetches": [], "reasoning_chain": qa_chain}],
        "lineage": {"source_record_ids": ["event-01"]},
    }


def test_four_task_samples_copy_self_contained_reasoning_metadata() -> None:
    samples = project_sft_samples([complete_event_with_chains()])
    assert len(samples) == 4
    for sample in samples:
        metadata = sample["metadata"]
        assert metadata["reasoning_chain_version"] == "v1"
        assert metadata["evidence_registry"]
        assert metadata["reasoning_chain"]["nodes"]
        assert metadata["conclusion_lineage"]["final_node_id"]
        json.dumps(metadata, ensure_ascii=False)


def test_assistant_messages_keep_auditable_summary_within_budget() -> None:
    samples = project_sft_samples([complete_event_with_chains()])
    for sample in samples:
        assistant = sample["messages"][2]["content"]
        assert "证据 ID" in assistant
        assert "ev-1" in assistant
        assert "证据边界" in assistant
        assert "Official event fact." not in assistant
        assert sum(len(message["content"]) for message in sample["messages"]) <= 2000
