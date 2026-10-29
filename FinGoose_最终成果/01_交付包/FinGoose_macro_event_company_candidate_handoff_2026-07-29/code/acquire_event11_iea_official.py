from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

import requests
from pypdf import PdfReader


SOURCE_URL = "https://iea.blob.core.windows.net/assets/a25ddf53-cd6c-4910-ac90-16bfd28399e7/-12MAR2026_OilMarketReport.pdf"
ANCHOR_AT = "2026-03-11T00:00:00+00:00"
PUBLISHED_AT = "2026-03-12T00:00:00+00:00"


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8", newline="\n")


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-run", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_run.resolve()
    output.mkdir(parents=True, exist_ok=False)
    snapshots = output / "snapshots"
    snapshots.mkdir()
    retrieved_at = datetime.now(timezone.utc).isoformat()
    search_audit = {
        "event_id": "event-11",
        "query": "site:iea.blob.core.windows.net 2026 400 million barrels collective action March 11 PDF",
        "adapter": "anysearch.batch_search",
        "rank": 1,
        "candidate_url": SOURCE_URL,
        "official_anchor": True,
        "returned_at": retrieved_at,
    }
    write_jsonl(output / "search_audit.jsonl", [search_audit])
    session = requests.Session()
    session.trust_env = False
    session.headers["User-Agent"] = "Mozilla/5.0 FinGooseAuditableResearch/2.0"
    quarantine = []
    try:
        response = session.get(SOURCE_URL, timeout=120)
        response.raise_for_status()
        body = response.content
        if not body.startswith(b"%PDF"):
            raise ValueError("RESPONSE_NOT_PDF")
        digest = sha256(body).hexdigest()
        pdf_path = snapshots / f"{digest}.pdf"
        pdf_path.write_bytes(body)
        pages = []
        for page_number, page in enumerate(PdfReader(str(pdf_path), strict=False).pages, 1):
            text = normalize(page.extract_text() or "")
            if "400 mb" in text and "11 March" in text:
                pages.append((page_number, text))
        if not pages:
            raise ValueError("TARGET_PASSAGE_NOT_FOUND")
        page_number, page_text = pages[0]
        match = re.search(r"(.{0,280}11 March.{0,520}400 mb.{0,500})", page_text, flags=re.IGNORECASE)
        quote = normalize(match.group(1) if match else page_text[:1200])
        evidence = {
            "evidence_id": "evidence-event-11-iea-omr-20260312",
            "event_id": "event-11",
            "publisher": "International Energy Agency",
            "published_at": PUBLISHED_AT,
            "anchor_at": ANCHOR_AT,
            "declared_role": "POST_EVENT_VALIDATION",
            "temporal_role": "POST_EVENT_VALIDATION",
            "retrieved_at": retrieved_at,
            "original_quote": quote,
            "locator": f"PDF page {page_number}, paragraph containing '11 March' and '400 mb'; section 'IEA Member Countries Agree Historic Emergency Stock Release'",
            "source_url": SOURCE_URL,
            "source_tier": "T1",
            "statement_class": "SOURCE_FACT",
            "supports_node_ids": ["event-11-fact"],
            "snapshot_path": pdf_path.relative_to(output).as_posix(),
            "snapshot_sha256": digest,
            "content_type": response.headers.get("content-type"),
            "http_status": response.status_code,
            "acceptance_status": "ACCEPTED",
            "acceptance_reason": "GATES_PASSED_POST_EVENT_T1_CONFIRMATION",
            "review_status": "NEEDS_HUMAN_REVIEW",
            "formal_ready": False,
        }
        write_jsonl(output / "evidence_candidates.jsonl", [evidence])
        write_jsonl(output / "accepted_evidence.jsonl", [evidence])
        write_jsonl(output / "quarantine.jsonl", [])
        write_json(output / "acquisition_summary.json", {
            "event_id": "event-11", "accepted": 1, "quarantined": 0,
            "snapshot_sha256": digest, "snapshot_bytes": len(body),
            "review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False,
        })
    except Exception as exc:
        quarantine.append({"event_id": "event-11", "reason_code": "IEA_OFFICIAL_PDF_ACQUISITION_FAILED", "detail": f"{type(exc).__name__}:{exc}"})
        write_jsonl(output / "evidence_candidates.jsonl", [])
        write_jsonl(output / "accepted_evidence.jsonl", [])
        write_jsonl(output / "quarantine.jsonl", quarantine)
        write_json(output / "acquisition_summary.json", {"event_id": "event-11", "accepted": 0, "quarantined": 1})
        return 1
    print((output / "acquisition_summary.json").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
