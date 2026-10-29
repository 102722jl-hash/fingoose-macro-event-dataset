"""Claim-level evidence gates for the company-impact v2 candidate package."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable, Mapping


OFFICIAL_SOURCE_CLASSES = {
    "ANNUAL_REPORT",
    "INTERIM_REPORT",
    "EXCHANGE_FILING",
    "PROSPECTUS",
    "COMPANY_IR_RECORD",
    "COMPANY_WEBSITE_DISCLOSURE",
}
PERIODIC_REPORT_CLASSES = {"ANNUAL_REPORT", "INTERIM_REPORT"}
REQUIRED_EVIDENCE_FIELDS = (
    "source_id",
    "document_id",
    "company_id",
    "source_class",
    "source_url",
    "document_title",
    "issuer",
    "published_at",
    "published_at_precision",
    "reporting_period",
    "original_quote",
    "page_or_section_locator",
)


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("TIMESTAMP_TIMEZONE_REQUIRED")
    return parsed


def _is_prediction_visible(
    source: Mapping[str, Any],
    selection_cutoff_at: str,
) -> bool:
    published_at = str(source["published_at"])
    precision = str(source["published_at_precision"])
    cutoff_date = date.fromisoformat(selection_cutoff_at[:10])
    if precision == "DATE":
        return date.fromisoformat(published_at[:10]) < cutoff_date
    if len(selection_cutoff_at) == 10:
        return date.fromisoformat(published_at[:10]) < cutoff_date
    return _parse_datetime(published_at) <= _parse_datetime(selection_cutoff_at)


def _validate_source(
    claim: Mapping[str, Any],
    source: Mapping[str, Any],
) -> None:
    for field in REQUIRED_EVIDENCE_FIELDS:
        if source.get(field) in (None, ""):
            raise ValueError(f"MISSING_EVIDENCE_FIELD:{field}")
    if source["company_id"] != claim["company_id"]:
        raise ValueError(
            f"SOURCE_COMPANY_MISMATCH:{source['source_id']}:{claim['company_id']}"
        )


def evaluate_claim(
    claim: Mapping[str, Any],
    sources: Iterable[Mapping[str, Any]],
    *,
    selection_cutoff_at: str,
) -> dict[str, Any]:
    unique_official: dict[str, dict[str, Any]] = {}
    for raw_source in sources:
        source = dict(raw_source)
        _validate_source(claim, source)
        if source["source_class"] not in OFFICIAL_SOURCE_CLASSES:
            continue
        unique_official.setdefault(str(source["document_id"]), source)

    official_sources = list(unique_official.values())
    prediction_visible_sources = [
        source
        for source in official_sources
        if _is_prediction_visible(source, selection_cutoff_at)
    ]
    has_periodic_report = any(
        source["source_class"] in PERIODIC_REPORT_CLASSES
        for source in official_sources
    )
    if len(official_sources) >= 2 and has_periodic_report:
        verification_status = "VERIFIED"
    elif official_sources:
        verification_status = "PARTIALLY_VERIFIED"
    else:
        verification_status = "DATA_PENDING"

    return {
        **dict(claim),
        "verification_status": verification_status,
        "availability_scope": (
            "PREDICTION_VISIBLE"
            if prediction_visible_sources
            else "VERIFICATION_ONLY"
        ),
        "evidence_source_ids": [
            str(source["source_id"]) for source in official_sources
        ],
        "prediction_visible_source_ids": [
            str(source["source_id"]) for source in prediction_visible_sources
        ],
        "official_document_count": len(official_sources),
        "formal_ready": False,
    }
