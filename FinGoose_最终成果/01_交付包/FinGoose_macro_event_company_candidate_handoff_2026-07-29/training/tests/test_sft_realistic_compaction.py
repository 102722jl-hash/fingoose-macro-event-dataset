from test_sft_projector import complete_event

from fingoose_training.sft_projector import project_sft_samples


def test_verbose_source_records_are_compacted_before_the_hard_limit():
    event = complete_event()
    evidence = [
        {
            "evidence_id": f"e-{index}",
            "title": f"证据{index}",
            "publisher": "官方来源",
            "published_at": "2020-03-11",
            "original_quote": "原始证据长段落" * 200,
            "snapshot_sha256": "a" * 64,
            "source_url": "https://example.com/evidence",
        }
        for index in range(20)
    ]
    event["companies"][0]["evidence"] = evidence
    event["qa"][0]["answer"]["evidence"] = evidence

    samples = project_sft_samples([event])
    company = next(row for row in samples if row["task_type"] == "COMPANY_IMPACT")
    qa = next(row for row in samples if row["task_type"] == "EVENT_QA")

    assert "[内容已按训练长度上限截断]" not in company["messages"][1]["content"]
    assert "[内容已按训练长度上限截断]" not in qa["messages"][1]["content"]
    assert "e-0" in company["messages"][1]["content"]
    assert "e-19" not in company["messages"][1]["content"]
