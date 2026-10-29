"""Build reproducible title-search and negative-result audits."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

from fingoose_company_confounder_evidence_closure_v2 import validate_search_audit
from fingoose_company_impact_io_v2 import read_jsonl, write_jsonl


QUERY_CATEGORIES = (
    "EARNINGS_AND_FORECAST",
    "CAPITAL_RETURN_AND_SHAREHOLDING",
    "FINANCING_AND_DEBT",
    "CONTRACTS_AND_ORDERS",
    "LITIGATION_AND_REGULATION",
    "RESTRUCTURING_AND_ASSETS",
    "SUSPENSION_AND_RESUMPTION",
    "MATERIAL_OPERATIONS",
)


def _snapshot_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, list):
        return payload
    for key in ("announcements", "records", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def build_audits(root: Path, candidate_root: Path) -> list[dict[str, Any]]:
    del root
    candidate_root = candidate_root.resolve()
    intake = read_jsonl(candidate_root / "company_announcement_intake.jsonl")
    reviews = read_jsonl(candidate_root / "announcement_body_reviews.jsonl")
    reviews_by_mapping: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for review in reviews:
        reviews_by_mapping[str(review["mapping_id"])].append(review)
    audits: list[dict[str, Any]] = []
    for row in intake:
        mapping_id = str(row["mapping_id"])
        snapshot_path = candidate_root / str(row["snapshot_path"])
        titles = _snapshot_records(snapshot_path)
        mapping_reviews = reviews_by_mapping.get(mapping_id, [])
        unresolved = [
            str(review["announcement_id"])
            for review in mapping_reviews
            if review.get("body_review_status") != "BODY_REVIEWED"
            or review.get("relevance_decision") == "UNRESOLVED"
        ]
        candidate_ids = [str(review["announcement_id"]) for review in mapping_reviews]
        reviewed_ids = [
            str(review["announcement_id"])
            for review in mapping_reviews
            if review.get("body_review_status") == "BODY_REVIEWED"
            and review.get("relevance_decision") != "UNRESOLVED"
        ]
        unresolved_reasons = (
            [f"BODY_REVIEW_UNRESOLVED:{announcement_id}" for announcement_id in unresolved]
            if unresolved
            else []
        )
        audit = {
            "search_audit_id": f"confounder-search-{mapping_id}",
            "mapping_id": mapping_id,
            "event_id": row["event_id"],
            "company_id": row["company_id"],
            "company_code": row.get("company_code"),
            "company_name": row.get("company_name"),
            "window_start": row["window_start"],
            "window_end": row["window_end"],
            "title_snapshot_path": row["snapshot_path"],
            "title_count": len(titles),
            "candidate_count": len(candidate_ids),
            "candidate_announcement_ids": candidate_ids,
            "body_reviewed_count": len(reviewed_ids),
            "body_reviewed_announcement_ids": reviewed_ids,
            "rejected_title_count": len(titles) - len(candidate_ids),
            "query_categories": list(QUERY_CATEGORIES),
            "source_providers": ["CNINFO_OFFICIAL_DISCLOSURE"],
            "search_completed_at": "2026-08-03T16:00:00+08:00",
            "search_status": "INCOMPLETE" if unresolved_reasons else "COMPLETE",
            "negative_result_basis": (
                "已复核该公司在事件窗口内的全部巨潮公告标题，固定八类重大事项规则均未筛出正文审核候选。"
                if not candidate_ids
                else None
            ),
            "unresolved_reasons": unresolved_reasons,
            "review_status": "NEEDS_HUMAN_REVIEW",
            "formal_ready": False,
            "sha_gate": "DEFERRED",
        }
        failures = validate_search_audit(audit)
        if failures:
            raise ValueError(
                f"INVALID_SEARCH_AUDIT:{mapping_id}:{','.join(failures)}"
            )
        audits.append(audit)
    return sorted(audits, key=lambda row: (str(row["event_id"]), str(row["company_code"])))


def build(root: Path, candidate_root: Path) -> dict[str, Any]:
    audits = build_audits(root, candidate_root)
    write_jsonl(candidate_root / "company_confounder_search_audits.jsonl", audits)
    return {
        "audit_count": len(audits),
        "title_count": sum(row["title_count"] for row in audits),
        "candidate_count": sum(row["candidate_count"] for row in audits),
        "complete_count": sum(row["search_status"] == "COMPLETE" for row in audits),
        "formal_ready": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--candidate-root",
        type=Path,
        default=Path("work/company_impact_high_quality_v2_candidate"),
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    candidate = args.candidate_root
    if not candidate.is_absolute():
        candidate = root / candidate
    print(json.dumps(build(root, candidate), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
