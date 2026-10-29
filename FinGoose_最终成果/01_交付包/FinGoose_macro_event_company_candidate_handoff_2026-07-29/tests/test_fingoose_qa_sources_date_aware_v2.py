from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


def test_date_precision_uses_end_of_day_for_cutoff_comparison(tmp_path: Path) -> None:
    from fingoose_qa_sources_date_aware_v2 import snapshot_source

    target = {
        "event_id": "event-07",
        "source_id": "event07-imo-galaxy-leader",
        "source_url": "https://www.imo.org/example",
        "media_type": "text/html",
        "first_public_at": "2023-11-19",
        "required_quote": "Galaxy Leader",
        "evidence_locator": "opening paragraph",
    }
    result = snapshot_source(
        target,
        cutoff_at="2023-10-10T23:59:59.999999Z",
        output_root=tmp_path,
        fetch_bytes=lambda _: (_ for _ in ()).throw(AssertionError("network called")),
        accessed_at="2026-08-05T00:00:00Z",
    )
    assert result["fetch_status"] == "POST_CUTOFF_EXCLUDED"
    assert result["first_public_at"] == "2023-11-19"


def test_eligible_date_precision_source_can_be_verified(tmp_path: Path) -> None:
    from fingoose_qa_sources_date_aware_v2 import snapshot_source

    result = snapshot_source(
        {
            "event_id": "event-06",
            "source_id": "event06-opec-jmmc",
            "source_url": "https://www.opec.org/example",
            "media_type": "text/html",
            "first_public_at": "2023-04-03",
            "required_quote": "1.66 million b/d",
            "evidence_locator": "final paragraphs",
        },
        cutoff_at="2023-04-06T23:59:59.999999Z",
        output_root=tmp_path,
        fetch_bytes=lambda _: b"<p>adjustments total 1.66 million b/d.</p>",
        accessed_at="2026-08-05T00:00:00Z",
    )
    assert result["fetch_status"] == "RETRIEVED_QUOTE_VERIFIED"
    assert result["first_public_at_precision"] == "DATE"
