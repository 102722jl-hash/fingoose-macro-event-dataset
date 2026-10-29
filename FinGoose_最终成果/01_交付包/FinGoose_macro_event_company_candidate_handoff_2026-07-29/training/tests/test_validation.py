from copy import deepcopy

import pytest

from fingoose_training.validation import validate_datasets


def valid_unified():
    return [
        {
            "event_id": "event-01",
            "industries": [{"event_industry_mapping_id": "ei-1", "mapping": {"sw1_id": "801170"}}],
            "companies": [
                {
                    "mapping_id": "ec-1",
                    "company_code": "600000.SH",
                    "mapping": {"industry_classification": {"sw1_id": "801170"}},
                }
            ],
            "qa": [{"case_id": "qa-1", "answer": {"task_answer": {"direct_answer_zh": "答案"}}}],
            "lineage": {"source_record_ids": ["ei-1", "ec-1", "qa-1"]},
        }
    ]


def valid_samples():
    messages = [
        {"role": "system", "content": "规则"},
        {"role": "user", "content": "问题"},
        {"role": "assistant", "content": "答案"},
    ]
    return [
        {
            "sample_id": "sample-1",
            "event_id": "event-01",
            "task_type": "EVENT_ANALYSIS",
            "split": "train",
            "messages": deepcopy(messages),
            "metadata": {
                "related_industry_ids": [],
                "related_company_codes": [],
                "evidence_ids": [],
                "source_record_ids": [],
            },
        },
        {
            "sample_id": "sample-2",
            "event_id": "event-01",
            "task_type": "EVENT_QA",
            "split": "train",
            "messages": deepcopy(messages),
            "metadata": {
                "related_industry_ids": [],
                "related_company_codes": [],
                "evidence_ids": [],
                "source_record_ids": [],
            },
        },
    ]


def test_validation_accepts_valid_linked_dataset():
    report = validate_datasets(
        valid_unified(), valid_samples(), expected_events={"event-01"}
    )

    assert report["valid"] is True
    assert report["counts"] == {"unified_events": 1, "sft_samples": 2}
    assert report["task_counts"] == {"EVENT_ANALYSIS": 1, "EVENT_QA": 1}


def test_validation_rejects_cross_split_event():
    samples = valid_samples()
    samples[1]["split"] = "test"

    report = validate_datasets(valid_unified(), samples, expected_events={"event-01"})

    assert report["valid"] is False
    assert "EVENT_SPLIT_LEAKAGE" in {error["code"] for error in report["errors"]}


def test_validation_rejects_nonstandard_message_roles():
    samples = valid_samples()
    samples[0]["messages"][2]["role"] = "model"

    report = validate_datasets(valid_unified(), samples, expected_events={"event-01"})

    assert "INVALID_MESSAGE_ROLES" in {error["code"] for error in report["errors"]}


def test_validation_rejects_hidden_field_or_path():
    samples = valid_samples()
    samples[0]["metadata"] = {"evaluator_only_path": "hidden/labels.jsonl"}

    report = validate_datasets(valid_unified(), samples, expected_events={"event-01"})

    assert "FORBIDDEN_HIDDEN_DATA" in {error["code"] for error in report["errors"]}


def test_validation_rejects_missing_event_and_empty_answer():
    samples = valid_samples()
    samples[0]["messages"][2]["content"] = ""

    report = validate_datasets(
        valid_unified(), samples, expected_events={"event-01", "event-02"}
    )

    codes = {error["code"] for error in report["errors"]}
    assert "MISSING_EVENT_COVERAGE" in codes
    assert "EMPTY_ASSISTANT_CONTENT" in codes


def test_validation_rejects_missing_task_coverage():
    report = validate_datasets(
        valid_unified(),
        valid_samples(),
        expected_events={"event-01"},
        expected_task_types={
            "EVENT_ANALYSIS",
            "INDUSTRY_IMPACT",
            "COMPANY_IMPACT",
            "EVENT_QA",
        },
    )

    assert "MISSING_TASK_COVERAGE" in {error["code"] for error in report["errors"]}


def test_validation_rejects_event_without_any_sft_sample():
    unified = valid_unified()
    second = deepcopy(unified[0])
    second["event_id"] = "event-02"
    second["industries"] = []
    second["companies"] = []
    second["qa"] = []
    unified.append(second)

    report = validate_datasets(
        unified, valid_samples(), expected_events={"event-01", "event-02"}
    )

    assert "MISSING_SAMPLE_EVENT_COVERAGE" in {
        error["code"] for error in report["errors"]
    }


def test_validation_rejects_invalid_split_name():
    samples = valid_samples()
    samples[0]["split"] = "dev"

    report = validate_datasets(valid_unified(), samples, expected_events={"event-01"})

    assert "INVALID_SPLIT" in {error["code"] for error in report["errors"]}


@pytest.mark.parametrize(
    ("message_index", "content"),
    [(0, ""), (1, ""), (0, None), (1, ["不是字符串"])],
)
def test_validation_rejects_empty_or_non_string_system_and_user(
    message_index, content
):
    samples = valid_samples()
    samples[0]["messages"][message_index]["content"] = content

    report = validate_datasets(valid_unified(), samples, expected_events={"event-01"})

    assert "INVALID_MESSAGE_CONTENT" in {
        error["code"] for error in report["errors"]
    }


def test_validation_rejects_unknown_related_industry():
    samples = valid_samples()
    samples[0]["metadata"]["related_industry_ids"] = ["missing-industry"]

    report = validate_datasets(valid_unified(), samples, expected_events={"event-01"})

    assert "UNKNOWN_RELATED_INDUSTRY" in {
        error["code"] for error in report["errors"]
    }


def test_validation_rejects_unknown_related_company():
    samples = valid_samples()
    samples[0]["metadata"]["related_company_codes"] = ["000000.SH"]

    report = validate_datasets(valid_unified(), samples, expected_events={"event-01"})

    assert "UNKNOWN_RELATED_COMPANY" in {
        error["code"] for error in report["errors"]
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("related_industry_ids", "ei-1"),
        ("related_company_codes", [123]),
        ("evidence_ids", None),
        ("source_record_ids", ["ok", 2]),
    ],
)
def test_validation_requires_metadata_lineage_string_lists(field, value):
    samples = valid_samples()
    samples[0]["metadata"][field] = value

    report = validate_datasets(valid_unified(), samples, expected_events={"event-01"})

    assert "INVALID_METADATA_LIST" in {
        error["code"] for error in report["errors"]
    }


def test_validation_rejects_hard_truncation_marker():
    samples = valid_samples()
    samples[0]["messages"][1]["content"] += "\\n[内容已按训练长度上限截断]"

    report = validate_datasets(valid_unified(), samples, expected_events={"event-01"})

    assert "HARD_TRUNCATION_MARKER" in {
        error["code"] for error in report["errors"]
    }


def test_validation_rejects_message_bundle_over_character_budget():
    samples = valid_samples()
    samples[0]["messages"][2]["content"] = "长" * 2001

    report = validate_datasets(valid_unified(), samples, expected_events={"event-01"})

    assert "MESSAGE_LENGTH_EXCEEDED" in {
        error["code"] for error in report["errors"]
    }
