import json
from pathlib import Path

from fingoose_training.sft_projector_impl_004 import project_sft_samples


def _event_01_sample():
    path = Path(__file__).resolve().parents[1] / "data" / "sft_dataset.jsonl"
    return next(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if json.loads(line).get("sample_id") == "event-01-event-analysis")


def test_event_01_answer_is_concrete_chinese_research_answer():
    sample = _event_01_sample()
    answer = sample["messages"][2]["content"]
    for heading in ("结论", "来源事实", "即时影响", "短期影响", "中期影响", "行情验证", "证据边界"):
        assert heading in answer
    for forbidden in ("待补充陈述", '"nodes": [{}, {}', "[嵌套内容省略]", "omitted_count"):
        assert forbidden not in answer
    assert "event01-who-pandemic" in answer
    assert "待人工审核" in answer or "NEEDS_HUMAN_REVIEW" in answer
