import argparse
import copy
import hashlib
import html
import json
import re
import sys
import unicodedata
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from pypdf import PdfReader


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.bindings import _load_mechanism_sources, binding_hard_failures
from src.io_utils import read_jsonl, write_jsonl
from src.market import market_hard_failures


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_EVENTS = {"event-02", "event-03", "event-04"}
ALLOWED_CHANNEL_VOCABULARY = {
    "ASIA_FX_SPILLOVER",
    "BANKING_STRESS",
    "CHINA_REOPENING",
    "DISCOUNT_RATE",
    "DOLLAR_LIQUIDITY",
    "ENERGY_SUPPLY",
    "GEOPOLITICAL_RISK",
    "GLOBAL_DEMAND",
    "GLOBAL_GROWTH",
    "GLOBAL_GROWTH_EXPECTATIONS",
    "GLOBAL_LIQUIDITY",
    "INFLATION_EXPECTATIONS",
    "RATE_DIFFERENTIAL",
    "RATE_EXPECTATIONS",
    "RISK_APPETITE",
    "SAFE_HAVEN_DEMAND",
    "TERMS_OF_TRADE",
    "TRADE_COSTS",
    "YEN_FUNDING",
}
TEXT_SNAPSHOT_SUFFIXES = {".html", ".htm", ".md", ".txt", ".json"}
PDF_SNAPSHOT_SUFFIXES = {".pdf"}

TRACKS = {
    "TIMELINE_RECONSTRUCTION": {
        "score": "node_precision_recall_and_phase_accuracy",
        "hard_failure_scope": ["FABRICATED_SOURCE", "D3_LEAKAGE"],
    },
    "GRAPH_CONSTRUCTION": {
        "score": "edge_precision_recall_and_path_field_accuracy",
        "hard_failure_scope": ["CAUSAL_LABEL_FROM_OBSERVATION_ANCHOR", "FORBIDDEN_REVIEW_STATE"],
    },
    "DIRECTION_AND_REFUSAL": {
        "score": "direction_accuracy_and_refusal_accuracy",
        "hard_failure_scope": ["NON_RECOMPUTABLE_VALUE", "CONFOUNDING_GATE_BYPASS"],
    },
}


def _publication_upper_bound(value: str, precision: str) -> datetime:
    if precision == "DATE":
        parsed_date = date.fromisoformat(value)
        return datetime.combine(parsed_date, time.max, tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("publication timestamp requires timezone")
    return parsed


def _format_timestamp(value: datetime) -> str:
    rendered = value.isoformat()
    return rendered.replace("+00:00", "Z")


def _event_cutoff(event_anchors: list[dict[str, Any]]) -> datetime:
    causal = [row for row in event_anchors if row["activation_mode"] == "CAUSAL_CANDIDATE"]
    candidates = causal or event_anchors
    if not candidates:
        raise ValueError("event has no anchor")
    anchor_time = min(
        _publication_upper_bound(
            row["first_public_at"],
            row["first_public_at_precision"],
        )
        for row in candidates
    )
    return anchor_time + timedelta(hours=72)

def _timeline_label(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "fast_node_id": row["fast_node_id"],
            "phase": row["phase"],
            "node_action": row["node_action"],
            "fact": row["fact"],
            "occurred_at": row["occurred_at"],
            "first_public_at": row["first_public_at"],
        }
        for row in sorted(nodes, key=lambda item: (item["sequence"], item["fast_node_id"]))
    ]


def _graph_label(bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "binding_id": row["binding_id"],
            "anchor_fast_node_id": row["anchor_fast_node_id"],
            "from_node_id": row["from_node_id"],
            "to_node_id": row["to_node_id"],
            "expected_path": copy.deepcopy(row["expected_path"]),
            "lag": copy.deepcopy(row["lag"]),
            "binding_status": row["binding_status"],
            "scoring_eligible": row["binding_status"] == "AI_REVIEWED",
        }
        for row in sorted(bindings, key=lambda item: item["binding_id"])
    ]


def _direction_label(
    anchors: list[dict[str, Any]],
    bindings: list[dict[str, Any]],
    industries: list[dict[str, Any]],
    windows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    confounding = (
        copy.deepcopy(windows[0]["confounding_by_horizon"])
        if windows
        else {
            "T_MINUS_20": "UNRESOLVED",
            "T_MINUS_1": "UNRESOLVED",
            "T0": "UNRESOLVED",
            "D1": "UNRESOLVED",
            "D3": "UNRESOLVED",
            "D5": "UNRESOLVED",
            "D20": "UNRESOLVED",
        }
    )
    binding_anchor_ids = {row["anchor_fast_node_id"] for row in bindings}
    rows: list[dict[str, Any]] = []
    for anchor in sorted(anchors, key=lambda item: item["anchor_id"]):
        causal = bool(anchor["causal_attribution_allowed"])
        anchor_industries = [
            row for row in industries if row["anchor_id"] == anchor["anchor_id"]
        ]
        unresolved_direction = not anchor_industries or any(
            row["direction_status"] == "NEEDS_HUMAN_REVIEW" for row in anchor_industries
        )
        refusal_required = (
            not causal
            or anchor["fast_node_id"] not in binding_anchor_ids
            or unresolved_direction
        )
        clean = {
            horizon: causal and not refusal_required and grade in {"CLEAN", "MINOR"}
            for horizon, grade in confounding.items()
        }
        rows.append(
            {
                "anchor_id": anchor["anchor_id"],
                "fast_node_id": anchor["fast_node_id"],
                "activation_mode": anchor["activation_mode"],
                "causal_attribution_allowed": causal,
                "refusal_required": refusal_required,
                "refusal_reason": (
                    "OBSERVATION_ONLY_ANCHOR"
                    if not causal
                    else "DIRECTION_OR_MECHANISM_REQUIRES_HUMAN_REVIEW"
                    if refusal_required
                    else None
                ),
                "confounding_by_horizon": copy.deepcopy(confounding),
                "clean_attribution_eligible_by_horizon": clean,
                "industry_direction_labels": [
                    {
                        "impact_candidate_id": row["impact_candidate_id"],
                        "direction_path": copy.deepcopy(row["direction_path"]),
                        "direction_status": row["direction_status"],
                    }
                    for row in anchor_industries
                ],
            }
        )
    return rows


def _public_evidence_documents(
    event_id: str,
    public_nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for node in public_nodes:
        for evidence in node["evidence"]:
            documents.append(
                {
                    "evidence_packet_id": (
                        f"{event_id}-evidence-{len(documents) + 1:02d}"
                    ),
                    "event_id": event_id,
                    "public_source_id": "pubsrc-"
                    + hashlib.sha256(
                        (
                            event_id
                            + "|"
                            + evidence["url"]
                            + "|"
                            + evidence["quote"]
                        ).encode("utf-8")
                    ).hexdigest()[:20],
                    "publisher": evidence.get("publisher"),
                    "source_tier": evidence["source_tier"],
                    "url": evidence["url"],
                    "quote": evidence["quote"],
                    "locator": evidence["locator"]
                    .split("| snapshot:", 1)[0]
                    .strip()
                    .replace("fast-event", "source"),
                    "first_public_at": node["first_public_at"],
                    "first_public_at_precision": node["first_public_at_precision"],
                    "publication_time_basis": "NODE_FIRST_PUBLIC_AT_WITH_EVIDENCE_LOCATOR",
                    "visibility": "PUBLIC_PREDICTION",
                }
            )
    return documents


def build_benchmark(
    timeline_nodes: list[dict[str, Any]],
    anchors: list[dict[str, Any]],
    bindings: list[dict[str, Any]],
    industry_impacts: list[dict[str, Any]],
    company_windows: list[dict[str, Any]],
) -> dict[str, Any]:
    event_ids = sorted({row["event_id"] for row in timeline_nodes})
    cases: list[dict[str, Any]] = []
    all_labels: list[dict[str, Any]] = []
    hidden_labels: list[dict[str, Any]] = []
    for event_id in event_ids:
        event_nodes = [row for row in timeline_nodes if row["event_id"] == event_id]
        event_anchors = [row for row in anchors if row["event_id"] == event_id]
        event_bindings = [row for row in bindings if row["event_id"] == event_id]
        event_industries = [row for row in industry_impacts if row["event_id"] == event_id]
        event_windows = [row for row in company_windows if row["event_id"] == event_id]
        cutoff = _event_cutoff(event_anchors)
        public_nodes = [
            row
            for row in event_nodes
            if row["visibility"] == "PUBLIC_PREDICTION"
            and _publication_upper_bound(
                row["first_public_at"], row["first_public_at_precision"]
            ) <= cutoff
        ]
        evidence_documents = _public_evidence_documents(event_id, public_nodes)
        labels = {
            "event_id": event_id,
            "timeline_reconstruction": _timeline_label(event_nodes),
            "graph_construction": _graph_label(event_bindings),
            "direction_and_refusal": _direction_label(
                event_anchors, event_bindings, event_industries, event_windows
            ),
        }
        case = {
            "case_id": f"benchmark-{event_id}",
            "event_id": event_id,
            "case_mode": "PUBLIC_EXAMPLE" if event_id in EXAMPLE_EVENTS else "HIDDEN_EVALUATION",
            "prediction_cutoff_date": cutoff.date().isoformat(),
            "prediction_cutoff_at": _format_timestamp(cutoff),
            "prediction_cutoff_policy": "ANCHOR_PUBLICATION_PLUS_72H_DATE_VALUES_USE_END_OF_DAY_UPPER_BOUND",
            "public_input": {
                "evidence_documents": evidence_documents,
                "allowed_channel_vocabulary": sorted(
                    {
                        channel
                        for row in event_industries
                        for channel in row.get("channels", [])
                    }
                ),
            },
            "tasks": [
                "TIMELINE_RECONSTRUCTION",
                "GRAPH_CONSTRUCTION",
                "DIRECTION_AND_REFUSAL",
            ],
        }
        if event_id in EXAMPLE_EVENTS:
            case["example_labels"] = copy.deepcopy(labels)
        else:
            hidden_labels.append(copy.deepcopy(labels))
        cases.append(case)
        all_labels.append(labels)
    tracks = copy.deepcopy(TRACKS)
    tracks["TIMELINE_RECONSTRUCTION"]["status"] = "READY"
    graph_scoring_labels = sum(
        edge["scoring_eligible"]
        for labels in all_labels
        for edge in labels["graph_construction"]
    )
    direction_scoring_labels = sum(
        industry["direction_status"] == "AI_REVIEWED"
        for labels in all_labels
        for decision in labels["direction_and_refusal"]
        for industry in decision["industry_direction_labels"]
    )
    tracks["GRAPH_CONSTRUCTION"]["status"] = (
        "READY" if graph_scoring_labels else "BLOCKED_NO_SCORING_LABELS"
    )
    tracks["DIRECTION_AND_REFUSAL"]["status"] = (
        "READY" if direction_scoring_labels else "BLOCKED_NO_SCORING_LABELS"
    )
    return {
        "cases": cases,
        "hidden_labels": hidden_labels,
        "all_labels": all_labels,
        "evaluation_report": {
            "tracks": tracks,
            "composite_scoring_policy": "FORBIDDEN",
            "example_events": sorted(EXAMPLE_EVENTS),
            "hidden_event_count": len(hidden_labels),
            "graph_scoring_label_count": graph_scoring_labels,
            "direction_scoring_label_count": direction_scoring_labels,
        },
    }


def _normalise_search_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(
        r"</?(?:p|div|br|h[1-6]|li|tr|td|section|article)[^>]*>",
        " ",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(r"<[^>]+>", "", value)
    value = unicodedata.normalize("NFKC", value)
    value = value.translate(
        {
            0x2018: "'",
            0x2019: "'",
            0x201C: '"',
            0x201D: '"',
            0x2013: "-",
            0x2014: "-",
        }
    )
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"\s*-\s*", "-", value)
    value = re.sub(r"\s+([,.;:])", r"\1", value)
    return value.casefold()


@lru_cache(maxsize=16)
def _extract_pdf_text_cached(
    path_text: str,
    size: int,
    modified_ns: int,
) -> str:
    del size, modified_ns
    path = Path(path_text)
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_pdf_text(path: Path) -> str:
    stat = path.stat()
    return _extract_pdf_text_cached(
        str(path.resolve()),
        stat.st_size,
        stat.st_mtime_ns,
    )


def _resolve_snapshot_path(project_root: Path, snapshot_path: str) -> Path | None:
    candidates = [
        project_root / snapshot_path,
        project_root / "work" / "timeline_fast_candidate_v2" / snapshot_path,
    ]
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def validate_release_gates(
    bundle: dict[str, Any],
    timeline_nodes: list[dict[str, Any]],
    anchors: list[dict[str, Any]],
    bindings: list[dict[str, Any]],
    company_windows: list[dict[str, Any]],
    source_manifest: list[dict[str, Any]],
    project_root: Path,
) -> dict[str, Any]:
    failures: list[str] = []
    if len(bundle["cases"]) != 10 or len(bundle["hidden_labels"]) != 7:
        failures.append("EVENT_ISOLATION_COUNT_FAILURE")
    examples = {
        row["event_id"] for row in bundle["cases"] if "example_labels" in row
    }
    hidden = {row["event_id"] for row in bundle["hidden_labels"]}
    if examples != EXAMPLE_EVENTS or examples & hidden:
        failures.append("PUBLIC_HIDDEN_EVENT_LEAKAGE")
    if "composite_score" in bundle["evaluation_report"]:
        failures.append("COMPOSITE_SCORE_FORBIDDEN")

    allowed_public_input_fields = {"evidence_documents", "allowed_channel_vocabulary"}
    allowed_public_evidence_fields = {
        "evidence_packet_id",
        "event_id",
        "public_source_id",
        "publisher",
        "source_tier",
        "url",
        "quote",
        "locator",
        "first_public_at",
        "first_public_at_precision",
        "publication_time_basis",
        "visibility",
    }
    timeline_by_event = {
        event_id: [row for row in timeline_nodes if row["event_id"] == event_id]
        for event_id in {row["event_id"] for row in timeline_nodes}
    }
    anchors_by_event = {
        event_id: [row for row in anchors if row["event_id"] == event_id]
        for event_id in {row["event_id"] for row in anchors}
    }
    for case in bundle["cases"]:
        public_input = case["public_input"]
        if set(public_input) != allowed_public_input_fields:
            failures.append("PUBLIC_LABEL_LEAKAGE")
        vocabulary = public_input.get("allowed_channel_vocabulary")
        if (
            not isinstance(vocabulary, list)
            or vocabulary != sorted(set(vocabulary))
            or any(
                not isinstance(item, str) or item not in ALLOWED_CHANNEL_VOCABULARY
                for item in vocabulary
            )
        ):
            failures.append("PUBLIC_VOCABULARY_INVALID")
        try:
            cutoff = datetime.fromisoformat(
                case["prediction_cutoff_at"].replace("Z", "+00:00")
            )
            if cutoff.tzinfo is None:
                raise ValueError("cutoff timezone missing")
        except (KeyError, TypeError, ValueError):
            failures.append("D3_CUTOFF_INVALID")
            cutoff = datetime.min.replace(tzinfo=timezone.utc)
        trusted_anchors = anchors_by_event.get(case.get("event_id"), [])
        try:
            trusted_cutoff = _event_cutoff(trusted_anchors)
        except (KeyError, TypeError, ValueError):
            failures.append("D3_CUTOFF_INVALID")
            trusted_cutoff = datetime.min.replace(tzinfo=timezone.utc)
        if cutoff != trusted_cutoff:
            failures.append("D3_CUTOFF_MISMATCH")
        evidence_documents = public_input.get("evidence_documents", [])
        if not isinstance(evidence_documents, list):
            failures.append("PUBLIC_LABEL_LEAKAGE")
            evidence_documents = []
        for evidence in evidence_documents:
            if not isinstance(evidence, dict) or set(evidence) != allowed_public_evidence_fields:
                failures.append("PUBLIC_LABEL_LEAKAGE")
                continue
            try:
                published = _publication_upper_bound(
                    evidence["first_public_at"],
                    evidence["first_public_at_precision"],
                )
            except (KeyError, TypeError, ValueError):
                failures.append("D3_LEAKAGE")
                continue
            if evidence.get("visibility") != "PUBLIC_PREDICTION" or published > cutoff:
                failures.append("D3_LEAKAGE")
            if (
                evidence.get("publication_time_basis")
                not in {
                    "NODE_FIRST_PUBLIC_AT_WITH_EVIDENCE_LOCATOR",
                    "DOCUMENT_PUBLICATION_AT",
                }
            ):
                failures.append("D3_PUBLICATION_BASIS_INVALID")
            if "fast-event" in json.dumps(evidence, ensure_ascii=False):
                failures.append("PUBLIC_LABEL_LEAKAGE")
        trusted_public_nodes = [
            row
            for row in timeline_by_event.get(case.get("event_id"), [])
            if row.get("visibility") == "PUBLIC_PREDICTION"
            and _publication_upper_bound(
                row["first_public_at"], row["first_public_at_precision"]
            )
            <= trusted_cutoff
        ]
        expected_documents = _public_evidence_documents(
            case.get("event_id", ""),
            trusted_public_nodes,
        )
        if evidence_documents != expected_documents:
            failures.append("PUBLIC_EVIDENCE_MISMATCH")

    forbidden = {
        row["binding_status"]
        for row in bindings
        if row["binding_status"] not in {"AI_REVIEWED", "REJECTED", "NEEDS_HUMAN_REVIEW"}
    }
    if forbidden:
        failures.append("FORBIDDEN_REVIEW_STATE")
    observation_ids = {
        row["fast_node_id"] for row in anchors if row["activation_mode"] == "OBSERVATION_ONLY"
    }
    if any(row["anchor_fast_node_id"] in observation_ids for row in bindings):
        failures.append("CAUSAL_LABEL_FROM_OBSERVATION_ANCHOR")

    manifest_ids = [row.get("source_id") for row in source_manifest]
    if len(set(manifest_ids)) != len(manifest_ids):
        failures.append("DUPLICATE_SOURCE_MANIFEST_ID")
    manifest_by_id = {row["source_id"]: row for row in source_manifest}
    source_events: dict[str, set[str]] = {}
    quote_snapshot_checked = 0
    pdf_quote_snapshot_checked = 0
    quote_snapshot_binary_unchecked = 0
    metadata_fields = (
        "url",
        "snapshot_path",
        "publisher",
        "source_tier",
    )
    for node in timeline_nodes:
        for evidence in node.get("evidence", []):
            source_id = evidence.get("source_id")
            manifest_row = manifest_by_id.get(source_id)
            if (
                not source_id
                or not evidence.get("url")
                or not evidence.get("quote")
                or not evidence.get("locator")
            ):
                failures.append("FABRICATED_OR_INCOMPLETE_SOURCE")
                continue
            manifest_excerpts = (
                manifest_row.get("evidence_excerpts", [])
                if manifest_row is not None
                else []
            )
            evidence_excerpt = {
                "quote": evidence.get("quote"),
                "locator": evidence.get("locator"),
            }
            if (
                manifest_row is None
                or any(
                    manifest_row.get(field) != evidence.get(field)
                    for field in metadata_fields
                )
                or evidence_excerpt not in manifest_excerpts
            ):
                failures.append("SOURCE_MANIFEST_MISMATCH")
                continue
            snapshot_path = _resolve_snapshot_path(
                project_root,
                manifest_row["snapshot_path"],
            )
            if snapshot_path is None:
                failures.append("SOURCE_SNAPSHOT_MISSING")
            else:
                if manifest_row.get("sha256"):
                    actual_sha = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
                    if actual_sha != manifest_row["sha256"]:
                        failures.append("SOURCE_SNAPSHOT_HASH_MISMATCH")
                if snapshot_path.suffix.lower() in TEXT_SNAPSHOT_SUFFIXES:
                    quote_snapshot_checked += 1
                    snapshot_text = snapshot_path.read_text(
                        encoding="utf-8-sig",
                        errors="replace",
                    )
                    if _normalise_search_text(evidence["quote"]) not in _normalise_search_text(
                        snapshot_text
                    ):
                        failures.append("SOURCE_QUOTE_NOT_IN_SNAPSHOT")
                elif snapshot_path.suffix.lower() in PDF_SNAPSHOT_SUFFIXES:
                    pdf_quote_snapshot_checked += 1
                    pdf_text = _extract_pdf_text(snapshot_path)
                    if _normalise_search_text(evidence["quote"]) not in _normalise_search_text(
                        pdf_text
                    ):
                        failures.append("SOURCE_QUOTE_NOT_IN_SNAPSHOT")
                else:
                    quote_snapshot_binary_unchecked += 1
            source_events.setdefault(source_id, set()).add(node["event_id"])
    if any(len(events) > 1 for events in source_events.values()):
        failures.append("CROSS_EVENT_CITATION")

    for row in company_windows:
        baseline = row["observations"]["T_MINUS_1"]["close"]
        for observation in row["observations"].values():
            expected = observation["close"] / baseline - 1.0
            if abs(expected - observation["absolute_return"]) > 1e-12:
                failures.append("NON_RECOMPUTABLE_VALUE")
            for relative_field, benchmark_field in (
                ("broad_market_relative_return", "broad_market_return"),
                ("industry_relative_return", "industry_return"),
            ):
                relative_value = observation.get(relative_field)
                benchmark_value = observation.get(benchmark_field)
                if relative_value is not None and benchmark_value is None:
                    failures.append("NON_RECOMPUTABLE_RELATIVE_RETURN")
                elif relative_value is not None and abs(
                    (observation["absolute_return"] - benchmark_value) - relative_value
                ) > 1e-12:
                    failures.append("NON_RECOMPUTABLE_RELATIVE_RETURN")
    for labels in bundle["all_labels"]:
        for decision in labels["direction_and_refusal"]:
            for horizon, grade in decision["confounding_by_horizon"].items():
                if grade in {"MATERIAL", "DOMINANT"} and decision[
                    "clean_attribution_eligible_by_horizon"
                ][horizon]:
                    failures.append("CONFOUNDING_GATE_BYPASS")

    unique_failures = sorted(set(failures))
    hash_count = sum(bool(row.get("sha256")) for row in source_manifest)
    publication_bases = [
        evidence.get("publication_time_basis")
        for case in bundle["cases"]
        for evidence in case["public_input"].get("evidence_documents", [])
    ]
    per_document_publication_time_complete = bool(publication_bases) and all(
        basis == "DOCUMENT_PUBLICATION_AT" for basis in publication_bases
    )
    checks = {
        "event_level_public_hidden_isolation": not any(
            item in unique_failures
            for item in {
                "EVENT_ISOLATION_COUNT_FAILURE",
                "PUBLIC_HIDDEN_EVENT_LEAKAGE",
                "PUBLIC_LABEL_LEAKAGE",
                "PUBLIC_VOCABULARY_INVALID",
                "PUBLIC_EVIDENCE_MISMATCH",
            }
        ),
        "per_document_publication_time_complete": per_document_publication_time_complete,
        "d3_cutoff_isolation": per_document_publication_time_complete
        and not any(
            item in unique_failures
            for item in {
                "D3_LEAKAGE",
                "D3_CUTOFF_INVALID",
                "D3_CUTOFF_MISMATCH",
                "D3_PUBLICATION_BASIS_INVALID",
                "PUBLIC_EVIDENCE_MISMATCH",
            }
        ),
        "source_metadata_integrity": not any(
            item in unique_failures
            for item in {
                "FABRICATED_OR_INCOMPLETE_SOURCE",
                "SOURCE_MANIFEST_MISMATCH",
                "DUPLICATE_SOURCE_MANIFEST_ID",
                "CROSS_EVENT_CITATION",
                "PUBLIC_EVIDENCE_MISMATCH",
            }
        ),
        "source_snapshot_existence": "SOURCE_SNAPSHOT_MISSING" not in unique_failures,
        "source_snapshot_hash_integrity": (
            "SOURCE_SNAPSHOT_HASH_MISMATCH" not in unique_failures
        ),
        "source_snapshot_hash_coverage_complete": hash_count == len(source_manifest),
        "source_quote_snapshot_alignment": (
            "SOURCE_QUOTE_NOT_IN_SNAPSHOT" not in unique_failures
        ),
        "observation_anchor_causality_gate": (
            "CAUSAL_LABEL_FROM_OBSERVATION_ANCHOR" not in unique_failures
        ),
        "confounding_exclusion_gate": "CONFOUNDING_GATE_BYPASS" not in unique_failures,
        "numeric_recomputation": not any(
            item in unique_failures
            for item in {"NON_RECOMPUTABLE_VALUE", "NON_RECOMPUTABLE_RELATIVE_RETURN"}
        ),
        "review_state_gate": "FORBIDDEN_REVIEW_STATE" not in unique_failures,
        "three_independent_tracks": "COMPOSITE_SCORE_FORBIDDEN" not in unique_failures,
    }
    checks["source_authenticity"] = all(
        checks[field]
        for field in (
            "source_metadata_integrity",
            "source_snapshot_existence",
            "source_snapshot_hash_integrity",
            "source_snapshot_hash_coverage_complete",
            "source_quote_snapshot_alignment",
        )
    )
    return {
        "hard_failures": unique_failures,
        "checks": checks,
        "source_validation": {
            "manifest_source_count": len(source_manifest),
            "sha256_present_count": hash_count,
            "sha256_missing_count": len(source_manifest) - hash_count,
            "text_quote_snapshot_checked_count": quote_snapshot_checked,
            "pdf_quote_snapshot_checked_count": pdf_quote_snapshot_checked,
            "binary_quote_snapshot_unchecked_count": quote_snapshot_binary_unchecked,
            "node_level_publication_basis_count": sum(
                basis == "NODE_FIRST_PUBLIC_AT_WITH_EVIDENCE_LOCATOR"
                for basis in publication_bases
            ),
        },
        "formal_ready": False,
        "sha_gate": "DEFERRED",
        "candidate_status": "CANDIDATE",
    }


def aggregate_layer_validation(
    release_validation: dict[str, Any],
    binding_failures: list[str],
    market_failures: list[str],
) -> dict[str, Any]:
    combined = copy.deepcopy(release_validation)
    combined["hard_failures"] = sorted(
        set(release_validation.get("hard_failures", []))
        | set(binding_failures)
        | set(market_failures)
    )
    combined.setdefault("checks", {})
    combined["checks"]["binding_layer_gate"] = not binding_failures
    combined["checks"]["market_layer_gate"] = not market_failures
    return combined


def _build_outputs() -> dict[str, Any]:
    timeline = read_jsonl(PACKAGE_ROOT / "timeline_nodes.jsonl")
    anchors = read_jsonl(PACKAGE_ROOT / "anchor_catalog.jsonl")
    bindings = read_jsonl(PACKAGE_ROOT / "dynamic_edge_bindings.jsonl")
    industries = read_jsonl(PACKAGE_ROOT / "event_industry_impacts.jsonl")
    windows = read_jsonl(PACKAGE_ROOT / "company_price_windows.jsonl")
    source_manifest = read_jsonl(PACKAGE_ROOT / "source_manifest.jsonl")
    bundle = build_benchmark(timeline, anchors, bindings, industries, windows)
    release_validation = validate_release_gates(
        bundle,
        timeline,
        anchors,
        bindings,
        windows,
        source_manifest,
        PACKAGE_ROOT.parents[1],
    )
    mechanism_sources = _load_mechanism_sources(
        PACKAGE_ROOT.parents[1] / "work" / "ten_event_rapid_candidate_v2" / "events"
    )
    binding_failures = binding_hard_failures(
        anchors,
        bindings,
        read_jsonl(PACKAGE_ROOT / "counterevidence_dispositions.jsonl"),
        mechanism_sources=mechanism_sources,
    )
    market_result = {
        "industry_impacts": industries,
        "company_windows": windows,
        "company_exposure_gaps": read_jsonl(
            PACKAGE_ROOT / "company_exposure_gaps.jsonl"
        ),
        "mysql_query_manifest": read_jsonl(PACKAGE_ROOT / "mysql_query_manifest.jsonl"),
        "reviewed_anchors": anchors,
        "reviewed_bindings": bindings,
        "candidate_company_mention_count": sum(
            len(row["companies"]) for row in industries
        ),
        "graph_linked_company_mention_count": sum(
            len(row["companies"])
            for row in industries
            if row["lineage_status"] == "GRAPH_LINKED_CANDIDATE"
        ),
        "verified_company_link_count": sum(
            row["verified_company_link_count"] for row in industries
        ),
    }
    market_failures = market_hard_failures(market_result)
    validation = aggregate_layer_validation(
        release_validation,
        binding_failures,
        market_failures,
    )
    write_jsonl(PACKAGE_ROOT / "benchmark_cases.jsonl", bundle["cases"])
    write_jsonl(PACKAGE_ROOT / "public" / "benchmark_cases.jsonl", bundle["cases"])
    write_jsonl(
        PACKAGE_ROOT / "evaluator_only" / "benchmark_labels.jsonl",
        bundle["hidden_labels"],
    )
    public_release_manifest = {
        "package": "PUBLIC_BENCHMARK_INPUT",
        "allowlist": ["benchmark_cases.jsonl"],
        "contains_hidden_labels": False,
    }
    evaluator_release_manifest = {
        "package": "EVALUATOR_ONLY_LABELS",
        "allowlist": ["benchmark_labels.jsonl"],
        "contains_hidden_labels": True,
    }
    (PACKAGE_ROOT / "public" / "release_manifest.json").write_text(
        json.dumps(public_release_manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    (PACKAGE_ROOT / "evaluator_only" / "release_manifest.json").write_text(
        json.dumps(evaluator_release_manifest, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    (PACKAGE_ROOT / "evaluation_report.json").write_text(
        json.dumps(bundle["evaluation_report"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "dataset_version": "fingoose-verifiable-evaluation-phase1-v2-candidate",
        "schemas": {
            "timeline_nodes": "phase1.timeline_node.v2",
            "dynamic_edge_bindings": "phase1.dynamic_binding.v2",
            "event_industry_impacts": "phase1.industry_impact.v2",
            "company_price_windows": "phase1.company_window.v2",
            "benchmark_cases": "phase1.benchmark_case.v2",
            "evaluator_only_labels": "phase1.benchmark_label.v2",
        },
        "counts": {
            "events": 10,
            "timeline_nodes": len(timeline),
            "anchors": len(anchors),
            "bindings": len(bindings),
            "industry_impacts": len(industries),
            "candidate_company_mentions": sum(len(row["companies"]) for row in industries),
            "graph_linked_company_mentions": sum(
                len(row["companies"])
                for row in industries
                if row["lineage_status"] == "GRAPH_LINKED_CANDIDATE"
            ),
            "verified_company_links": sum(
                row["verified_company_link_count"] for row in industries
            ),
            "company_windows": len(windows),
            "benchmark_cases": len(bundle["cases"]),
            "hidden_labels": len(bundle["hidden_labels"]),
        },
        "source_scope": "official event evidence plus isolated post-event mechanism review",
        "vendor_license_boundary": "Public-vendor and MySQL rows are candidate-only and not redistributable until licence review.",
        "known_gaps": [
            "111 dynamic bindings require edge-level human review",
            "43 industry directions require human review",
            "30 broad-market benchmarks unavailable",
            "30 event-date Shenwan index benchmarks unavailable",
            "30 official company exposure dossiers remain open",
            "Graph construction and direction tracks are blocked until scoring labels are human-reviewed.",
            "Public evidence documents use node-level first_public_at; independent per-document publication timestamps remain incomplete.",
            "MySQL audit is internally reproducible but has no signed execution log; execution authenticity remains unverified.",
            f"{validation['source_validation']['sha256_missing_count']} source snapshots lack SHA-256; SHA gate remains deferred.",
        ],
        "sha_gate": "DEFERRED",
        "formal_ready": False,
        "hard_failures": validation["hard_failures"],
    }
    (PACKAGE_ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    reconciliation = {
        "input_timeline_baseline": {"verified": 42, "pending": 8},
        "output_timeline_baseline": {"verified": 50, "pending": 0},
        "old_promotable_count": 18,
        "recomputed_promotable_count": len(read_jsonl(PACKAGE_ROOT / "promotable_milestones.jsonl")),
        "semantic_replacement_count": len(read_jsonl(PACKAGE_ROOT / "semantic_replacements.jsonl")),
        "binding_status_counts": {
            state: sum(row["binding_status"] == state for row in bindings)
            for state in {row["binding_status"] for row in bindings}
        },
        "industry_human_review_count": sum(
            row["direction_status"] == "NEEDS_HUMAN_REVIEW" for row in industries
        ),
        "company_exposure_gap_count": len(read_jsonl(PACKAGE_ROOT / "company_exposure_gaps.jsonl")),
        "limitations": manifest["known_gaps"],
        "formal_ready": False,
    }
    (PACKAGE_ROOT / "reconciliation_report.json").write_text(
        json.dumps(reconciliation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    full_validation = {
        **validation,
        "known_gaps": manifest["known_gaps"],
        "public_release_allowlist": public_release_manifest["allowlist"],
        "evaluator_release_allowlist": evaluator_release_manifest["allowlist"],
    }
    (PACKAGE_ROOT / "validation_report.json").write_text(
        json.dumps(full_validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"validation": full_validation, "manifest": manifest, "reconciliation": reconciliation}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-all", action="store_true")
    args = parser.parse_args()
    if args.build_all:
        print(json.dumps(_build_outputs(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
