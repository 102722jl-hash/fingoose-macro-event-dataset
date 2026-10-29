"""Build the FinGoose company-impact high-quality v2 candidate package."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping, Sequence

from build_fingoose_company_candidate_completion_v2 import (
    build as build_completion_layers,
)
from fingoose_company_impact_io_v2 import read_jsonl, write_jsonl
from fingoose_company_impact_ui_v2 import write_ui


DATASET_VERSION = "fingoose-company-impact-high-quality-v2-candidate"
CONFIG_FILES = {
    "company_registry.jsonl": "company_registry.jsonl",
    "event_company_map.jsonl": "event_company_map.jsonl",
    "industry_classification_reviews.jsonl": "industry_classification_reviews.jsonl",
    "direction_reviews.jsonl": "direction_reviews.jsonl",
    "confounders.jsonl": "confounders.jsonl",
    "benchmark_registry.jsonl": "benchmark_registry.jsonl",
}
CANDIDATE_FILES = (
    "source_manifest_seed.jsonl",
    "company_claim_candidates.jsonl",
    "company_master_dossiers.jsonl",
    "company_evidence.jsonl",
    "event_company_exposures.jsonl",
    "direction_assessments.jsonl",
    "company_market_windows.jsonl",
    "relative_return_windows.jsonl",
    "market_source_registry.jsonl",
    "company_announcement_intake.jsonl",
    "company_confounders.jsonl",
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _copy_jsonl(source: Path, destination: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(source)
    if source.resolve() != destination.resolve():
        write_jsonl(destination, rows)
    return rows


def _recompute_relative_returns(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[int, list[str]]:
    count = 0
    errors: list[str] = []
    for row in rows:
        for horizon, observation in row.get("observations", {}).items():
            value = observation.get("market_relative_return")
            if value is None:
                continue
            company_start, company_end = observation["formula_inputs"]["company"]
            market_start, market_end = observation["formula_inputs"]["market"]
            expected = (company_end / company_start - 1) - (
                market_end / market_start - 1
            )
            if abs(expected - float(value)) > 1e-12:
                errors.append(f"{row['mapping_id']}:{horizon}")
            count += 1
    return count, errors


def _count_values(
    rows: Sequence[Mapping[str, Any]], field: str
) -> dict[str, int]:
    values = {str(row[field]) for row in rows if row.get(field) is not None}
    return {
        value: sum(str(row.get(field)) == value for row in rows)
        for value in sorted(values)
    }


def _public_ui_bundle(
    *,
    mappings: Sequence[Mapping[str, Any]],
    dossiers: Sequence[Mapping[str, Any]],
    directions: Sequence[Mapping[str, Any]],
    market_windows: Sequence[Mapping[str, Any]],
    relative_windows: Sequence[Mapping[str, Any]],
    confounders: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "dataset_version": DATASET_VERSION,
        "formal_ready": False,
        "sha_gate": "DEFERRED",
        "mappings": [
            {
                key: row.get(key)
                for key in (
                    "mapping_id",
                    "event_id",
                    "anchor_id",
                    "company_id",
                    "company_code",
                    "company_name",
                    "industry",
                    "industry_impact_id",
                    "lineage_status",
                )
            }
            for row in mappings
        ],
        "dossiers": [
            {
                key: row.get(key)
                for key in (
                    "company_id",
                    "company_code",
                    "company_name",
                    "dossier_status",
                    "business_exposure",
                    "geographic_exposure",
                    "demand_cost_exposure",
                    "limitations_and_counterevidence",
                    "gap_reason",
                    "review_status",
                )
            }
            for row in dossiers
        ],
        "directions": [
            {
                key: row.get(key)
                for key in (
                    "direction_id",
                    "mapping_id",
                    "event_id",
                    "company_id",
                    "horizons",
                    "mechanism",
                    "conditions",
                    "invalidation_conditions",
                    "review_status",
                )
            }
            for row in directions
        ],
        "company_market_windows": list(market_windows),
        "relative_return_windows": list(relative_windows),
        "company_confounders": list(confounders),
    }


def build(root: Path, output_root: Path) -> dict[str, Any]:
    root = root.resolve()
    output_root = output_root.resolve()
    config_root = root / "configs/company_impact_high_quality_v2"
    source_root = root / "work/company_impact_high_quality_v2_candidate"
    output_root.mkdir(parents=True, exist_ok=True)

    loaded: dict[str, list[dict[str, Any]]] = {}
    for output_name, config_name in CONFIG_FILES.items():
        loaded[output_name] = _copy_jsonl(
            config_root / config_name,
            output_root / output_name,
        )
    for name in CANDIDATE_FILES:
        loaded[name] = _copy_jsonl(source_root / name, output_root / name)

    completion_summary = build_completion_layers(root, output_root)
    for name in (
        "company_master_dossiers.jsonl",
        "direction_assessments.jsonl",
        "company_market_windows.jsonl",
        "relative_return_windows.jsonl",
        "company_confounders.jsonl",
    ):
        loaded[name] = read_jsonl(output_root / name)
    binding_reviews = read_jsonl(output_root / "event_company_binding_reviews.jsonl")
    completion_reports = read_jsonl(output_root / "candidate_completion_report.jsonl")
    mechanism_chains = read_jsonl(
        output_root / "event_company_mechanism_chains.jsonl"
    )

    companies = loaded["company_registry.jsonl"]
    mappings = loaded["event_company_map.jsonl"]
    dossiers = loaded["company_master_dossiers.jsonl"]
    directions = loaded["direction_assessments.jsonl"]
    market_windows = loaded["company_market_windows.jsonl"]
    relative_windows = loaded["relative_return_windows.jsonl"]
    confounders = loaded["company_confounders.jsonl"]
    benchmarks = loaded["benchmark_registry.jsonl"]
    industry_reviews = loaded["industry_classification_reviews.jsonl"]

    mappings_by_id = {str(row["mapping_id"]): row for row in mappings}
    for output_name, rows in (
        ("company_market_windows.jsonl", market_windows),
        ("relative_return_windows.jsonl", relative_windows),
    ):
        for row in rows:
            mapping = mappings_by_id.get(str(row.get("mapping_id")))
            if mapping is None:
                continue
            classification = mapping.get("industry_classification") or {}
            row["industry_id"] = classification.get("sw1_id")
            row["industry_name"] = classification.get("sw1_name")
            row["industry_classification_edition"] = classification.get(
                "classification_edition"
            )
            row["industry_classification_as_of_date"] = classification.get(
                "event_as_of_date"
            )
        write_jsonl(output_root / output_name, rows)

    company_ids = {row["company_id"] for row in companies}
    mapping_ids = {row["mapping_id"] for row in mappings}
    industry_review_mapping_ids = [
        str(row.get("mapping_id")) for row in industry_reviews
    ]
    industry_reviews_by_mapping = {
        str(row.get("mapping_id")): row for row in industry_reviews
    }
    orphan_ids = sorted(
        {
            str(row.get("company_id"))
            for row in mappings
            if row.get("company_id") not in company_ids
        }
    )
    hard_failures: list[str] = []
    if len(companies) != 23 or len(company_ids) != 23:
        hard_failures.append("COMPANY_CARDINALITY_MISMATCH")
    if len(mappings) != 30 or len(mapping_ids) != 30:
        hard_failures.append("EVENT_COMPANY_CARDINALITY_MISMATCH")
    if orphan_ids:
        hard_failures.append("ORPHAN_COMPANY_IDS")
    if (
        len(industry_reviews) != 30
        or len(set(industry_review_mapping_ids)) != 30
        or set(industry_review_mapping_ids) != mapping_ids
    ):
        hard_failures.append(
            "INDUSTRY_CLASSIFICATION_MAPPING_COVERAGE_MISMATCH"
        )

    industry_classifications: list[dict[str, Any]] = []
    industry_classification_unknown_count = 0
    industry_classification_coverage_count = 0
    for mapping in mappings:
        mapping_id = str(mapping["mapping_id"])
        classification = dict(mapping.get("industry_classification") or {})
        industry_classifications.append(classification)
        required_values = (
            classification.get("sw1_id"),
            classification.get("sw1_name"),
            classification.get("sw_industry_code"),
            classification.get("event_as_of_date"),
        )
        has_unknown = any(
            value in (None, "", "UNKNOWN") for value in required_values
        )
        if has_unknown:
            industry_classification_unknown_count += 1
            continue
        review = industry_reviews_by_mapping.get(mapping_id)
        if review is None:
            continue
        review_classification = review.get("industry_classification") or {}
        if (
            review.get("event_id") != mapping.get("event_id")
            or review_classification.get("event_as_of_date")
            != classification.get("event_as_of_date")
        ):
            hard_failures.append(
                "INDUSTRY_CLASSIFICATION_EVENT_DATE_MISMATCH"
            )
            continue
        if review_classification != classification:
            hard_failures.append(
                "INDUSTRY_CLASSIFICATION_REVIEW_MISMATCH"
            )
            continue
        industry_classification_coverage_count += 1
    if industry_classification_unknown_count:
        hard_failures.append("INDUSTRY_CLASSIFICATION_UNKNOWN")

    for name, rows in (
        ("DIRECTION", directions),
        ("MARKET", market_windows),
        ("RELATIVE", relative_windows),
        ("CONFOUNDER", confounders),
    ):
        row_mapping_ids = {row.get("mapping_id") for row in rows}
        if row_mapping_ids != mapping_ids:
            hard_failures.append(f"{name}_MAPPING_COVERAGE_MISMATCH")
    if (
        len(binding_reviews) != 30
        or {row.get("mapping_id") for row in binding_reviews} != mapping_ids
    ):
        hard_failures.append("BINDING_REVIEW_MAPPING_COVERAGE_MISMATCH")
    if (
        len(completion_reports) != 30
        or {row.get("mapping_id") for row in completion_reports} != mapping_ids
    ):
        hard_failures.append("COMPLETION_REPORT_MAPPING_COVERAGE_MISMATCH")
    if (
        len(mechanism_chains) != 30
        or {row.get("mapping_id") for row in mechanism_chains} != mapping_ids
    ):
        hard_failures.append("MECHANISM_CHAIN_MAPPING_COVERAGE_MISMATCH")
    if any(
        row.get("chain_status") != "PROPOSED_COMPANY_MECHANISM"
        or row.get("review_status") != "NEEDS_HUMAN_REVIEW"
        or row.get("formal_ready") is not False
        or row.get("sha_gate") != "DEFERRED"
        or row.get("price_selection_used") is not False
        for row in mechanism_chains
    ):
        hard_failures.append("MECHANISM_CHAIN_BOUNDARY_VIOLATION")
    if any(row.get("review_status") != "NEEDS_HUMAN_REVIEW" for row in binding_reviews):
        hard_failures.append("BINDING_REVIEW_BOUNDARY_VIOLATION")
    if any(row.get("review_status") != "NEEDS_HUMAN_REVIEW" for row in directions):
        hard_failures.append("AI_DIRECTION_REVIEW_BOUNDARY_VIOLATION")
    if any(row.get("hidden_label_eligible") for row in directions):
        hard_failures.append("AI_DIRECTION_LABEL_LEAKAGE")
    if any(row.get("price_selection_used") for row in mappings + directions):
        hard_failures.append("PRICE_SELECTION_LEAKAGE")

    market_observation_count, recompute_errors = _recompute_relative_returns(
        relative_windows
    )
    if recompute_errors:
        hard_failures.append("RELATIVE_RETURN_RECOMPUTE_FAILURE")

    warnings = [
        f"PARTIAL_DOSSIERS:{sum(row.get('dossier_status') == 'PARTIALLY_VERIFIED' for row in dossiers)}",
        f"DIRECTION_HUMAN_REVIEW_PENDING:{len(directions)}",
        f"INDUSTRY_BENCHMARK_PENDING:{sum(row.get('industry_benchmark_status') == 'DATA_PENDING' for row in market_windows)}",
        f"CONFOUNDER_BODY_REVIEW_PENDING:{sum(row.get('company_confounder_status') == 'CANDIDATES_REGISTERED_NEEDS_BODY_REVIEW' for row in confounders)}",
        f"CONFOUNDER_SEARCH_PENDING:{sum(row.get('company_confounder_status') == 'SEARCH_PENDING' for row in confounders)}",
        f"SUSPENSION_UNVERIFIED:{sum(row.get('suspension_status') == 'UNVERIFIED' for row in confounders)}",
    ]

    benchmark_types = {
        row["benchmark_id"]: row.get("benchmark_type") for row in benchmarks
    }
    industry_benchmark_types = [
        benchmark_types.get(row.get("industry_benchmark_id"))
        for row in market_windows
        if row.get("industry_benchmark_id")
    ]

    ui_root = output_root / "ui"
    write_ui(root, ui_root, candidate_root=output_root)

    report = {
        "dataset_version": DATASET_VERSION,
        "company_count": len(companies),
        "event_company_count": len(mappings),
        "binding_review_count": completion_summary["binding_review_count"],
        "completion_report_count": completion_summary["completion_report_count"],
        "mechanism_chain_count": completion_summary["mechanism_chain_count"],
        "mechanism_chain_node_count": completion_summary["mechanism_chain_node_count"],
        "mechanism_chain_edge_count": completion_summary["mechanism_chain_edge_count"],
        "candidate_complete_count": completion_summary["candidate_complete_count"],
        "candidate_open_count": completion_summary["open_count"],
        "broad_channel_only_count": completion_summary["broad_channel_only_count"],
        "dossier_search_audit_count": completion_summary["dossier_search_audit_count"],
        "industry_benchmark_registry_count": completion_summary["industry_benchmark_count"],
        "industry_classification_coverage_count": (
            industry_classification_coverage_count
        ),
        "industry_classification_unknown_count": (
            industry_classification_unknown_count
        ),
        "industry_classification_status_counts": _count_values(
            industry_classifications, "classification_status"
        ),
        "dossier_count": len(dossiers),
        "verified_dossier_count": sum(
            row.get("dossier_status") == "VERIFIED" for row in dossiers
        ),
        "partial_dossier_count": sum(
            row.get("dossier_status") == "PARTIALLY_VERIFIED" for row in dossiers
        ),
        "evidence_complete_candidate_dossier_count": sum(
            row.get("dossier_status") == "EVIDENCE_COMPLETE_CANDIDATE" for row in dossiers
        ),
        "direction_review_count": len(directions),
        "company_market_window_count": len(market_windows),
        "csi300_coverage_count": sum(
            row.get("market_benchmark_id") == "CSI300" for row in market_windows
        ),
        "shenwan_coverage_count": sum(
            value == "SHENWAN_L1_INDEX" for value in industry_benchmark_types
        ),
        "etf_proxy_count": sum(
            value == "ETF_PROXY" for value in industry_benchmark_types
        ),
        "relative_return_window_count": len(relative_windows),
        "company_confounder_count": len(confounders),
        "announcement_title_candidate_count": sum(
            len(row.get("registered_confounders") or []) for row in confounders
        ),
        "suspension_status_counts": _count_values(confounders, "suspension_status"),
        "confounder_grade_counts": _count_values(confounders, "overall_grade"),
        "orphan_id_count": len(orphan_ids),
        "market_relative_observation_count": market_observation_count,
        "relative_return_recompute_error_count": len(recompute_errors),
        "hard_failures": sorted(set(hard_failures)),
        "warnings": warnings,
        "formal_ready": False,
        "sha_gate": "DEFERRED",
        "ui_path": "ui/index.html",
    }
    _write_json(output_root / "summary.json", report)
    _write_json(
        output_root / "validation_report.json",
        {**report, "valid_candidate": not hard_failures},
    )
    (output_root / "README.md").write_text(
        "# FinGoose 公司影响高质量 v2 候选包\n\n"
        "本包连接十个事件、23 家公司、30 条事件-公司映射，并统一展示事件时间线、动态传导链、行业、公司证据、方向候选、价格窗口、相对收益与混杂候选。\n\n"
        "## 当前覆盖\n\n"
        f"- dossier：{report['verified_dossier_count']} 个已验证，{report['partial_dossier_count']} 个部分验证。\n"
        f"- 方向判断：{report['direction_review_count']} 条，全部待人工审核。\n"
        f"- 沪深300：覆盖 {report['csi300_coverage_count']}/30 个公司窗口，共 {report['market_relative_observation_count']} 个可复算相对收益观测。\n"
        f"- 行业基准：申万 {report['shenwan_coverage_count']} 条，ETF 替代 {report['etf_proxy_count']} 条；其余保持 DATA_PENDING。\n"
        f"- 混杂：{report['announcement_title_candidate_count']} 条公告标题候选待正文审核；停复牌状态 {report['suspension_status_counts']}；混杂等级 {report['confounder_grade_counts']}。\n\n"
        "## 发布边界\n\n"
        "当前 `formal_ready=false`、`sha_gate=DEFERRED`。AI 方向不得进入隐藏标签；申万行业基准、公司公告正文、停复牌与公司级反证仍是明确缺口。\n\n"
        "## 页面\n\n"
        "直接打开 `ui/index.html`，也可通过本地静态服务器访问。\n",
        encoding="utf-8",
    )

    manifest_files = sorted(
        path
        for path in output_root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    )
    manifest = {
        "dataset_version": DATASET_VERSION,
        "formal_ready": False,
        "sha_gate": "DEFERRED",
        "files": [
            {
                "path": path.relative_to(output_root).as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in manifest_files
        ],
    }
    _write_json(output_root / "manifest.json", manifest)
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
    output = args.output if args.output.is_absolute() else root / args.output
    print(json.dumps(build(root, output), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
