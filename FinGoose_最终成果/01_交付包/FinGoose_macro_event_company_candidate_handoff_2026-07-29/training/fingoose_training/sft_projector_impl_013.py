"""Final no-fragment SFT projector with legacy compatibility."""

from __future__ import annotations

from copy import deepcopy

from .answer_renderer_impl_007 import render_answer
from .research_content import select_task_content
from .sft_projector_impl_004 import _chain_for_sample
from .sft_projector_impl_001 import project_sft_samples as _project_v1
from .sft_projector_impl_003 import project_sft_samples as _project_legacy


def project_sft_samples(unified_events, enabled_tasks=None):
    if any(not isinstance(event.get("research_content"), dict) for event in unified_events):
        return _project_legacy(unified_events, enabled_tasks)
    events = {event["event_id"]: event for event in unified_events}
    result = []
    for sample in _project_v1(unified_events, enabled_tasks):
        sample = deepcopy(sample)
        event = events[sample["event_id"]]
        chain = _chain_for_sample(event, sample)
        metadata = sample.setdefault("metadata", {})
        if chain:
            metadata.update({
                "reasoning_chain_version": chain.get("reasoning_chain_version"),
                "evidence_registry": deepcopy(chain.get("evidence_registry", [])),
                "reasoning_chain": deepcopy(chain.get("reasoning_chain", {})),
                "conclusion_lineage": deepcopy(chain.get("conclusion_lineage", {})),
                "parent_chain_refs": deepcopy(chain.get("parent_chain_refs", [])),
            })
        metadata["research_content_version"] = "research-content-v1"
        content = select_task_content(event, sample)
        metadata["research_content"] = content
        if sample["task_type"] == "EVENT_ANALYSIS":
            metadata["related_industry_ids"] = sorted(
                str(row.get("event_industry_mapping_id"))
                for row in event.get("industries", [])
                if row.get("event_industry_mapping_id")
            )
            metadata["related_company_codes"] = sorted(
                str(row.get("company_code"))
                for row in event.get("companies", [])
                if row.get("company_code")
            )
        elif sample["task_type"] == "INDUSTRY_IMPACT":
            mapping_id = content.get("event_industry_mapping_id")
            metadata["related_industry_ids"] = [str(mapping_id)] if mapping_id else []
            metadata["related_company_codes"] = []
        elif sample["task_type"] == "COMPANY_IMPACT":
            company_code = content.get("company_code")
            metadata["related_industry_ids"] = []
            metadata["related_company_codes"] = [str(company_code)] if company_code else []
        elif sample["task_type"] == "EVENT_QA":
            industry_ids = {
                str(row.get("event_industry_mapping_id"))
                for row in content.get("industry_results") or []
                if isinstance(row, dict) and row.get("event_industry_mapping_id")
            }
            if not industry_ids:
                industry_ids = {
                    str(row.get("event_industry_mapping_id"))
                    for row in event.get("industries", [])
                    if row.get("event_industry_mapping_id")
                }
            metadata["related_industry_ids"] = sorted(industry_ids)
            metadata["related_company_codes"] = sorted({
                str(row.get("company_code"))
                for row in content.get("company_results") or []
                if isinstance(row, dict) and row.get("company_code")
            })
        content_evidence_ids = {
            str(value) for value in content.get("evidence_ids") or [] if value
        }
        content_evidence_ids.update(
            str(row.get("evidence_id"))
            for row in content.get("official_facts") or []
            if isinstance(row, dict) and row.get("evidence_id")
        )
        metadata["evidence_ids"] = sorted(
            set(str(value) for value in metadata.get("evidence_ids") or [])
            | content_evidence_ids
        )
        sample["messages"][2]["content"] = render_answer(sample["task_type"], event=event, sample=sample, chain=chain)
        if sum(len(message.get("content") or "") for message in sample["messages"]) > 2000:
            raise ValueError(f"answer exceeds message budget for {sample['sample_id']}")
        result.append(sample)
    return result


__all__ = ["project_sft_samples"]
