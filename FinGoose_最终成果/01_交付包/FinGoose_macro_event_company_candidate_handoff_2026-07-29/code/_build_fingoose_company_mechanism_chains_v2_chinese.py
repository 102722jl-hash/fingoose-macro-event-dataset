"""Build company mechanism chains with verified Chinese event-fact display text."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import _build_fingoose_company_mechanism_chains_v2_base as _base
from fingoose_company_impact_io_v2 import read_jsonl, write_jsonl


def build(
    root: Path,
    *,
    output: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    destination = (output or root / "work/company_impact_high_quality_v2_candidate").resolve()
    report = _base.build(root, output=destination)
    profiles = {
        str(row["fast_node_id"]): row
        for row in read_jsonl(
            root / "configs/company_impact_high_quality_v2/timeline_display_profiles.jsonl"
        )
    }
    chains = read_jsonl(destination / "event_company_mechanism_chains.jsonl")
    for chain in chains:
        timeline_node_id = str(chain["timeline_node_id"])
        profile = profiles.get(timeline_node_id)
        if not profile or not profile.get("event_title_zh"):
            raise ValueError(f"CHINESE_TIMELINE_PROFILE_MISSING:{timeline_node_id}")
        title = str(profile["event_title_zh"]).strip()
        summary = str(profile.get("event_summary_zh") or "").strip()
        chain["nodes"][0]["statement"] = f"{title}：{summary}" if summary else title
        chain["nodes"][0]["display_language"] = "zh-CN"
    write_jsonl(destination / "event_company_mechanism_chains.jsonl", chains)
    report["chinese_event_fact_count"] = len(chains)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    output = args.output
    if output is not None and not output.is_absolute():
        output = args.root / output
    print(json.dumps(build(args.root, output=output), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
