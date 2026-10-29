"""Attach canonical reasoning chains after the existing source joins complete."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .reasoning_chain import compile_reasoning_chain
from .unified_builder_impl_001 import (
    BuildError,
    build_unified_events as _build_v1,
    group_by,
    index_unique,
)


def _evidence_records(*values: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("evidence_id") or value.get("source_id"):
                records.append(deepcopy(value))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for value in values:
        visit(value)
    deduplicated: dict[str, dict[str, Any]] = {}
    for record in records:
        evidence_id = record.get("evidence_id") or record.get("source_id")
        if evidence_id and str(evidence_id) not in deduplicated:
            deduplicated[str(evidence_id)] = record
    return [deduplicated[key] for key in sorted(deduplicated)]


def _attach_event_chain(record: dict[str, Any]) -> None:
    event = record["event"]
    scope = {"event_id": record["event_id"], **deepcopy(event)}
    evidence = _evidence_records(event.get("sources"), event.get("milestones"))
    event["reasoning_chain"] = compile_reasoning_chain(
        "EVENT_ANALYSIS", scope=scope, evidence_registry=evidence
    )


def _attach_industry_chains(record: dict[str, Any]) -> None:
    event_chain_ref = record["event"]["reasoning_chain"]["reasoning_chain"]["scope_id"]
    for industry in record.get("industries", []):
        mapping = industry.get("mapping") or {}
        scope = {
            **deepcopy(mapping),
            "event_id": record["event_id"],
            "event_industry_mapping_id": industry["event_industry_mapping_id"],
            "mechanism_chain": deepcopy(industry.get("mechanism_chain")),
            "market_window": deepcopy(industry.get("market_window")),
        }
        industry["reasoning_chain"] = compile_reasoning_chain(
            "INDUSTRY_IMPACT",
            scope=scope,
            evidence_registry=_evidence_records(industry.get("evidence"), industry.get("mechanism_chain")),
            parent_chain_refs=[event_chain_ref],
        )


def _company_parent_refs(record: dict[str, Any], company: dict[str, Any]) -> list[str]:
    mapping = company.get("mapping") or {}
    classification = mapping.get("industry_classification") or {}
    sw1_id = classification.get("sw1_id")
    refs = [
        industry["event_industry_mapping_id"]
        for industry in record.get("industries", [])
        if sw1_id
        and str((industry.get("mapping") or {}).get("sw1_id")) == str(sw1_id)
    ]
    legacy = company.get("industry_impact_id")
    valid = {
        industry["event_industry_mapping_id"]
        for industry in record.get("industries", [])
    }
    if not refs and legacy in valid:
        refs.append(legacy)
    return refs or [record["event_id"]]


def _attach_company_chains(record: dict[str, Any]) -> None:
    for company in record.get("companies", []):
        mapping = company.get("mapping") or {}
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
        }
        company["reasoning_chain"] = compile_reasoning_chain(
            "COMPANY_IMPACT",
            scope=scope,
            evidence_registry=_evidence_records(
                company.get("evidence"),
                company.get("mechanism_chain"),
                company.get("counterevidence_reviews"),
            ),
            parent_chain_refs=_company_parent_refs(record, company),
        )


def _qa_parent_refs(record: dict[str, Any], qa: dict[str, Any]) -> list[str]:
    answer = qa.get("answer") or {}
    refs = [record["event_id"]]
    valid_industry_ids = {
        industry["event_industry_mapping_id"] for industry in record.get("industries", [])
    }
    for impact in answer.get("industry_impacts") or []:
        mapping_id = impact.get("event_industry_mapping_id")
        if mapping_id in valid_industry_ids:
            refs.append(mapping_id)
    return sorted(set(refs))


def _attach_qa_chains(record: dict[str, Any]) -> None:
    for qa in record.get("qa", []):
        qa["reasoning_chain"] = compile_reasoning_chain(
            "EVENT_QA",
            scope=qa,
            evidence_registry=_evidence_records(
                (qa.get("answer") or {}).get("evidence"), qa.get("source_fetches")
            ),
            parent_chain_refs=_qa_parent_refs(record, qa),
        )


def build_unified_events(
    source: dict[str, list[dict[str, Any]]], dataset_version: str
) -> list[dict[str, Any]]:
    records = _build_v1(source, dataset_version)
    for record in records:
        _attach_event_chain(record)
        _attach_industry_chains(record)
        _attach_company_chains(record)
        _attach_qa_chains(record)
    return records


__all__ = ["BuildError", "build_unified_events", "group_by", "index_unique"]
