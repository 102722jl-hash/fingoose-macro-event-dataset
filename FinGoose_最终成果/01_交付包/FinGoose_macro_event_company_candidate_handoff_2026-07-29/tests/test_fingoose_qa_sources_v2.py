from __future__ import annotations

import hashlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


def _target(**overrides):
    row = {
        "event_id": "event-05",
        "source_id": "event05-fed-joint",
        "source_url": "https://www.federalreserve.gov/example",
        "media_type": "text/html",
        "first_public_at": "2023-03-12T22:15:00Z",
        "required_quote": "fully protects all depositors",
        "evidence_locator": "joint statement, second paragraph",
    }
    row.update(overrides)
    return row


def test_snapshot_verifies_quote_locator_cutoff_and_hash(tmp_path: Path) -> None:
    from fingoose_qa_sources_v2 import snapshot_source

    payload = b"<html><body><p>fully protects all depositors</p></body></html>"
    result = snapshot_source(
        _target(),
        cutoff_at="2023-03-13T23:59:59.999999Z",
        output_root=tmp_path,
        fetch_bytes=lambda _: payload,
        accessed_at="2026-08-05T00:00:00Z",
    )
    assert result["fetch_status"] == "RETRIEVED_QUOTE_VERIFIED"
    assert result["snapshot_sha256"] == hashlib.sha256(payload).hexdigest()
    assert result["evidence_locator"] == "joint statement, second paragraph"
    assert (tmp_path / result["snapshot_path"]).exists()


def test_post_cutoff_source_is_excluded_without_fetch(tmp_path: Path) -> None:
    from fingoose_qa_sources_v2 import snapshot_source

    def fail_if_called(_: str) -> bytes:
        raise AssertionError("network must not be called")

    result = snapshot_source(
        _target(first_public_at="2023-03-14T00:00:00Z"),
        cutoff_at="2023-03-13T23:59:59.999999Z",
        output_root=tmp_path,
        fetch_bytes=fail_if_called,
        accessed_at="2026-08-05T00:00:00Z",
    )
    assert result["fetch_status"] == "POST_CUTOFF_EXCLUDED"
    assert result["snapshot_path"] is None


def test_missing_publication_time_is_not_fetched(tmp_path: Path) -> None:
    from fingoose_qa_sources_v2 import snapshot_source

    result = snapshot_source(
        _target(first_public_at=None),
        cutoff_at="2023-03-13T23:59:59.999999Z",
        output_root=tmp_path,
        fetch_bytes=lambda _: (_ for _ in ()).throw(AssertionError("network called")),
        accessed_at="2026-08-05T00:00:00Z",
    )
    assert result["fetch_status"] == "PUBLICATION_TIME_UNVERIFIED"


def test_fetch_failure_remains_structured(tmp_path: Path) -> None:
    from fingoose_qa_sources_v2 import snapshot_source

    def timeout(_: str) -> bytes:
        raise TimeoutError("official source timed out")

    result = snapshot_source(
        _target(),
        cutoff_at="2023-03-13T23:59:59.999999Z",
        output_root=tmp_path,
        fetch_bytes=timeout,
        accessed_at="2026-08-05T00:00:00Z",
    )
    assert result["fetch_status"] == "FETCH_FAILED"
    assert result["verified_quote"] is None
    assert result["failure_reason"].startswith("TimeoutError:")
