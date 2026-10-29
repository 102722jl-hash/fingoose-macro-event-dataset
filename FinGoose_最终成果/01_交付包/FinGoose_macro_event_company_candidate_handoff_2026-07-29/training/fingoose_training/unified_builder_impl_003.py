"""Build unified records with UI-aligned research content and audited chains."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .reasoning_chain_impl_009 import compile_reasoning_chain
from .research_content_impl_001 import build_event_research_content
from .unified_builder_impl_001 import BuildError, build_unified_events as _build_v1, group_by, index_unique


def _evidence_records(*values: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            if value.get("evidence_id") or value.get("source_id"):
                records.append(deepcopy(dict(value)))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for value in values:
        visit(value)
    unique: dict[str, dict[str, Any]] = {}
    for record in records:
        evidence_id = record.get("evidence_id") or record.get("source_id")
        if not evidence_id:
            continue
        key = str(evidence_id)
        current = unique.setdefault(key, {"evidence_id": key})
        for field, value in record.items():
            if value in (None, "", []):
                continue
            if field == "supports_node_ids":
                merged = set(current.get(field) or []) | set(value or [])
                current[field] = sorted(str(item) for item in merged if item)
                continue
            if current.get(field) in (None, "") or (
                field in {"original_quote", "quote", "locator", "locator_zh", "source_url", "url", "sha256", "snapshot_sha256"}
                and len(str(value)) > len(str(current.get(field) or ""))
            ):
                current[field] = deepcopy(value)
        current["missing"] = not bool(
            (current.get("original_quote") or current.get("quote"))
            and (current.get("locator") or current.get("locator_zh") or current.get("page_or_section_locator"))
            and (current.get("source_url") or current.get("url"))
        )
    return [unique[key] for key in sorted(unique)]


def _attach_content_to_scopes(record: dict[str, Any], content: Mapping[str, Any]) -> None:
    record["research_content"] = deepcopy(dict(content))
    record["event"]["research_content"] = deepcopy(content.get("macro_mechanism") or {})
    industries = {str(row.get("event_industry_mapping_id")): row for row in content.get("industry_impacts") or []}
    for industry in record.get("industries", []):
        mapping_id = str(industry["event_industry_mapping_id"])
        if mapping_id not in industries:
            raise BuildError(f"ui reference missing industry mapping_id={mapping_id}")
        industry["research_content"] = deepcopy(industries[mapping_id])
    companies = {str(row.get("mapping_id")): row for row in content.get("company_impacts") or []}
    for company in record.get("companies", []):
        mapping_id = str(company["mapping_id"])
        if mapping_id not in companies:
            raise BuildError(f"ui reference missing company mapping_id={mapping_id}")
        company["research_content"] = deepcopy(companies[mapping_id])
    qa_rows = {str(row.get("case_id")): row for row in content.get("qa_sections") or []}
    for qa in record.get("qa", []):
        case_id = str(qa["case_id"])
        if case_id not in qa_rows:
            raise BuildError(f"ui reference missing QA case_id={case_id}")
        qa["research_content"] = deepcopy(qa_rows[case_id])


def _attach_event_chain(record: dict[str, Any], content: Mapping[str, Any]) -> None:
    event = record["event"]
    scope = {"event_id": record["event_id"], **deepcopy(event), "research_content": content}
    evidence = _evidence_records(event.get("sources"), event.get("milestones"), content.get("evidence_registry"))
    event["reasoning_chain"] = compile_reasoning_chain(
        "EVENT_ANALYSIS", scope=scope, evidence_registry=evidence
    )


def _attach_industry_chains(record: dict[str, Any], content: Mapping[str, Any]) -> None:
    event_chain_ref = record["event"]["reasoning_chain"]["reasoning_chain"]["scope_id"]
    content_by_id = {str(row.get("event_industry_mapping_id")): row for row in content.get("industry_impacts") or []}
    for industry in record.get("industries", []):
        mapping = industry.get("mapping") or {}
        industry_content = content_by_id[str(industry["event_industry_mapping_id"])]
        scope = {
            **deepcopy(mapping),
            "event_id": record["event_id"],
            "event_industry_mapping_id": industry["event_industry_mapping_id"],
            "mechanism_chain": deepcopy(industry.get("mechanism_chain")),
            "market_window": deepcopy(industry.get("market_window")),
            "research_content": industry_content,
        }
        industry["reasoning_chain"] = compile_reasoning_chain(
            "INDUSTRY_IMPACT", scope=scope,
            evidence_registry=_evidence_records(industry.get("evidence"), industry.get("mechanism_chain"), industry_content),
            parent_chain_refs=[event_chain_ref],
        )


def _company_parent_refs(record: dict[str, Any], company: dict[str, Any]) -> list[str]:
    mapping = company.get("mapping") or {}
    classification = mapping.get("industry_classification") or {}
    sw1_id = classification.get("sw1_id")
    refs = [
        industry["event_industry_mapping_id"]
        for industry in record.get("industries", [])
        if sw1_id and str((industry.get("mapping") or {}).get("sw1_id")) == str(sw1_id)
    ]
    legacy = company.get("industry_impact_id")
    valid = {industry["event_industry_mapping_id"] for industry in record.get("industries", [])}
    if not refs and legacy in valid:
        refs.append(legacy)
    return refs or [record["event_id"]]


def _attach_company_chains(record: dict[str, Any], content: Mapping[str, Any]) -> None:
    content_by_id = {str(row.get("mapping_id")): row for row in content.get("company_impacts") or []}
    for company in record.get("companies", []):
        mapping = company.get("mapping") or {}
        company_content = content_by_id[str(company["mapping_id"])]
        scope = {
            **deepcopy(mapping),
            "event_id": record["event_id"],
            "mapping_id": company["mapping_id"],
            "company_code": company.get("company_code"),
            "mechanism_chain": deepcopy(company.get("mechanism_chain")),
            "direction_assessment": deepcopy(company.get("direction_assessment")),
            "market_windows": deepcopy(company.get("market_windows")),
            "confounders": deepcopy(company.get("confounders")),
            "counterevidence_reviews": deepcopy(company.get("counterevidence_reviews")),
            "research_content": company_content,
        }
        company["reasoning_chain"] = compile_reasoning_chain(
            "COMPANY_IMPACT", scope=scope,
            evidence_registry=_evidence_records(company.get("evidence"), company.get("mechanism_chain"), company.get("counterevidence_reviews"), company_content),
            parent_chain_refs=_company_parent_refs(record, company),
        )


def _qa_parent_refs(record: dict[str, Any], qa: dict[str, Any]) -> list[str]:
    answer = qa.get("answer") or {}
    refs = [record["event_id"]]
    valid = {industry["event_industry_mapping_id"] for industry in record.get("industries", [])}
    for impact in answer.get("industry_impacts") or []:
        mapping_id = impact.get("event_industry_mapping_id")
        if mapping_id in valid:
            refs.append(mapping_id)
    return sorted(set(refs))


def _attach_qa_chains(record: dict[str, Any], content: Mapping[str, Any]) -> None:
    content_by_id = {str(row.get("case_id")): row for row in content.get("qa_sections") or []}
    for qa in record.get("qa", []):
        qa_content = content_by_id[str(qa["case_id"])]
        qa["reasoning_chain"] = compile_reasoning_chain(
            "EVENT_QA", scope={**deepcopy(qa), "research_content": qa_content},
            evidence_registry=_evidence_records((qa.get("answer") or {}).get("evidence"), qa.get("source_fetches"), qa_content),
            parent_chain_refs=_qa_parent_refs(record, qa),
        )


def build_unified_events(
    source: dict[str, list[dict[str, Any]]],
    dataset_version: str,
    *,
    ui_reference: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    records = _build_v1(source, dataset_version)
    if ui_reference is None:
        if len(records) > 1:
            raise BuildError("content alignment requires ui_reference")
        return records
    ui_by_id = {str(row.get("event_id")): row for row in ui_reference.get("events") or [] if isinstance(row, Mapping)}
    for record in records:
        ui_event = ui_by_id.get(str(record["event_id"]))
        if ui_event is None:
            raise BuildError(f"ui reference missing event_id={record['event_id']}")
        content = build_event_research_content(ui_event)
        _attach_content_to_scopes(record, content)
        _attach_event_chain(record, content)
        _attach_industry_chains(record, content)
        _attach_company_chains(record, content)
        _attach_qa_chains(record, content)
    return records


__all__ = ["BuildError", "build_unified_events", "group_by", "index_unique"]
