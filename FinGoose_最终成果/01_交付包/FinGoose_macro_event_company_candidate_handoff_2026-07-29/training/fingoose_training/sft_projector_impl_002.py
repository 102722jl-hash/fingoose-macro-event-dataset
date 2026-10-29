"""Project legacy SFT messages and attach self-contained reasoning metadata."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .reasoning_chain import render_chain_summary
from .sft_projector_impl_001 import (
    MAX_ASSISTANT_CHARS,
    project_sft_samples as _project_v1,
)


def _chain_for_sample(event: dict[str, Any], sample: dict[str, Any]) -> dict[str, Any] | None:
    task_type = sample.get("task_type")
    if task_type == "EVENT_ANALYSIS":
        return (event.get("event") or {}).get("reasoning_chain")
    if task_type == "INDUSTRY_IMPACT":
        ids = sample.get("metadata", {}).get("related_industry_ids") or []
        for industry in event.get("industries", []):
            if industry.get("event_industry_mapping_id") in ids:
                return industry.get("reasoning_chain")
    if task_type == "COMPANY_IMPACT":
        codes = sample.get("metadata", {}).get("related_company_codes") or []
        for company in event.get("companies", []):
            if company.get("company_code") in codes:
                return company.get("reasoning_chain")
    if task_type == "EVENT_QA":
        suffix = f"-qa-"
        case_id = str(sample.get("sample_id", "")).split(suffix, 1)[-1]
        for qa in event.get("qa", []):
            if str(qa.get("case_id")) == case_id:
                return qa.get("reasoning_chain")
    return None


def _message_summary(chain: dict[str, Any]) -> str:
    lines = render_chain_summary(chain).splitlines()
    if len(lines) > 5:
        lines = lines[:4] + [lines[-1]]
    return "\n".join(lines)[:560]


def _augment_sample(sample: dict[str, Any], chain: dict[str, Any] | None) -> dict[str, Any]:
    if not chain:
        return sample
    result = deepcopy(sample)
    metadata = result.setdefault("metadata", {})
    metadata.update(
        {
            "reasoning_chain_version": chain.get("reasoning_chain_version"),
            "evidence_registry": deepcopy(chain.get("evidence_registry", [])),
            "reasoning_chain": deepcopy(chain.get("reasoning_chain", {})),
            "conclusion_lineage": deepcopy(chain.get("conclusion_lineage", {})),
            "parent_chain_refs": deepcopy(chain.get("parent_chain_refs", [])),
        }
    )
    lineage_ids = chain.get("conclusion_lineage", {}).get("evidence_ids", [])
    metadata["evidence_ids"] = sorted(set(metadata.get("evidence_ids", [])) | set(lineage_ids))
    assistant = result["messages"][2]["content"]
    summary = _message_summary(chain)
    base_budget = max(0, MAX_ASSISTANT_CHARS - len(summary) - 2)
    result["messages"][2]["content"] = (assistant[:base_budget].rstrip() + "\n" + summary).strip()
    return result


def project_sft_samples(
    unified_events: list[dict[str, Any]], enabled_tasks: list[str] | None = None
) -> list[dict[str, Any]]:
    legacy_samples = _project_v1(unified_events, enabled_tasks)
    events = {event["event_id"]: event for event in unified_events}
    return [
        _augment_sample(sample, _chain_for_sample(events[sample["event_id"]], sample))
        for sample in legacy_samples
    ]


__all__ = ["project_sft_samples"]
