"""Project unified records with content-aligned Chinese assistant answers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .answer_renderer import render_answer
from .research_content import select_task_content
from .sft_projector_impl_001 import MAX_ASSISTANT_CHARS, project_sft_samples as _project_v1


def _chain_for_sample(event: dict[str, Any], sample: dict[str, Any]) -> dict[str, Any] | None:
    task_type = sample.get("task_type")
    if task_type == "EVENT_ANALYSIS":
        return (event.get("event") or {}).get("reasoning_chain")
    if task_type == "INDUSTRY_IMPACT":
        ids = sample.get("metadata", {}).get("related_industry_ids") or []
        return next((row.get("reasoning_chain") for row in event.get("industries", []) if row.get("event_industry_mapping_id") in ids), None)
    if task_type == "COMPANY_IMPACT":
        codes = sample.get("metadata", {}).get("related_company_codes") or []
        return next((row.get("reasoning_chain") for row in event.get("companies", []) if row.get("company_code") in codes), None)
    if task_type == "EVENT_QA":
        case_id = str(sample.get("sample_id", "")).split("-qa-", 1)[-1]
        return next((row.get("reasoning_chain") for row in event.get("qa", []) if str(row.get("case_id")) == case_id), None)
    return None


def _augment_sample(sample: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(sample)
    chain = _chain_for_sample(event, result)
    metadata = result.setdefault("metadata", {})
    if chain:
        metadata.update({
            "reasoning_chain_version": chain.get("reasoning_chain_version"),
            "evidence_registry": deepcopy(chain.get("evidence_registry", [])),
            "reasoning_chain": deepcopy(chain.get("reasoning_chain", {})),
            "conclusion_lineage": deepcopy(chain.get("conclusion_lineage", {})),
            "parent_chain_refs": deepcopy(chain.get("parent_chain_refs", [])),
        })
    metadata["research_content_version"] = "research-content-v1"
    metadata["research_content"] = select_task_content(event, result)
    result["messages"][2]["content"] = render_answer(result["task_type"], event=event, sample=result, chain=chain)
    # Keep the existing loader's strict hard ceiling without slicing a section mid-text.
    system_and_user = sum(len(message.get("content") or "") for message in result["messages"][:2])
    if system_and_user + len(result["messages"][2]["content"]) > 2000:
        raise ValueError(f"answer exceeds message budget for {result.get('sample_id')}")
    return result


def project_sft_samples(unified_events: list[dict[str, Any]], enabled_tasks: list[str] | None = None) -> list[dict[str, Any]]:
    legacy_samples = _project_v1(unified_events, enabled_tasks)
    events = {event["event_id"]: event for event in unified_events}
    return [_augment_sample(sample, events[sample["event_id"]]) for sample in legacy_samples]


__all__ = ["MAX_ASSISTANT_CHARS", "project_sft_samples"]
