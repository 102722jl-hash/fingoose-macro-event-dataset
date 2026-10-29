"""Stable public builder for Chinese company mechanism chains."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from _build_fingoose_company_mechanism_chains_v2_chinese import build as _build


def build(root: Path, *, output: Path | None = None) -> dict[str, Any]:
    report = _build(root, output=output)
    report.pop("chinese_event_fact_count", None)
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
