"""Final projector with clean QA horizon prose."""

from __future__ import annotations

from copy import deepcopy

from .answer_renderer_impl_004 import render_answer
from .research_content import select_task_content
from .sft_projector_impl_004 import _chain_for_sample
from .sft_projector_impl_001 import project_sft_samples as _project_v1


def project_sft_samples(unified_events, enabled_tasks=None):
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
        metadata["research_content"] = select_task_content(event, sample)
        sample["messages"][2]["content"] = render_answer(sample["task_type"], event=event, sample=sample, chain=chain)
        if sum(len(message.get("content") or "") for message in sample["messages"]) > 2000:
            raise ValueError(f"answer exceeds message budget for {sample['sample_id']}")
        result.append(sample)
    return result


__all__ = ["project_sft_samples"]
