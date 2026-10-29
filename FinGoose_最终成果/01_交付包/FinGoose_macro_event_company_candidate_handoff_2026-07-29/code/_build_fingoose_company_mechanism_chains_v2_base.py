"""Build seven-layer company mechanism chains for the frozen mappings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from fingoose_company_binding_selection_v2 import BINDING_SELECTIONS
from fingoose_company_impact_io_v2 import read_jsonl, write_jsonl
from fingoose_company_mechanism_chain_v2 import build_mechanism_chain


def _index_unique(
    rows: Sequence[Mapping[str, Any]], field: str, label: str
) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        key = str(row.get(field) or "")
        if not key or key in index:
            raise ValueError(f"{label}_KEY_INVALID:{field}:{key}")
        index[key] = row
    return index


def _candidate_path(destination: Path, source: Path, name: str) -> Path:
    preferred = destination / name
    return preferred if preferred.exists() else source / name


def _load_binding_reviews(
    destination: Path,
    source: Path,
    mappings: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    path = _candidate_path(destination, source, "event_company_binding_reviews.jsonl")
    if path.exists():
        return read_jsonl(path)
    return [
        {
            "mapping_id": str(mapping["mapping_id"]),
            "primary_binding_id": BINDING_SELECTIONS[str(mapping["event_id"])][0],
        }
        for mapping in mappings
    ]

def build(
    root: Path,
    *,
    output: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    config = root / "configs/company_impact_high_quality_v2"
    source = root / "work/company_impact_high_quality_v2_candidate"
    destination = (output or source).resolve()

    mappings = read_jsonl(config / "event_company_map.jsonl")
    profiles = read_jsonl(config / "company_mechanism_profiles.jsonl")
    binding_reviews = _load_binding_reviews(destination, source, mappings)
    evidence = read_jsonl(_candidate_path(destination, source, "company_evidence.jsonl"))
    directions = read_jsonl(
        _candidate_path(destination, source, "direction_assessments.jsonl")
    )
    market_windows = read_jsonl(
        _candidate_path(destination, source, "company_market_windows.jsonl")
    )
    relative_windows = read_jsonl(
        _candidate_path(destination, source, "relative_return_windows.jsonl")
    )
    confounders = read_jsonl(
        _candidate_path(destination, source, "company_confounders.jsonl")
    )
    timeline_nodes = read_jsonl(
        root / "work/timeline_fast_candidate_v2/timeline_nodes.jsonl"
    )

    mappings_by_id = _index_unique(mappings, "mapping_id", "MAPPING")
    profiles_by_mapping = _index_unique(profiles, "mapping_id", "PROFILE")
    bindings_by_mapping = _index_unique(
        binding_reviews, "mapping_id", "BINDING_REVIEW"
    )
    directions_by_mapping = _index_unique(directions, "mapping_id", "DIRECTION")
    markets_by_mapping = _index_unique(
        market_windows, "mapping_id", "MARKET_WINDOW"
    )
    relatives_by_mapping = _index_unique(
        relative_windows, "mapping_id", "RELATIVE_WINDOW"
    )
    confounders_by_mapping = _index_unique(
        confounders, "mapping_id", "CONFOUNDER"
    )
    timeline_by_id = _index_unique(timeline_nodes, "fast_node_id", "TIMELINE")
    evidence_by_company: dict[str, list[Mapping[str, Any]]] = {}
    for row in evidence:
        evidence_by_company.setdefault(str(row["company_id"]), []).append(row)

    mapping_ids = set(mappings_by_id)
    if len(mapping_ids) != 30:
        raise ValueError("FROZEN_MAPPING_CARDINALITY_MISMATCH")
    for label, index in (
        ("PROFILE", profiles_by_mapping),
        ("BINDING_REVIEW", bindings_by_mapping),
        ("DIRECTION", directions_by_mapping),
        ("MARKET_WINDOW", markets_by_mapping),
        ("RELATIVE_WINDOW", relatives_by_mapping),
        ("CONFOUNDER", confounders_by_mapping),
    ):
        if set(index) != mapping_ids:
            raise ValueError(f"{label}_MAPPING_COVERAGE_MISMATCH")

    chains: list[dict[str, Any]] = []
    for mapping in mappings:
        mapping_id = str(mapping["mapping_id"])
        profile = profiles_by_mapping[mapping_id]
        for field in ("event_id", "company_code", "company_name"):
            if str(profile.get(field) or "") != str(mapping.get(field) or ""):
                raise ValueError(f"PROFILE_IDENTITY_MISMATCH:{mapping_id}:{field}")
        event_node_id = str(mapping["event_node_id"])
        if event_node_id not in timeline_by_id:
            raise ValueError(f"TIMELINE_NODE_MISSING:{mapping_id}:{event_node_id}")
        company_id = str(mapping["company_id"])
        chains.append(
            build_mechanism_chain(
                mapping,
                profile,
                binding_review=bindings_by_mapping[mapping_id],
                company_evidence=evidence_by_company.get(company_id, []),
                direction_assessment=directions_by_mapping[mapping_id],
                market_window=markets_by_mapping[mapping_id],
                relative_window=relatives_by_mapping[mapping_id],
                confounder=confounders_by_mapping[mapping_id],
                timeline_node=timeline_by_id[event_node_id],
            )
        )

    write_jsonl(destination / "event_company_mechanism_chains.jsonl", chains)
    return {
        "mapping_count": len(mappings),
        "chain_count": len(chains),
        "node_count": sum(len(chain["nodes"]) for chain in chains),
        "edge_count": sum(len(chain["edges"]) for chain in chains),
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output
    if output is not None and not output.is_absolute():
        output = args.root / output
    print(
        json.dumps(
            build(args.root, output=output),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
