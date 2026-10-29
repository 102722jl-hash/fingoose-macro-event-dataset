from __future__ import annotations

from fingoose_training.reasoning_chain import compile_reasoning_chain


def test_hidden_event_milestone_is_not_compiled() -> None:
    chain = compile_reasoning_chain(
        "EVENT_ANALYSIS",
        scope={
            "event_id": "event-03",
            "milestones": [
                {"milestone_id": "public", "fact": "公开事实", "visibility": "PUBLIC_PREDICTION"},
                {"milestone_id": "hidden", "fact": "隐藏验证事实", "visibility": "HIDDEN_VALIDATION"},
            ],
        },
        evidence_registry=[],
    )

    assert [node["node_id"] for node in chain["reasoning_chain"]["nodes"]] == ["public"]
    assert "hidden" not in str(chain).lower()
