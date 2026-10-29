"""Validation gates for unified FinGoose and projected SFT datasets."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


EXPECTED_ROLES = ["system", "user", "assistant"]
ALLOWED_SPLITS = {"train", "validation", "test"}
ALLOWED_TASK_TYPES = {
    "EVENT_ANALYSIS",
    "INDUSTRY_IMPACT",
    "COMPANY_IMPACT",
    "EVENT_QA",
}
FORBIDDEN_TOKENS = (
    "evaluator_only",
    "hidden",
    "benchmark_labels",
)
METADATA_LIST_FIELDS = (
    "related_industry_ids",
    "related_company_codes",
    "evidence_ids",
    "source_record_ids",
)
TRUNCATION_MARKER = "[内容已按训练长度上限截断]"
MAX_MESSAGE_CHARS = 2000


def _issue(code: str, message: str, record_id: str | None = None) -> dict[str, Any]:
    issue: dict[str, Any] = {"code": code, "message_zh": message}
    if record_id:
        issue["record_id"] = record_id
    return issue


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if any(token in key.lower() for token in FORBIDDEN_TOKENS):
                return True
            if _contains_forbidden(child):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_forbidden(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return any(token in lowered for token in FORBIDDEN_TOKENS)
    return False


def validate_datasets(
    unified_events: list[dict[str, Any]],
    sft_samples: list[dict[str, Any]],
    expected_events: set[str],
    expected_task_types: set[str] | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    unified_ids = [row.get("event_id") for row in unified_events]
    duplicate_events = sorted(
        event_id for event_id, count in Counter(unified_ids).items() if count > 1
    )
    for event_id in duplicate_events:
        errors.append(
            _issue("DUPLICATE_EVENT_ID", "统一主数据存在重复事件。", event_id)
        )

    actual_events = {event_id for event_id in unified_ids if event_id}
    event_references = {
        event.get("event_id"): {
            "industry_ids": {
                industry.get("event_industry_mapping_id")
                for industry in event.get("industries", [])
                if industry.get("event_industry_mapping_id")
            },
            "company_codes": {
                company.get("company_code")
                for company in event.get("companies", [])
                if company.get("company_code")
            },
        }
        for event in unified_events
        if event.get("event_id")
    }
    missing_events = sorted(expected_events - actual_events)
    unexpected_events = sorted(actual_events - expected_events)
    if missing_events:
        errors.append(
            _issue(
                "MISSING_EVENT_COVERAGE",
                f"统一主数据缺少事件：{', '.join(missing_events)}",
            )
        )
    if unexpected_events:
        errors.append(
            _issue(
                "UNEXPECTED_EVENT",
                f"统一主数据包含未配置事件：{', '.join(unexpected_events)}",
            )
        )

    for event in unified_events:
        event_id = event.get("event_id")
        industry_sw1_ids = {
            str(industry.get("mapping", {}).get("sw1_id"))
            for industry in event.get("industries", [])
            if industry.get("mapping", {}).get("sw1_id")
        }
        for company in event.get("companies", []):
            classification = company.get("mapping", {}).get("industry_classification") or {}
            sw1_id = classification.get("sw1_id")
            if sw1_id and str(sw1_id) not in industry_sw1_ids:
                warnings.append(
                    _issue(
                        "UNMATCHED_COMPANY_INDUSTRY",
                        "公司的申万一级行业未在该事件行业映射中找到。",
                        company.get("mapping_id"),
                    )
                )
        for qa in event.get("qa", []):
            if not qa.get("answer"):
                errors.append(
                    _issue(
                        "MISSING_QA_ANSWER", "统一事件中的问答缺少答案。", qa.get("case_id")
                    )
                )

    sample_ids: set[str] = set()
    event_splits: dict[str, set[str]] = defaultdict(set)
    task_counts: Counter[str] = Counter()
    event_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()

    for sample in sft_samples:
        sample_id = sample.get("sample_id")
        event_id = sample.get("event_id")
        task_type = sample.get("task_type")
        split = sample.get("split")
        if not sample_id:
            errors.append(_issue("MISSING_SAMPLE_ID", "SFT 样本缺少 sample_id。"))
        elif sample_id in sample_ids:
            errors.append(
                _issue("DUPLICATE_SAMPLE_ID", "SFT 样本 ID 重复。", sample_id)
            )
        else:
            sample_ids.add(sample_id)

        if event_id not in actual_events:
            errors.append(
                _issue(
                    "UNKNOWN_SAMPLE_EVENT",
                    "SFT 样本引用了统一主数据中不存在的事件。",
                    sample_id,
                )
            )
        if event_id and split:
            event_splits[event_id].add(split)
        if split not in ALLOWED_SPLITS:
            errors.append(
                _issue("INVALID_SPLIT", f"不支持的数据分区：{split}", sample_id)
            )
        if task_type not in ALLOWED_TASK_TYPES:
            errors.append(
                _issue("INVALID_TASK_TYPE", f"不支持的任务类型：{task_type}", sample_id)
            )

        messages = sample.get("messages")
        roles = (
            [
                message.get("role") if isinstance(message, dict) else None
                for message in messages
            ]
            if isinstance(messages, list)
            else []
        )
        if roles != EXPECTED_ROLES:
            errors.append(
                _issue(
                    "INVALID_MESSAGE_ROLES",
                    "messages 必须依次包含 system、user、assistant。",
                    sample_id,
                )
            )
        else:
            for index, message in enumerate(messages):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    continue
                if index == 2 and isinstance(content, str):
                    errors.append(
                        _issue(
                            "EMPTY_ASSISTANT_CONTENT",
                            "assistant 答案不能为空。",
                            sample_id,
                        )
                    )
                else:
                    errors.append(
                        _issue(
                            "INVALID_MESSAGE_CONTENT",
                            "system、user、assistant 的 content 必须是非空字符串。",
                            sample_id,
                        )
                    )

            contents = [message["content"] for message in messages]
            if all(isinstance(content, str) for content in contents):
                if any(TRUNCATION_MARKER in content for content in contents):
                    errors.append(
                        _issue(
                            "HARD_TRUNCATION_MARKER",
                            "训练消息包含硬截断标记。",
                            sample_id,
                        )
                    )
                if sum(len(content) for content in contents) > MAX_MESSAGE_CHARS:
                    errors.append(
                        _issue(
                            "MESSAGE_LENGTH_EXCEEDED",
                            f"训练消息总字符数超过 {MAX_MESSAGE_CHARS}。",
                            sample_id,
                        )
                    )

        metadata = sample.get("metadata")
        invalid_metadata_fields: set[str] = set()
        if not isinstance(metadata, dict):
            errors.append(
                _issue(
                    "INVALID_METADATA_LIST",
                    "metadata 必须包含四个字符串列表字段。",
                    sample_id,
                )
            )
            metadata = {}
            invalid_metadata_fields.update(METADATA_LIST_FIELDS)
        for field in METADATA_LIST_FIELDS:
            value = metadata.get(field)
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                invalid_metadata_fields.add(field)
                errors.append(
                    _issue(
                        "INVALID_METADATA_LIST",
                        f"metadata.{field} 必须是字符串列表。",
                        sample_id,
                    )
                )

        references = event_references.get(event_id, {})
        if "related_industry_ids" not in invalid_metadata_fields:
            unknown_industries = sorted(
                set(metadata["related_industry_ids"])
                - references.get("industry_ids", set())
            )
            if unknown_industries:
                errors.append(
                    _issue(
                        "UNKNOWN_RELATED_INDUSTRY",
                        f"样本引用了同一事件中不存在的行业：{', '.join(unknown_industries)}",
                        sample_id,
                    )
                )
        if "related_company_codes" not in invalid_metadata_fields:
            unknown_companies = sorted(
                set(metadata["related_company_codes"])
                - references.get("company_codes", set())
            )
            if unknown_companies:
                errors.append(
                    _issue(
                        "UNKNOWN_RELATED_COMPANY",
                        f"样本引用了同一事件中不存在的公司：{', '.join(unknown_companies)}",
                        sample_id,
                    )
                )
        if _contains_forbidden(sample):
            errors.append(
                _issue(
                    "FORBIDDEN_HIDDEN_DATA",
                    "训练样本包含隐藏评测字段或受限路径。",
                    sample_id,
                )
            )

        if task_type:
            task_counts[task_type] += 1
        if event_id:
            event_counts[event_id] += 1
        if split:
            split_counts[split] += 1

    for event_id, split_names in sorted(event_splits.items()):
        if len(split_names) > 1:
            errors.append(
                _issue(
                    "EVENT_SPLIT_LEAKAGE",
                    f"同一事件跨越多个数据分区：{', '.join(sorted(split_names))}",
                    event_id,
                )
            )

    missing_sample_events = sorted(expected_events - set(event_counts))
    if missing_sample_events:
        errors.append(
            _issue(
                "MISSING_SAMPLE_EVENT_COVERAGE",
                f"SFT 数据缺少事件样本：{', '.join(missing_sample_events)}",
            )
        )

    required_tasks = expected_task_types or set()
    missing_tasks = sorted(required_tasks - set(task_counts))
    if missing_tasks:
        errors.append(
            _issue(
                "MISSING_TASK_COVERAGE",
                f"SFT 数据缺少任务类型：{', '.join(missing_tasks)}",
            )
        )

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "unified_events": len(unified_events),
            "sft_samples": len(sft_samples),
        },
        "task_counts": dict(sorted(task_counts.items())),
        "event_counts": dict(sorted(event_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
    }
