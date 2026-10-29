from test_sft_projector import complete_event

from fingoose_training.sft_projector import project_sft_samples


def test_company_sample_links_to_unified_industry_mapping_by_sw1_id():
    event = complete_event()
    event["industries"][0]["mapping"]["sw1_id"] = "801170"
    event["companies"][0]["industry_impact_id"] = "legacy-anchor-industry-id"
    event["companies"][0]["mapping"]["industry_classification"] = {
        "sw1_id": "801170",
        "sw1_name": "交通运输",
    }

    sample = next(
        row
        for row in project_sft_samples([event])
        if row["task_type"] == "COMPANY_IMPACT"
    )

    assert sample["metadata"]["related_industry_ids"] == ["ei-1"]
    assert sample["metadata"]["legacy_industry_impact_id"] == "legacy-anchor-industry-id"
