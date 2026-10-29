from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


def test_snapshot_marks_missing_registered_quote_as_content_mismatch(
    tmp_path: Path,
) -> None:
    from fingoose_qa_sources_v2 import snapshot_source

    result = snapshot_source(
        {
            "event_id": "event-05",
            "source_id": "event05-fed-joint",
            "source_url": "https://www.federalreserve.gov/example",
            "media_type": "text/html",
            "first_public_at": "2023-03-12T22:15:00Z",
            "required_quote": "fully protects all depositors",
            "evidence_locator": "joint statement, second paragraph",
        },
        cutoff_at="2023-03-13T23:59:59.999999Z",
        output_root=tmp_path,
        fetch_bytes=lambda _: b"<p>different official statement</p>",
        accessed_at="2026-08-05T00:00:00Z",
    )

    assert result["fetch_status"] == "CONTENT_MISMATCH"
    assert result["verified_quote"] is None
    assert result["failure_reason"] == "REQUIRED_QUOTE_NOT_FOUND"
    assert result["snapshot_sha256"]
