import pytest

from fingoose_training.evidence_closure import EvidenceClosureError
from fingoose_training.reasoning_chain_impl_001 import compile_evidence_registry
from fingoose_training.unified_builder_impl_008 import (
    _complete_evidence,
    _inherit_event_evidence,
)


def _complete_record(quote: str = "Official parent quote") -> dict:
    return {
        "evidence_id": "evidence-1",
        "original_quote": quote,
        "locator": "section 1",
        "source_url": "https://example.com/source",
    }


def test_builder_fails_closed_before_conflicting_complete_records_are_collapsed():
    with pytest.raises(EvidenceClosureError, match="original_quote"):
        _complete_evidence(
            [_complete_record("First official quote")],
            [_complete_record("Second conflicting official quote")],
        )


def test_event_complete_record_wins_over_conflicting_sparse_reference():
    [record] = _complete_evidence(
        [{
            "evidence_id": "evidence-1",
            "source_id": "source-document-sparse",
            "original_quote": "Conflicting sparse quote",
            "supports_node_ids": ["milestone-node"],
        }],
        [{
            **_complete_record("Canonical official quote"),
            "source_id": "source-document-complete",
        }],
    )

    assert record["original_quote"] == "Canonical official quote"
    assert record["source_record_ids"] == [
        "source-document-complete",
        "source-document-sparse",
    ]
    assert record["supports_node_ids"] == ["milestone-node"]
    assert record["missing"] is False


def test_conflicting_sparse_records_remain_missing_without_false_conflict():
    [record] = _complete_evidence(
        [{
            "evidence_id": "evidence-1",
            "source_id": "source-document-1",
            "original_quote": "First sparse quote",
        }],
        [{
            "evidence_id": "evidence-1",
            "source_id": "source-document-2",
            "original_quote": "Second sparse quote",
        }],
    )

    assert record["original_quote"] is None
    assert record["source_record_ids"] == [
        "source-document-1",
        "source-document-2",
    ]
    assert record["missing"] is True


def test_sparse_child_keeps_parent_canonical_fields_and_source_lineage():
    [parent] = _complete_evidence([_complete_record()])

    [inherited] = _inherit_event_evidence(
        [parent],
        [{
            "evidence_id": "evidence-1",
            "source_id": "source-document-child",
            "quote": "A longer sparse child quote that is not independently complete",
            "supports_node_ids": ["child-node"],
        }],
    )

    assert inherited["original_quote"] == "Official parent quote"
    assert inherited["source_record_ids"] == ["source-document-child"]
    assert inherited["supports_node_ids"] == ["child-node"]
    assert inherited["missing"] is False


def test_compiled_registry_preserves_stable_source_record_lineage():
    [record] = compile_evidence_registry(
        [{
            **_complete_record(),
            "source_record_ids": ["source-document-2", "source-document-1"],
        }],
        [{"node_id": "event-node", "evidence_ids": ["evidence-1"]}],
    )

    assert record["source_record_ids"] == [
        "source-document-1",
        "source-document-2",
    ]
