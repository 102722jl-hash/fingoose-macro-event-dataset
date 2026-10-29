"""Validation and grade gates for company confounder evidence closure."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


VALID_RELEVANCE = {
    "RELEVANT",
    "MINOR_RELEVANCE",
    "IRRELEVANT",
    "UNRESOLVED",
}
VALID_GRADES = {"CLEAN", "MINOR", "MATERIAL", "DOMINANT", "UNRESOLVED"}
VALID_WINDOWS = {"T_MINUS_1", "T0", "D1", "D3", "D5", "D20"}
RESOLVED_TRADING = {"VERIFIED_TRADING", "VERIFIED_SUSPENDED"}


def _required(row: Mapping[str, Any], fields: Mapping[str, str]) -> list[str]:
    return [failure for field, failure in fields.items() if not row.get(field)]


def validate_body_review(row: Mapping[str, Any]) -> list[str]:
    failures = _required(
        row,
        {
            "review_id": "REVIEW_ID_REQUIRED",
            "mapping_id": "MAPPING_ID_REQUIRED",
            "event_id": "EVENT_ID_REQUIRED",
            "company_id": "COMPANY_ID_REQUIRED",
            "announcement_id": "ANNOUNCEMENT_ID_REQUIRED",
            "announcement_title": "ANNOUNCEMENT_TITLE_REQUIRED",
            "source_url": "SOURCE_URL_REQUIRED",
            "first_public_at": "FIRST_PUBLIC_AT_REQUIRED",
            "body_review_status": "BODY_REVIEW_STATUS_REQUIRED",
            "relevance_decision": "RELEVANCE_DECISION_REQUIRED",
            "severity_candidate": "SEVERITY_CANDIDATE_REQUIRED",
            "review_status": "REVIEW_STATUS_REQUIRED",
        },
    )
    relevance = str(row.get("relevance_decision") or "")
    severity = str(row.get("severity_candidate") or "")
    if relevance and relevance not in VALID_RELEVANCE:
        failures.append("INVALID_RELEVANCE_DECISION")
    if severity and severity not in VALID_GRADES:
        failures.append("INVALID_SEVERITY_CANDIDATE")
    if relevance in {"RELEVANT", "MINOR_RELEVANCE"}:
        if not row.get("original_quote"):
            failures.append("ORIGINAL_QUOTE_REQUIRED")
        if not row.get("body_locator"):
            failures.append("BODY_LOCATOR_REQUIRED")
        if not row.get("mechanism_zh"):
            failures.append("MECHANISM_REQUIRED")
        windows = row.get("affected_windows")
        if not isinstance(windows, Sequence) or isinstance(windows, (str, bytes)) or not windows:
            failures.append("AFFECTED_WINDOWS_REQUIRED")
        elif any(str(window) not in VALID_WINDOWS for window in windows):
            failures.append("INVALID_AFFECTED_WINDOW")
    if relevance == "IRRELEVANT" and not row.get("rejection_reason"):
        failures.append("REJECTION_REASON_REQUIRED")
    return failures


def validate_search_audit(row: Mapping[str, Any]) -> list[str]:
    failures = _required(
        row,
        {
            "mapping_id": "MAPPING_ID_REQUIRED",
            "window_start": "WINDOW_START_REQUIRED",
            "window_end": "WINDOW_END_REQUIRED",
            "title_snapshot_path": "TITLE_SNAPSHOT_PATH_REQUIRED",
            "source_providers": "SOURCE_PROVIDERS_REQUIRED",
            "query_categories": "QUERY_CATEGORIES_REQUIRED",
            "search_status": "SEARCH_STATUS_REQUIRED",
        },
    )
    candidate_count = int(row.get("candidate_count") or 0)
    reviewed_count = int(row.get("body_reviewed_count") or 0)
    if reviewed_count > candidate_count:
        failures.append("BODY_REVIEW_COUNT_EXCEEDS_CANDIDATES")
    if row.get("search_status") == "COMPLETE":
        if candidate_count != reviewed_count:
            failures.append("COMPLETE_SEARCH_HAS_UNREVIEWED_CANDIDATES")
        if row.get("unresolved_reasons"):
            failures.append("COMPLETE_SEARCH_HAS_UNRESOLVED_REASONS")
        if candidate_count == 0 and not row.get("negative_result_basis"):
            failures.append("NEGATIVE_RESULT_BASIS_REQUIRED")
    return failures


def validate_trading_review(row: Mapping[str, Any]) -> list[str]:
    failures = _required(
        row,
        {
            "mapping_id": "MAPPING_ID_REQUIRED",
            "overall_status": "OVERALL_STATUS_REQUIRED",
            "window_reviews": "WINDOW_REVIEWS_REQUIRED",
        },
    )
    window_reviews = row.get("window_reviews") or {}
    if set(window_reviews) != VALID_WINDOWS:
        failures.append("TRADING_WINDOW_COVERAGE_REQUIRED")
    return failures


def validate_counterevidence_review(row: Mapping[str, Any]) -> list[str]:
    failures = _required(
        row,
        {
            "mapping_id": "MAPPING_ID_REQUIRED",
            "review_status": "REVIEW_STATUS_REQUIRED",
        },
    )
    if not row.get("findings") and not row.get("negative_search_basis"):
        failures.append("COUNTEREVIDENCE_DISPOSITION_REQUIRED")
    return failures


def derive_grade(
    search_audit: Mapping[str, Any],
    body_reviews: Sequence[Mapping[str, Any]],
    trading_review: Mapping[str, Any],
    counterevidence: Sequence[Mapping[str, Any]],
) -> str:
    del counterevidence
    if search_audit.get("search_status") != "COMPLETE":
        return "UNRESOLVED"
    if int(search_audit.get("candidate_count") or 0) != int(
        search_audit.get("body_reviewed_count") or 0
    ):
        return "UNRESOLVED"
    if trading_review.get("overall_status") not in RESOLVED_TRADING:
        return "UNRESOLVED"
    if any(
        row.get("body_review_status") != "BODY_REVIEWED"
        or row.get("relevance_decision") == "UNRESOLVED"
        for row in body_reviews
    ):
        return "UNRESOLVED"
    severities = [
        str(row.get("severity_candidate"))
        for row in body_reviews
        if row.get("relevance_decision") in {"RELEVANT", "MINOR_RELEVANCE"}
    ]
    if "DOMINANT" in severities:
        return "DOMINANT"
    if "MATERIAL" in severities:
        return "MATERIAL"
    if severities:
        return "MINOR"
    return "CLEAN"
