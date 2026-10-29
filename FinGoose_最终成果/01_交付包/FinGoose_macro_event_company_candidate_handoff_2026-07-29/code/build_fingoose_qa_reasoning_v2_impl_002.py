"""Date-aware CLI implementation for official-source candidate builds."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_fingoose_qa_reasoning_v2_impl_001 import _fetch_url
from fingoose_qa_contract_v2 import load_event_profiles
from fingoose_qa_reasoning_v2 import (
    build_qa_records,
    load_existing_source_fetches,
    read_jsonl,
    write_candidate_package,
)
from fingoose_qa_sources_date_aware_v2 import snapshot_source


def _fetch_registered_sources(root: Path, output_root: Path) -> list[dict[str, Any]]:
    registry = read_jsonl(root / "configs/qa_reasoning_v2/official_source_registry.jsonl")
    profiles = {
        row["event_id"]: row
        for row in load_event_profiles(root / "configs/qa_reasoning_v2/qa_event_profiles.json")
    }
    accessed_at = datetime.now(timezone.utc).isoformat()
    return [
        snapshot_source(
            source,
            cutoff_at=str(profiles[source["event_id"]]["prediction_cutoff_at"]),
            output_root=output_root,
            fetch_bytes=_fetch_url,
            accessed_at=accessed_at,
        )
        for source in registry
    ]


def build(
    root: Path,
    output_root: Path,
    *,
    fetch_sources: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    output_root = output_root.resolve()
    bundle = build_qa_records(root)
    if fetch_sources:
        source_fetches = _fetch_registered_sources(root, output_root)
    elif (output_root / "source_fetches.jsonl").exists():
        source_fetches = read_jsonl(output_root / "source_fetches.jsonl")
    else:
        source_fetches = load_existing_source_fetches(root)
    return write_candidate_package(
        root,
        output_root,
        bundle,
        source_fetches=source_fetches,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("work/qa_reasoning_pilot_v2_candidate"),
    )
    parser.add_argument("--fetch-sources", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    report = build(root, output, fetch_sources=args.fetch_sources)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if not report["hard_failures"] else 1


__all__ = ["build", "main"]
