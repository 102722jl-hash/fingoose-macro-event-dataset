"""Resolve event-date SWS L1 classifications from official change history."""

from __future__ import annotations

import argparse
import copy
import json
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

from fingoose_company_impact_io_v2 import read_jsonl, write_jsonl


SW2021_TRANSITION_DATE = date.fromisoformat("2021-07-30")
CODE_NAMESPACE = {
    "sw_industry_code": "SWS_CLASSIFICATION_6_DIGIT",
    "sw_index_code": "SWS_L1_BENCHMARK_INDEX",
}

# The workbook records six-digit classification codes. L1 benchmark/index codes
# live in a separate namespace and are derived from the two-digit L1 prefix.
L1_BY_EDITION: dict[str, dict[str, tuple[str, str]]] = {
    "SW2014": {
        "37": ("801150", "医药生物"),
        "42": ("801170", "交通运输"),
    },
    "SW2021": {
        "27": ("801080", "电子"),
        "33": ("801110", "家用电器"),
        "37": ("801150", "医药生物"),
        "42": ("801170", "交通运输"),
        "43": ("801180", "房地产"),
        "46": ("801210", "社会服务"),
        "48": ("801780", "银行"),
        "49": ("801790", "非银金融"),
        "63": ("801730", "电力设备"),
        "75": ("801960", "石油石化"),
    },
}


class ClassificationError(ValueError):
    """Raised when event-date classification cannot be resolved safely."""


def _as_date(value: str) -> date:
    return date.fromisoformat(str(value)[:10])


def classification_edition(event_as_of_date: str) -> str:
    return (
        "SW2021"
        if _as_date(event_as_of_date) >= SW2021_TRANSITION_DATE
        else "SW2014"
    )


def select_asof_history_record(
    history: Sequence[Mapping[str, Any]],
    company_code: str,
    event_as_of_date: str,
) -> dict[str, Any]:
    bare_code = str(company_code).split(".", 1)[0]
    company_rows = sorted(
        (
            row
            for row in history
            if str(row.get("company_code")) == bare_code
        ),
        key=lambda row: str(row["member_valid_from"]),
    )
    cutoff = _as_date(event_as_of_date)
    active_index = None
    for index, row in enumerate(company_rows):
        if _as_date(str(row["member_valid_from"])) <= cutoff:
            active_index = index
        else:
            break
    if active_index is None:
        raise ClassificationError(
            f"NO_HISTORY_ACTIVE_ASOF:{company_code}:{event_as_of_date}"
        )
    selected = dict(company_rows[active_index])
    selected["member_valid_to_exclusive"] = (
        str(company_rows[active_index + 1]["member_valid_from"])
        if active_index + 1 < len(company_rows)
        else None
    )
    return selected


def map_l1_industry(
    sw_industry_code: str, edition: str
) -> tuple[str, str]:
    code = str(sw_industry_code)
    if len(code) != 6 or not code.isdigit():
        raise ClassificationError(f"INVALID_SW_INDUSTRY_CODE:{code}")
    try:
        return L1_BY_EDITION[edition][code[:2]]
    except KeyError as exc:
        raise ClassificationError(
            f"UNMAPPED_L1_PREFIX:{edition}:{code[:2]}"
        ) from exc


def classify_mapping(
    mapping: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    event_as_of_at = str(mapping["selection_cutoff_at"])
    event_as_of_date = event_as_of_at[:10]
    edition = classification_edition(event_as_of_date)
    selected = select_asof_history_record(
        history,
        str(mapping["company_code"]),
        event_as_of_date,
    )
    sw_industry_code = str(selected["sw_industry_code"])
    sw_index_code, sw1_name = map_l1_industry(sw_industry_code, edition)
    source_row = int(selected["source_row_number"])
    return {
        "system": "SHENWAN",
        "classification_edition": edition,
        "classification_level": "L1",
        "code_namespace": dict(CODE_NAMESPACE),
        "sw_industry_code": sw_industry_code,
        "sw_index_code": sw_index_code,
        "sw1_id": sw_index_code,
        "sw1_name": sw1_name,
        "sw2_id": "UNKNOWN",
        "sw2_name": "UNKNOWN",
        "member_valid_from": str(selected["member_valid_from"]),
        "member_valid_to_exclusive": selected["member_valid_to_exclusive"],
        "event_as_of_at": event_as_of_at,
        "event_as_of_date": event_as_of_date,
        "asof_match_status": "LATEST_START_NOT_AFTER_EVENT_DATE",
        "classification_status": "OFFICIAL_HISTORY_ASOF_MATCHED",
        "historical_effective_date_status": "VERIFIED_ACTIVE_ASOF",
        "review_status": "SOURCE_VERIFIED_RULE_APPLIED",
        "source_publisher": selected["source_publisher"],
        "source_title": selected["source_title"],
        "source_url": selected["source_url"],
        "source_snapshot_path": selected["source_snapshot_path"],
        "source_snapshot_sha256": selected["source_snapshot_sha256"],
        "source_update_date": selected.get("source_update_date"),
        "source_row_number": source_row,
        "evidence_locator": f"Sheet1 row {source_row}",
        "transport_verification": selected.get("transport_verification"),
    }


def _validate_event_asof_consistency(
    mappings: Sequence[Mapping[str, Any]],
) -> None:
    event_dates: dict[str, str] = {}
    for mapping in mappings:
        event_id = str(mapping["event_id"])
        event_date = str(mapping["selection_cutoff_at"])[:10]
        previous = event_dates.setdefault(event_id, event_date)
        if previous != event_date:
            raise ClassificationError(
                f"EVENT_ASOF_INCONSISTENT:{event_id}:{previous}:{event_date}"
            )


def build_classification_reviews(
    mappings: Sequence[Mapping[str, Any]],
    history: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    _validate_event_asof_consistency(mappings)
    reviews: list[dict[str, Any]] = []
    enriched_mappings: list[dict[str, Any]] = []
    for source_mapping in mappings:
        mapping = copy.deepcopy(dict(source_mapping))
        classification = classify_mapping(mapping, history)
        mapping["industry"] = classification["sw1_name"]
        mapping["industry_classification"] = classification
        reviews.append(
            {
                "review_id": f"industry-classification-{mapping['mapping_id']}",
                "mapping_id": mapping["mapping_id"],
                "event_id": mapping["event_id"],
                "anchor_id": mapping["anchor_id"],
                "company_id": mapping["company_id"],
                "company_code": mapping["company_code"],
                "company_name": mapping["company_name"],
                "industry_classification": copy.deepcopy(classification),
                "review_boundary": "RULE_APPLIED_NOT_MANUAL_APPROVAL",
                "formal_ready": False,
                "price_selection_used": False,
            }
        )
        enriched_mappings.append(mapping)
    return reviews, enriched_mappings


def generate(
    root: Path,
    *,
    output_root: Path | None = None,
) -> dict[str, int]:
    root = root.resolve()
    config_root = root / "configs/company_impact_high_quality_v2"
    destination = (output_root or config_root).resolve()
    mappings = read_jsonl(config_root / "event_company_map.jsonl")
    history = read_jsonl(config_root / "industry_classification_history_extract.jsonl")
    reviews, enriched = build_classification_reviews(mappings, history)
    write_jsonl(destination / "industry_classification_reviews.jsonl", reviews)
    write_jsonl(destination / "event_company_map.jsonl", enriched)
    return {
        "mapping_count": len(enriched),
        "review_count": len(reviews),
        "unknown_count": sum(
            row["industry_classification"]["sw1_id"] == "UNKNOWN"
            for row in enriched
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output
    if output is not None and not output.is_absolute():
        output = args.root / output
    print(
        json.dumps(
            generate(args.root, output_root=output),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
