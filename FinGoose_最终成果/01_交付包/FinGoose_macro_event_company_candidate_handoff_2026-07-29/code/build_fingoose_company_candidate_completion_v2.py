"""Build completion layers after closing company-confounder evidence ledgers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from fingoose_company_candidate_completion_v2 import evaluate_completion
from fingoose_company_impact_io_v2 import read_jsonl, write_jsonl

import _build_fingoose_company_candidate_completion_v2_base as _base
from build_fingoose_company_confounder_closure_v2 import build_closure


CONFOUNDER_INPUT_FILES = (
    "announcement_body_retrieval.jsonl",
    "announcement_body_reviews.jsonl",
    "company_confounder_search_audits.jsonl",
    "trading_status_reviews.jsonl",
    "company_counterevidence_reviews.jsonl",
)


def _copy_jsonl(source: Path, destination: Path) -> None:
    if source.resolve() == destination.resolve():
        return
    write_jsonl(destination, read_jsonl(source))


def _index(path: Path, key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in read_jsonl(path)}


def build(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve()
    output = output.resolve()
    source = root / "work/company_impact_high_quality_v2_candidate"
    output.mkdir(parents=True, exist_ok=True)
    _copy_jsonl(source / "event_company_map.jsonl", output / "event_company_map.jsonl")
    for name in CONFOUNDER_INPUT_FILES:
        _copy_jsonl(source / name, output / name)

    report = _base.build(root, output)
    confounders, arguments = build_closure(root, output)
    searches = _index(output / "company_confounder_search_audits.jsonl", "mapping_id")
    for row in confounders:
        row["search_status"] = searches[str(row["mapping_id"])]["search_status"]
    write_jsonl(output / "company_confounders.jsonl", confounders)
    write_jsonl(output / "company_confounder_arguments.jsonl", arguments)

    mappings = read_jsonl(output / "event_company_map.jsonl")
    dossiers = _index(output / "company_master_dossiers.jsonl", "company_id")
    directions = _index(output / "direction_assessments.jsonl", "mapping_id")
    bindings = _index(output / "event_company_binding_reviews.jsonl", "mapping_id")
    markets = _index(output / "company_market_windows.jsonl", "mapping_id")
    relatives = _index(output / "relative_return_windows.jsonl", "mapping_id")
    confounder_index = {str(row["mapping_id"]): row for row in confounders}
    chains = _index(output / "event_company_mechanism_chains.jsonl", "mapping_id")
    completion = []
    for mapping in sorted(mappings, key=_base._mapping_sort_key):
        mapping_id = str(mapping["mapping_id"])
        item = evaluate_completion(
            mapping_id=mapping_id,
            mechanism_chain=chains[mapping_id],
            binding_review=bindings[mapping_id],
            dossier=dossiers[str(mapping["company_id"])],
            direction=directions[mapping_id],
            market_window=markets[mapping_id],
            relative_window=relatives[mapping_id],
            confounder=confounder_index[mapping_id],
        )
        item["sha_gate"] = "DEFERRED"
        completion.append(item)
    write_jsonl(output / "candidate_completion_report.jsonl", completion)

    report.update(
        {
            "announcement_body_review_count": len(
                read_jsonl(output / "announcement_body_reviews.jsonl")
            ),
            "confounder_search_audit_count": len(searches),
            "trading_status_review_count": len(
                read_jsonl(output / "trading_status_reviews.jsonl")
            ),
            "counterevidence_review_count": len(
                read_jsonl(output / "company_counterevidence_reviews.jsonl")
            ),
            "confounder_argument_count": len(arguments),
            "candidate_complete_count": sum(
                row["completion_status"] == "CANDIDATE_COMPLETE" for row in completion
            ),
            "open_count": sum(row["completion_status"] == "OPEN" for row in completion),
        }
    )
    _base._write_json(output / "candidate_completion_summary.json", report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("work/company_impact_high_quality_v2_candidate"),
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output
    if not output.is_absolute():
        output = root / output
    print(json.dumps(build(root, output), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
