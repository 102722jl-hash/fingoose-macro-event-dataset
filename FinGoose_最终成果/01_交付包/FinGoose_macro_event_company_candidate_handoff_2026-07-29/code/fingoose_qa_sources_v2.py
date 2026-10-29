"""Cutoff-safe snapshots for evidence used by the event research Q&A."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from fingoose_industry_source_snapshot_v2 import _quote_match_text, payload_text


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone is required")
    return parsed.astimezone(timezone.utc)


def _result_base(target: Mapping[str, Any], accessed_at: str) -> dict[str, Any]:
    return {
        **dict(target),
        "accessed_at": accessed_at,
        "snapshot_path": None,
        "snapshot_sha256": None,
        "verified_quote": None,
        "failure_reason": None,
    }


def snapshot_source(
    target: Mapping[str, Any],
    *,
    cutoff_at: str,
    output_root: Path,
    fetch_bytes: Callable[[str], bytes],
    accessed_at: str,
) -> dict[str, Any]:
    """Fetch one source only when its publication time is cutoff eligible."""
    result = _result_base(target, accessed_at)
    first_public_at = target.get("first_public_at")
    if not first_public_at:
        result["fetch_status"] = "PUBLICATION_TIME_UNVERIFIED"
        result["failure_reason"] = "MISSING_FIRST_PUBLIC_AT"
        return result

    try:
        published = _parse_datetime(str(first_public_at))
        cutoff = _parse_datetime(cutoff_at)
    except (TypeError, ValueError) as exc:
        result["fetch_status"] = "PUBLICATION_TIME_UNVERIFIED"
        result["failure_reason"] = f"INVALID_PUBLICATION_TIME:{type(exc).__name__}:{exc}"
        return result

    if published > cutoff:
        result["fetch_status"] = "POST_CUTOFF_EXCLUDED"
        result["failure_reason"] = "FIRST_PUBLIC_AT_AFTER_CUTOFF"
        return result

    try:
        payload = fetch_bytes(str(target["source_url"]))
    except Exception as exc:
        result["fetch_status"] = "FETCH_FAILED"
        result["failure_reason"] = f"{type(exc).__name__}:{exc}"
        return result

    suffix = ".pdf" if target.get("media_type") == "application/pdf" else ".html"
    relative = Path("sources") / "snapshots" / f"{target['source_id']}{suffix}"
    destination = output_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    result["snapshot_path"] = relative.as_posix()
    result["snapshot_sha256"] = hashlib.sha256(payload).hexdigest()

    try:
        text = payload_text(payload, str(target.get("media_type") or "text/html"))
    except Exception as exc:
        result["fetch_status"] = "CONTENT_MISMATCH"
        result["failure_reason"] = f"CONTENT_PARSE_FAILED:{type(exc).__name__}:{exc}"
        return result

    quote = " ".join(str(target.get("required_quote") or "").split())
    if quote and _quote_match_text(quote) in _quote_match_text(text):
        result["fetch_status"] = "RETRIEVED_QUOTE_VERIFIED"
        result["verified_quote"] = quote
        return result

    result["fetch_status"] = "CONTENT_MISMATCH"
    result["failure_reason"] = "REQUIRED_QUOTE_NOT_FOUND"
    return result
