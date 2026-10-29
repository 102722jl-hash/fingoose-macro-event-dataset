"""Apply hidden-record filtering to event milestone inputs as well as graph nodes."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .reasoning_chain_impl_004 import (
    _is_hidden_node,
    compile_reasoning_chain as _compile_v4,
    render_chain_summary,
)


def compile_reasoning_chain(
    task_type: str,
    *,
    scope: Mapping[str, Any],
    evidence_registry: Sequence[Mapping[str, Any]],
    parent_chain_refs: Sequence[str] = (),
) -> dict[str, Any]:
    prepared = deepcopy(dict(scope))
    if isinstance(prepared.get("milestones"), list):
        prepared["milestones"] = [
            milestone
            for milestone in prepared["milestones"]
            if not (isinstance(milestone, Mapping) and _is_hidden_node(milestone))
        ]
    return _compile_v4(
        task_type,
        scope=prepared,
        evidence_registry=evidence_registry,
        parent_chain_refs=parent_chain_refs,
    )


__all__ = ["compile_reasoning_chain", "render_chain_summary"]
