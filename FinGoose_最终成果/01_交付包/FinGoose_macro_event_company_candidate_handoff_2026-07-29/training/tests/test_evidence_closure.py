from copy import deepcopy

import pytest

from fingoose_training.evidence_closure import (
    EvidenceClosureError,
    bind_milestone_evidence_aliases,
    build_milestone_evidence_aliases,
    merge_evidence_records,
)


def test_merge_inherits_complete_event_evidence_for_sparse_child_without_mutation():
    event_evidence = [
        {
            "evidence_id": "event-1",
            "original_quote": "Official event statement.",
            "locator": "section 2",
            "source_url": "https://example.com/event",
            "supports_node_ids": ["event-node"],
        }
    ]
    child_evidence = [
        {
            "source_id": "event-1",
            "quote": "Official event statement.",
            "supports_node_ids": ["child-node", "event-node"],
        }
    ]
    before = deepcopy((event_evidence, child_evidence))

    records = merge_evidence_records(event_evidence, child_evidence)

    assert records == [
        {
            "evidence_id": "event-1",
            "original_quote": "Official event statement.",
            "locator": "section 2",
            "source_url": "https://example.com/event",
            "supports_node_ids": ["child-node", "event-node"],
            "missing": False,
        }
    ]
    assert (event_evidence, child_evidence) == before


def test_merge_fails_closed_for_conflicting_complete_source_urls():
    with pytest.raises(EvidenceClosureError, match="source_url"):
        merge_evidence_records(
            [{"evidence_id": "ev-1", "source_url": "https://example.com/one"}],
            [{"source_id": "ev-1", "url": "https://example.com/two"}],
        )


def test_merge_fails_closed_for_conflicting_aliases_in_one_record():
    with pytest.raises(EvidenceClosureError, match="original_quote"):
        merge_evidence_records(
            [
                {
                    "evidence_id": "ev-1",
                    "original_quote": "One statement.",
                    "quote": "Another statement.",
                }
            ]
        )


def test_merge_normalizes_aliases_and_sorts_results_stably():
    records = merge_evidence_records(
        [
            {
                "source_id": "z",
                "quote": "Z quote",
                "locator_zh": "第 1 节",
                "url": "https://example.com/z",
            },
            {
                "evidence_id": "a",
                "original_quote": "A quote",
                "page_or_section_locator": "p. 3",
                "source_url": "https://example.com/a",
            },
        ]
    )

    assert records == [
        {
            "evidence_id": "a",
            "original_quote": "A quote",
            "locator": "p. 3",
            "source_url": "https://example.com/a",
            "supports_node_ids": [],
            "missing": False,
        },
        {
            "evidence_id": "z",
            "original_quote": "Z quote",
            "locator": "第 1 节",
            "source_url": "https://example.com/z",
            "supports_node_ids": [],
            "missing": False,
        },
    ]


def test_fast_supplemental_evidence_binds_to_canonical_milestone_without_mutation():
    timeline = [
        {
            "fast_node_id": "fast-2020-03",
            "original_milestone_id": "milestone-pandemic",
            "source_id": "event-1",
        },
        {
            "fast_node_id": "fast-2020-03",
            "original_milestone_id": "milestone-pandemic",
            "evidence_id": "event-2",
        },
        {"fast_node_id": "fast-only", "evidence_id": "ignored"},
    ]
    milestones = [{"id": "milestone-pandemic", "sources": [{"evidence_id": "event-1"}]}]
    before = deepcopy((timeline, milestones))

    aliases = build_milestone_evidence_aliases(timeline)
    bound = bind_milestone_evidence_aliases(milestones, aliases)

    assert aliases == {"milestone-pandemic": ["event-1", "event-2"]}
    assert bound == [
        {
            "id": "milestone-pandemic",
            "sources": [{"evidence_id": "event-1"}, {"evidence_id": "event-2"}],
        }
    ]
    assert (timeline, milestones) == before


def test_embedded_ui_evidence_binds_to_milestone_id():
    timeline = [
        {
            "fast_node_id": "fast-2020-03",
            "original_milestone_id": "milestone-pandemic",
            "evidence": [
                {"source_id": "event-2"},
                {"evidence_id": "event-1"},
                {"source_id": "event-2"},
            ],
        }
    ]
    milestones = [{"milestone_id": "milestone-pandemic", "sources": []}]

    aliases = build_milestone_evidence_aliases(timeline)
    bound = bind_milestone_evidence_aliases(milestones, aliases)

    assert aliases == {"milestone-pandemic": ["event-1", "event-2"]}
    assert bound[0]["sources"] == [{"evidence_id": "event-1"}, {"evidence_id": "event-2"}]


def test_bind_fails_closed_when_canonical_milestone_does_not_exist():
    with pytest.raises(EvidenceClosureError, match="milestone-missing"):
        bind_milestone_evidence_aliases([], {"milestone-missing": ["event-1"]})


def test_bind_deduplicates_existing_and_aliased_evidence_sources():
    bound = bind_milestone_evidence_aliases(
        [
            {
                "id": "milestone-1",
                "sources": [{"evidence_id": "event-1"}, {"source_id": "event-1"}],
            }
        ],
        {"milestone-1": ["event-1", "event-2"]},
    )

    assert bound[0]["sources"] == [{"evidence_id": "event-1"}, {"evidence_id": "event-2"}]


@pytest.mark.parametrize("field", ["original_quote", "locator", "source_url"])
def test_whitespace_only_critical_fields_remain_missing(field):
    record = {
        "evidence_id": "event-1",
        "original_quote": "Official text",
        "locator": "section 2",
        "source_url": "https://example.com/event",
    }
    record[field] = "   "

    [merged] = merge_evidence_records([record])

    assert merged["missing"] is True


def test_primary_evidence_id_preserves_distinct_source_record_lineage():
    [record] = merge_evidence_records(
        [{"evidence_id": "event-1", "source_id": "source-document-1"}]
    )
    assert record["evidence_id"] == "event-1"
    assert record["source_record_ids"] == ["source-document-1"]


def test_merge_preserves_cutoff_and_audit_metadata():
    [record] = merge_evidence_records([{
        "evidence_id": "event-1",
        "original_quote": "Official text",
        "locator": "section 2",
        "source_url": "https://example.com/event",
        "publisher": "Official publisher",
        "published_at": "2020-01-01",
        "snapshot_sha256": "abc123",
    }])
    assert record["publisher"] == "Official publisher"
    assert record["published_at"] == "2020-01-01"
    assert record["snapshot_sha256"] == "abc123"


def test_merge_accepts_and_preserves_structured_locator():
    locator = {"type": "html_text", "value": "official sentence"}
    [record] = merge_evidence_records([{
        "evidence_id": "event-1",
        "original_quote": "Official text",
        "locator": locator,
        "source_url": "https://example.com/event",
    }])
    assert record["locator"] == locator
    assert record["missing"] is False


def test_alias_builder_prefers_evidence_id_over_source_lineage_id():
    aliases = build_milestone_evidence_aliases(
        [{
            "fast_node_id": "fast-1",
            "original_milestone_id": "milestone-1",
            "evidence": [{
                "evidence_id": "event-1",
                "source_id": "source-document-1",
            }],
        }]
    )
    assert aliases == {"milestone-1": ["event-1"]}


def test_bind_rejects_duplicate_canonical_milestones():
    with pytest.raises(EvidenceClosureError, match="duplicate canonical milestone"):
        bind_milestone_evidence_aliases(
            [
                {"milestone_id": "milestone-1", "sources": []},
                {"milestone_id": "milestone-1", "sources": []},
            ],
            {"milestone-1": ["event-1"]},
        )


def test_bind_rejects_conflicting_milestone_identity_aliases():
    with pytest.raises(EvidenceClosureError, match="milestone identity"):
        bind_milestone_evidence_aliases(
            [{"milestone_id": "milestone-1", "id": "milestone-2", "sources": []}],
            {"milestone-1": ["event-1"]},
        )
