"""Final task-aware content validation."""

from __future__ import annotations

from collections import Counter
import re
from typing import Any, Mapping

from .answer_renderer import PLACEHOLDER_TOKENS
from .validation_impl_003 import validate_datasets as _validate_v3, validate_reasoning_chain

HORIZONS = ("IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM")
EVENT_SECTIONS = ("结论", "来源事实", "即时影响", "短期影响", "中期影响", "公司影响", "行情验证", "证据边界")
QA_SECTIONS = ("直接回答", "来源事实", "研究推断", "即时影响", "短期影响", "中期影响", "行情验证", "证据边界")
MOJIBAKE_TOKENS = ("浣犳槸", "浜嬩欢", "寰呰ˉ鍏呴檲杩", "â")


def _error(code, sample_id, detail):
    return {"code": code, "sample_id": str(sample_id), "detail": detail}


def _check(sample: Mapping[str, Any]) -> list[dict[str, str]]:
    metadata = sample.get("metadata") or {}
    content = metadata.get("research_content")
    if not isinstance(content, Mapping):
        return []
    sample_id = sample.get("sample_id")
    task = sample.get("task_type")
    answer = str((sample.get("messages") or [{}, {}, {}])[2].get("content") or "")
    errors = []
    message_text = "\n".join(
        str(message.get("content") or "")
        for message in sample.get("messages") or []
        if isinstance(message, Mapping)
    )
    if any(token in message_text for token in MOJIBAKE_TOKENS):
        errors.append(_error("TEXT_ENCODING_GARBLED", sample_id, "UTF-8 mojibake token"))
    if metadata.get("research_content_version") != "research-content-v1":
        errors.append(_error("CONTENT_SCHEMA_MISSING", sample_id, "research_content_version"))
    if any(token in answer for token in PLACEHOLDER_TOKENS):
        errors.append(_error("ANSWER_PLACEHOLDER", sample_id, "placeholder token"))
    if task == "EVENT_ANALYSIS":
        if content.get("schema_version") != "research-content-v1":
            errors.append(_error("CONTENT_SCHEMA_MISSING", sample_id, "schema_version"))
        horizons = content.get("horizon_analysis") or {}
        texts = [str((horizons.get(name) or {}).get("summary_zh") or "").strip() for name in HORIZONS]
        if any(not text for text in texts):
            errors.append(_error("CONTENT_HORIZON_MISSING", sample_id, "three horizons"))
        elif len(set(texts)) != 3:
            errors.append(_error("CONTENT_HORIZON_DUPLICATE", sample_id, "duplicate horizon summary"))
        if any(section not in answer for section in EVENT_SECTIONS):
            errors.append(_error("ANSWER_REQUIRED_SECTION_MISSING", sample_id, "event sections"))
        registry = {str(row.get("evidence_id")) for row in metadata.get("evidence_registry") or [] if isinstance(row, Mapping) and row.get("evidence_id")}
        wanted = set(str(value) for value in content.get("primary_answer_evidence_ids") or [])
        if not wanted <= registry:
            errors.append(_error("CONTENT_EVIDENCE_UNKNOWN", sample_id, ",".join(sorted(wanted - registry))))
    elif task == "INDUSTRY_IMPACT":
        directions = content.get("horizon_directions") or {}
        if any(not directions.get(name) for name in HORIZONS):
            errors.append(_error("CONTENT_HORIZON_MISSING", sample_id, "industry directions"))
        if content.get("event_industry_mapping_id") not in set(metadata.get("related_industry_ids") or []):
            errors.append(_error("CONTENT_SCOPE_MISMATCH", sample_id, "industry"))
    elif task == "COMPANY_IMPACT":
        directions = content.get("horizon_directions") or {}
        if any(not directions.get(name) for name in HORIZONS):
            errors.append(_error("CONTENT_HORIZON_MISSING", sample_id, "company directions"))
        if content.get("company_code") not in set(metadata.get("related_company_codes") or []):
            errors.append(_error("CONTENT_SCOPE_MISMATCH", sample_id, "company"))
    elif task == "EVENT_QA" and not content.get("direct_answer_zh"):
        errors.append(_error("CONTENT_REQUIRED_FIELD_MISSING", sample_id, "direct_answer_zh"))
    elif task == "EVENT_QA":
        if any(section not in answer for section in QA_SECTIONS):
            errors.append(_error("ANSWER_REQUIRED_SECTION_MISSING", sample_id, "qa sections"))
        registry = {
            str(row.get("evidence_id")): row
            for row in metadata.get("evidence_registry") or []
            if isinstance(row, Mapping) and row.get("evidence_id")
        }
        if registry and any(not bool(row.get("missing")) for row in registry.values()) and not content.get("official_facts"):
            errors.append(_error("CONTENT_QA_OFFICIAL_FACTS_MISSING", sample_id, "source facts were dropped from answer content"))
        if content.get("official_facts"):
            fact_ids = {
                str(row.get("evidence_id"))
                for row in content.get("official_facts") or []
                if isinstance(row, Mapping) and row.get("evidence_id")
            }
            unknown = fact_ids - set(registry)
            if unknown:
                errors.append(_error("CONTENT_EVIDENCE_UNKNOWN", sample_id, ",".join(sorted(unknown))))
        parent_refs = {str(value) for value in metadata.get("parent_chain_refs") or []}
        related_industries = {str(value) for value in metadata.get("related_industry_ids") or []}
        if any(value.startswith("event-industry-") for value in parent_refs) and not related_industries:
            errors.append(_error("CONTENT_QA_SCOPE_MISSING", sample_id, "industry links were not projected"))
        if str(content.get("task_type") or "").upper() == "MARKET_VALIDATION":
            direct = str(content.get("direct_answer_zh") or "")
            mentions_market_verdict = any(token in direct for token in ("支持", "削弱", "无法区分", "数据缺失"))
            calculated = content.get("calculated_facts") or []
            if mentions_market_verdict and not calculated:
                errors.append(_error("CONTENT_QA_CALCULATED_FACTS_MISSING", sample_id, "market verdict has no calculated facts"))
            if calculated:
                observed = Counter(str(row.get("overall_verdict") or "").upper() for row in calculated if isinstance(row, Mapping))
                match = re.search(r"支持\s*(\d+).*?削弱\s*(\d+).*?无法区分\s*(\d+).*?数据缺失\s*(\d+)", direct)
                if match:
                    expected = dict(zip(("SUPPORTS", "WEAKENS", "INDISTINGUISHABLE", "DATA_MISSING"), map(int, match.groups())))
                    if any(observed.get(key, 0) != value for key, value in expected.items()):
                        errors.append(_error("CONTENT_MARKET_NODE_MISMATCH", sample_id, "market verdict counts do not match calculated facts"))
    boundary_required = content.get("formal_ready") is False or "REVIEW" in str(content.get("review_status") or "").upper() or content.get("causal_attribution_allowed") is False
    if boundary_required and not any(token in answer for token in ("待人工审核", "候选", "不允许确定性", "因果边界")):
        errors.append(_error("ANSWER_REVIEW_BOUNDARY_MISSING", sample_id, "review boundary"))
    return errors


def validate_datasets(unified_events, sft_samples, expected_events, expected_task_types=None):
    report = _validate_v3(unified_events, sft_samples, expected_events, expected_task_types)
    content_errors = [error for sample in sft_samples for error in _check(sample)]
    report["errors"] = list(report.get("errors") or []) + content_errors
    report["valid"] = not report["errors"]
    sections = Counter()
    placeholder_count = 0
    complete_horizons = 0
    boundary_count = 0
    for sample in sft_samples:
        metadata = sample.get("metadata") or {}
        if not metadata.get("research_content"):
            continue
        answer = str(sample.get("messages", [{}, {}, {}])[2].get("content") or "")
        for section in EVENT_SECTIONS:
            if section in answer:
                sections[section] += 1
        if any(token in answer for token in PLACEHOLDER_TOKENS):
            placeholder_count += 1
        content = metadata["research_content"]
        horizons = content.get("horizon_analysis") or content.get("horizon_directions") or content.get("horizon_reasoning_zh") or {}
        if all(horizons.get(name) for name in HORIZONS):
            complete_horizons += 1
        if any(token in answer for token in ("待人工审核", "候选", "不允许确定性", "因果边界")):
            boundary_count += 1
    report["content_quality_stats"] = {
        "content_contract_count": len(sft_samples),
        "complete_horizon_count": complete_horizons,
        "placeholder_sample_count": placeholder_count,
        "ui_parity_pass_count": len(sft_samples) - len({error["sample_id"] for error in content_errors}),
        "answer_section_coverage": dict(sorted(sections.items())),
        "review_boundary_count": boundary_count,
    }
    return report


__all__ = ["validate_datasets", "validate_reasoning_chain"]
