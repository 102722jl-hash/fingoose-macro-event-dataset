from __future__ import annotations

import argparse
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from fingoose_macro_event_dashboard_v1 import MacroEventDashboardRepository


REASONING_SEQUENCE = (
    "MACRO_REPORT",
    "DATA",
    "PERIOD_DESCRIPTION",
    "FACT_TRANSMISSION_CHAIN",
    "MULTI_DATA_TREND_CONFIRMATION",
    "SHORT_TERM_PREDICTION",
)

COMPANY_NODE_SEQUENCE = (
    "MAJOR_EVENT",
    "INDUSTRY_MACRO_VARIABLE",
    "COMPANY_BUSINESS_EXPOSURE",
    "OPERATING_METRIC",
    "FINANCIAL_RESULT",
    "COMPETING_EXPLANATION",
    "ATTRIBUTION_OR_FORECAST",
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _index(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows if row.get(key) is not None}


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        value = row.get(key)
        if value is not None:
            grouped.setdefault(str(value), []).append(row)
    return grouped


class DeepDashboardRepository:
    """Read-only composition of archived market and candidate company releases."""

    def __init__(self, market_root: Path, company_root: Path) -> None:
        self.market_root = Path(market_root)
        self.company_root = Path(company_root)
        self.base = MacroEventDashboardRepository(self.market_root, self.company_root)
        hidden_labels = _read_jsonl(
            self.company_root / "company_candidate_hidden_labels.jsonl"
        )
        hidden_outcomes = _read_jsonl(
            self.company_root / "company_hidden_outcomes.jsonl"
        )
        self.company_hidden_labels_by_record = _index(hidden_labels, "record_id")
        self.company_hidden_outcomes_by_record = _index(hidden_outcomes, "record_id")

    def overview(self) -> dict[str, Any]:
        market = self.base.persisted_summary
        company = self.base.company_summary
        return {
            "event_count": len(self.base.event_dossiers),
            "market_sample_count": len(self.base.attribution_samples),
            "company_dossier_count": len(self.base.company_dossiers),
            "company_sample_count": (
                int(company.get("attribution_sample_count", 0))
                + int(company.get("forecast_sample_count", 0))
            ),
            "market_formal_ready": bool(market.get("formal_ready")),
            "company_release_tier": company.get("release_tier"),
            "company_candidate_ready": bool(company.get("candidate_ready")),
            "company_formal_ready": bool(company.get("formal_ready")),
            "company_formal_blockers": deepcopy(company.get("formal_blockers", [])),
            "company_verified_metric_fact_count": int(
                company.get("verified_metric_fact_count", 0)
            ),
            "company_second_review_required_count": int(
                company.get("second_review_required_count", 0)
            ),
        }

    def list_events(self) -> list[dict[str, Any]]:
        return self.base.list_events()

    def event_workspace(self, event_id: str) -> dict[str, Any]:
        detail = self.base.event_detail(event_id)
        return {
            "event": detail["event"],
            "market_samples": [
                {
                    "record_id": row["record_id"],
                    "event_id": row["event_id"],
                    "task_type": row["task_type"],
                    "target_series_ids": row.get("target_series_ids", []),
                    "label": row.get("attribution", {}).get("label"),
                    "confidence": row.get("attribution", {}).get("confidence"),
                }
                for row in detail["market_samples"]
            ],
            "companies": detail["company_dossiers"],
        }

    def market_sample_detail(self, record_id: str) -> dict[str, Any]:
        if record_id not in self.base.samples_by_id:
            raise KeyError(record_id)
        sample = deepcopy(self.base.samples_by_id[record_id])
        projection = deepcopy(self.base.training_projection_by_id[record_id])
        chain = deepcopy(sample.get("forecast_reasoning_chain", {}))
        event = deepcopy(self.base.events_by_id[sample["event_id"]])
        windows = [
            deepcopy(self.base.market_windows_by_id[window_id])
            for window_id in sample.get("market_window_ids", [])
            if window_id in self.base.market_windows_by_id
        ]
        sources = [
            deepcopy(self.base.sources_by_id[source_id])
            for source_id in sample.get("visible_evidence_ids", [])
            if source_id in self.base.sources_by_id
        ]
        visible_windows = []
        for window in windows:
            visible = deepcopy(window)
            visible["windows"] = {
                code: deepcopy(window.get("windows", {}).get(code))
                for code in ("D1", "D3")
                if window.get("windows", {}).get(code) is not None
            }
            visible_windows.append(visible)
        steps = [
            {
                "step_id": "MACRO_REPORT",
                "content": {
                    "evidence": deepcopy(chain.get("macro_report_evidence", [])),
                    "sources": sources,
                },
            },
            {
                "step_id": "DATA",
                "content": {
                    "forecast_as_of_at": sample.get("forecast_as_of_at"),
                    "visible_window_codes": ["D1", "D3"],
                    "market_windows": visible_windows,
                },
            },
            {
                "step_id": "PERIOD_DESCRIPTION",
                "content": {
                    "event": event,
                    "period_description": deepcopy(chain.get("period_description", {})),
                    "market_windows": visible_windows,
                },
            },
            {
                "step_id": "FACT_TRANSMISSION_CHAIN",
                "content": {
                    **deepcopy(chain.get("fact_transmission_chain", {})),
                    "channels": deepcopy(sample.get("attribution", {}).get("channels", [])),
                    "counterevidence": deepcopy(
                        sample.get("attribution", {}).get("counterevidence", [])
                    ),
                    "market_windows": visible_windows,
                },
            },
            {
                "step_id": "MULTI_DATA_TREND_CONFIRMATION",
                "content": deepcopy(chain.get("trend_confirmation", {})),
            },
            {
                "step_id": "SHORT_TERM_PREDICTION",
                "content": {
                    "prediction": deepcopy(chain.get("short_term_prediction", {})),
                    "forecast_as_of_at": sample.get("forecast_as_of_at"),
                    "visible_market_windows": visible_windows,
                },
            },
        ]
        review = self.base.reviews_by_id.get(sample.get("review_id"), {})
        return {
            "record_id": record_id,
            "event": event,
            "sample": sample,
            "public_projection": projection,
            "steps": steps,
            "audit_only": {
                "hidden_label": deepcopy(
                    self.base.hidden_labels_by_record_id.get(record_id, {})
                ),
                "outcome": deepcopy(
                    self.base.hidden_outcomes_by_record_id.get(record_id, {})
                ),
                "review": deepcopy(review),
                "d20_windows": [
                    {
                        "market_window_id": window.get("market_window_id"),
                        "series": deepcopy(window.get("series", {})),
                        "D20": deepcopy(window.get("windows", {}).get("D20")),
                    }
                    for window in windows
                ],
            },
        }

    def company_chain_detail(self, dossier_id: str) -> dict[str, Any]:
        raw = self.base.company_detail(dossier_id)
        dossier = raw["dossier"]
        source_by_id = {
            str(source["source_id"]): source
            for source in raw["sources"]
            if source.get("source_id")
        }
        gaps_by_type = _group(raw["evidence_gaps"], "node_type")
        nodes = []
        for node in dossier.get("transmission_chain", {}).get("nodes", []):
            resolved_sources = []
            unresolved_refs = []
            for reference in node.get("evidence_refs", []):
                source = source_by_id.get(str(reference.get("source_id")))
                if source:
                    resolved_sources.append(deepcopy(source))
                else:
                    unresolved_refs.append(deepcopy(reference))
            node_gaps = deepcopy(gaps_by_type.get(str(node.get("node_type")), []))
            if node.get("gap_reason") and not node_gaps:
                node_gaps = [{
                    "node_type": node.get("node_type"),
                    "status": node.get("status"),
                    "gap_reason": node.get("gap_reason"),
                }]
            nodes.append({
                **deepcopy(node),
                "sources": resolved_sources,
                "unresolved_evidence_refs": unresolved_refs,
                "evidence_gaps": node_gaps,
            })
        attribution = raw.get("attribution_sample", {})
        forecast = raw.get("forecast_sample", {})
        record_ids = [
            str(row.get("record_id"))
            for row in (attribution, forecast)
            if row.get("record_id")
        ]
        return {
            "dossier": dossier,
            "nodes": nodes,
            "edges": deepcopy(dossier.get("transmission_chain", {}).get("edges", [])),
            "metric_facts": raw["metric_facts"],
            "stock_window": raw["stock_window"],
            "attribution_sample": attribution,
            "forecast_sample": forecast,
            "review": raw["review"],
            "sources": raw["sources"],
            "evidence_gaps": raw["evidence_gaps"],
            "audit_only": {
                "hidden_labels": [
                    deepcopy(self.company_hidden_labels_by_record[record_id])
                    for record_id in record_ids
                    if record_id in self.company_hidden_labels_by_record
                ],
                "hidden_outcomes": [
                    deepcopy(self.company_hidden_outcomes_by_record[record_id])
                    for record_id in record_ids
                    if record_id in self.company_hidden_outcomes_by_record
                ],
            },
        }

    def list_companies(self, **filters: str) -> list[dict[str, Any]]:
        return self.base.list_companies(**filters)

    def list_reviews(self) -> list[dict[str, Any]]:
        return self.base.list_reviews()


ROOT = Path(__file__).resolve().parent
HTML_PATH = ROOT / "fingoose_macro_event_company_deep_dashboard_v1.html"
CSS_PATH = ROOT / "fingoose_macro_event_company_deep_dashboard_v1.css"
JS_PATH = ROOT / "fingoose_macro_event_company_deep_dashboard_v1.js"
INDEX_HTML = HTML_PATH.read_text(encoding="utf-8") if HTML_PATH.is_file() else ""


def make_handler(repository: DeepDashboardRepository) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def send_payload(self, status: int, payload: Any, content_type: str) -> None:
            body = payload.encode("utf-8") if isinstance(payload, str) else json.dumps(
                payload, ensure_ascii=False
            ).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, status: int, payload: Any) -> None:
            self.send_payload(status, payload, "application/json; charset=utf-8")

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            query = parse_qs(parsed.query)
            first = lambda name: query.get(name, [""])[0]
            try:
                if path == "/":
                    self.send_payload(200, INDEX_HTML, "text/html; charset=utf-8")
                elif path in {
                    "/assets/dashboard.css",
                    "/fingoose_macro_event_company_deep_dashboard_v1.css",
                }:
                    self.send_payload(200, CSS_PATH.read_text(encoding="utf-8"), "text/css; charset=utf-8")
                elif path in {
                    "/assets/dashboard.js",
                    "/fingoose_macro_event_company_deep_dashboard_v1.js",
                }:
                    self.send_payload(200, JS_PATH.read_text(encoding="utf-8"), "text/javascript; charset=utf-8")
                elif path == "/api/overview":
                    self.send_json(200, repository.overview())
                elif path == "/api/events":
                    self.send_json(200, repository.list_events())
                elif path.startswith("/api/events/"):
                    self.send_json(200, repository.event_workspace(path.removeprefix("/api/events/")))
                elif path.startswith("/api/market-samples/"):
                    self.send_json(200, repository.market_sample_detail(path.removeprefix("/api/market-samples/")))
                elif path.startswith("/api/company-chains/"):
                    self.send_json(200, repository.company_chain_detail(path.removeprefix("/api/company-chains/")))
                elif path == "/api/companies":
                    self.send_json(200, repository.list_companies(
                        event_id=first("event_id"),
                        company_query=first("company"),
                        association=first("association"),
                        direction=first("direction"),
                        evidence_status=first("evidence_status"),
                        review_status=first("review_status"),
                    ))
                elif path == "/api/reviews":
                    self.send_json(200, repository.list_reviews())
                else:
                    self.send_json(404, {"error": "NOT_FOUND"})
            except KeyError as exc:
                self.send_json(404, {"error": "NOT_FOUND", "id": str(exc.args[0])})
            except (FileNotFoundError, ValueError) as exc:
                self.send_json(500, {"error": "DATA_ERROR", "message": str(exc)})

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the FinGoose deep event-company dashboard.")
    parser.add_argument(
        "--market-output-root",
        type=Path,
        default=ROOT / "outputs" / "fingoose_macro_event_attribution_v1",
    )
    parser.add_argument(
        "--company-output-root",
        type=Path,
        default=ROOT / "outputs" / "fingoose_macro_event_company_enriched_candidate_v1",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8776)
    args = parser.parse_args()
    repository = DeepDashboardRepository(args.market_output_root, args.company_output_root)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(repository))
    print(f"FinGoose deep dashboard: http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
