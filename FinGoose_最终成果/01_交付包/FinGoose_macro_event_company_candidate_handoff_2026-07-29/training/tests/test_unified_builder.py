import pytest

from fingoose_training.unified_builder import BuildError, build_unified_events


def complete_source():
    return {
        "event_episodes": [
            {"event_id": "event-01", "episode_id": "ep-1", "phase": "SHOCK"}
        ],
        "event_milestones": [
            {"event_id": "event-01", "milestone_id": "m-1", "fact": "事件事实"}
        ],
        "transmission_graphs": [
            {"event_id": "event-01", "graph_id": "g-1", "nodes": [], "edges": []}
        ],
        "macro_market_windows": [
            {"event_id": "event-01", "market_window_id": "mw-1", "windows": {}}
        ],
        "macro_sources": [],
        "event_industry_mappings": [
            {
                "event_id": "event-01",
                "event_industry_mapping_id": "ei-1",
                "display_name_zh": "航空",
                "event_title_zh": "测试事件",
                "event_evidence_ids": ["ie-1"],
            }
        ],
        "industry_mechanism_chains": [
            {
                "event_id": "event-01",
                "event_industry_mapping_id": "ei-1",
                "nodes": [],
            }
        ],
        "industry_market_windows": [
            {
                "event_id": "event-01",
                "event_industry_mapping_id": "ei-1",
                "fixed_windows": {},
            }
        ],
        "industry_evidence": [{"evidence_id": "ie-1", "title": "行业证据"}],
        "event_company_map": [
            {
                "event_id": "event-01",
                "mapping_id": "ec-1",
                "company_code": "600009.SH",
                "industry_impact_id": "ei-1",
            }
        ],
        "company_mechanism_chains": [
            {
                "event_id": "event-01",
                "mapping_id": "ec-1",
                "company_code": "600009.SH",
                "nodes": [],
            }
        ],
        "direction_assessments": [
            {
                "event_id": "event-01",
                "mapping_id": "ec-1",
                "company_code": "600009.SH",
                "horizons": {},
            }
        ],
        "company_evidence": [
            {"evidence_id": "ce-1", "company_code": "600009.SH", "claim_id": "c-1"}
        ],
        "company_market_windows": [],
        "company_confounders": [],
        "company_counterevidence_reviews": [],
        "trading_status_reviews": [],
        "qa_cases": [
            {
                "event_id": "event-01",
                "case_id": "qa-1",
                "question_zh": "如何影响？",
                "event_title_zh": "测试事件",
            }
        ],
        "qa_answers": [
            {
                "event_id": "event-01",
                "case_id": "qa-1",
                "task_answer": {"direct_answer_zh": "影响说明"},
            }
        ],
        "qa_sources": [],
    }


def test_build_unified_event_nests_industry_company_and_qa():
    records = build_unified_events(
        complete_source(), dataset_version="fingoose-unified-sft-v1"
    )

    assert len(records) == 1
    assert records[0]["event"]["title_zh"] == "测试事件"
    assert records[0]["industries"][0]["event_industry_mapping_id"] == "ei-1"
    assert records[0]["companies"][0]["mapping_id"] == "ec-1"
    assert records[0]["qa"][0]["case_id"] == "qa-1"
    assert records[0]["companies"][0]["evidence"][0]["evidence_id"] == "ce-1"


def test_missing_qa_answer_is_rejected():
    source = complete_source()
    source["qa_answers"] = []

    with pytest.raises(BuildError, match="missing answer"):
        build_unified_events(source, dataset_version="test")


def test_conflicting_qa_event_ids_are_rejected():
    source = complete_source()
    source["qa_answers"][0]["event_id"] = "event-02"

    with pytest.raises(BuildError, match="event mismatch"):
        build_unified_events(source, dataset_version="test")


def test_unknown_company_mapping_detail_is_rejected():
    source = complete_source()
    source["company_mechanism_chains"][0]["mapping_id"] = "missing"

    with pytest.raises(BuildError, match="unknown mapping_id"):
        build_unified_events(source, dataset_version="test")
