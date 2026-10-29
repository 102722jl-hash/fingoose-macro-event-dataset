from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


HORIZON_KEYS = ("IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM")


def test_research_horizons_use_distinct_time_specific_reasoning() -> None:
    from fingoose_qa_reasoning_v2 import build_qa_records

    answers = {
        (row["event_id"], row["task_type"]): row
        for row in build_qa_records(ROOT).answers
    }
    required_markers = {
        "IMMEDIATE": ("首轮", "预期", "T0", "D1"),
        "SHORT_TERM": ("经营", "兑现", "D3", "D5"),
        "MEDIUM_TERM": ("持续", "结构", "D20"),
    }
    for event_index in range(1, 11):
        answer = answers[(f"event-{event_index:02d}", "MAIN_REASONING")]
        reasoning = answer["horizon_reasoning_zh"]
        assert set(reasoning) == set(HORIZON_KEYS)
        texts = []
        observation_sets = []
        for horizon, markers in required_markers.items():
            row = reasoning[horizon]
            text = row["reasoning_zh"]
            assert all(marker in text for marker in markers)
            assert row["observation_focus_zh"]
            assert row["window_keys"]
            texts.append(text)
            observation_sets.append(tuple(row["observation_focus_zh"]))
        assert len(set(texts)) == 3
        assert len(set(observation_sets)) == 3


def test_horizon_reasoning_is_rendered_as_three_distinct_sections() -> None:
    from fingoose_company_impact_qa_ui_v2 import build_ui_bundle, render_workbench

    html = render_workbench(
        build_ui_bundle(
            ROOT,
            qa_root=ROOT / "work/qa_reasoning_pilot_v2_candidate",
        )
    )
    assert "qaHorizonReasoningHtml" in html
    for label in ("首轮预期与交易反应", "经营兑现与反馈", "持续性与结构变化"):
        assert label in html
