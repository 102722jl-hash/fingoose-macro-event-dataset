from test_sft_projector import complete_event

from fingoose_training.sft_projector import project_sft_samples


def test_projected_messages_fit_the_2048_token_character_budget():
    event = complete_event()
    event["qa"][0]["answer"]["evidence"] = [
        {"evidence_id": "qe-1", "original_quote": "很长的证据" * 5000}
    ]
    event["qa"][0]["answer"]["task_answer"]["direct_answer_zh"] = (
        "很长的直接答案" * 3000
    )

    samples = project_sft_samples([event])

    assert all(
        sum(len(message["content"]) for message in sample["messages"]) <= 2000
        for sample in samples
    )
    qa_sample = next(sample for sample in samples if sample["task_type"] == "EVENT_QA")
    assert "问题：事件如何影响航空和上海机场？" in qa_sample["messages"][1]["content"]
