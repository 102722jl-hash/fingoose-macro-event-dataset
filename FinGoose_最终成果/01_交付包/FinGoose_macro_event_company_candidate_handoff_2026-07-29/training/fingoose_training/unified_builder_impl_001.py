"""Build event-centered records from FinGoose candidate packages."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any, Iterable


class BuildError(ValueError):
    """Raised when source records cannot be joined without guessing."""


def index_unique(
    rows: Iterable[dict[str, Any]], key: str, label: str
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row.get(key)
        if not value:
            raise BuildError(f"{label}: missing {key}")
        if value in index:
            raise BuildError(f"{label}: duplicate {key}={value}")
        index[value] = row
    return index


def group_by(
    rows: Iterable[dict[str, Any]], key: str
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = row.get(key)
        if value:
            groups[value].append(row)
    return dict(groups)


def _validate_detail_mappings(
    rows: Iterable[dict[str, Any]], valid_ids: set[str], label: str
) -> None:
    for row in rows:
        mapping_id = row.get("mapping_id")
        if mapping_id not in valid_ids:
            raise BuildError(f"{label}: unknown mapping_id={mapping_id}")


def _validate_industry_details(
    rows: Iterable[dict[str, Any]], valid_ids: set[str], label: str
) -> None:
    for row in rows:
        mapping_id = row.get("event_industry_mapping_id")
        if mapping_id not in valid_ids:
            raise BuildError(
                f"{label}: unknown event_industry_mapping_id={mapping_id}"
            )


def _stable_ids(records: Iterable[dict[str, Any]]) -> list[str]:
    keys = (
        "episode_id",
        "milestone_id",
        "graph_id",
        "market_window_id",
        "event_industry_mapping_id",
        "mapping_id",
        "case_id",
        "evidence_id",
    )
    values: set[str] = set()
    for record in records:
        for key in keys:
            value = record.get(key)
            if value:
                values.add(str(value))
                break
    return sorted(values)


def build_unified_events(
    source: dict[str, list[dict[str, Any]]], dataset_version: str
) -> list[dict[str, Any]]:
    macro_keys = (
        "event_episodes",
        "event_milestones",
        "transmission_graphs",
        "macro_market_windows",
    )
    event_ids = sorted(
        {
            row["event_id"]
            for key in macro_keys
            for row in source.get(key, [])
            if row.get("event_id")
        }
    )
    if not event_ids:
        raise BuildError("no macro event_id values found")
    event_id_set = set(event_ids)

    industry_mappings = index_unique(
        source.get("event_industry_mappings", []),
        "event_industry_mapping_id",
        "event_industry_mappings",
    )
    industry_ids = set(industry_mappings)
    _validate_industry_details(
        source.get("industry_mechanism_chains", []),
        industry_ids,
        "industry_mechanism_chains",
    )
    _validate_industry_details(
        source.get("industry_market_windows", []),
        industry_ids,
        "industry_market_windows",
    )

    company_mappings = index_unique(
        source.get("event_company_map", []), "mapping_id", "event_company_map"
    )
    company_mapping_ids = set(company_mappings)
    for logical_name in (
        "company_mechanism_chains",
        "direction_assessments",
        "company_market_windows",
        "company_confounders",
        "company_counterevidence_reviews",
        "trading_status_reviews",
    ):
        _validate_detail_mappings(
            source.get(logical_name, []), company_mapping_ids, logical_name
        )

    qa_cases = index_unique(source.get("qa_cases", []), "case_id", "qa_cases")
    qa_answers = index_unique(source.get("qa_answers", []), "case_id", "qa_answers")
    for case_id, case in qa_cases.items():
        answer = qa_answers.get(case_id)
        if answer is None:
            raise BuildError(f"qa case {case_id}: missing answer")
        if answer.get("event_id") != case.get("event_id"):
            raise BuildError(f"qa case {case_id}: event mismatch")
    extra_answers = set(qa_answers) - set(qa_cases)
    if extra_answers:
        raise BuildError(f"qa answers without cases: {sorted(extra_answers)}")

    for logical_name, rows in source.items():
        for row in rows:
            event_id = row.get("event_id")
            if event_id and event_id not in event_id_set:
                raise BuildError(f"{logical_name}: unknown event_id={event_id}")

    by_event = {
        key: group_by(source.get(key, []), "event_id")
        for key in (
            *macro_keys,
            "macro_sources",
            "event_industry_mappings",
            "event_company_map",
            "qa_cases",
            "qa_sources",
        )
    }
    industry_chains = index_unique(
        source.get("industry_mechanism_chains", []),
        "event_industry_mapping_id",
        "industry_mechanism_chains",
    )
    industry_windows = index_unique(
        source.get("industry_market_windows", []),
        "event_industry_mapping_id",
        "industry_market_windows",
    )
    industry_evidence = index_unique(
        source.get("industry_evidence", []), "evidence_id", "industry_evidence"
    )
    company_detail_indexes = {
        key: group_by(source.get(key, []), "mapping_id")
        for key in (
            "company_mechanism_chains",
            "direction_assessments",
            "company_market_windows",
            "company_confounders",
            "company_counterevidence_reviews",
            "trading_status_reviews",
        )
    }
    company_evidence_by_code = group_by(
        source.get("company_evidence", []), "company_code"
    )

    records: list[dict[str, Any]] = []
    for event_id in event_ids:
        event_cases = sorted(
            by_event["qa_cases"].get(event_id, []), key=lambda row: row["case_id"]
        )
        event_industries = sorted(
            by_event["event_industry_mappings"].get(event_id, []),
            key=lambda row: row["event_industry_mapping_id"],
        )
        event_companies = sorted(
            by_event["event_company_map"].get(event_id, []),
            key=lambda row: row["mapping_id"],
        )
        title = next(
            (
                row.get("event_title_zh")
                for row in [*event_cases, *event_industries]
                if row.get("event_title_zh")
            ),
            event_id,
        )

        industries: list[dict[str, Any]] = []
        for mapping in event_industries:
            mapping_id = mapping["event_industry_mapping_id"]
            evidence_ids = mapping.get("event_evidence_ids") or []
            industries.append(
                {
                    "event_industry_mapping_id": mapping_id,
                    "mapping": deepcopy(mapping),
                    "mechanism_chain": deepcopy(industry_chains.get(mapping_id)),
                    "market_window": deepcopy(industry_windows.get(mapping_id)),
                    "evidence": [
                        deepcopy(industry_evidence[evidence_id])
                        for evidence_id in evidence_ids
                        if evidence_id in industry_evidence
                    ],
                }
            )

        companies: list[dict[str, Any]] = []
        for mapping in event_companies:
            mapping_id = mapping["mapping_id"]
            company_code = mapping.get("company_code")
            companies.append(
                {
                    "mapping_id": mapping_id,
                    "company_code": company_code,
                    "company_name": mapping.get("company_name"),
                    "industry_impact_id": mapping.get("industry_impact_id"),
                    "mapping": deepcopy(mapping),
                    "mechanism_chain": deepcopy(
                        (company_detail_indexes["company_mechanism_chains"].get(mapping_id) or [None])[0]
                    ),
                    "direction_assessment": deepcopy(
                        (company_detail_indexes["direction_assessments"].get(mapping_id) or [None])[0]
                    ),
                    "market_windows": deepcopy(
                        company_detail_indexes["company_market_windows"].get(mapping_id, [])
                    ),
                    "confounders": deepcopy(
                        company_detail_indexes["company_confounders"].get(mapping_id, [])
                    ),
                    "counterevidence_reviews": deepcopy(
                        company_detail_indexes["company_counterevidence_reviews"].get(mapping_id, [])
                    ),
                    "trading_status_reviews": deepcopy(
                        company_detail_indexes["trading_status_reviews"].get(mapping_id, [])
                    ),
                    "evidence": deepcopy(company_evidence_by_code.get(company_code, [])),
                }
            )

        qa = [
            {
                "case_id": case["case_id"],
                "case": deepcopy(case),
                "answer": deepcopy(qa_answers[case["case_id"]]),
                "source_fetches": deepcopy(by_event["qa_sources"].get(event_id, [])),
            }
            for case in event_cases
        ]
        event_records = [
            *by_event["event_episodes"].get(event_id, []),
            *by_event["event_milestones"].get(event_id, []),
            *by_event["transmission_graphs"].get(event_id, []),
            *by_event["macro_market_windows"].get(event_id, []),
            *event_industries,
            *event_companies,
            *event_cases,
        ]
        records.append(
            {
                "event_id": event_id,
                "dataset_version": dataset_version,
                "event": {
                    "title_zh": title,
                    "episodes": deepcopy(by_event["event_episodes"].get(event_id, [])),
                    "milestones": deepcopy(by_event["event_milestones"].get(event_id, [])),
                    "transmission_graphs": deepcopy(
                        by_event["transmission_graphs"].get(event_id, [])
                    ),
                    "market_windows": deepcopy(
                        by_event["macro_market_windows"].get(event_id, [])
                    ),
                    "sources": deepcopy(by_event["macro_sources"].get(event_id, [])),
                },
                "industries": industries,
                "companies": companies,
                "qa": qa,
                "lineage": {"source_record_ids": _stable_ids(event_records)},
            }
        )
    return records
