"""Use the refined content-aligned renderer for SFT projection."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .answer_renderer_impl_001 import render_answer
from .research_content import select_task_content
from .sft_projector_impl_004 import _chain_for_sample
from .sft_projector_impl_001 import MAX_ASSISTANT_CHARS, project_sft_samples as _project_v1


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
    if sum(len(message.get("content") or "") for message in result["messages"]) > 2000:
        raise ValueError(f"answer exceeds message budget for {result.get('sample_id')}")
    return result


def project_sft_samples(unified_events: list[dict[str, Any]], enabled_tasks: list[str] | None = None) -> list[dict[str, Any]]:
    legacy_samples = _project_v1(unified_events, enabled_tasks)
    events = {event["event_id"]: event for event in unified_events}
    return [_augment_sample(sample, events[sample["event_id"]]) for sample in legacy_samples]


__all__ = ["MAX_ASSISTANT_CHARS", "project_sft_samples"]
