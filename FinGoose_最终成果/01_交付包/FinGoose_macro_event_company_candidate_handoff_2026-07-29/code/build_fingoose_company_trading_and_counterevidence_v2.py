"""Build six-window trading reviews and company-level counterevidence ledgers."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

from fingoose_company_confounder_evidence_closure_v2 import (
    validate_counterevidence_review,
    validate_trading_review,
)
from fingoose_company_impact_io_v2 import read_jsonl, write_jsonl


WINDOWS = ("T_MINUS_1", "T0", "D1", "D3", "D5", "D20")
HORIZONS = ("IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM")


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _market_sources(candidate_root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(candidate_root / "market_source_registry.jsonl"):
        for key in (row.get("price_window_id"), row.get("source_record_id")):
            if key:
                result[str(key)] = row
    return result


def build_trading_reviews(root: Path, candidate_root: Path) -> list[dict[str, Any]]:
    del root
    windows = read_jsonl(candidate_root / "company_market_windows.jsonl")
    sources = _market_sources(candidate_root)
    output: list[dict[str, Any]] = []
    for row in windows:
        source_key = str(row.get("source_price_window_id") or "")
        source = sources.get(source_key) or sources.get(f"market-source-{source_key}")
        reviews: dict[str, dict[str, Any]] = {}
        for window in WINDOWS:
            observation = (row.get("observations") or {}).get(window) or {}
            actual_date = observation.get("actual_date")
            company_observation = observation.get("forward_adjusted_close")
            observed = (
                observation.get("status") == "OBSERVED"
                and actual_date is not None
                and company_observation is not None
                and source is not None
            )
            reviews[window] = {
                "actual_date": actual_date,
                "status": "VERIFIED_TRADING" if observed else "UNRESOLVED",
                "company_observation": company_observation,
                "observation_status": observation.get("status"),
                "source_record_id": source.get("source_record_id") if source else None,
                "source_url": source.get("source_url") if source else None,
                "snapshot_path": source.get("snapshot_path") if source else None,
                "reason": None if observed else "MISSING_OBSERVATION_OR_PUBLIC_PRICE_LINEAGE",
            }
        statuses = {review["status"] for review in reviews.values()}
        overall = "VERIFIED_TRADING" if statuses == {"VERIFIED_TRADING"} else "UNRESOLVED"
        audit = {
            "trading_review_id": f"trading-review-{row['mapping_id']}",
            "mapping_id": row["mapping_id"],
            "event_id": row["event_id"],
            "company_id": row["company_id"],
            "company_code": row.get("company_code"),
            "overall_status": overall,
            "window_reviews": reviews,
            "verification_basis": (
                "六个窗口均存在非空复权收盘观测，并可追溯至既有公开行情源。"
                if overall == "VERIFIED_TRADING"
                else "至少一个窗口缺少非空行情观测或公开行情血缘；未据此推断停牌。"
            ),
            "review_status": "NEEDS_HUMAN_REVIEW",
            "formal_ready": False,
            "sha_gate": "DEFERRED",
        }
        failures = validate_trading_review(audit)
        if failures:
            raise ValueError(f"INVALID_TRADING_REVIEW:{row['mapping_id']}:{','.join(failures)}")
        output.append(audit)
    return sorted(output, key=lambda item: (str(item["event_id"]), str(item["company_code"])))


def _window_horizons(windows: Sequence[str]) -> list[str]:
    result: list[str] = []
    for window in windows:
        if window in {"T_MINUS_1", "T0", "D1"}:
            result.append("IMMEDIATE")
        elif window in {"D3", "D5"}:
            result.append("SHORT_TERM")
        elif window == "D20":
            result.append("MEDIUM_TERM")
    return _unique(result)


def build_counterevidence_reviews(
    root: Path, candidate_root: Path
) -> list[dict[str, Any]]:
    del root
    mappings = read_jsonl(candidate_root / "event_company_map.jsonl")
    dossiers = {
        str(row["company_id"]): row
        for row in read_jsonl(candidate_root / "company_master_dossiers.jsonl")
    }
    evidence = {
        str(row["evidence_id"]): row
        for row in read_jsonl(candidate_root / "company_evidence.jsonl")
    }
    directions = {
        str(row["mapping_id"]): row
        for row in read_jsonl(candidate_root / "direction_assessments.jsonl")
    }
    bodies_by_mapping: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in read_jsonl(candidate_root / "announcement_body_reviews.jsonl"):
        bodies_by_mapping[str(row["mapping_id"])].append(row)

    output: list[dict[str, Any]] = []
    for mapping in mappings:
        mapping_id = str(mapping["mapping_id"])
        company_id = str(mapping["company_id"])
        dossier = dossiers.get(company_id, {})
        direction = directions.get(mapping_id, {})
        evidence_horizons: dict[str, list[str]] = defaultdict(list)
        for horizon, review in (direction.get("horizon_reviews") or {}).items():
            for evidence_id in review.get("counterevidence_ids") or []:
                evidence_horizons[str(evidence_id)].append(str(horizon))
        for category in dossier.get("research_categories") or []:
            if category.get("category") == "LIMITATIONS_AND_COUNTEREVIDENCE":
                for evidence_id in category.get("evidence_ids") or []:
                    evidence_horizons[str(evidence_id)].extend(HORIZONS)

        findings: list[dict[str, Any]] = []
        for evidence_id, affected_horizons in evidence_horizons.items():
            item = evidence.get(evidence_id)
            if not item or not item.get("original_quote"):
                continue
            findings.append(
                {
                    "counterevidence_id": f"counter-{mapping_id}-{evidence_id}",
                    "evidence_id": evidence_id,
                    "evidence_kind": "OFFICIAL_COMPANY_REPORT",
                    "claim_zh": "公司官方披露包含可能限制宏观事件直接归因的业务条件或风险因素。",
                    "source_url": item.get("source_url"),
                    "first_public_at": item.get("published_at"),
                    "locator": item.get("page_or_section_locator"),
                    "original_quote": item.get("original_quote"),
                    "affected_horizons": _unique(affected_horizons) or list(HORIZONS),
                    "effect_on_thesis": "LIMITS_DIRECT_ATTRIBUTION",
                    "review_status": "NEEDS_HUMAN_REVIEW",
                }
            )

        for body in bodies_by_mapping.get(mapping_id, []):
            if body.get("relevance_decision") not in {"RELEVANT", "MINOR_RELEVANCE"}:
                continue
            announcement_id = str(body["announcement_id"])
            findings.append(
                {
                    "counterevidence_id": f"counter-{mapping_id}-announcement-{announcement_id}",
                    "evidence_id": f"announcement:{announcement_id}",
                    "evidence_kind": "OFFICIAL_ANNOUNCEMENT_BODY",
                    "claim_zh": body.get("mechanism_zh")
                    or "事件窗口内存在可能独立影响公司价格或经营预期的公司公告。",
                    "source_url": body.get("source_url"),
                    "first_public_at": body.get("first_public_at"),
                    "locator": body.get("body_locator"),
                    "original_quote": body.get("original_quote"),
                    "affected_horizons": _window_horizons(body.get("affected_windows") or [])
                    or list(HORIZONS),
                    "effect_on_thesis": "INDEPENDENT_COMPANY_FACTOR",
                    "review_status": "NEEDS_HUMAN_REVIEW",
                }
            )

        negative_basis = None
        if not findings:
            negative_basis = (
                "已检查公司 dossier 的 LIMITATIONS_AND_COUNTEREVIDENCE 类别、三期限方向失效条件"
                "及事件窗口内已审核公告正文，未形成可引用的公司级反证记录。"
            )
        review = {
            "counterevidence_review_id": f"counterevidence-review-{mapping_id}",
            "mapping_id": mapping_id,
            "event_id": mapping["event_id"],
            "company_id": company_id,
            "company_code": mapping.get("company_code"),
            "findings": findings,
            "searched_categories": [
                "DOSSIER_LIMITATIONS_AND_COUNTEREVIDENCE",
                "DIRECTION_INVALIDATION_CONDITIONS",
                "REVIEWED_EVENT_WINDOW_ANNOUNCEMENTS",
            ],
            "negative_search_basis": negative_basis,
            "review_status": "NEEDS_HUMAN_REVIEW",
            "formal_ready": False,
            "sha_gate": "DEFERRED",
        }
        failures = validate_counterevidence_review(review)
        if failures:
            raise ValueError(
                f"INVALID_COUNTEREVIDENCE_REVIEW:{mapping_id}:{','.join(failures)}"
            )
        output.append(review)
    return sorted(output, key=lambda item: (str(item["event_id"]), str(item["company_code"])))


def build(root: Path, candidate_root: Path) -> dict[str, Any]:
    trading = build_trading_reviews(root, candidate_root)
    counterevidence = build_counterevidence_reviews(root, candidate_root)
    write_jsonl(candidate_root / "trading_status_reviews.jsonl", trading)
    write_jsonl(
        candidate_root / "company_counterevidence_reviews.jsonl", counterevidence
    )
    return {
        "trading_review_count": len(trading),
        "verified_trading_count": sum(
            row["overall_status"] == "VERIFIED_TRADING" for row in trading
        ),
        "counterevidence_review_count": len(counterevidence),
        "counterevidence_finding_count": sum(
            len(row["findings"]) for row in counterevidence
        ),
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
    candidate_root = args.candidate_root
    if not candidate_root.is_absolute():
        candidate_root = root / candidate_root
    print(json.dumps(build(root, candidate_root), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
