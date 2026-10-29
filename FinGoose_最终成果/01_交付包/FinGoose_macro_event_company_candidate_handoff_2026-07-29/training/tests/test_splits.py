import pytest

from fingoose_training.splits import SplitError, build_event_split_index, tag_samples


def test_build_event_split_index_rejects_overlap():
    with pytest.raises(SplitError, match="appears in both"):
        build_event_split_index({"train": ["event-01"], "test": ["event-01"]})


def test_tag_samples_keeps_every_sample_for_an_event_together():
    samples = [
        {"sample_id": "a", "event_id": "event-01"},
        {"sample_id": "b", "event_id": "event-01"},
        {"sample_id": "c", "event_id": "event-10"},
    ]

    tagged = tag_samples(
        samples, {"train": ["event-01"], "test": ["event-10"]}
    )

    assert [row["split"] for row in tagged] == ["train", "train", "test"]
    assert all("split" not in row for row in samples)


def test_tag_samples_rejects_event_missing_from_manifest():
    with pytest.raises(SplitError, match="missing from split manifest"):
        tag_samples(
            [{"sample_id": "a", "event_id": "event-02"}],
            {"train": ["event-01"]},
        )
