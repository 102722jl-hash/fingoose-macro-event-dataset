"""Budget-aware reasoning summaries for the final SFT projection."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .reasoning_chain import render_chain_summary
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


def _message_summary(chain: dict[str, Any]) -> str:
    lines = render_chain_summary(chain).splitlines()
    if len(lines) > 5:
        lines = lines[:4] + [lines[-1]]
    return "\n".join(lines)[:520]


def _augment_sample(sample: dict[str, Any], chain: dict[str, Any] | None) -> dict[str, Any]:
    if not chain:
        return sample
    result = deepcopy(sample)
    metadata = result.setdefault("metadata", {})
    metadata.update({
        "reasoning_chain_version": chain.get("reasoning_chain_version"),
        "evidence_registry": deepcopy(chain.get("evidence_registry", [])),
        "reasoning_chain": deepcopy(chain.get("reasoning_chain", {})),
        "conclusion_lineage": deepcopy(chain.get("conclusion_lineage", {})),
        "parent_chain_refs": deepcopy(chain.get("parent_chain_refs", [])),
    })
    lineage_ids = chain.get("conclusion_lineage", {}).get("evidence_ids", [])
    metadata["evidence_ids"] = sorted(set(metadata.get("evidence_ids", [])) | set(lineage_ids))
    messages = result["messages"]
    summary = _message_summary(chain)
    total_other = len(messages[0]["content"]) + len(messages[1]["content"])
    assistant_budget = min(MAX_ASSISTANT_CHARS, max(1, 2000 - total_other))
    if len(summary) >= assistant_budget:
        summary = summary[:assistant_budget]
        base_budget = 0
    else:
        base_budget = assistant_budget - len(summary) - 1
    messages[2]["content"] = (messages[2]["content"][:base_budget].rstrip() + "\n" + summary).strip()
    return result


def project_sft_samples(unified_events: list[dict[str, Any]], enabled_tasks: list[str] | None = None) -> list[dict[str, Any]]:
    legacy_samples = _project_v1(unified_events, enabled_tasks)
    events = {event["event_id"]: event for event in unified_events}
    return [_augment_sample(sample, _chain_for_sample(events[sample["event_id"]], sample)) for sample in legacy_samples]


__all__ = ["project_sft_samples"]
