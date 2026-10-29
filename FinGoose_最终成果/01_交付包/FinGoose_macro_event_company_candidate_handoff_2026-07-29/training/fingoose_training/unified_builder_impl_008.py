"""Build content-aligned records with inherited event evidence."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .evidence_closure import (
    bind_milestone_evidence_aliases,
    merge_evidence_records,
)
from .reasoning_chain_impl_009 import compile_reasoning_chain
from .research_content import build_event_research_content
from .unified_builder_impl_001 import (
    BuildError,
    build_unified_events as _build_v1,
    group_by,
    index_unique,
)
from .unified_builder_impl_002 import build_unified_events as _build_legacy
from .unified_builder_impl_003 import (
    _attach_content_to_scopes,
    _attach_qa_chains,
    _company_parent_refs,
)


def _raw_evidence_records(*values: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            if value.get("evidence_id") or value.get("source_id"):
                records.append(deepcopy(dict(value)))
            for child in value.values():
                visit(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child)

    for value in values:
        visit(value)
    return records


def _sparse_reference(record: Mapping[str, Any]) -> dict[str, Any]:
    reference: dict[str, Any] = {
        "evidence_id": _evidence_id(record),
        "supports_node_ids": deepcopy(record.get("supports_node_ids") or []),
    }
    if record.get("source_record_ids"):
        reference["source_record_ids"] = deepcopy(
            record["source_record_ids"]
        )
    return reference


def _merge_sparse_group(
    evidence_id: str, records: list[dict[str, Any]]
) -> dict[str, Any]:
    combined: dict[str, Any] = {
        "evidence_id": evidence_id,
        "source_record_ids": sorted({
            str(source_id)
            for record in records
            for source_id in record.get("source_record_ids") or []
            if source_id
        }),
        "supports_node_ids": sorted({
            str(node_id)
            for record in records
            for node_id in record.get("supports_node_ids") or []
            if node_id
        }),
    }
    for field in ("original_quote", "locator", "source_url"):
        values = [record.get(field) for record in records if record.get(field)]
        if values and all(value == values[0] for value in values[1:]):
            combined[field] = deepcopy(values[0])
    for field in (
        "title",
        "publisher",
        "published_at",
        "snapshot_sha256",
        "availability_scope",
        "review_status",
    ):
        value = next(
            (record.get(field) for record in records if record.get(field)),
            None,
        )
        if value:
            combined[field] = deepcopy(value)
    return merge_evidence_records([combined])[0]


def _complete_evidence(*values: Any) -> list[dict[str, Any]]:
    grouped: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for raw_record in _raw_evidence_records(*values):
        normalized = merge_evidence_records([raw_record])
        if not normalized:
            continue
        record = normalized[0]
        grouped.setdefault(record["evidence_id"], []).append(
            (raw_record, record)
        )

    result: list[dict[str, Any]] = []
    for evidence_id in sorted(grouped):
        candidates = grouped[evidence_id]
        complete = [raw for raw, record in candidates if not record["missing"]]
        sparse = [record for _, record in candidates if record["missing"]]
        if complete:
            canonical = merge_evidence_records(complete)
            result.extend(
                merge_evidence_records(
                    canonical,
                    [_sparse_reference(record) for record in sparse],
                )
            )
        else:
            result.append(
                _merge_sparse_group(
                    evidence_id,
                    [record for _, record in candidates],
                )
            )
    return result


def _evidence_id(record: Mapping[str, Any]) -> str:
    return str(record.get("evidence_id") or record.get("source_id") or "").strip()


def _prefer_complete_event_fact_evidence(
    value: Any, evidence_registry: list[dict[str, Any]]
) -> Any:
    prepared = deepcopy(value)
    complete_ids = {
        _evidence_id(record)
        for record in evidence_registry
        if _evidence_id(record) and record.get("missing") is False
    }

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            if item.get("milestone_id") and isinstance(item.get("sources"), list):
                complete_sources = [
                    source
                    for source in item["sources"]
                    if isinstance(source, Mapping)
                    and _evidence_id(source) in complete_ids
                ]
                if complete_sources:
                    item["sources"] = complete_sources
            if str(item.get("node_type")) == "EVENT_FACT":
                evidence_ids = [
                    str(evidence_id)
                    for evidence_id in item.get("evidence_ids") or []
                    if evidence_id
                ]
                complete = [
                    evidence_id
                    for evidence_id in evidence_ids
                    if evidence_id in complete_ids
                ]
                if complete:
                    item["evidence_ids"] = complete
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(prepared)
    return prepared


def _inherit_event_evidence(
    event_registry: list[dict[str, Any]], *child_values: Any
) -> list[dict[str, Any]]:
    parent_by_id = {
        str(record["evidence_id"]): record for record in event_registry
    }
    child_records: list[dict[str, Any]] = []
    for record in _raw_evidence_records(*child_values):
        evidence_id = _evidence_id(record)
        parent = parent_by_id.get(evidence_id)
        normalized = merge_evidence_records([record])
        child_is_sparse = not normalized or normalized[0]["missing"]
        if parent is not None and not parent.get("missing") and child_is_sparse:
            child_records.append(
                _sparse_reference(
                    normalized[0]
                    if normalized
                    else {"evidence_id": evidence_id}
                )
            )
        else:
            child_records.append(record)
    return merge_evidence_records(event_registry, child_records)


def _attach_event_chain(
    record: dict[str, Any], content: Mapping[str, Any]
) -> None:
    event = deepcopy(record["event"])
    event["milestones"] = bind_milestone_evidence_aliases(
        event.get("milestones") or [],
        content.get("milestone_evidence_aliases") or {},
    )
    evidence = _complete_evidence(
        event.get("sources"),
        event.get("milestones"),
        content.get("evidence_registry"),
    )
    event = _prefer_complete_event_fact_evidence(event, evidence)
    record["event"]["reasoning_chain"] = compile_reasoning_chain(
        "EVENT_ANALYSIS",
        scope={
            "event_id": record["event_id"],
            **event,
            "research_content": content,
        },
        evidence_registry=evidence,
    )


def _attach_industry_chains(
    record: dict[str, Any], content: Mapping[str, Any]
) -> None:
    event_chain = record["event"]["reasoning_chain"]
    event_registry = event_chain["evidence_registry"]
    event_chain_ref = event_chain["reasoning_chain"]["scope_id"]
    content_by_id = {
        str(row.get("event_industry_mapping_id")): row
        for row in content.get("industry_impacts") or []
    }
    for industry in record.get("industries", []):
        mapping_id = str(industry["event_industry_mapping_id"])
        industry_content = content_by_id[mapping_id]
        evidence = _inherit_event_evidence(
            event_registry,
            industry.get("evidence"),
            industry.get("mechanism_chain"),
            industry_content,
        )
        mapping = industry.get("mapping") or {}
        mechanism_chain = _prefer_complete_event_fact_evidence(
            industry.get("mechanism_chain"), evidence
        )
        industry["reasoning_chain"] = compile_reasoning_chain(
            "INDUSTRY_IMPACT",
            scope={
                **deepcopy(mapping),
                "event_id": record["event_id"],
                "event_industry_mapping_id": mapping_id,
                "mechanism_chain": mechanism_chain,
                "market_window": deepcopy(industry.get("market_window")),
                "research_content": industry_content,
            },
            evidence_registry=evidence,
            parent_chain_refs=[event_chain_ref],
        )


def _attach_company_chains(
    record: dict[str, Any], content: Mapping[str, Any]
) -> None:
    event_registry = record["event"]["reasoning_chain"]["evidence_registry"]
    content_by_id = {
        str(row.get("mapping_id")): row
        for row in content.get("company_impacts") or []
    }
    for company in record.get("companies", []):
        mapping_id = str(company["mapping_id"])
        company_content = content_by_id[mapping_id]
        evidence = _inherit_event_evidence(
            event_registry,
            company.get("evidence"),
            company.get("mechanism_chain"),
            company.get("counterevidence_reviews"),
            company_content,
        )
        mapping = company.get("mapping") or {}
        mechanism_chain = _prefer_complete_event_fact_evidence(
            company.get("mechanism_chain"), evidence
        )
        company["reasoning_chain"] = compile_reasoning_chain(
            "COMPANY_IMPACT",
            scope={
                **deepcopy(mapping),
                "event_id": record["event_id"],
                "mapping_id": mapping_id,
                "company_code": company.get("company_code"),
                "mechanism_chain": mechanism_chain,
                "direction_assessment": deepcopy(
                    company.get("direction_assessment")
                ),
                "market_windows": deepcopy(company.get("market_windows")),
                "trading_status_reviews": deepcopy(
                    company.get("trading_status_reviews")
                ),
                "confounders": deepcopy(company.get("confounders")),
                "counterevidence_reviews": deepcopy(
                    company.get("counterevidence_reviews")
                ),
                "research_content": company_content,
            },
            evidence_registry=evidence,
            parent_chain_refs=_company_parent_refs(record, company),
        )


def build_unified_events(
    source: dict[str, list[dict[str, Any]]],
    dataset_version: str,
    *,
    ui_reference: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if ui_reference is None:
        event_ids = {
            str(row.get("event_id"))
            for row in source.get("event_episodes") or []
            if row.get("event_id")
        }
        if len(event_ids) > 1:
            raise BuildError("content alignment requires ui_reference")
        return _build_legacy(source, dataset_version)
    records = _build_v1(source, dataset_version)
    ui_by_id = {
        str(row.get("event_id")): row
        for row in ui_reference.get("events") or []
        if isinstance(row, Mapping)
    }
    for record in records:
        ui_event = ui_by_id.get(str(record["event_id"]))
        if ui_event is None:
            raise BuildError(
                f"ui reference missing event_id={record['event_id']}"
            )
        content = build_event_research_content(ui_event)
        _attach_content_to_scopes(record, content)
        _attach_event_chain(record, content)
        _attach_industry_chains(record, content)
        _attach_company_chains(record, content)
        _attach_qa_chains(record, content)
    return records


__all__ = ["BuildError", "build_unified_events", "group_by", "index_unique"]
