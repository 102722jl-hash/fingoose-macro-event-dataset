from pathlib import Path
from functools import lru_cache

from fingoose_training.artifacts import resolve_project_root
from fingoose_training.loaders import (
    load_source_bundle,
    load_ui_reference_bundle,
    read_json,
)
from fingoose_training.research_content import build_event_research_content
from fingoose_training.sft_projector import project_sft_samples
from fingoose_training.ui_reference import load_ui_reference
from fingoose_training.unified_builder import build_unified_events


PROJECT = Path(__file__).resolve().parents[2]
UI_PATH = PROJECT / "work/company_impact_high_quality_v2_candidate/ui/ui_data_bundle.js"
CONFIG_PATH = PROJECT / "training/configs/dataset.json"


def _all_content():
    return [
        build_event_research_content(event)
        for event in load_ui_reference(UI_PATH)["events"]
    ]


@lru_cache(maxsize=1)
def _events():
    config = read_json(CONFIG_PATH)
    root = resolve_project_root(CONFIG_PATH, config)
    source, _ = load_source_bundle(root, config)
    ui_reference, _ = load_ui_reference_bundle(root, config)
    return build_unified_events(
        source, config["dataset_version"], ui_reference=ui_reference
    )


def test_all_industries_receive_fixed_market_windows():
    industries = [
        row for content in _all_content() for row in content["industry_impacts"]
    ]
    assert len(industries) == 77
    assert all(
        set((row["market_window"].get("fixed_windows") or {}))
        >= {"T0", "D1", "D3", "D5", "D20"}
        for row in industries
    )


def test_all_companies_receive_reproducible_or_explicitly_missing_windows():
    companies = [
        row for content in _all_content() for row in content["company_impacts"]
    ]
    assert len(companies) == 30
    for company in companies:
        assert set(company["relative_market_windows"]) == {
            "T0", "D1", "D3", "D5", "D20"
        }
        assert any(
            window["status"] in {"CALCULATED", "PARTIAL_CALCULATED"}
            for window in company["relative_market_windows"].values()
        )
        for window in company["relative_market_windows"].values():
            assert window["status"] in {
                "CALCULATED", "PARTIAL_CALCULATED", "DATA_MISSING"
            }
            assert window.get("formula_inputs") or window.get("missing_reason")


def test_current_companies_abstain_and_endpoint_reviews_do_not_verify_suspension():
    companies = [
        row for content in _all_content() for row in content["company_impacts"]
    ]
    assert all(
        company["market_window"]["suspension_alignment"] == "UNVERIFIED"
        for company in companies
    )
    assert all(
        company["causal_identification"]["status"] == "NOT_IDENTIFIED"
        for company in companies
    )
    assert all(
        company["causal_identification"]["causal_conclusion"] == "ABSTAIN"
        for company in companies
    )
    assert all(company["causal_attribution_allowed"] is False for company in companies)


def test_event_02_and_event_03_expose_explicit_milestone_evidence_aliases():
    by_event = {content["event_id"]: content for content in _all_content()}
    assert by_event["event-02"]["milestone_evidence_aliases"][
        "milestone-event-02-a15f1fe4410d"
    ] == ["official-kremlin-67843"]
    assert by_event["event-03"]["milestone_evidence_aliases"][
        "milestone-event-03-3c2b0dbb65d4"
    ] == ["supplemental-fast-event-03-M03"]


def test_child_event_fact_evidence_is_complete_after_inheritance():
    for event in _events():
        for scope in [*event["industries"], *event["companies"]]:
            chain = scope["reasoning_chain"]
            registry = {
                row["evidence_id"]: row for row in chain["evidence_registry"]
            }
            for node in chain["reasoning_chain"]["nodes"]:
                if node["node_type"] != "EVENT_FACT":
                    continue
                assert node["evidence_ids"]
                assert all(
                    evidence_id in registry
                    and registry[evidence_id]["missing"] is False
                    for evidence_id in node["evidence_ids"]
                )


def test_event_milestone_fact_evidence_is_complete_after_alias_binding():
    for event in _events():
        chain = event["event"]["reasoning_chain"]
        registry = {
            row["evidence_id"]: row for row in chain["evidence_registry"]
        }
        for node in chain["reasoning_chain"]["nodes"]:
            if node["node_type"] != "EVENT_FACT":
                continue
            assert node["evidence_ids"]
            assert all(
                evidence_id in registry
                and registry[evidence_id]["missing"] is False
                for evidence_id in node["evidence_ids"]
            )


def test_final_company_registries_preserve_source_document_lineage():
    records = [
        evidence
        for event in _events()
        for company in event["companies"]
        for evidence in company["reasoning_chain"]["evidence_registry"]
        if evidence.get("source_record_ids")
    ]

    assert records
    for record in records:
        source_record_ids = record["source_record_ids"]
        assert source_record_ids == sorted(set(source_record_ids))
        assert record["evidence_id"] not in source_record_ids


def test_known_94_open_chains_close_after_recompile():
    open_scopes = []
    for event in _events():
        for scope in [event["event"], *event["industries"], *event["companies"]]:
            graph = scope["reasoning_chain"]["reasoning_chain"]
            if graph["closure_gate"]["status"] == "OPEN":
                open_scopes.append((event["event_id"], graph["scope_id"], graph["closure_gate"]["blockers"]))
    assert open_scopes == []


def test_company_answer_separates_market_observation_from_causal_abstention():
    samples = project_sft_samples(_events())
    company = next(row for row in samples if row["task_type"] == "COMPANY_IMPACT")
    answer = company["messages"][2]["content"]

    assert "绝对收益" in answer
    assert "相对沪深300" in answer
    assert "相对行业" in answer
    assert "因果识别" in answer
    assert "ABSTAIN" in answer
    assert "不能把同期波动直接归因" in answer


def test_partial_company_answer_keeps_reproducible_absolute_return():
    samples = project_sft_samples(_events())
    company = next(
        row
        for row in samples
        if row["task_type"] == "COMPANY_IMPACT"
        and row["metadata"]["research_content"]["relative_market_windows"]["T0"][
            "status"
        ]
        == "PARTIAL_CALCULATED"
    )
    answer = company["messages"][2]["content"]

    assert "状态 PARTIAL_CALCULATED" in answer
    assert "绝对收益 缺失" not in answer
