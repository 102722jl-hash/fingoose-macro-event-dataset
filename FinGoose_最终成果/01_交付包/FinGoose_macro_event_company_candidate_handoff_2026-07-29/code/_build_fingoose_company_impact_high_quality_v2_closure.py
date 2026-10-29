"""Build the company-impact package with confounder evidence closure."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import _build_fingoose_company_impact_high_quality_v2_base as _base
from fingoose_company_impact_io_v2 import read_jsonl


DATASET_VERSION = _base.DATASET_VERSION
CONFIG_FILES = _base.CONFIG_FILES
CANDIDATE_FILES = _base.CANDIDATE_FILES + (
    "announcement_body_retrieval.jsonl",
    "announcement_body_reviews.jsonl",
    "company_confounder_search_audits.jsonl",
    "trading_status_reviews.jsonl",
    "company_counterevidence_reviews.jsonl",
    "company_confounder_arguments.jsonl",
)


def build(root: Path, output_root: Path) -> dict[str, object]:
    root = root.resolve()
    output_root = output_root.resolve()
    report = _base.build(root, output_root)
    bodies = read_jsonl(output_root / "announcement_body_reviews.jsonl")
    searches = read_jsonl(output_root / "company_confounder_search_audits.jsonl")
    trading = read_jsonl(output_root / "trading_status_reviews.jsonl")
    counters = read_jsonl(output_root / "company_counterevidence_reviews.jsonl")
    arguments = read_jsonl(output_root / "company_confounder_arguments.jsonl")
    retrievals = read_jsonl(output_root / "announcement_body_retrieval.jsonl")
    report.update(
        {
            "announcement_retrieval_count": len(retrievals),
            "announcement_body_review_count": len(bodies),
            "confounder_search_audit_count": len(searches),
            "trading_status_review_count": len(trading),
            "counterevidence_review_count": len(counters),
            "confounder_argument_count": len(arguments),
        }
    )
    report["warnings"] = [
        warning
        for warning in report.get("warnings", [])
        if not str(warning).startswith(
            (
                "CONFOUNDER_BODY_REVIEW_PENDING:",
                "CONFOUNDER_SEARCH_PENDING:",
                "SUSPENSION_UNVERIFIED:",
            )
        )
    ] + ["CONFOUNDER_HUMAN_REVIEW_PENDING:30"]
    _base._write_json(output_root / "summary.json", report)
    _base._write_json(
        output_root / "validation_report.json",
        {**report, "valid_candidate": not report.get("hard_failures")},
    )
    (output_root / "README.md").write_text(
        "# FinGoose 公司影响高质量 v2 候选包\n\n"
        "本包连接十个事件、23 家公司和 30 条事件-公司映射。混杂层已覆盖官方公告正文、"
        "负向检索审计、六窗口交易状态、公司级反证和映射级中文论证。\n\n"
        "## 混杂证据闭环\n\n"
        f"- 公告正文抓取：{len(retrievals)} 条；正文审核：{len(bodies)} 条。\n"
        f"- 映射级检索审计：{len(searches)} 条；交易状态审核：{len(trading)} 条。\n"
        f"- 公司级反证审核：{len(counters)} 条；中文论证：{len(arguments)} 条。\n"
        f"- 混杂等级：{report.get('confounder_grade_counts')}。\n\n"
        "## 发布边界\n\n"
        "当前 `formal_ready=false`、`sha_gate=DEFERRED`，所有结论均为 "
        "`NEEDS_HUMAN_REVIEW`。标题不替代正文，缺失不转换为零，"
        "MATERIAL、DOMINANT 与 UNRESOLVED 仅进入挑战集。\n\n"
        "## 页面\n\n"
        "打开 `ui/index.html`，可按事件、时间线节点、行业和公司联动查看证据。\n",
        encoding="utf-8",
    )
    manifest_files = sorted(
        path
        for path in output_root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    )
    _base._write_json(
        output_root / "manifest.json",
        {
            "dataset_version": DATASET_VERSION,
            "formal_ready": False,
            "sha_gate": "DEFERRED",
            "files": [
                {
                    "path": path.relative_to(output_root).as_posix(),
                    "size": path.stat().st_size,
                    "sha256": _base._sha256(path),
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
