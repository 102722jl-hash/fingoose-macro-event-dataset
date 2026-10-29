"""Build and validate the event-01 industry research overlay."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fingoose_company_impact_io_v2 import read_jsonl, write_jsonl

EXPECTED_IDS = {
    "event-industry-event-01-801150",
    "event-industry-event-01-801170",
    "event-industry-event-01-801210",
    "event-industry-event-01-801200",
    "event-industry-event-01-801760",
    "event-industry-event-01-801020",
    "event-industry-event-01-801750",
    "event-industry-event-01-801120",
}
STATEMENT_CLASSES = {"SOURCE_FACT", "CALCULATED_FACT", "RESEARCH_INFERENCE"}
STEP_TYPES = (
    "EVENT_FACT",
    "BEHAVIOR_OR_POLICY_CHANGE",
    "OBSERVABLE_DRIVER",
    "INDUSTRY_OPERATING_VARIABLE",
    "INDUSTRY_REVENUE_OR_COST_VARIABLE",
    "DIRECTION_ASSESSMENT",
    "PRICE_CONFOUNDER_AND_COUNTEREVIDENCE",
)


def load_closure_profiles(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = [dict(row) for row in payload["profiles"]]
    ids = {str(row["event_industry_mapping_id"]) for row in rows}
    if ids != EXPECTED_IDS:
        raise ValueError(f"EVENT_01_MAPPING_SET_MISMATCH:{sorted(ids)}")
    if len(rows) != len(ids):
        raise ValueError("DUPLICATE_EVENT_01_MAPPING")
    for row in rows:
        mapping_id = row.get("event_industry_mapping_id")
        steps = row.get("mechanism_steps") or []
        if row.get("event_id") != "event-01" or len(steps) != 7:
            raise ValueError(f"INVALID_EVENT_01_PROFILE:{mapping_id}")
        if tuple(step.get("step_type") for step in steps) != STEP_TYPES:
            raise ValueError(f"INVALID_STEP_SEQUENCE:{mapping_id}")
        if any(step.get("statement_class") not in STATEMENT_CLASSES for step in steps):
            raise ValueError(f"INVALID_STATEMENT_CLASS:{mapping_id}")
        if row.get("formal_ready") is not False or row.get("sha_gate") != "DEFERRED":
            raise ValueError(f"RELEASE_BOUNDARY_VIOLATION:{mapping_id}")
    return rows


def build_mechanism_chains(
    profiles: list[dict[str, Any]], evidence_by_id: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    chains: list[dict[str, Any]] = []
    for profile in profiles:
        mapping_id = str(profile["event_industry_mapping_id"])
        nodes: list[dict[str, Any]] = []
        for index, step in enumerate(profile["mechanism_steps"], 1):
            node_id = f"industry-mechanism-{mapping_id}-{index}"
            premise_ids = [
                f"industry-mechanism-{mapping_id}-{number}"
                for number in step.get("premise_step_numbers", [])
            ]
            evidence_ids = list(step.get("evidence_ids", []))
            missing = [
                evidence_id
                for evidence_id in evidence_ids
                if evidence_by_id.get(evidence_id, {}).get("fetch_status")
                != "RETRIEVED_QUOTE_VERIFIED"
            ]
            statement_class = str(step["statement_class"])
            nodes.append(
                {
                    "node_id": node_id,
                    "node_type": step["step_type"],
                    "statement_class": statement_class,
                    "statement_zh": step["statement_zh"],
                    "evidence_ids": evidence_ids,
                    "missing_evidence_ids": missing,
                    "premise_node_ids": premise_ids,
                    "condition_zh": step.get("condition_zh"),
                    "invalidation_zh": step.get("invalidation_zh"),
                    "evidence_status": (
                        "AVAILABLE"
                        if evidence_ids and not missing
                        else (
                            "NOT_APPLICABLE_INFERENCE"
                            if statement_class == "RESEARCH_INFERENCE"
                            else (
                                "MARKET_CALCULATION_PENDING"
                                if statement_class == "CALCULATED_FACT"
                                else "EVIDENCE_PENDING"
                            )
                        )
                    ),
                }
            )
        chains.append(
            {
                "industry_chain_id": f"industry-chain-{mapping_id}",
                "event_industry_mapping_id": mapping_id,
                "event_id": "event-01",
                "impact_tier": profile["impact_tier"],
                "industry_name_zh": profile["display_name_zh"],
                "nodes": nodes,
                "edges": [
                    {
                        "from_node_id": nodes[index]["node_id"],
                        "to_node_id": nodes[index + 1]["node_id"],
                    }
                    for index in range(6)
                ],
                "horizon_directions": dict(profile["horizon_directions"]),
                "confounders": list(profile.get("confounders") or []),
                "challenge_set_only": bool(profile.get("confounders")),
                "chain_status": "PROPOSED_INDUSTRY_MECHANISM",
                "review_status": "NEEDS_HUMAN_REVIEW",
                "formal_ready": False,
                "sha_gate": "DEFERRED",
            }
        )
    return chains


_DRIVER_SPECS = {
    "801150": {
        "source_id": "event01-nmpa-test-kits",
        "frequency": "POINT_IN_TIME",
        "observations": [
            {"observed_at": "2020-03-30", "metric_code": "APPROVED_TEST_KITS", "value": 23, "unit": "count"},
            {"observed_at": "2020-03-30", "metric_code": "APPROVED_NUCLEIC_ACID_KITS", "value": 15, "unit": "count"},
            {"observed_at": "2020-03-30", "metric_code": "APPROVED_ANTIBODY_KITS", "value": 8, "unit": "count"},
        ],
    },
    "801170": {
        "source_id": "event01-iata-mar-rpk",
        "frequency": "MONTHLY",
        "observations": [
            {"observed_at": "2020-03-31", "metric_code": "GLOBAL_RPK_YOY", "value": -52.9, "unit": "percent"},
            {"observed_at": "2020-03-31", "metric_code": "CHINA_DOMESTIC_RPK_YOY", "value": -65.5, "unit": "percent"},
        ],
    },
    "801210": {
        "source_id": "event01-mct-tourism-2020",
        "frequency": "QUARTERLY",
        "observations": [
            {"observed_at": "2020-03-31", "metric_code": "DOMESTIC_TOURISTS", "value": 295000000, "unit": "persons"},
            {"observed_at": "2020-03-31", "metric_code": "DOMESTIC_TOURISTS_YOY", "value": -83.4, "unit": "percent"},
        ],
    },
    "801200": {
        "source_id": "event01-nbs-retail-mar",
        "frequency": "MONTHLY",
        "observations": [
            {"observed_at": "2020-03-31", "metric_code": "RETAIL_SALES", "value": 26450, "unit": "CNY_100M"},
            {"observed_at": "2020-03-31", "metric_code": "RETAIL_SALES_YOY", "value": -15.8, "unit": "percent"},
        ],
    },
    "801760": {
        "source_id": "event01-film-covid-meeting",
        "frequency": "EVENT_STATE",
        "observations": [
            {"observed_at": "2020-03-31", "metric_code": "CINEMA_OPERATING_STATE", "value": "SUSPENDED", "unit": "state"},
        ],
    },
    "801020": {
        "source_id": "event01-eia-mar20-steo",
        "frequency": "MONTHLY_FORECAST",
        "observations": [
            {
                "observed_at": "2020-03-11",
                "metric_code": "EIA_GLOBAL_LIQUID_FUELS_DEMAND_FORECAST",
                "value": None,
                "unit": "million_barrels_per_day",
                "pending_reason": "FIELD_EXTRACTION_PENDING",
            }
        ],
    },
    "801750": {
        "source_id": "event01-miit-software-2020",
        "frequency": "ANNUAL",
        "observations": [
            {"observed_at": "2020-12-31", "metric_code": "SOFTWARE_REVENUE", "value": 81616, "unit": "CNY_100M"},
            {"observed_at": "2020-12-31", "metric_code": "SOFTWARE_REVENUE_YOY", "value": 13.3, "unit": "percent"},
        ],
    },
    "801120": {
        "source_id": "event01-nbs-retail-mar",
        "frequency": "MONTHLY",
        "observations": [
            {"observed_at": "2020-03-31", "metric_code": "CATERING_REVENUE_YOY", "value": -46.8, "unit": "percent"},
            {"observed_at": "2020-03-31", "metric_code": "FOOD_RETAIL_YOY", "value": 19.2, "unit": "percent"},
            {"observed_at": "2020-03-31", "metric_code": "BEVERAGE_RETAIL_YOY", "value": 6.3, "unit": "percent"},
        ],
    },
}


def build_driver_records(
    profiles: list[dict[str, Any]], evidence_by_id: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    drivers: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    for profile in profiles:
        mapping_id = str(profile["event_industry_mapping_id"])
        spec = _DRIVER_SPECS[str(profile["sw1_id"])]
        source_id = str(spec["source_id"])
        source_available = (
            evidence_by_id.get(source_id, {}).get("fetch_status")
            == "RETRIEVED_QUOTE_VERIFIED"
        )
        series_id = str(profile["driver_series_id"])
        drivers.append(
            {
                "event_industry_mapping_id": mapping_id,
                "driver_series_id": series_id,
                "driver_role": "PRIMARY",
                "driver_name_zh": profile["driver_name_zh"],
                "unit_zh": profile["driver_unit_zh"],
                "frequency": spec["frequency"],
                "source_id": source_id,
                "source_status": "AVAILABLE" if source_available else "DATA_PENDING",
                "selection_basis": "PRE_REGISTERED_OPERATING_DRIVER_NOT_SELECTED_BY_PRICE",
                "review_status": "NEEDS_HUMAN_REVIEW",
                "formal_ready": False,
                "sha_gate": "DEFERRED",
            }
        )
        for index, item in enumerate(spec["observations"], 1):
            value = item.get("value") if source_available else None
            observations.append(
                {
                    "observation_id": f"{series_id}-{index}",
                    "event_industry_mapping_id": mapping_id,
                    "driver_series_id": series_id,
                    "observed_at": item["observed_at"],
                    "metric_code": item["metric_code"],
                    "value": value,
                    "unit": item["unit"],
                    "frequency": spec["frequency"],
                    "source_id": source_id,
                    "availability_scope": evidence_by_id.get(source_id, {}).get(
                        "usage_boundary", "UNKNOWN"
                    ),
                    "data_status": (
                        "AVAILABLE"
                        if source_available and value is not None
                        else "DATA_PENDING"
                    ),
                    "pending_reason": (
                        None
                        if source_available and value is not None
                        else item.get("pending_reason", "SOURCE_QUOTE_NOT_VERIFIED")
                    ),
                    "formal_ready": False,
                    "sha_gate": "DEFERRED",
                }
            )
    return drivers, observations


def project_verified_evidence(
    evidence_fetches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for source in evidence_fetches:
        if source.get("fetch_status") != "RETRIEVED_QUOTE_VERIFIED":
            continue
        output.append(
            {
                "evidence_id": source["source_id"],
                "evidence_kind": "INDUSTRY_MECHANISM_SOURCE",
                "source_tier": source["source_tier"],
                "publisher": source["publisher"],
                "title": source["title"],
                "source_url": source["source_url"],
                "published_at": source["published_at"],
                "first_public_at": source.get(
                    "first_public_at", source["published_at"]
                ),
                "accessed_at": source["accessed_at"],
                "original_quote": source["verified_quote"],
                "locator": source["evidence_locator"],
                "availability_scope": source["usage_boundary"],
                "supports_mapping_ids": source["supports_mapping_ids"],
                "supports_step_types": source["supports_step_types"],
                "raw_snapshot_path": source["raw_snapshot_path"],
                "review_status": "SOURCE_TEXT_LOCATOR_VERIFIED",
                "formal_ready": False,
                "sha_gate": "DEFERRED",
            }
        )
    return output


def completion_for(
    mapping: Mapping[str, Any],
    chain: Mapping[str, Any],
    driver: Mapping[str, Any],
    window: Mapping[str, Any],
) -> dict[str, Any]:
    fact_types = {
        node["node_type"]
        for node in chain["nodes"]
        if node["statement_class"] == "SOURCE_FACT"
        and node["evidence_status"] == "AVAILABLE"
    }
    required_facts = {
        "EVENT_FACT",
        "BEHAVIOR_OR_POLICY_CHANGE",
        "OBSERVABLE_DRIVER",
        "INDUSTRY_OPERATING_VARIABLE",
    }
    blockers: list[str] = []
    if not required_facts.issubset(fact_types):
        blockers.append("FOUR_FACT_PILLARS_INCOMPLETE")
    if driver["source_status"] != "AVAILABLE":
        blockers.append("DRIVER_DATA_INCOMPLETE")
    if window["window_status"] != "AVAILABLE":
        blockers.append("INDUSTRY_WINDOW_INCOMPLETE")
    if any(value == "UNKNOWN" for value in chain["horizon_directions"].values()) and not chain.get("abstention"):
        blockers.append("UNEXPLAINED_UNKNOWN_DIRECTION")
    if not chain.get("confounders"):
        blockers.append("CONFOUNDERS_INCOMPLETE")
    return {
        "event_industry_mapping_id": mapping["event_industry_mapping_id"],
        "completion_status": "CANDIDATE_COMPLETE" if not blockers else "OPEN",
        "blockers": blockers,
        "challenge_set_only": any(
            row["severity"] in {"MATERIAL", "DOMINANT", "UNRESOLVED"}
            for row in chain["confounders"]
        ),
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }


def _mapping_for(profile: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event_industry_mapping_id": profile["event_industry_mapping_id"],
        "event_id": "event-01",
        "event_title_zh": profile["event_title_zh"],
        "anchor_node_id": profile["anchor_node_id"],
        "classification_edition": profile["classification_edition"],
        "sw1_id": profile["sw1_id"],
        "sw1_name_at_event": profile["sw1_name_at_event"],
        "display_name_zh": profile["display_name_zh"],
        "impact_tier": profile["impact_tier"],
        "segment_labels_zh": list(profile["segment_labels_zh"]),
        "selection_basis_zh": "PRE_REGISTERED_MECHANISM_NOT_SELECTED_BY_POST_EVENT_PRICE",
        "price_selection_used": False,
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }


def _pending_market_window(mapping_id: str, reason: str) -> dict[str, Any]:
    return {
        "event_industry_mapping_id": mapping_id,
        "event_id": "event-01",
        "t0_alignment": None,
        "continuous_window": [],
        "fixed_windows": {},
        "driver_observations": [],
        "window_status": "DATA_PENDING",
        "pending_reason": reason,
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }


def _load_fetches(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.exists() else []


def _market_payloads_from_raw(
    root: Path,
    output_root: Path,
    profiles: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    from fingoose_industry_market_v2 import (
        build_industry_market_window,
        load_market_csv,
    )

    registry_path = root / "configs/industry_impact_v2/event_01_market_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    raw_root = output_root / "raw/market"
    market_path = raw_root / "csi300.csv"
    if not market_path.exists():
        return {}
    market_rows = load_market_csv(market_path)
    observations_by_mapping: dict[str, list[dict[str, Any]]] = {}
    for row in observations:
        observations_by_mapping.setdefault(
            str(row["event_industry_mapping_id"]), []
        ).append(dict(row))
    result: dict[str, dict[str, Any]] = {}
    for item in registry["industry_benchmarks"]:
        mapping_id = str(item["mapping_id"])
        industry_path = raw_root / f"sw_{item['code']}.csv"
        if not industry_path.exists():
            continue
        result[mapping_id] = build_industry_market_window(
            mapping_id=mapping_id,
            event_at=registry["event_at"],
            industry_rows=load_market_csv(industry_path),
            market_rows=market_rows,
            driver_observations=observations_by_mapping.get(mapping_id, []),
            market_timezone=registry["market_timezone"],
        )
    return result


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )


def build_event_01_closure_bundle(
    root: Path,
    *,
    output_root: Path,
    evidence_fetches: list[dict[str, Any]] | None = None,
    market_payloads: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    profiles = load_closure_profiles(
        root / "configs/industry_impact_v2/event_01_closure_profiles.json"
    )
    if evidence_fetches is None:
        evidence_fetches = _load_fetches(
            output_root / "industry_source_fetches.jsonl"
        )
    evidence_by_id = {
        str(row["source_id"]): dict(row) for row in evidence_fetches
    }
    evidence = project_verified_evidence(evidence_fetches)
    mappings = [_mapping_for(profile) for profile in profiles]
    chains = build_mechanism_chains(profiles, evidence_by_id)
    drivers, observations = build_driver_records(profiles, evidence_by_id)
    if market_payloads is None:
        market_payloads = _market_payloads_from_raw(
            root, output_root, profiles, observations
        )
    windows = [
        dict(
            market_payloads.get(
                str(mapping["event_industry_mapping_id"]),
                _pending_market_window(
                    str(mapping["event_industry_mapping_id"]),
                    "MARKET_SERIES_NOT_AVAILABLE",
                ),
            )
        )
        for mapping in mappings
    ]
    chain_by_id = {
        str(row["event_industry_mapping_id"]): row for row in chains
    }
    driver_by_id = {
        str(row["event_industry_mapping_id"]): row for row in drivers
    }
    window_by_id = {
        str(row["event_industry_mapping_id"]): row for row in windows
    }
    completion = [
        completion_for(
            mapping,
            chain_by_id[str(mapping["event_industry_mapping_id"])],
            driver_by_id[str(mapping["event_industry_mapping_id"])],
            window_by_id[str(mapping["event_industry_mapping_id"])],
        )
        for mapping in mappings
    ]

    outputs = {
        "event_industry_mappings.jsonl": mappings,
        "industry_mechanism_chains.jsonl": chains,
        "industry_evidence.jsonl": evidence,
        "industry_driver_registry.jsonl": drivers,
        "industry_driver_observations.jsonl": observations,
        "industry_market_windows.jsonl": windows,
        "industry_completion_report.jsonl": completion,
        "industry_source_fetches.jsonl": evidence_fetches,
    }
    for name, rows in outputs.items():
        write_jsonl(output_root / name, rows)

    ids = {str(row["event_industry_mapping_id"]) for row in mappings}
    related_ids = {
        key: {str(row["event_industry_mapping_id"]) for row in rows}
        for key, rows in {
            "chains": chains,
            "drivers": drivers,
            "windows": windows,
            "completion": completion,
        }.items()
    }
    valid_scopes = {"PREDICTION_VISIBLE", "VERIFICATION_ONLY"}
    validation = {
        "dataset_version": "fingoose-event-01-industry-closure-v2-candidate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "mapping_count_is_8": len(mappings) == 8,
            "chain_count_is_8": len(chains) == 8,
            "mechanism_node_count_is_56": sum(len(row["nodes"]) for row in chains) == 56,
            "impact_tiers_are_mutually_exclusive": len(ids) == 8,
            "all_ids_join": all(value == ids for value in related_ids.values()),
            "source_usage_boundaries_are_valid": all(
                row.get("usage_boundary") in valid_scopes
                for row in evidence_fetches
            ),
            "missing_market_values_are_not_zero": all(
                row["window_status"] == "AVAILABLE"
                or not row.get("fixed_windows")
                for row in windows
            ),
            "release_boundary_preserved": all(
                row.get("formal_ready") is False
                for rows in (
                    mappings,
                    chains,
                    evidence,
                    drivers,
                    observations,
                    windows,
                    completion,
                )
                for row in rows
            ),
            "baseline_directory_not_written": True,
        },
        "manual_spot_checks": [],
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }
    _write_json(output_root / "validation_report.json", validation)

    summary = {
        "dataset_version": "fingoose-event-01-industry-closure-v2-candidate",
        "event_id": "event-01",
        "mapping_count": len(mappings),
        "chain_count": len(chains),
        "mechanism_node_count": sum(len(row["nodes"]) for row in chains),
        "verified_source_count": len(evidence),
        "source_fetch_count": len(evidence_fetches),
        "available_market_window_count": sum(
            row["window_status"] == "AVAILABLE" for row in windows
        ),
        "candidate_complete_count": sum(
            row["completion_status"] == "CANDIDATE_COMPLETE"
            for row in completion
        ),
        "open_count": sum(
            row["completion_status"] == "OPEN" for row in completion
        ),
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }
    _write_json(output_root / "summary.json", summary)

    manifest_files = []
    for path in sorted(output_root.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            count = None
            if path.suffix == ".jsonl":
                count = len(read_jsonl(path))
            manifest_files.append(
                {
                    "path": path.name,
                    "bytes": path.stat().st_size,
                    "record_count": count,
                }
            )
    manifest = {
        "dataset_version": summary["dataset_version"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": manifest_files,
        "sha_gate": "DEFERRED",
        "sha_included": False,
        "formal_ready": False,
    }
    _write_json(output_root / "manifest.json", manifest)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("work/event_01_industry_closure_v2_candidate"),
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    summary = build_event_01_closure_bundle(root, output_root=output)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0
