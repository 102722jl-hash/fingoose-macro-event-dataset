from copy import deepcopy

from fingoose_training.sft_projector import project_sft_samples


def complete_event():
    return {
        "event_id": "event-01",
        "dataset_version": "test-v1",
        "event": {
            "title_zh": "测试事件",
            "episodes": [{"phase": "SHOCK"}],
            "milestones": [{"milestone_id": "m-1", "fact": "公开事件事实"}],
            "transmission_graphs": [{"nodes": [], "edges": []}],
            "market_windows": [{"series_id": "SP500", "windows": {"D1": {"change": -1}}}],
            "sources": [],
        },
        "industries": [
            {
                "event_industry_mapping_id": "ei-1",
                "mapping": {
                    "display_name_zh": "航空",
                    "behavior_change_zh": "出行需求下降",
                    "horizon_directions": {"immediate": "NEGATIVE"},
                    "counterevidence_zh": "国内出行恢复",
                    "invalidation_condition_zh": "客流快速恢复",
                },
                "mechanism_chain": {"nodes": [{"value_zh": "旅客量下降"}], "edges": []},
                "market_window": {"fixed_windows": {"EVENT": {"return": -0.1}}},
                "evidence": [{"evidence_id": "ie-1", "title": "行业证据"}],
            }
        ],
        "companies": [
            {
                "mapping_id": "ec-1",
                "company_code": "600009.SH",
                "company_name": "上海机场",
                "industry_impact_id": "ei-1",
                "mapping": {"company_name": "上海机场", "industry": "航空"},
                "mechanism_chain": {"nodes": [{"value_zh": "收入承压"}], "edges": []},
                "direction_assessment": {
                    "horizons": {"immediate": "NEGATIVE"},
                    "mechanism": "旅客量影响收入",
                    "hidden_label_eligible": True,
                },
                "market_windows": [],
                "confounders": [{"factor_zh": "合同变化"}],
                "counterevidence_reviews": [],
                "trading_status_reviews": [],
                "evidence": [{"evidence_id": "ce-1", "original_quote": "公司证据"}],
            }
        ],
        "qa": [
            {
                "case_id": "qa-1",
                "case": {
                    "question_zh": "事件如何影响航空和上海机场？",
                    "task_type": "INDUSTRY_COMPANY",
                    "prediction_cutoff_at": "2020-03-13T23:59:59+00:00",
                },
                "answer": {
                    "task_answer": {
                        "direct_answer_zh": "候选直接答案",
                        "official_facts": ["官方事实"],
                        "calculated_facts": ["计算事实"],
                        "research_inferences": ["研究推断"],
                        "refusal_boundaries": ["拒答边界"],
                    },
                    "horizon_reasoning_zh": {"immediate": "即时影响"},
                    "research_conclusion_zh": "研究结论",
                    "evidence": [{"evidence_id": "qe-1"}],
                },
                "source_fetches": [],
            }
        ],
        "lineage": {"source_record_ids": ["m-1", "ei-1", "ec-1", "qa-1"]},
    }


def test_projector_emits_four_task_types_for_one_complete_event():
    samples = project_sft_samples([complete_event()])

    assert {sample["task_type"] for sample in samples} == {
        "EVENT_ANALYSIS",
        "INDUSTRY_IMPACT",
        "COMPANY_IMPACT",
        "EVENT_QA",
    }
    for sample in samples:
        assert sample["event_id"] == "event-01"
        assert [message["role"] for message in sample["messages"]] == [
            "system",
            "user",
            "assistant",
        ]
        assert all(message["content"].strip() for message in sample["messages"])


def test_qa_answer_uses_candidate_direct_answer_not_hidden_labels():
    sample = next(
        row
        for row in project_sft_samples([complete_event()])
        if row["task_type"] == "EVENT_QA"
    )

    assert "候选直接答案" in sample["messages"][2]["content"]
    assert "hidden" not in str(sample).lower()


def test_projection_is_deterministic_and_does_not_mutate_source():
    event = complete_event()
    original = deepcopy(event)

    first = project_sft_samples([event])
    second = project_sft_samples([event])

    assert first == second
    assert event == original
    assert len({sample["sample_id"] for sample in first}) == len(first)
