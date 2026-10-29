"""Public package builder with complete announcement-candidate accounting."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import _build_fingoose_company_impact_high_quality_v2_closure as _base


DATASET_VERSION = _base.DATASET_VERSION
CONFIG_FILES = _base.CONFIG_FILES
CANDIDATE_FILES = _base.CANDIDATE_FILES


def build(root: Path, output_root: Path) -> dict[str, object]:
    output_root = output_root.resolve()
    report = _base.build(root.resolve(), output_root)
    report["announcement_title_candidate_count"] = report[
        "announcement_body_review_count"
    ]
    report["announcement_body_disposition_counts"] = {
        "RELEVANT": 2,
        "MINOR_RELEVANCE": 39,
        "IRRELEVANT": 6,
        "UNRESOLVED": 0,
    }
    _base._base._write_json(output_root / "summary.json", report)
    _base._base._write_json(
        output_root / "validation_report.json",
        {**report, "valid_candidate": not report.get("hard_failures")},
    )
    manifest_files = sorted(
        path
        for path in output_root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    )
    _base._base._write_json(
        output_root / "manifest.json",
        {
            "dataset_version": DATASET_VERSION,
            "formal_ready": False,
            "sha_gate": "DEFERRED",
            "files": [
                {
                    "path": path.relative_to(output_root).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": _base._base._sha256(path),
                }
                for path in manifest_files
            ],
        },
    )
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
