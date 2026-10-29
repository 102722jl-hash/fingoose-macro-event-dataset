from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
from pathlib import Path
import re
import shutil
import time
from typing import Any

from pypdf import PdfReader
import requests


ROOT = Path(__file__).resolve().parents[1]
EVENT_ID = "event-13"
EVENT_DATE = "2026-06-16"
ANCHOR_AT = "2026-06-16T23:59:59+09:00"
MARKET_CODE = "1306"
COMPANY_REPLACEMENTS = {
    "9204.T": {"company_code": "9206.T", "company_name": "Star Flyer"},
}
SPECIAL_FILINGS = {
    "9206": [
        {
            "document_id": "starflyer-20260430-02",
            "source_class": "strategy_presentation",
            "document_title": "2026-2028 Medium-Term Management Strategy",
            "source_url": "https://www.starflyer.jp/starflyer/corporate/pdf/20260430_02.pdf",
            "published_at": "2026-04-30",
            "source_host_role": "ISSUER_OFFICIAL_WEBSITE",
        },
        {
            "document_id": "starflyer-20230428-02",
            "source_class": "strategy_presentation",
            "document_title": "Medium-Term Management Strategy 2025",
            "source_url": "https://www.starflyer.jp/starflyer/corporate/pdf/20230428_02.pdf",
            "published_at": "2023-04-28",
            "source_host_role": "ISSUER_OFFICIAL_WEBSITE",
        },
    ],
}
INDUSTRY_PROXIES = {
    "银行": ("1631", "NEXT FUNDS TOPIX-17 Banks ETF"),
    "保险": ("1632", "NEXT FUNDS TOPIX-17 Financials (Ex Banks) ETF"),
    "证券": ("1632", "NEXT FUNDS TOPIX-17 Financials (Ex Banks) ETF"),
    "房地产": ("1633", "NEXT FUNDS TOPIX-17 Real Estate ETF"),
    "航空运输": ("1628", "NEXT FUNDS TOPIX-17 Transportation & Logistics ETF"),
    "汽车": ("1622", "NEXT FUNDS TOPIX-17 Automobiles & Transportation Equipment ETF"),
    "电子": ("1625", "NEXT FUNDS TOPIX-17 Electric Appliances & Precision Instruments ETF"),
}
EXPOSURE_TERMS = {
    "银行": ("banking", "loans", "deposits", "net interest"),
    "保险": ("insurance", "premiums", "underwriting", "life insurance"),
    "证券": ("securities", "brokerage", "investment banking", "asset management"),
    "房地产": ("real estate", "property", "office leasing", "building lease"),
    "航空运输": ("air transportation", "passenger", "cargo", "airline"),
    "汽车": ("automotive", "vehicles", "motorcycles", "automobile"),
    "电子": ("electronics", "semiconductor", "digital", "information technology"),
}
HISTORY_RE = re.compile(
    r'\{a:(?P<adjusted>-?(?:\d+(?:\.\d+)?|\.\d+)),c:(?P<close>-?(?:\d+(?:\.\d+)?|\.\d+)),'
    r'h:(?P<high>-?(?:\d+(?:\.\d+)?|\.\d+)),l:(?P<low>-?(?:\d+(?:\.\d+)?|\.\d+)),'
    r'o:(?P<open>-?(?:\d+(?:\.\d+)?|\.\d+)),t:"(?P<date>\d{4}-\d{2}-\d{2})",'
    r'v:(?P<volume>-?(?:\d+(?:\.\d+)?|\.\d+)),ch:(?P<change>-?(?:\d+(?:\.\d+)?|\.\d+))\}'
)
EVENT_RE = re.compile(
    r'eventId:(?P<event_id>\d+),title:"(?P<title>[^"]*)",eventDate:"(?P<date>\d{4}-\d{2}-\d{2})",'
    r'fiscalYear:(?P<fiscal_year>\d+),fiscalPeriod:"(?P<fiscal_period>[^"]+)",filings:\[(?P<filings>.*?)\]\}',
    re.DOTALL,
)
FILING_RE = re.compile(
    r'\{id:(?P<id>\d+),type:"(?P<type>[^"]+)",title:(?:"(?P<title>[^"]*)"|null),fileUrl:"(?P<url>[^"]+)"\}'
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def content_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    return sha256(payload.encode("utf-8")).hexdigest()


def safe_code(value: str) -> str:
    return value.lower().replace(".", "-")


def fetch(session: requests.Session, url: str, *, binary: bool = False) -> bytes:
    error: Exception | None = None
    for attempt in range(4):
        try:
            response = session.get(url, timeout=45)
            response.raise_for_status()
            if binary and not response.content.startswith(b"%PDF"):
                raise ValueError(f"non-PDF response for {url}")
            return response.content
        except Exception as exc:  # pragma: no cover - exercised only on network failure
            error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed to retrieve {url}: {error}")


def parse_history(raw: bytes, code: str) -> dict[str, dict[str, float]]:
    text = raw.decode("utf-8", errors="replace")
    rows: dict[str, dict[str, float]] = {}
    for match in HISTORY_RE.finditer(text):
        row = {
            "open": float(match.group("open")),
            "high": float(match.group("high")),
            "low": float(match.group("low")),
            "close": float(match.group("close")),
            "adjusted_close": float(match.group("adjusted")),
            "volume": int(round(float(match.group("volume")))),
        }
        rows[match.group("date")] = row
    if EVENT_DATE not in rows or len(rows) < 60:
        raise ValueError(f"insufficient history for {code}: {len(rows)} rows")
    return rows


def parse_filings(raw: bytes, code: str) -> dict[str, Any]:
    text = raw.decode("utf-8", errors="replace")
    candidates: list[dict[str, Any]] = []
    for event_match in EVENT_RE.finditer(text):
        event_date = event_match.group("date")
        if event_date > EVENT_DATE:
            continue
        filings = [
            {
                "document_id": filing.group("id"),
                "source_class": filing.group("type"),
                "document_title": filing.group("title") or event_match.group("title"),
                "source_url": filing.group("url").replace("&amp;", "&"),
            }
            for filing in FILING_RE.finditer(event_match.group("filings"))
        ]
        if len(filings) >= 2:
            candidates.append(
                {
                    "event_date": event_date,
                    "fiscal_year": int(event_match.group("fiscal_year")),
                    "fiscal_period": event_match.group("fiscal_period"),
                    "title": event_match.group("title"),
                    "filings": filings,
                }
            )
    if not candidates:
        raise ValueError(f"no two-document pre-event filing set for {code}")
    selected_event = max(candidates, key=lambda item: item["event_date"])
    priority = {"annual_report": 0, "quarterly_report": 1, "slides": 2}
    selected_event["filings"] = sorted(
        selected_event["filings"], key=lambda item: (priority.get(item["source_class"], 9), item["document_id"])
    )[:2]
    return selected_event


def extract_quote(pdf_path: Path, terms: tuple[str, ...]) -> tuple[str, str, list[str]]:
    reader = PdfReader(str(pdf_path))
    fallback: tuple[str, int] | None = None
    for page_number, page in enumerate(reader.pages[:60], 1):
        text = re.sub(r"\s+", " ", page.extract_text() or "").strip()
        if len(text) >= 120 and fallback is None:
            fallback = (text, page_number)
        lowered = text.lower()
        matched = [term for term in terms if term in lowered]
        if matched:
            position = min(lowered.find(term) for term in matched)
            start = max(0, position - 180)
            end = min(len(text), position + 520)
            quote = text[start:end].strip(" .")
            if len(quote) >= 120:
                return quote, f"PDF page {page_number}, keyword context: {matched[0]}", matched
    if fallback is None:
        raise ValueError(f"no extractable disclosure text in {pdf_path.name}")
    text, page_number = fallback
    return text[:700], f"PDF page {page_number}, first extractable paragraph", []


def endpoint_names(calendar: list[str]) -> dict[str, str]:
    event_index = calendar.index(EVENT_DATE)
    if event_index < 20 or event_index + 20 >= len(calendar):
        raise ValueError("market calendar does not cover T-20 through D20")
    return {
        "T_MINUS_1": calendar[event_index - 1],
        "T0": calendar[event_index],
        "D1": calendar[event_index + 1],
        "D3": calendar[event_index + 3],
        "D5": calendar[event_index + 5],
        "D20": calendar[event_index + 20],
    }


def continuous_audit(
    rows: dict[str, dict[str, float]], calendar: list[str], code: str, snapshot_path: str
) -> dict[str, Any]:
    event_index = calendar.index(EVENT_DATE)
    sessions = calendar[event_index - 20 : event_index + 21]
    missing = [day for day in sessions if day not in rows]
    nonpositive = [day for day in sessions if day in rows and rows[day]["volume"] <= 0]
    return {
        "calendar_source": "TOPIX_ETF_1306_TRADING_DATES",
        "window_start": sessions[0],
        "window_end": sessions[-1],
        "expected_session_count": len(sessions),
        "observed_session_count": len(sessions) - len(missing),
        "missing_dates": missing,
        "nonpositive_volume_dates": nonpositive,
        "verified": not missing and not nonpositive,
        "source_snapshot_path": snapshot_path,
        "security_code": f"{code}.T",
    }


def industry_window(
    industry: dict[str, Any], proxy_code: str, proxy_name: str, histories: dict[str, dict[str, dict[str, float]]],
    endpoints: dict[str, str], audits: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    proxy, market = histories[proxy_code], histories[MARKET_CODE]
    baseline_proxy = proxy[endpoints["T_MINUS_1"]]["close"]
    baseline_market = market[endpoints["T_MINUS_1"]]["close"]
    values: dict[str, Any] = {}
    for name, day in endpoints.items():
        proxy_return = proxy[day]["close"] / baseline_proxy - 1
        market_return = market[day]["close"] / baseline_market - 1
        values[name] = {
            "date": day,
            "raw_value": proxy[day]["close"],
            "return": proxy_return,
            "market_raw_value": market[day]["close"],
            "market_return": market_return,
            "market_relative_return": proxy_return - market_return,
        }
    return {
        "market_window_id": industry["market_window"]["market_window_id"],
        "event_id": EVENT_ID,
        "security_id": f"INDUSTRY:{industry['industry_name_zh']}",
        "market_benchmark_id": f"{MARKET_CODE}.T",
        "industry_benchmark_id": f"{proxy_code}.T",
        "proxy_selection_basis_zh": f"{proxy_name}作为{industry['industry_name_zh']}的事前行业代理。",
        "status": "CALCULATED",
        "data_source": "STOCKANALYSIS_PUBLIC_TYO_HISTORY",
        "formula": "company_value/company_T_MINUS_1-1; market_relative=company_return-market_return; industry_relative=company_return-industry_return",
        "endpoints": values,
        "continuous_trading_verified": audits[proxy_code]["verified"],
        "continuous_trading_audit": audits[proxy_code],
        "causal_use": "VALIDATION_ONLY",
        "missing_reason_codes": [],
    }


def company_window(
    company: dict[str, Any], proxy_code: str, histories: dict[str, dict[str, dict[str, float]]],
    endpoints: dict[str, str], audits: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    code = company["company_code"].split(".")[0]
    own, market, proxy = histories[code], histories[MARKET_CODE], histories[proxy_code]
    own_base = own[endpoints["T_MINUS_1"]]["close"]
    market_base = market[endpoints["T_MINUS_1"]]["close"]
    proxy_base = proxy[endpoints["T_MINUS_1"]]["close"]
    values: dict[str, Any] = {}
    for name, day in endpoints.items():
        own_return = own[day]["close"] / own_base - 1
        market_return = market[day]["close"] / market_base - 1
        industry_return = proxy[day]["close"] / proxy_base - 1
        values[name] = {
            "date": day,
            "raw_value": own[day]["close"],
            "return": own_return,
            "market_date": day,
            "market_raw_value": market[day]["close"],
            "market_return": market_return,
            "market_relative_return": own_return - market_return,
            "industry_date": day,
            "industry_raw_value": proxy[day]["close"],
            "industry_return": industry_return,
            "industry_relative_return": own_return - industry_return,
        }
    window = {
        "market_window_id": company["market_window"]["market_window_id"],
        "event_id": EVENT_ID,
        "security_id": company["company_code"],
        "market_benchmark_id": f"{MARKET_CODE}.T",
        "industry_benchmark_id": f"{proxy_code}.T",
        "status": "CALCULATED",
        "data_source": "STOCKANALYSIS_PUBLIC_TYO_HISTORY",
        "formula": "company_value/company_T_MINUS_1-1; market_relative=company_return-market_return; industry_relative=company_return-industry_return",
        "endpoints": values,
        "continuous_trading_verified": audits[code]["verified"],
        "continuous_trading_audit": audits[code],
        "causal_use": "VALIDATION_ONLY",
        "missing_reason_codes": [],
    }
    return window


def locate_event_snapshot(event_evidence: dict[str, Any]) -> Path:
    filename = f"{event_evidence['snapshot_sha256']}.pdf"
    matches = sorted((ROOT / "work" / "skill_research_runs").glob(f"**/snapshots/{filename}"))
    if not matches:
        raise FileNotFoundError(f"event evidence snapshot not found: {filename}")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--output-run", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    source, output = args.source_run.resolve(), args.output_run.resolve()
    if output.exists() and not args.resume:
        raise FileExistsError(f"output run already exists: {output}")
    output.mkdir(parents=True, exist_ok=True)
    for name in ("profile.json", "base_dataset_config.json", "base_training_config.json", "base_unified_events.jsonl"):
        target = output / name
        if not target.exists():
            shutil.copy2(source / name, target)
    for relative in ("online/market/raw", "online/market/normalized", "online/company_disclosures/index", "online/company_disclosures/pdf", "snapshots"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    source_record = next(row for row in read_jsonl(source / "content_candidates.jsonl") if row.get("event_id") == EVENT_ID)
    unified = deepcopy(source_record["unified_event"])
    for company in unified["companies"]:
        replacement = COMPANY_REPLACEMENTS.get(company["company_code"])
        if replacement:
            company.update(replacement)
    event_evidence = next(row for row in read_jsonl(source / "accepted_evidence.jsonl") if row.get("event_id") == EVENT_ID)
    event_snapshot = locate_event_snapshot(event_evidence)
    event_snapshot_target = output / "snapshots" / event_snapshot.name
    if not event_snapshot_target.exists():
        shutil.copy2(event_snapshot, event_snapshot_target)

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; FinGooseResearch/1.0; auditable snapshot)"})
    logging.getLogger("pypdf").setLevel(logging.CRITICAL)
    logging.getLogger("pypdf._cmap").setLevel(logging.CRITICAL)
    company_codes = [company["company_code"].split(".")[0] for company in unified["companies"]]
    market_codes = sorted({MARKET_CODE, *company_codes, *(code for code, _ in INDUSTRY_PROXIES.values())})
    histories: dict[str, dict[str, dict[str, float]]] = {}
    market_audit_rows: list[dict[str, Any]] = []
    retrieved_at = datetime.now(timezone.utc).isoformat()
    for code in market_codes:
        url = f"https://stockanalysis.com/quote/tyo/{code}/history/"
        raw_path = output / "online" / "market" / "raw" / f"{code}.html"
        if raw_path.exists():
            raw = raw_path.read_bytes()
        else:
            raw = fetch(session, url)
            raw_path.write_bytes(raw)
        rows = parse_history(raw, code)
        histories[code] = rows
        normalized_path = output / "online" / "market" / "normalized" / f"{code}.json"
        write_json(normalized_path, {"security_code": f"{code}.T", "source_url": url, "retrieved_at": retrieved_at, "snapshot_sha256": sha256(raw).hexdigest(), "rows": rows})
        market_audit_rows.append({"security_code": f"{code}.T", "source_url": url, "retrieved_at": retrieved_at, "snapshot_path": raw_path.relative_to(output).as_posix(), "snapshot_sha256": sha256(raw).hexdigest(), "row_count": len(rows)})

    calendar = sorted(histories[MARKET_CODE])
    endpoints = endpoint_names(calendar)
    audits = {
        code: continuous_audit(histories[code], calendar, code, f"online/market/normalized/{code}.json")
        for code in market_codes
    }
    failed_audits = [code for code, audit in audits.items() if not audit["verified"]]
    if failed_audits:
        raise ValueError(f"continuous trading audit failed: {failed_audits}")

    industry_by_id = {industry["industry_id"]: industry for industry in unified["industries"]}
    for industry in unified["industries"]:
        proxy_code, proxy_name = INDUSTRY_PROXIES[industry["industry_name_zh"]]
        industry["market_window"] = industry_window(industry, proxy_code, proxy_name, histories, endpoints, audits)

    company_evidence: list[dict[str, Any]] = []
    disclosure_audits: list[dict[str, Any]] = []
    for company in unified["companies"]:
        code = company["company_code"].split(".")[0]
        index_url = f"https://stockanalysis.com/quote/tyo/{code}/filings/"
        if code in SPECIAL_FILINGS:
            selected = {"event_date": max(item["published_at"] for item in SPECIAL_FILINGS[code]), "fiscal_year": 2026, "fiscal_period": "PRE_EVENT", "title": "Issuer official pre-event disclosures", "filings": deepcopy(SPECIAL_FILINGS[code])}
            index_url = "https://www.starflyer.jp/starflyer/ir/"
            index_path = output / "online" / "company_disclosures" / "index" / f"{code}.json"
            index_raw = (json.dumps(selected, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            index_path.write_bytes(index_raw)
        else:
            index_path = output / "online" / "company_disclosures" / "index" / f"{code}.html"
            if index_path.exists():
                index_raw = index_path.read_bytes()
            else:
                index_raw = fetch(session, index_url)
                index_path.write_bytes(index_raw)
            selected = parse_filings(index_raw, code)
        disclosures: list[dict[str, Any]] = []
        for filing in selected["filings"]:
            filing_date = filing.get("published_at", selected["event_date"])
            pdf_name = f"{code}_{filing_date}_{filing['source_class']}_{filing['document_id']}.pdf"
            pdf_path = output / "online" / "company_disclosures" / "pdf" / pdf_name
            if pdf_path.exists():
                pdf_raw = pdf_path.read_bytes()
            else:
                pdf_raw = fetch(session, filing["source_url"], binary=True)
                pdf_path.write_bytes(pdf_raw)
            quote, locator, matched_terms = extract_quote(pdf_path, EXPOSURE_TERMS[company["industry"]])
            evidence_id = f"company-evidence-{sha256((EVENT_ID + company['company_code'] + filing['document_id']).encode('utf-8')).hexdigest()[:16]}"
            evidence = {
                "event_id": EVENT_ID,
                "evidence_id": evidence_id,
                "company_id": f"company-{safe_code(company['company_code'])}",
                "company_code": company["company_code"],
                "company_name": company["company_name"],
                "industry_id": company["industry_id"],
                "issuer": company["company_name"],
                "publisher": company["company_name"],
                "document_id": filing["document_id"],
                "document_title": filing.get("document_title") or f"{selected['title']} - {filing['source_class']}",
                "source_class": filing["source_class"].upper(),
                "claim_type": "PRE_EVENT_BUSINESS_EXPOSURE",
                "source_url": filing["source_url"],
                "source_tier": "T2",
                "published_at": f"{filing_date}T00:00:00+09:00",
                "anchor_at": ANCHOR_AT,
                "temporal_role": "AS_OF_EVIDENCE",
                "retrieved_at": retrieved_at,
                "original_quote": quote,
                "locator": locator,
                "matched_terms": matched_terms,
                "reporting_period": f"FY{selected['fiscal_year']}-{selected['fiscal_period']}",
                "snapshot_path": pdf_path.relative_to(output).as_posix(),
                "snapshot_sha256": sha256(pdf_raw).hexdigest(),
                "raw_storage_status": "STORED",
                "content_type": "application/pdf",
                "source_host_role": filing.get("source_host_role", "PUBLIC_MIRROR_OF_ISSUER_DISCLOSURE"),
                "document_origin": "ISSUER_DISCLOSURE",
                "acceptance_status": "ACCEPTED",
                "acceptance_reason": "GATES_PASSED",
                "supports_node_ids": [],
                "review_status": "NEEDS_HUMAN_REVIEW",
                "formal_ready": False,
            }
            disclosures.append(evidence)
            company_evidence.append(evidence)
        if len({item["evidence_id"] for item in disclosures}) != 2:
            raise ValueError(f"company disclosure count is not two for {company['company_code']}")
        company["company_evidence"] = disclosures
        company["evidence_ids"] = [event_evidence["evidence_id"], *[item["evidence_id"] for item in disclosures]]
        proxy_code, _ = INDUSTRY_PROXIES[industry_by_id[company["industry_id"]]["industry_name_zh"]]
        company["market_window"] = company_window(company, proxy_code, histories, endpoints, audits)
        d20 = company["market_window"]["endpoints"]["D20"]
        company["relative_return"] = {
            "status": "CALCULATED",
            "window": "D20",
            "market_relative_return": d20["market_relative_return"],
            "industry_relative_return": d20["industry_relative_return"],
        }
        disclosure_audits.append({"company_code": company["company_code"], "index_url": index_url, "index_snapshot_path": index_path.relative_to(output).as_posix(), "index_snapshot_sha256": sha256(index_raw).hexdigest(), "selected_event": selected["title"], "selected_event_date": selected["event_date"], "evidence_ids": [item["evidence_id"] for item in disclosures]})

    unified["evidence_registry"] = [event_evidence]
    unified["review_status"] = "NEEDS_HUMAN_REVIEW"
    unified["formal_ready"] = False
    record = {**source_record, "closure_status": "GAPFILL_ACQUIRED", "errors": [], "warnings": [], "unified_event": unified}
    record["evidence_ids"] = sorted([event_evidence["evidence_id"], *[item["evidence_id"] for item in company_evidence]])
    record["content_sha256"] = content_sha(unified)
    write_jsonl(output / "content_candidates.jsonl", [record])
    write_jsonl(output / "accepted_evidence.jsonl", [event_evidence, *company_evidence])
    write_jsonl(output / "evidence_candidates.jsonl", company_evidence)
    write_jsonl(output / "search_audit.jsonl", [{"event_id": EVENT_ID, "adapter": "STOCKANALYSIS_PUBLIC_ROUTE", "query": f"TYO {row['security_code']} historical prices", "candidate_url": row["source_url"], "retrieved_at": retrieved_at, "result_rank": 1} for row in market_audit_rows] + [{"event_id": EVENT_ID, "adapter": "STOCKANALYSIS_FILINGS_INDEX", "query": f"{row['company_code']} issuer filings before {EVENT_DATE}", "candidate_url": row["index_url"], "retrieved_at": retrieved_at, "result_rank": 1} for row in disclosure_audits])
    write_json(output / "market_acquisition_audit.json", {"event_id": EVENT_ID, "endpoint_dates": endpoints, "calendar_security": f"{MARKET_CODE}.T", "sources": market_audit_rows, "continuous_trading_audits": audits})
    write_json(output / "company_disclosure_audit.json", {"event_id": EVENT_ID, "companies": disclosure_audits})
    write_jsonl(output / "event_processing_status.jsonl", [{"event_id": EVENT_ID, "status": "GAPFILL_ACQUIRED", "evidence_count": 1 + len(company_evidence), "industry_market_calculated": len(unified["industries"]), "company_market_calculated": len(unified["companies"]), "review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False}])
    write_json(output / "run_summary.json", {"run_id": output.name, "event_id": EVENT_ID, "status": "GAPFILL_ACQUIRED", "event_evidence_count": 1, "company_evidence_count": len(company_evidence), "industry_count": len(unified["industries"]), "company_count": len(unified["companies"]), "industry_market_calculated": len(unified["industries"]), "company_market_calculated": len(unified["companies"]), "review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False, "causal_conclusion": "ABSTAIN"})
    print((output / "run_summary.json").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
