import argparse
import copy
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.io_utils import read_jsonl, write_jsonl


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
ALLOWED_REVIEW_STATES = {"AI_REVIEWED", "REJECTED", "NEEDS_HUMAN_REVIEW"}


def _load_mechanism_sources(events_path: Path) -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for path in sorted(events_path.glob("event-*/sources.json")):
        event_id = path.parent.name
        rows = json.loads(path.read_text(encoding="utf-8-sig"))
        mechanism_rows = [row for row in rows if row["source_id"].startswith("mechanism-")]
        if len(mechanism_rows) != 1:
            raise ValueError(f"{event_id}: expected exactly one mechanism source")
        source = copy.deepcopy(mechanism_rows[0])
        source["event_id"] = event_id
        sources[event_id] = source
    return sources


def _event_fact_evidence(node: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": source["source_id"],
            "publisher": source.get("publisher"),
            "source_tier": source["source_tier"],
            "url": source["url"],
            "quote": source["quote"],
            "locator": source["locator"],
            "visibility": "PUBLIC_PREDICTION",
            "evidence_scope": "EVENT_FACT_AND_TIME",
        }
        for source in node["evidence"]
    ]


def _mechanism_evidence(source: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": source["source_id"],
            "publisher": source["publisher"],
            "source_tier": source["source_tier"],
            "url": source["url"],
            "published_at": source["published_at"],
            "quote": source["quote"],
            "locator": source["locator"],
            "evidence_scope": source["evidence_scope"],
            "visibility": "HIDDEN_FROM_PRIMARY_PREDICTION",
        }
    ]


def _node_kind(node_id: str) -> str:
    if node_id.endswith("-shock"):
        return "shock"
    if "-channel-" in node_id:
        return "channel"
    if "-intermediate-" in node_id:
        return "intermediate"
    if "-asset-" in node_id:
        return "asset"
    return "unknown"


def _duration_days(value: str) -> int | None:
    match = re.fullmatch(r"P([0-9]+)D", value or "")
    return int(match.group(1)) if match else None


def _binding_validation_errors(binding: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_path = binding.get("expected_path", {})
    if set(expected_path) != {"IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM"}:
        errors.append("expected_path_fields")
    elif any(value not in {"UP", "DOWN", "MIXED", "UNKNOWN"} for value in expected_path.values()):
        errors.append("expected_path_direction")
    lag = binding.get("lag", {})
    minimum = _duration_days(lag.get("minimum", ""))
    maximum = _duration_days(lag.get("maximum", ""))
    if minimum is None or maximum is None or minimum > maximum:
        errors.append("lag_order")
    for field in ("conditions", "invalidation_conditions", "from_node_id", "to_node_id"):
        if not binding.get(field):
            errors.append(field)
    event_prefix = f"{binding.get('event_id', '')}-"
    from_node = binding.get("from_node_id", "")
    to_node = binding.get("to_node_id", "")
    if not from_node.startswith(event_prefix) or not to_node.startswith(event_prefix):
        errors.append("cross_event_node")
    transition = (_node_kind(from_node), _node_kind(to_node))
    if transition not in {
        ("shock", "channel"),
        ("channel", "intermediate"),
        ("intermediate", "asset"),
    }:
        errors.append("invalid_node_transition")
    return errors


def review_bindings(
    timeline_nodes: list[dict[str, Any]],
    anchors: list[dict[str, Any]],
    bindings: list[dict[str, Any]],
    workbench_events_path: Path,
    reviewed_at: str,
) -> dict[str, list[dict[str, Any]]]:
    nodes = {row["fast_node_id"]: row for row in timeline_nodes}
    superseded_nodes = {
        row["supersedes_node_id"]: row
        for row in timeline_nodes
        if row.get("supersedes_node_id")
    }
    mechanism_sources = _load_mechanism_sources(workbench_events_path)

    projected_anchors: list[dict[str, Any]] = []
    anchor_map: dict[str, dict[str, Any]] = {}
    for original in anchors:
        original_node_id = original["fast_node_id"]
        node = nodes.get(original_node_id) or superseded_nodes.get(original_node_id)
        if node is None:
            raise ValueError(f"anchor node not found in 50/0 timeline: {original_node_id}")
        node_id = node["fast_node_id"]
        anchor = copy.deepcopy(original)
        if node_id != original_node_id:
            anchor["superseded_anchor_id"] = original["anchor_id"]
            anchor["anchor_id"] = f"anchor-{node_id}"
            anchor["fast_node_id"] = node_id
        for field in (
            "fact",
            "occurred_at",
            "first_public_at",
            "occurred_at_precision",
            "first_public_at_precision",
            "evidence_status",
            "phase",
            "node_action",
            "source_ids",
        ):
            anchor[field] = copy.deepcopy(node[field])
        anchor["causal_attribution_allowed"] = anchor["activation_mode"] == "CAUSAL_CANDIDATE"
        anchor["binding_status"] = "AI_REVIEWED"
        anchor["review"] = {
            "reviewer_type": "AI_DESK_REVIEW",
            "reviewed_at": reviewed_at,
            "rationale_zh": (
                "已与50/0时间线重新对齐；该锚点仅用于观察，不生成因果标签。"
                if anchor["activation_mode"] == "OBSERVATION_ONLY"
                else "已与50/0时间线重新对齐，可作为因果候选锚点；AI审核不等同于人工确认。"
            ),
        }
        projected_anchors.append(anchor)
        anchor_map[node_id] = anchor

    reviewed_bindings: list[dict[str, Any]] = []
    dispositions: list[dict[str, Any]] = []
    for original in bindings:
        binding = copy.deepcopy(original)
        anchor_id = binding["anchor_fast_node_id"]
        anchor = anchor_map.get(anchor_id)
        if anchor is None:
            raise ValueError(f"binding anchor not found: {anchor_id}")
        if not anchor["causal_attribution_allowed"]:
            raise ValueError(f"observation-only anchor has causal binding: {anchor_id}")

        errors = _binding_validation_errors(binding)
        node = nodes[anchor_id]
        mechanism_source = mechanism_sources[binding["event_id"]]
        binding["anchor_source_ids"] = copy.deepcopy(node["source_ids"])
        binding["event_fact_evidence"] = _event_fact_evidence(node)
        binding["mechanism_evidence"] = _mechanism_evidence(mechanism_source)
        binding["mechanism_evidence_scope"] = "SEPARATE_REVIEW_EVIDENCE"
        binding["causal_attribution_allowed"] = True
        explicitly_supported = binding["edge_id"] in mechanism_source.get("supported_edge_ids", [])
        binding["edge_support_status"] = (
            "EXPLICIT_EDGE_SUPPORT" if explicitly_supported else "EVENT_LEVEL_ONLY"
        )

        if binding.get("counterevidence_status") == "UNLINKED":
            if (
                _node_kind(binding["from_node_id"]) == "shock"
                and _node_kind(binding["to_node_id"]) == "channel"
            ):
                binding["counterevidence_status"] = "NOT_APPLICABLE"
                dispositions.append(
                    {
                        "binding_id": binding["binding_id"],
                        "event_id": binding["event_id"],
                        "disposition": "NOT_APPLICABLE",
                        "reason_zh": "已验证该边为冲击到统一渠道的入口边；原图未提供独立反证文本，失效条件保留为可证伪边界。",
                        "reviewed_at": reviewed_at,
                        "reviewer_type": "AI_DESK_REVIEW",
                    }
                )
            else:
                errors.append("unresolved_counterevidence")

        if errors:
            binding["binding_status"] = "REJECTED"
            rationale = f"结构或语义边界校验失败：{', '.join(sorted(set(errors)))}。"
        elif not explicitly_supported:
            binding["binding_status"] = "NEEDS_HUMAN_REVIEW"
            rationale = (
                "方向、时滞、节点类型和反证处置通过结构校验，但现有机制来源仅覆盖事件层，"
                "未显式支持该 edge_id；因此不得作为边级真值，需人工逐边审核。"
            )
        else:
            binding["binding_status"] = "AI_REVIEWED"
            rationale = (
                "方向、时滞、节点类型、反证处置及边级机制来源均通过审核；"
                "AI审核仍不等同于人工确认。"
            )
        binding["review"] = {
            "reviewer_type": "AI_DESK_REVIEW",
            "reviewed_at": reviewed_at,
            "rationale_zh": rationale,
            "human_confirmation": False,
        }
        reviewed_bindings.append(binding)

    states = {row["binding_status"] for row in reviewed_bindings}
    if not states <= ALLOWED_REVIEW_STATES:
        raise ValueError(f"forbidden binding review state: {sorted(states - ALLOWED_REVIEW_STATES)}")
    return {
        "anchors": projected_anchors,
        "bindings": reviewed_bindings,
        "counterevidence_dispositions": dispositions,
    }


def _anchor_status_conflict_count(anchors: list[dict[str, Any]]) -> int:
    return sum(
        bool(row.get("causal_attribution_allowed"))
        != (row.get("activation_mode") == "CAUSAL_CANDIDATE")
        for row in anchors
    )


def _valid_ai_review(review: Any, require_human_flag: bool) -> bool:
    if not isinstance(review, dict):
        return False
    try:
        reviewed_at = datetime.fromisoformat(
            str(review.get("reviewed_at", "")).replace("Z", "+00:00")
        )
    except ValueError:
        return False
    if reviewed_at.tzinfo is None:
        return False
    if (
        review.get("reviewer_type") != "AI_DESK_REVIEW"
        or not isinstance(review.get("rationale_zh"), str)
        or not review["rationale_zh"].strip()
    ):
        return False
    return not require_human_flag or review.get("human_confirmation") is False


def binding_hard_failures(
    anchors: list[dict[str, Any]],
    bindings: list[dict[str, Any]],
    dispositions: list[dict[str, Any]],
    mechanism_sources: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    failures: list[str] = []
    if len(anchors) != 24:
        failures.append("ANCHOR_COUNT_MISMATCH")
    if len({row.get("anchor_id") for row in anchors}) != len(anchors):
        failures.append("DUPLICATE_ANCHOR_ID")
    if sum(row.get("activation_mode") == "CAUSAL_CANDIDATE" for row in anchors) != 14:
        failures.append("CAUSAL_ANCHOR_COUNT_MISMATCH")
    if sum(row.get("activation_mode") == "OBSERVATION_ONLY" for row in anchors) != 10:
        failures.append("OBSERVATION_ANCHOR_COUNT_MISMATCH")
    if _anchor_status_conflict_count(anchors):
        failures.append("ANCHOR_STATUS_CONFLICT")

    if len(bindings) != 111:
        failures.append("BINDING_COUNT_MISMATCH")
    if len({row.get("binding_id") for row in bindings}) != len(bindings):
        failures.append("DUPLICATE_BINDING_ID")
    if any(row.get("binding_status") not in ALLOWED_REVIEW_STATES for row in bindings):
        failures.append("FORBIDDEN_BINDING_REVIEW_STATE")
    if any(row.get("counterevidence_status") == "UNLINKED" for row in bindings):
        failures.append("UNRESOLVED_COUNTEREVIDENCE")
    if len(dispositions) != 39:
        failures.append("COUNTEREVIDENCE_DISPOSITION_COUNT_MISMATCH")
    disposition_ids = {row.get("binding_id") for row in dispositions}
    if len(disposition_ids) != len(dispositions):
        failures.append("DUPLICATE_COUNTEREVIDENCE_DISPOSITION")
    not_applicable_ids = {
        row.get("binding_id")
        for row in bindings
        if row.get("counterevidence_status") == "NOT_APPLICABLE"
    }
    if disposition_ids != not_applicable_ids:
        failures.append("COUNTEREVIDENCE_DISPOSITION_MISMATCH")
    bindings_by_id = {row.get("binding_id"): row for row in bindings}
    for disposition in dispositions:
        binding = bindings_by_id.get(disposition.get("binding_id"))
        try:
            disposition_reviewed_at = datetime.fromisoformat(
                str(disposition.get("reviewed_at", "")).replace("Z", "+00:00")
            )
        except ValueError:
            disposition_reviewed_at = None
        if (
            binding is None
            or disposition.get("event_id") != binding.get("event_id")
            or disposition.get("disposition") != "NOT_APPLICABLE"
            or binding.get("counterevidence_status") != "NOT_APPLICABLE"
            or _node_kind(binding.get("from_node_id", "")) != "shock"
            or _node_kind(binding.get("to_node_id", "")) != "channel"
            or disposition.get("reviewer_type") != "AI_DESK_REVIEW"
            or not isinstance(disposition.get("reason_zh"), str)
            or not disposition["reason_zh"].strip()
            or disposition_reviewed_at is None
            or disposition_reviewed_at.tzinfo is None
        ):
            failures.append("COUNTEREVIDENCE_DISPOSITION_INVALID")

    observation_ids = {
        row.get("fast_node_id")
        for row in anchors
        if row.get("activation_mode") == "OBSERVATION_ONLY"
    }
    if any(row.get("anchor_fast_node_id") in observation_ids for row in bindings):
        failures.append("CAUSAL_BINDING_FROM_OBSERVATION_ANCHOR")
    for row in bindings:
        structural_errors = _binding_validation_errors(row)
        if structural_errors and row.get("binding_status") != "REJECTED":
            failures.append("INVALID_BINDING_NOT_REJECTED")
        trusted_source = (
            mechanism_sources.get(row.get("event_id"))
            if mechanism_sources is not None
            else None
        )
        explicitly_supported = bool(
            trusted_source
            and row.get("edge_id") in trusted_source.get("supported_edge_ids", [])
        )
        expected_support_status = (
            "EXPLICIT_EDGE_SUPPORT" if explicitly_supported else "EVENT_LEVEL_ONLY"
        )
        if row.get("edge_support_status") != expected_support_status:
            failures.append("EDGE_SUPPORT_STATUS_MISMATCH")
        if row.get("binding_status") == "AI_REVIEWED" and not explicitly_supported:
            failures.append("UNTRUSTED_EDGE_SUPPORT_CLAIM")
        if not _valid_ai_review(row.get("review"), require_human_flag=True):
            failures.append("BINDING_REVIEW_INVALID")
        if mechanism_sources is not None:
            expected_mechanism_evidence = (
                _mechanism_evidence(trusted_source) if trusted_source else []
            )
            if (
                row.get("mechanism_evidence") != expected_mechanism_evidence
                or row.get("mechanism_evidence_scope")
                != "SEPARATE_REVIEW_EVIDENCE"
            ):
                failures.append("MECHANISM_EVIDENCE_MISMATCH")
    return sorted(set(failures))


def _build_outputs() -> dict[str, Any]:
    events_path = PROJECT_ROOT / "work" / "ten_event_rapid_candidate_v2" / "events"
    mechanism_sources = _load_mechanism_sources(events_path)
    result = review_bindings(
        timeline_nodes=read_jsonl(PACKAGE_ROOT / "timeline_nodes.jsonl"),
        anchors=read_jsonl(
            PROJECT_ROOT / "work" / "transmission_24_anchor_v2_candidate" / "anchor_catalog.jsonl"
        ),
        bindings=read_jsonl(
            PROJECT_ROOT
            / "work"
            / "transmission_24_anchor_v2_candidate"
            / "dynamic_edge_bindings.jsonl"
        ),
        workbench_events_path=events_path,
        reviewed_at="2026-08-01T12:00:00+08:00",
    )
    write_jsonl(PACKAGE_ROOT / "anchor_catalog.jsonl", result["anchors"])
    write_jsonl(PACKAGE_ROOT / "dynamic_edge_bindings.jsonl", result["bindings"])
    write_jsonl(
        PACKAGE_ROOT / "counterevidence_dispositions.jsonl",
        result["counterevidence_dispositions"],
    )
    status_counts: dict[str, int] = {}
    for row in result["bindings"]:
        status_counts[row["binding_status"]] = status_counts.get(row["binding_status"], 0) + 1
    report = {
        "anchor_count": len(result["anchors"]),
        "binding_count": len(result["bindings"]),
        "causal_anchor_count": sum(
            row["activation_mode"] == "CAUSAL_CANDIDATE" for row in result["anchors"]
        ),
        "observation_anchor_count": sum(
            row["activation_mode"] == "OBSERVATION_ONLY" for row in result["anchors"]
        ),
        "binding_status_counts": status_counts,
        "counterevidence_unresolved_count": sum(
            row["counterevidence_status"] == "UNLINKED" for row in result["bindings"]
        ),
        "counterevidence_disposition_count": len(result["counterevidence_dispositions"]),
        "anchor_status_conflict_count": _anchor_status_conflict_count(result["anchors"]),
        "hard_failures": binding_hard_failures(
            result["anchors"],
            result["bindings"],
            result["counterevidence_dispositions"],
            mechanism_sources=mechanism_sources,
        ),
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }
    (PACKAGE_ROOT / "binding_validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    if args.build:
        print(json.dumps(_build_outputs(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
