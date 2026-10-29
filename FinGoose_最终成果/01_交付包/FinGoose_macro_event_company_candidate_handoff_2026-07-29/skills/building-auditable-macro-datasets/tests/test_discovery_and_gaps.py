from macro_dataset_pipeline import deduplicate_candidates, scan_record_gaps


def test_discovery_candidates_are_deduplicated_by_anchor_and_official_url():
    rows = [
        {"title_zh": "事件 A", "anchor_at": "2026-01-01", "official_seed_urls": ["https://a.test/x"]},
        {"title_zh": "事件 A 重复", "anchor_at": "2026-01-01", "official_seed_urls": ["https://a.test/x"]},
    ]
    result = deduplicate_candidates(rows)
    assert len(result) == 1
    assert result[0]["candidate_event_id"].startswith("candidate-event-")


def test_gap_scan_emits_stable_codes_without_fabricating_values():
    gaps = scan_record_gaps({
        "event_id": "event-x",
        "evidence_registry": [{"evidence_id": "e1", "original_quote": "事实"}],
        "industries": [],
        "companies": [],
        "qa": [],
    })
    assert {row["gap_code"] for row in gaps} == {
        "EVIDENCE_LOCATOR_MISSING",
        "EVIDENCE_URL_MISSING",
        "SUPPORTED_INDUSTRIES_MISSING",
        "SUPPORTED_COMPANIES_MISSING",
        "EVENT_QA_MISSING",
    }
    assert all(row["event_id"] == "event-x" for row in gaps)
