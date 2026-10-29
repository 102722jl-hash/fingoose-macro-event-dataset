"""Content-quality and UI/metadata/assistant consistency gates."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from .answer_renderer import PLACEHOLDER_TOKENS
from .validation_impl_003 import validate_datasets as _validate_v3
from .validation_impl_003 import validate_reasoning_chain as _validate_chain_v3

CONTENT_ERROR_CODES = {
    "CONTENT_SCHEMA_MISSING", "CONTENT_REQUIRED_FIELD_MISSING", "CONTENT_PLACEHOLDER",
    "CONTENT_HORIZON_MISSING", "CONTENT_HORIZON_DUPLICATE", "CONTENT_EVIDENCE_UNKNOWN",
    "CONTENT_SCOPE_MISMATCH", "CONTENT_MARKET_NODE_MISMATCH", "CONTENT_UI_PARITY_MISMATCH",
    "ANSWER_REQUIRED_SECTION_MISSING", "ANSWER_PLACEHOLDER", "ANSWER_EVIDENCE_UNKNOWN",
    "ANSWER_REVIEW_BOUNDARY_MISSING", "REASONING_MAIN_PATH_TOO_SHALLOW", "REASONING_PRECONDITION_IS_FINAL",
}
REQUIRED_CONTENT_FIELDS = {"schema_version", "event_id", "horizon_analysis", "evidence_registry", "boundaries"}
HORIZONS = ("IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM")
REQUIRED_ANSWER_SECTIONS = ("结论", "来源事实", "即时影响", "短期影响", "中期影响", "行情验证", "证据边界")


def _error(code: str, sample_id: str, detail: str) -> dict[str, str]:
    return {"code": code, "sample_id": sample_id, "detail": detail}


def validate_reasoning_chain(metadata: Mapping[str, Any], task_type: str | None = None) -> list[str]:
    return _validate_chain_v3(metadata, task_type)


def _content_errors(sample: Mapping[str, Any], unified: Mapping[str, Any]) -> list[dict[str, str]]:
    metadata = sample.get("metadata") or {}
    content = metadata.get("research_content")
    if not isinstance(content, Mapping):
        return []
    sample_id = str(sample.get("sample_id"))
    errors: list[dict[str, str]] = []
    missing = REQUIRED_CONTENT_FIELDS - set(content)
    if missing:
        errors.append(_error("CONTENT_REQUIRED_FIELD_MISSING", sample_id, ",".join(sorted(missing))))
        return errors
    if content.get("schema_version") != "research-content-v1":
        errors.append(_error("CONTENT_SCHEMA_MISSING", sample_id, "schema_version"))
    horizons = content.get("horizon_analysis") or {}
    texts = [str((horizons.get(name) or {}).get("summary_zh") or "").strip() for name in HORIZONS]
    if any(not text for text in texts):
        errors.append(_error("CONTENT_HORIZON_MISSING", sample_id, "three horizon summaries required"))
    elif len(set(texts)) != len(texts):
        errors.append(_error("CONTENT_HORIZON_DUPLICATE", sample_id, "horizon summaries duplicated"))
    registry = {str(row.get("evidence_id")) for row in metadata.get("evidence_registry") or [] if isinstance(row, Mapping) and row.get("evidence_id")}
    content_ids = set(str(value) for value in content.get("answer_evidence_ids") or [])
    if not content_ids <= registry:
        errors.append(_error("CONTENT_EVIDENCE_UNKNOWN", sample_id, ",".join(sorted(content_ids - registry))))
    task_type = sample.get("task_type")
    if task_type == "INDUSTRY_IMPACT":
        related = set(metadata.get("related_industry_ids") or [])
        if content.get("event_industry_mapping_id") not in related:
            errors.append(_error("CONTENT_SCOPE_MISMATCH", sample_id, "industry scope"))
    if task_type == "COMPANY_IMPACT":
        related = set(metadata.get("related_company_codes") or [])
        if content.get("company_code") not in related:
            errors.append(_error("CONTENT_SCOPE_MISMATCH", sample_id, "company scope"))
    answer = str((sample.get("messages") or [{}, {}, {}])[2].get("content") or "")
    if any(token in answer for token in PLACEHOLDER_TOKENS):
        errors.append(_error("ANSWER_PLACEHOLDER", sample_id, "placeholder token"))
    if task_type == "EVENT_ANALYSIS" and any(section not in answer for section in REQUIRED_ANSWER_SECTIONS):
        errors.append(_error("ANSWER_REQUIRED_SECTION_MISSING", sample_id, "required section"))
    answer_ids = {str(row.get("evidence_id")) for row in metadata.get("evidence_registry") or [] if isinstance(row, Mapping) and row.get("evidence_id")}
    referenced = {value for value in answer_ids if value in answer}
    if not referenced and content.get("answer_evidence_ids"):
        errors.append(_error("ANSWER_EVIDENCE_UNKNOWN", sample_id, "assistant has no registry evidence id"))
    boundary_required = (
        content.get("formal_ready") is False
        or "REVIEW" in str(content.get("review_status") or "").upper()
        or content.get("causal_attribution_allowed") is False
    )
    if boundary_required and not any(token in answer for token in ("待人工审核", "候选", "不允许确定性", "因果边界")):
        errors.append(_error("ANSWER_REVIEW_BOUNDARY_MISSING", sample_id, "review boundary"))
    return errors


def validate_datasets(unified_events, sft_samples, expected_events, expected_task_types=None):
    report = _validate_v3(unified_events, sft_samples, expected_events, expected_task_types)
    errors = list(report.get("errors") or [])
    unified_by_id = {str(row.get("event_id")): row for row in unified_events}
    content_errors: list[dict[str, str]] = []
    section_coverage: Counter[str] = Counter()
    complete_horizon_count = 0
    placeholder_count = 0
    parity_count = 0
    boundary_count = 0
    for sample in sft_samples:
        event = unified_by_id.get(str(sample.get("event_id")), {})
        local = _content_errors(sample, event)
        content_errors.extend(local)
        if sample.get("metadata", {}).get("research_content"):
            content = sample["metadata"]["research_content"]
            horizons = content.get("horizon_analysis") or {}
            if all((horizons.get(name) or {}).get("summary_zh") for name in HORIZONS):
                complete_horizon_count += 1
            answer = str((sample.get("messages") or [{}, {}, {}])[2].get("content") or "")
            if any(token in answer for token in PLACEHOLDER_TOKENS):
                placeholder_count += 1
            for section in REQUIRED_ANSWER_SECTIONS:
                if section in answer:
                    section_coverage[section] += 1
            if any(token in answer for token in ("待人工审核", "候选", "不允许确定性", "因果边界")):
                boundary_count += 1
            parity_count += 1
    report["errors"] = errors + content_errors
    report["valid"] = not report["errors"]
    report["content_quality_stats"] = {
        "content_contract_count": parity_count,
        "complete_horizon_count": complete_horizon_count,
        "placeholder_sample_count": placeholder_count,
        "ui_parity_pass_count": parity_count - len({error["sample_id"] for error in content_errors if error["code"].startswith("CONTENT_")}),
        "answer_section_coverage": dict(sorted(section_coverage.items())),
        "review_boundary_count": boundary_count,
    }
    return report


__all__ = ["CONTENT_ERROR_CODES", "validate_datasets", "validate_reasoning_chain"]
