"""Project unified FinGoose event records into standard SFT messages."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any


SYSTEM_PROMPT = (
    "你是宏观事件、行业与公司影响研究助手。回答必须区分来源事实、计算事实和研究推断，"
    "明确即时、短期与中期影响；证据不足时必须表达不确定性，不得制造来源或投资建议。"
)
FORBIDDEN_KEY_PARTS = ("hidden", "evaluator_only", "benchmark_labels")
MAX_USER_CHARS = 800
MAX_ASSISTANT_CHARS = 1250
COMPACT_DROP_KEYS = {
    "calculation_basis",
    "candidate_binding_ids",
    "content_sha256",
    "continuous_window",
    "dataset_version",
    "formal_ready",
    "matched_terms",
    "observations",
    "release_tier",
    "sha_gate",
    "snapshot_path",
    "snapshot_sha256",
    "source_snapshot_path",
    "source_snapshot_sha256",
}
COMPACT_PRIORITY_KEYS = (
    "evidence_id",
    "source_id",
    "title",
    "publisher",
    "published_at",
    "fact",
    "fact_zh",
    "summary",
    "evidence_summary",
    "direction",
    "status",
    "node_type",
    "statement",
    "value",
    "value_zh",
    "relation",
    "from_node_id",
    "to_node_id",
    "source_url",
    "original_quote",
)


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize(item)
            for key, item in value.items()
            if not any(token in key.lower() for token in FORBIDDEN_KEY_PARTS)
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return deepcopy(value)


def _compact(value: Any, depth: int = 0) -> Any:
    if depth >= 5:
        return "[嵌套内容省略]"
    if isinstance(value, str):
        return value if len(value) <= 100 else value[:97] + "..."
    if isinstance(value, list):
        compacted = [_compact(item, depth + 1) for item in value[:2]]
        if len(value) > 2:
            compacted.append({"omitted_count": len(value) - 2})
        return compacted
    if isinstance(value, dict):
        available = [key for key in value if key not in COMPACT_DROP_KEYS]
        ordered = [key for key in COMPACT_PRIORITY_KEYS if key in available]
        ordered.extend(key for key in available if key not in ordered)
        selected = ordered[:6]
        result = {key: _compact(value[key], depth + 1) for key in selected}
        if len(available) > len(selected):
            result["omitted_field_count"] = len(available) - len(selected)
        return result
    return value


def _json(value: Any) -> str:
    return json.dumps(_compact(_sanitize(value)), ensure_ascii=False, sort_keys=True)


def _short_text(value: Any, max_chars: int = 120) -> Any:
    if not isinstance(value, str):
        return value
    value = value.strip()
    return value if len(value) <= max_chars else value[: max_chars - 3].rstrip() + "..."


def _short_evidence(records: Any, limit: int = 1) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        return []
    result = []
    for record in records[:limit]:
        if not isinstance(record, dict):
            result.append({"summary": _compact(record)})
            continue
        summary = (
            record.get("fact_zh")
            or record.get("evidence_summary")
            or record.get("summary")
            or record.get("original_quote")
        )
        result.append(
            {
                key: value
                for key, value in {
                    "evidence_id": record.get("evidence_id") or record.get("source_id"),
                    "publisher": record.get("publisher") or record.get("issuer"),
                    "published_at": record.get("published_at") or record.get("first_public_at"),
                    "summary": _short_text(summary, 100),
                }.items()
                if value not in (None, "", [])
            }
        )
    if len(records) > limit:
        result.append({"omitted_count": len(records) - limit})
    return result


def _short_milestones(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "fact": _short_text(row.get("fact"), 120),
            "occurred_at": row.get("occurred_at"),
            "evidence_ids": [
                source.get("evidence_id")
                for source in row.get("sources", [])
                if isinstance(source, dict) and source.get("evidence_id")
            ][:2],
        }
        for row in records[:2]
    ]


def _short_market(records: Any, limit: int = 2) -> Any:
    if isinstance(records, list):
        result = []
        for row in records[:limit]:
            if not isinstance(row, dict):
                continue
            windows = row.get("windows") or row.get("fixed_windows") or {}
            short_windows = {}
            if isinstance(windows, dict):
                for name in ("D1", "D3", "SHORT", "D20", "MEDIUM"):
                    value = windows.get(name)
                    if isinstance(value, dict):
                        short_windows[name] = {
                            key: value.get(key)
                            for key in (
                                "date",
                                "raw_change",
                                "relative_change",
                                "return",
                                "direction",
                            )
                            if value.get(key) is not None
                        }
            result.append(
                {
                    key: value
                    for key, value in {
                        "series_id": row.get("series_id"),
                        "anchor_date": row.get("anchor_date"),
                        "window_status": row.get("window_status"),
                        "windows": short_windows,
                    }.items()
                    if value not in (None, "", {})
                }
            )
        return result
    if isinstance(records, dict):
        return _short_market([records], limit=1)[0] if records else {}
    return records


def _short_graphs(graphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for graph in graphs[:1]:
        nodes = [
            {
                key: _short_text(node.get(key), 110)
                for key in ("node_type", "statement_zh", "statement")
                if node.get(key) not in (None, "", [])
            }
            for node in graph.get("nodes", [])[:3]
        ]
        result.append({"nodes": nodes})
    return result


def _short_node(node: Any) -> dict[str, Any]:
    if not isinstance(node, dict):
        return {"statement": _short_text(str(node), 110)}
    statement = (
        node.get("statement_zh")
        or node.get("statement")
        or node.get("value_zh")
        or node.get("value")
        or node.get("inference_zh")
    )
    return {
        key: value
        for key, value in {
            "node_type": node.get("node_type_zh") or node.get("node_type"),
            "statement": _short_text(statement, 110),
            "status": node.get("status") or node.get("claim_kind"),
        }.items()
        if value not in (None, "", [])
    }


def _short_chain(chain: Any) -> Any:
    if isinstance(chain, list):
        return [_short_node(node) for node in chain[:3]]
    if not isinstance(chain, dict):
        return chain
    nodes = [_short_node(node) for node in chain.get("nodes", [])[:3]]
    return {
        key: value
        for key, value in {
            "chain_status": chain.get("chain_status"),
            "horizon_directions": chain.get("horizon_directions"),
            "conditions": (chain.get("conditions") or chain.get("conditions_zh") or [])[:1],
            "nodes": nodes,
        }.items()
        if value not in (None, "", [], {})
    }


def _short_company_mapping(mapping: Any) -> dict[str, Any]:
    if not isinstance(mapping, dict):
        return {}
    classification = mapping.get("industry_classification") or {}
    return {
        key: value
        for key, value in {
            "company_code": mapping.get("company_code"),
            "company_name": mapping.get("company_name"),
            "industry": mapping.get("industry"),
            "sw1_id": classification.get("sw1_id"),
            "sw1_name": classification.get("sw1_name"),
            "binding_selection_status": mapping.get("binding_selection_status"),
            "selection_cutoff_at": mapping.get("selection_cutoff_at"),
        }.items()
        if value not in (None, "", [])
    }


def _short_direction(direction: Any) -> dict[str, Any]:
    if not isinstance(direction, dict):
        return {}
    return {
        key: _compact(value)
        for key, value in {
            "mechanism": _short_text(direction.get("mechanism"), 150),
            "horizons": direction.get("horizons") or {
                key: value.get("direction")
                for key, value in (direction.get("horizon_reviews") or {}).items()
                if isinstance(value, dict) and value.get("direction")
            },
            "conditions": (direction.get("conditions") or [])[:1],
            "invalidation_conditions": (direction.get("invalidation_conditions") or [])[:1],
            "confidence": direction.get("confidence"),
            "review_status": direction.get("review_status"),
        }.items()
        if value not in (None, "", [], {})
    }


def _short_items(value: Any, limit: int = 1, text_limit: int = 120) -> list[Any]:
    records = value if isinstance(value, list) else [value]
    result: list[Any] = []
    text_keys = (
        "fact_zh",
        "fact",
        "statement_zh",
        "inference_zh",
        "calculation_zh",
        "description_zh",
        "factor_zh",
        "conclusion_zh",
        "reason_zh",
        "summary",
        "value_zh",
    )
    for record in records[:limit]:
        if isinstance(record, str):
            result.append(_short_text(record, text_limit))
            continue
        if not isinstance(record, dict):
            result.append(_short_text(str(record), text_limit))
            continue
        short = {
            key: _short_text(record.get(key), text_limit)
            for key in text_keys
            if record.get(key) not in (None, "", [])
        }
        if record.get("evidence_id"):
            short["evidence_id"] = record["evidence_id"]
        result.append(short or _compact(record))
    return result


def _short_calculated_facts(value: Any) -> list[dict[str, Any]]:
    records = value if isinstance(value, list) else []
    result = []
    for record in records[:1]:
        if not isinstance(record, dict):
            continue
        windows = record.get("windows") or {}
        short_windows = {}
        for name in ("D1", "D3", "D20"):
            window = windows.get(name)
            if not isinstance(window, dict):
                continue
            relative_return = window.get("market_relative_return")
            if relative_return is not None:
                short_windows[name] = relative_return
        result.append(
            {
                key: item
                for key, item in {
                    "行业": record.get("industry_name_zh"),
                    "公式": _short_text(record.get("formula_zh"), 70),
                    "状态": record.get("window_status"),
                    "相对收益": short_windows,
                }.items()
                if item not in (None, "", [], {})
            }
        )
    return result


def _short_confounders(value: Any) -> list[dict[str, Any]]:
    records = value if isinstance(value, list) else []
    result = []
    for record in records[:1]:
        if not isinstance(record, dict):
            continue
        registered = record.get("registered_confounders") or []
        detail = registered[0] if registered and isinstance(registered[0], dict) else {}
        result.append(
            {
                key: item
                for key, item in {
                    "status": record.get("company_confounder_status")
                    or record.get("review_status"),
                    "type": detail.get("confounder_type"),
                    "title": _short_text(detail.get("announcement_title"), 70),
                    "mechanism_zh": _short_text(detail.get("mechanism_zh"), 100),
                    "affected_windows": detail.get("affected_windows"),
                }.items()
                if item not in (None, "", [], {})
            }
        )
    return result


def _short_counterevidence(value: Any) -> list[dict[str, Any]]:
    records = value if isinstance(value, list) else []
    result = []
    for record in records[:1]:
        if not isinstance(record, dict):
            continue
        findings = record.get("findings") or []
        finding = findings[0] if findings and isinstance(findings[0], dict) else {}
        result.append(
            {
                key: item
                for key, item in {
                    "review_status": record.get("review_status"),
                    "claim_zh": _short_text(finding.get("claim_zh"), 100),
                    "effect_on_thesis": finding.get("effect_on_thesis"),
                    "evidence_id": finding.get("evidence_id"),
                }.items()
                if item not in (None, "", [], {})
            }
        )
    return result


def _short_refusals(value: Any) -> list[dict[str, Any]]:
    records = value if isinstance(value, list) else []
    return [
        {
            key: record.get(key)
            for key in ("decision", "direction", "refusal_reason")
            if record.get(key) not in (None, "", [])
        }
        for record in records[:1]
        if isinstance(record, dict)
    ]


def _short_horizon_reasoning(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result = {}
    labels = {
        "IMMEDIATE": "即时",
        "SHORT_TERM": "短期",
        "MEDIUM_TERM": "中期",
    }
    for horizon in ("IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM"):
        detail = value.get(horizon)
        if isinstance(detail, dict):
            result[labels[horizon]] = _short_text(detail.get("reasoning_zh"), 90)
        elif detail not in (None, "", []):
            result[labels[horizon]] = _short_text(detail, 90)
    return result


def _short_episodes(records: Any) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        return []
    return [
        {
            key: row.get(key)
            for key in ("phase", "start_at", "end_at")
            if row.get(key) not in (None, "", [])
        }
        for row in records[:2]
        if isinstance(row, dict)
    ]


def _short_industry_context(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in {
            "industry_name_zh": value.get("industry_name_zh")
            or value.get("display_name_zh"),
            "observable_driver_zh": _short_text(value.get("observable_driver_zh"), 80),
            "horizon_directions": value.get("horizon_directions"),
            "invalidation_condition_zh": _short_text(
                value.get("invalidation_condition_zh"), 80
            ),
        }.items()
        if item not in (None, "", [], {})
    }


def _evidence_ids(value: Any) -> list[str]:
    found: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            evidence_id = item.get("evidence_id")
            if evidence_id:
                found.add(str(evidence_id))
            for key, child in item.items():
                if key in {"evidence_ids", "event_evidence_ids"} and isinstance(child, list):
                    found.update(str(value) for value in child if value)
                else:
                    visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return sorted(found)


def _clip_text(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    marker = "\n[内容已按训练长度上限截断]"
    return text[: max_chars - len(marker)].rstrip() + marker


def _messages(user: str, assistant: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _clip_text(user, MAX_USER_CHARS)},
        {"role": "assistant", "content": _clip_text(assistant, MAX_ASSISTANT_CHARS)},
    ]


def _sample(
    *,
    sample_id: str,
    event_id: str,
    task_type: str,
    user: str,
    assistant: str,
    related_industry_ids: list[str] | None = None,
    related_company_codes: list[str] | None = None,
    evidence_source: Any = None,
    source_record_ids: list[str] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = {
        "related_industry_ids": sorted(related_industry_ids or []),
        "related_company_codes": sorted(related_company_codes or []),
        "evidence_ids": _evidence_ids(evidence_source),
        "source_record_ids": sorted(source_record_ids or []),
    }
    if extra_metadata:
        metadata.update(_sanitize(extra_metadata))
    return {
        "sample_id": sample_id,
        "event_id": event_id,
        "task_type": task_type,
        "messages": _messages(user, assistant),
        "metadata": metadata,
    }


def _event_sample(event_record: dict[str, Any]) -> dict[str, Any]:
    event_id = event_record["event_id"]
    event = event_record["event"]
    user = (
        f"事件：{event.get('title_zh', event_id)}（{event_id}）\n"
        "任务：基于以上材料给出宏观事件分析，并说明传导路径、时间窗口和不确定性。\n"
        f"公开里程碑：{_json(_short_milestones(event.get('milestones', [])))}\n"
        f"事件阶段：{_json(_short_episodes(event.get('episodes', [])))}"
    )
    facts = [row.get("fact") for row in event.get("milestones", []) if row.get("fact")]
    assistant = (
        f"来源事实：{_json(facts)}\n"
        f"行情验证：{_json(_short_market(event.get('market_windows', []), limit=1))}\n"
        f"研究推断与传导路径：{_json(_short_graphs(event.get('transmission_graphs', [])))}\n"
        "边界：以上材料不足以证明严格因果；缺少证据的环节保持不确定。"
    )
    return _sample(
        sample_id=f"{event_id}-event-analysis",
        event_id=event_id,
        task_type="EVENT_ANALYSIS",
        user=user,
        assistant=assistant,
        evidence_source=event,
        source_record_ids=event_record.get("lineage", {}).get("source_record_ids", []),
    )


def _industry_sample(
    event_record: dict[str, Any], industry: dict[str, Any]
) -> dict[str, Any]:
    event_id = event_record["event_id"]
    mapping_id = industry["event_industry_mapping_id"]
    mapping = industry.get("mapping") or {}
    input_fields = {
        key: mapping.get(key)
        for key in (
            "anchor_fact",
            "anchor_first_public_at",
            "observable_driver_zh",
            "condition_zh",
            "event_evidence_ids",
        )
        if mapping.get(key) not in (None, "", [])
    }
    conclusion_fields = {
        key: value
        for key, value in {
            "behavior_change_zh": _short_text(mapping.get("behavior_change_zh"), 100),
            "industry_operating_variable_zh": _short_text(
                mapping.get("industry_operating_variable_zh"), 90
            ),
            "industry_financial_variable_zh": _short_text(
                mapping.get("industry_financial_variable_zh"), 90
            ),
            "horizon_directions": mapping.get("horizon_directions"),
            "counterevidence_zh": _short_items(
                mapping.get("counterevidence_zh", []), text_limit=90
            ),
            "invalidation_condition_zh": _short_text(
                mapping.get("invalidation_condition_zh"), 90
            ),
        }.items()
        if value not in (None, "", [], {})
    }
    user = (
        f"事件：{event_record['event'].get('title_zh', event_id)}（{event_id}）\n"
        f"行业：{mapping.get('display_name_zh') or mapping.get('sw1_name_at_event') or mapping_id}\n"
        "任务：分析该事件对行业的传导机制、方向、即时/短期/中期变化及失效条件。\n"
        f"事件与驱动事实：{_json(input_fields)}\n"
        f"行业证据：{_json(_short_evidence(industry.get('evidence', [])))}\n"
        f"行情窗口：{_json(_short_market(industry.get('market_window')))}"
    )
    assistant = (
        f"行业结论：{_json(conclusion_fields)}\n"
        f"机制链：{_json(_short_chain(industry.get('mechanism_chain')))}\n"
        f"行情验证：{_json(_short_market(industry.get('market_window')))}\n"
        "边界：行业方向不自动等同于任何单一公司的方向，统计验证不证明严格因果。"
    )
    return _sample(
        sample_id=f"{event_id}-industry-{mapping_id}",
        event_id=event_id,
        task_type="INDUSTRY_IMPACT",
        user=user,
        assistant=assistant,
        related_industry_ids=[mapping_id],
        evidence_source=industry,
        source_record_ids=[mapping_id],
    )


def _company_sample(
    event_record: dict[str, Any], company: dict[str, Any]
) -> dict[str, Any]:
    event_id = event_record["event_id"]
    mapping_id = company["mapping_id"]
    company_code = company.get("company_code")
    direction = company.get("direction_assessment") or {}
    user = (
        f"事件：{event_record['event'].get('title_zh', event_id)}（{event_id}）\n"
        f"公司：{company.get('company_name') or company_code}（{company_code}）\n"
        "任务：区分行业影响与公司影响，说明机制、方向、时间窗口、混杂因素和反证。\n"
        f"事件—公司映射：{_json(_short_company_mapping(company.get('mapping')))}\n"
        f"公司证据：{_json(_short_evidence(company.get('evidence', [])))}\n"
        f"行情窗口：{_json(_short_market(company.get('market_windows', []), limit=1))}"
    )
    assistant = (
        f"公司方向判断：{_json(_short_direction(direction))}\n"
        f"公司机制链：{_json(_short_chain(company.get('mechanism_chain')))}\n"
        f"混杂因素：{_json(_short_confounders(company.get('confounders', [])))}\n"
        f"反证审查：{_json(_short_counterevidence(company.get('counterevidence_reviews', [])))}\n"
        "边界：证据缺失或仍待人工复核时，不把候选方向表述为确定结论。"
    )
    legacy_industry_id = company.get("industry_impact_id")
    classification = (company.get("mapping") or {}).get("industry_classification") or {}
    company_sw1_id = classification.get("sw1_id")
    related_industry_ids = [
        industry["event_industry_mapping_id"]
        for industry in event_record.get("industries", [])
        if company_sw1_id
        and str((industry.get("mapping") or {}).get("sw1_id")) == str(company_sw1_id)
    ]
    if not related_industry_ids and legacy_industry_id in {
        industry.get("event_industry_mapping_id")
        for industry in event_record.get("industries", [])
    }:
        related_industry_ids = [legacy_industry_id]
    return _sample(
        sample_id=f"{event_id}-company-{mapping_id}",
        event_id=event_id,
        task_type="COMPANY_IMPACT",
        user=user,
        assistant=assistant,
        related_industry_ids=related_industry_ids,
        related_company_codes=[company_code] if company_code else [],
        evidence_source=company,
        source_record_ids=[mapping_id],
        extra_metadata={"legacy_industry_impact_id": legacy_industry_id},
    )


def _qa_sample(event_record: dict[str, Any], qa: dict[str, Any]) -> dict[str, Any]:
    event_id = event_record["event_id"]
    case_id = qa["case_id"]
    case = qa.get("case") or {}
    answer = qa.get("answer") or {}
    industry_impacts = answer.get("industry_impacts", [])
    context = {
        "evidence": _short_evidence(answer.get("evidence", [])),
        "market_windows": _short_market(answer.get("market_windows", []), limit=1),
        "industry_impact": _short_industry_context(
            industry_impacts[0] if industry_impacts else {}
        ),
    }
    task_answer = answer.get("task_answer") or {}
    assistant_parts = [
        f"直接回答：{_short_text(task_answer.get('direct_answer_zh', ''), 240)}",
        f"来源事实：{_json(_short_evidence(task_answer.get('official_facts', [])))}",
        f"计算事实：{_json(_short_calculated_facts(task_answer.get('calculated_facts', [])))}",
        f"研究推断：{_json(_short_items(task_answer.get('research_inferences', []), text_limit=110))}",
        f"时间窗口：{_json(_short_horizon_reasoning(answer.get('horizon_reasoning_zh', {})))}",
        f"研究结论：{_short_text(answer.get('research_conclusion_zh', ''), 120)}",
        f"拒答与边界：{_json(_short_refusals(task_answer.get('refusal_boundaries', answer.get('refusals', []))))}",
    ]
    user = (
        f"事件：{event_record['event'].get('title_zh', event_id)}（{event_id}）\n"
        f"预测截止时间：{case.get('prediction_cutoff_at', answer.get('prediction_cutoff_at', '未提供'))}\n"
        f"问题：{case.get('question_zh', '')}\n"
        "任务：基于给定研究材料直接回答问题，并区分事实、计算与推断。\n"
        f"可用研究材料：{_json(context)}"
    )
    return _sample(
        sample_id=f"{event_id}-qa-{case_id}",
        event_id=event_id,
        task_type="EVENT_QA",
        user=user,
        assistant="\n".join(assistant_parts),
        evidence_source=answer.get("evidence", []),
        source_record_ids=[case_id],
        extra_metadata={"original_task_type": case.get("task_type")},
    )


def project_sft_samples(
    unified_events: list[dict[str, Any]], enabled_tasks: list[str] | None = None
) -> list[dict[str, Any]]:
    enabled = set(
        enabled_tasks
        or ("EVENT_ANALYSIS", "INDUSTRY_IMPACT", "COMPANY_IMPACT", "EVENT_QA")
    )
    samples: list[dict[str, Any]] = []
    for event_record in sorted(unified_events, key=lambda row: row["event_id"]):
        if "EVENT_ANALYSIS" in enabled:
            samples.append(_event_sample(event_record))
        if "INDUSTRY_IMPACT" in enabled:
            samples.extend(
                _industry_sample(event_record, industry)
                for industry in sorted(
                    event_record.get("industries", []),
                    key=lambda row: row["event_industry_mapping_id"],
                )
            )
        if "COMPANY_IMPACT" in enabled:
            samples.extend(
                _company_sample(event_record, company)
                for company in sorted(
                    event_record.get("companies", []),
                    key=lambda row: row["mapping_id"],
                )
            )
        if "EVENT_QA" in enabled:
            samples.extend(
                _qa_sample(event_record, qa)
                for qa in sorted(
                    event_record.get("qa", []), key=lambda row: row["case_id"]
                )
            )
    return samples
