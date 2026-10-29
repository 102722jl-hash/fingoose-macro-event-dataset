import pytest

from fingoose_training.metrics import evaluate_predictions


def test_metrics_group_results_by_task_and_event():
    rows = [
        {
            "event_id": "event-01",
            "task_type": "EVENT_QA",
            "metadata": {"evidence_ids": ["e-1"]},
        }
    ]
    predictions = [
        {"text": "依据证据 e-1，即时影响与短期影响不同；中期仍不确定。"}
    ]

    report = evaluate_predictions(rows, predictions)

    assert report["sample_count"] == 1
    assert report["by_task"]["EVENT_QA"]["sample_count"] == 1
    assert report["by_event"]["event-01"]["sample_count"] == 1
    assert report["evidence_reference_valid_rate"] == 1.0
    assert report["horizon_term_coverage_rate"] == 1.0
    assert report["uncertainty_language_rate"] == 1.0


def test_metrics_require_one_prediction_per_sample():
    with pytest.raises(ValueError, match="same length"):
        evaluate_predictions([{"event_id": "event-01"}], [])
