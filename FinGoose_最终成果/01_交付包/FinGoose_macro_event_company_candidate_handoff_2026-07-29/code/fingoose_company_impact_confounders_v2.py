"""Suspension, confounder, and counterevidence gates for company impact v2."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


VALID_GRADES = {"CLEAN", "MINOR", "MATERIAL", "DOMINANT", "UNRESOLVED"}
CHALLENGE_GRADES = {"MATERIAL", "DOMINANT", "UNRESOLVED"}
GRADE_RANK = {"CLEAN": 0, "MINOR": 1, "MATERIAL": 2, "DOMINANT": 3, "UNRESOLVED": 4}
VALID_WINDOWS = {"T_MINUS_1", "T0", "D1", "D3", "D5", "D20"}


def classify_suspension(
    *,
    missing_bar: bool,
    exchange_notice: Mapping[str, Any] | None,
) -> str:
    if exchange_notice is None:
        return "UNVERIFIED"
    if exchange_notice.get("verification_status") != "VERIFIED":
        return "UNVERIFIED"
    notice_type = str(exchange_notice.get("notice_type", "")).upper()
    if notice_type == "SUSPENSION":
        return "CONFIRMED_SUSPENDED"
    if notice_type == "RESUMPTION":
        return "CONFIRMED_RESUMED"
    if notice_type == "NO_SUSPENSION":
        return "VERIFIED_CLEAR"
    return "UNVERIFIED"


def score_eligibility(grade: str) -> str:
    normalized = grade.upper()
    if normalized not in VALID_GRADES:
        raise ValueError(f"INVALID_CONFOUNDING_GRADE:{grade}")
    if normalized in CHALLENGE_GRADES:
        return "CHALLENGE_ONLY"
    return "PRIMARY_SCORE_ELIGIBLE"


def validate_confounder(item: Mapping[str, Any]) -> list[str]:
    failures: list[str] = []
    severity = str(item.get("severity", "")).upper()
    if severity not in VALID_GRADES:
        failures.append("VALID_SEVERITY_REQUIRED")
    windows = item.get("affected_windows")
    if not isinstance(windows, Sequence) or isinstance(windows, (str, bytes)) or not windows:
        failures.append("AFFECTED_WINDOWS_REQUIRED")
    elif any(str(window) not in VALID_WINDOWS for window in windows):
        failures.append("INVALID_AFFECTED_WINDOW")
    required = {
        "confounder_id": "CONFOUNDER_ID_REQUIRED",
        "occurred_at": "OCCURRED_AT_REQUIRED",
        "first_public_at": "FIRST_PUBLIC_AT_REQUIRED",
        "source_url": "SOURCE_URL_REQUIRED",
        "quote": "QUOTE_REQUIRED",
        "locator": "LOCATOR_REQUIRED",
        "mechanism": "MECHANISM_REQUIRED",
    }
    for field, failure in required.items():
        if not item.get(field):
            failures.append(failure)
    return failures


def _overall_grade(registered_confounders: Sequence[Mapping[str, Any]]) -> str:
    if not registered_confounders:
        return "UNRESOLVED"
    return max(
        (str(item["severity"]).upper() for item in registered_confounders),
        key=lambda grade: GRADE_RANK[grade],
    )


def build_company_confounder_record(
    *,
    mapping: Mapping[str, Any],
    market_window: Mapping[str, Any],
    registered_confounders: Sequence[Mapping[str, Any]],
    counterevidence: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    failures = {
        str(item.get("confounder_id", "UNKNOWN")): validate_confounder(item)
        for item in registered_confounders
    }
    failures = {item_id: errors for item_id, errors in failures.items() if errors}
    if failures:
        detail = ";".join(
            f"{item_id}={','.join(errors)}" for item_id, errors in sorted(failures.items())
        )
        raise ValueError(f"INVALID_CONFOUNDER:{detail}")

    overall_grade = _overall_grade(registered_confounders)
    suspension_status = str(
        market_window.get("suspension_alignment")
        or market_window.get("suspension_status")
        or "UNVERIFIED"
    )
    if suspension_status not in {
        "UNVERIFIED",
        "CONFIRMED_SUSPENDED",
        "CONFIRMED_RESUMED",
        "VERIFIED_CLEAR",
        "WINDOW_CONTAMINATED",
    }:
        suspension_status = "UNVERIFIED"
    if not registered_confounders:
        company_confounder_status = "SEARCH_PENDING"
    elif any(
        item.get("review_status") != "BODY_REVIEWED"
        for item in registered_confounders
    ):
        company_confounder_status = "CANDIDATES_REGISTERED_NEEDS_BODY_REVIEW"
    else:
        company_confounder_status = "REVIEWED"
    return {
        "company_confounder_id": f"company-confounder-{mapping['mapping_id']}",
        "mapping_id": mapping["mapping_id"],
        "event_id": mapping["event_id"],
        "company_id": mapping["company_id"],
        "company_code": mapping.get("company_code"),
        "anchor_id": mapping.get("anchor_id"),
        "window_scope": ["T_MINUS_1", "T0", "D1", "D3", "D5", "D20"],
        "suspension_status": suspension_status,
        "suspension_evidence": [],
        "company_confounder_status": company_confounder_status,
        "registered_confounders": [dict(item) for item in registered_confounders],
        "overall_grade": overall_grade,
        "score_eligibility": score_eligibility(overall_grade),
        "counterevidence_status": (
            "REGISTERED" if counterevidence else "SEARCH_PENDING"
        ),
        "counterevidence": [dict(item) for item in counterevidence],
        "search_scope": {
            "exchange_suspension_notices": "PENDING",
            "company_announcements_T_MINUS_1_to_D20": "PENDING",
            "company_specific_counterevidence": "PENDING",
        },
        "formal_ready": False,
        "causal_attribution_allowed": False,
    }
