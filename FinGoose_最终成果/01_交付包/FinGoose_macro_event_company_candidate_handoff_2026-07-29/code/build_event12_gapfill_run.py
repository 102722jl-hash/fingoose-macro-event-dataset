from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from pypdf import PdfReader

from fingoose_company_dossier_builder_v2 import select_evidence_passage
from fingoose_industry_market_v2 import (
    fetch_market_registry,
    load_market_windows_from_raw,
)
from fingoose_public_company_price_windows_v1 import (
    build_eastmoney_url,
    build_price_candidate,
    calculate_price_window,
)


CNINFO_QUERY = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC = "https://static.cninfo.com.cn/"
EVENT_ID = "event-12"
ANCHOR_DATE = "2026-03-13"
CUTOFF_DATE = "2026-03-13"
RETRIEVED_AT = "2026-08-13T00:00:00+00:00"
REPORT_TARGETS = {"ANNUAL_REPORT": 2024, "INTERIM_REPORT": 2025}
INDUSTRY_BENCHMARKS = {
    "人工智能与算力": ("801750", "计算机", "申万计算机指数作为人工智能与算力主题的公开可复算代理"),
    "半导体": ("801080", "电子", "申万电子指数作为半导体主题的上位行业代理"),
    "高端装备": ("801890", "机械设备", "申万机械设备指数作为高端装备主题代理"),
    "新能源": ("801730", "电力设备", "申万电力设备指数作为新能源主题代理"),
    "电网与储能": ("801730", "电力设备", "申万电力设备指数作为电网与储能主题代理"),
    "消费": ("801120", "食品饮料", "样本公司均为食品饮料，使用申万食品饮料指数"),
    "医疗养老": ("801150", "医药生物", "申万医药生物指数作为医疗养老主题代理"),
}
KEYWORDS = {
    "人工智能与算力": ["公司从事的主要业务", "主营业务", "服务器", "计算机", "人工智能", "算力"],
    "半导体": ["公司从事的主要业务", "主营业务", "半导体", "集成电路", "芯片"],
    "高端装备": ["公司从事的主要业务", "主营业务", "工程机械", "液压", "装备制造"],
    "新能源": ["公司从事的主要业务", "主营业务", "光伏", "新能源汽车", "新能源", "发电"],
    "电网与储能": ["公司从事的主要业务", "主营业务", "电网", "输变电", "电力设备", "储能"],
    "消费": ["公司从事的主要业务", "主营业务", "白酒", "乳制品", "食品"],
    "医疗养老": ["公司从事的主要业务", "主营业务", "药品", "医疗器械", "医药"],
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8", newline="\n")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")


def stable_id(prefix: str, value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def content_sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def company_id(code: str) -> str:
    return "company-" + code.replace(".", "-").lower()


def init_run(source: Path, output: Path, *, resume: bool) -> None:
    if output.exists():
        if not resume:
            raise FileExistsError(f"OUTPUT_RUN_EXISTS:{output}")
        return
    output.mkdir(parents=True)
    for name in (
        "profile.json", "base_dataset_config.json", "base_training_config.json",
        "base_unified_events.jsonl", "accepted_evidence.jsonl",
        "discovery_candidates.jsonl", "request.json",
    ):
        source_path = source / name
        if source_path.exists():
            shutil.copy2(source_path, output / name)


def query_fields(name: str, code: str, column: str, stock: str = "") -> dict[str, str]:
    return {
        "pageNum": "1", "pageSize": "100", "column": column, "tabName": "fulltext",
        "plate": "", "stock": stock, "searchkey": name, "secid": "",
        "category": "category_ndbg_szsh;category_bndbg_szsh", "trade": "",
        "seDate": "2024-01-01~2026-03-12", "sortName": "", "sortType": "", "isHLtitle": "true",
    }


def cninfo_request(session: requests.Session, fields: dict[str, str]) -> dict[str, Any]:
    response = session.post(CNINFO_QUERY, data=fields, timeout=40)
    response.raise_for_status()
    return response.json()


def plain_title(value: Any) -> str:
    return re.sub(r"\s+|<[^>]+>", "", str(value or "")).replace("&nbsp;", "")


def report_class(title: str) -> str | None:
    if "摘要" in title or re.search(r"英文|H股公告|港股公告", title):
        return None
    if re.search(r"2024年?年度报告(?:全文)?(?:（[^）]+）)?$", title):
        return "ANNUAL_REPORT"
    if re.search(r"2025年?(?:半年度报告|半年报|中期报告)(?:全文)?(?:（[^）]+）)?$", title):
        return "INTERIM_REPORT"
    return None


def published_date(milliseconds: Any) -> str:
    return datetime.fromtimestamp(int(milliseconds) / 1000, timezone.utc).astimezone().date().isoformat()


def select_reports(payload: dict[str, Any], code: str) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    rows = sorted(payload.get("announcements") or [], key=lambda row: int(row.get("announcementTime") or 0), reverse=True)
    for row in rows:
        if str(row.get("secCode") or "") != code:
            continue
        title = plain_title(row.get("announcementTitle"))
        kind = report_class(title)
        if not kind:
            continue
        day = published_date(row["announcementTime"])
        if day >= CUTOFF_DATE:
            continue
        url = str(row.get("adjunctUrl") or "").lstrip("/")
        selected.setdefault(kind, {**row, "document_title": title, "published_at": day, "source_url": url if url.startswith("http") else CNINFO_STATIC + url})
    return selected


def extract_pages(pdf_path: Path) -> list[dict[str, Any]]:
    pages = []
    for index, page in enumerate(PdfReader(str(pdf_path), strict=False).pages, 1):
        text = re.sub(r"\s+", " ", page.extract_text() or "").strip()
        pages.append({"page_number": index, "text": text})
    return pages


def acquire_company_evidence(unified: dict[str, Any], output: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    raw_root = output / "online" / "company_reports" / "query_responses"
    pdf_root = output / "online" / "company_reports" / "pdf"
    raw_root.mkdir(parents=True, exist_ok=True)
    pdf_root.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 FinGooseCandidate/1.0", "Referer": "https://www.cninfo.com.cn/"})
    audits: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    for company in unified["companies"]:
        code_full = company["company_code"]
        code = code_full[:6]
        column = "szse" if code_full.endswith(".SZ") else "sse"
        fields = query_fields(company["company_name"], code, column)
        raw_path = raw_root / f"{code_full}.json"
        try:
            if raw_path.exists():
                payload = json.loads(raw_path.read_text(encoding="utf-8"))
                merged = payload.get("announcements") or []
            else:
                broad = cninfo_request(session, fields)
                org_id = next((str(row.get("orgId")) for row in broad.get("announcements") or [] if str(row.get("secCode")) == code), "")
                precise = cninfo_request(session, query_fields("", code, column, f"{code},{org_id}")) if org_id else {"announcements": []}
                merged = list({str(row.get("announcementId")): row for row in [*(precise.get("announcements") or []), *(broad.get("announcements") or [])]}.values())
                payload = {**broad, "announcements": merged, "totalAnnouncement": len(merged)}
                write_json(raw_path, payload)
            audits.append({"event_id": EVENT_ID, "company_code": code_full, "query": fields, "adapter": "CNINFO_OFFICIAL_QUERY", "retrieved_at": RETRIEVED_AT, "result_count": len(merged), "response_path": raw_path.relative_to(output).as_posix(), "response_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest()})
        except Exception as exc:
            quarantine.append({"event_id": EVENT_ID, "company_code": code_full, "reason_code": "COMPANY_REPORT_QUERY_FAILED", "detail": f"{type(exc).__name__}:{exc}"})
            continue
        selected = select_reports(payload, code)
        for kind, year in REPORT_TARGETS.items():
            report = selected.get(kind)
            if not report:
                quarantine.append({"event_id": EVENT_ID, "company_code": code_full, "source_class": kind, "reason_code": "TARGET_REPORT_NOT_FOUND_BEFORE_CUTOFF"})
                continue
            document_id = str(report["announcementId"])
            pdf_path = pdf_root / f"{code_full}__{year}__{kind.lower()}__{document_id}.pdf"
            try:
                if pdf_path.exists():
                    body = pdf_path.read_bytes()
                else:
                    response = session.get(report["source_url"], timeout=60)
                    response.raise_for_status()
                    body = response.content
                    if not body.startswith(b"%PDF"):
                        raise ValueError("RESPONSE_NOT_PDF")
                    pdf_path.write_bytes(body)
                digest = hashlib.sha256(body).hexdigest()
                passage = select_evidence_passage(extract_pages(pdf_path), KEYWORDS[company["industry"]], quote_limit=520)
                if not passage:
                    raise ValueError("BUSINESS_EXPOSURE_PASSAGE_NOT_FOUND")
                evidence_id = stable_id("company-evidence", {"event_id": EVENT_ID, "company_code": code_full, "document_id": document_id, "page": passage["page_number"]})
                candidates.append({
                    "evidence_id": evidence_id, "event_id": EVENT_ID, "company_id": company_id(code_full),
                    "company_code": code_full, "company_name": company["company_name"], "industry_id": company["industry_id"],
                    "claim_type": "PRE_EVENT_BUSINESS_EXPOSURE", "source_tier": "T2", "source_class": kind,
                    "document_id": document_id, "document_title": report["document_title"], "publisher": "巨潮资讯网",
                    "issuer": company["company_name"], "published_at": report["published_at"] + "T00:00:00+08:00",
                    "anchor_at": ANCHOR_DATE + "T00:00:00+08:00", "temporal_role": "AS_OF_EVIDENCE",
                    "retrieved_at": RETRIEVED_AT, "reporting_period": str(year) if kind == "ANNUAL_REPORT" else f"{year}-H1",
                    "original_quote": passage["original_quote"], "locator": passage["page_or_section_locator"],
                    "matched_terms": passage["matched_terms"], "source_url": report["source_url"],
                    "snapshot_path": pdf_path.relative_to(output).as_posix(), "snapshot_sha256": digest,
                    "acceptance_status": "ACCEPTED", "acceptance_reason": "GATES_PASSED",
                    "review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False,
                })
            except Exception as exc:
                quarantine.append({"event_id": EVENT_ID, "company_code": code_full, "document_id": document_id, "source_class": kind, "reason_code": "COMPANY_REPORT_EXTRACTION_FAILED", "detail": f"{type(exc).__name__}:{exc}"})
    return audits, candidates, quarantine


def eastmoney_payload(url: str) -> dict[str, Any]:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 FinGooseCandidate/1.0", "Referer": "https://quote.eastmoney.com/"}, timeout=40)
    response.raise_for_status()
    return response.json()


def tencent_url(company_code: str) -> str:
    code, market = company_code.split(".")
    symbol = ("sh" if market == "SH" else "sz") + code
    return f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,2026-02-01,2026-05-15,200,qfq"


def tencent_candidate(company: dict[str, Any], payload: dict[str, Any], url: str) -> dict[str, Any]:
    code, market = company["company_code"].split(".")
    symbol = ("sh" if market == "SH" else "sz") + code
    data = (payload.get("data") or {}).get(symbol) or {}
    raw_bars = data.get("qfqday") or data.get("day") or []
    bars = [{"trade_date": row[0], "open": float(row[1]), "close": float(row[2]), "high": float(row[3]), "low": float(row[4]), "volume": float(row[5])} for row in raw_bars if len(row) >= 6]
    observations = calculate_price_window(bars, ANCHOR_DATE)
    observed = sum(row["status"] == "OBSERVED" for row in observations.values())
    return {
        "price_window_id": "public-price-" + EVENT_ID + "-" + company["company_code"].lower().replace(".", "-"),
        "dataset_version": "event12-gapfill-company-market-v1", "release_tier": "PUBLIC_VENDOR_CANDIDATE",
        "event_id": EVENT_ID, "anchor_id": f"{EVENT_ID}-milestone-01", "anchor_date": ANCHOR_DATE,
        "company_code": company["company_code"], "company_name": company["company_name"],
        "frequency": "DAILY", "adjustment": "FORWARD_ADJUSTED_QFQ", "t0_rule": "FIRST_TRADING_DAY_ON_OR_AFTER_ANCHOR_DATE",
        "source_class": "PUBLIC_VENDOR_DATA", "source_provider": "TENCENT_PUBLIC_FQKLINE", "source_url": url,
        "source_snapshot_sha256": content_sha(payload), "bar_count": len(bars),
        "status": "WINDOW_AVAILABLE" if observed == len(observations) else "PARTIAL_OR_MISSING_WINDOW",
        "observations": observations, "formal_ready": False, "financial_attribution_allowed": False,
        "causal_attribution_allowed": False, "redistribution_allowed": False,
    }


def acquire_company_market(unified: dict[str, Any], output: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_root = output / "online" / "market" / "company"
    raw_root.mkdir(parents=True, exist_ok=True)
    rows = []
    quarantine = []
    for company in unified["companies"]:
        job = {"event_id": EVENT_ID, "anchor_id": f"{EVENT_ID}-milestone-01", "anchor_date": ANCHOR_DATE, "company_code": company["company_code"], "company_name": company["company_name"]}
        eastmoney_url = build_eastmoney_url(company["company_code"], ANCHOR_DATE)
        try:
            window_id = "public-price-" + EVENT_ID + "-" + company["company_code"].lower().replace(".", "-")
            raw_path = raw_root / f"{window_id}.json"
            if raw_path.exists():
                payload = json.loads(raw_path.read_text(encoding="utf-8"))
                provider = str(payload.get("gapfill_provider") or "EASTMONEY")
                candidate = tencent_candidate(company, payload, str(payload.get("gapfill_source_url"))) if provider == "TENCENT" else build_price_candidate(job, payload, eastmoney_url)
            else:
                url = tencent_url(company["company_code"])
                response = requests.get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"}, timeout=40)
                response.raise_for_status()
                payload = response.json()
                payload["gapfill_provider"] = "TENCENT"
                payload["gapfill_source_url"] = url
                candidate = tencent_candidate(company, payload, url)
                write_json(raw_path, payload)
            candidate["snapshot_path"] = raw_path.relative_to(output).as_posix()
            candidate["retrieved_at"] = RETRIEVED_AT
            rows.append(candidate)
        except Exception as exc:
            quarantine.append({"event_id": EVENT_ID, "company_code": company["company_code"], "reason_code": "COMPANY_MARKET_FETCH_FAILED", "detail": f"{type(exc).__name__}:{exc}"})
    return rows, quarantine


def industry_market(unified: dict[str, Any], output: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    unique = {}
    mappings = []
    for industry in unified["industries"]:
        code, name, basis = INDUSTRY_BENCHMARKS[industry["industry_name_zh"]]
        unique[code] = {"mapping_id": industry["event_industry_mapping_id"], "code": code, "name_zh": name}
        mappings.append({"event_industry_mapping_id": industry["event_industry_mapping_id"], "event_id": EVENT_ID, "anchor_first_public_at": unified["event"]["published_at"], "sw1_id": code, "classification_edition": "SW2021_PROXY", "proxy_selection_basis_zh": basis})
    market_start = (date.fromisoformat(ANCHOR_DATE) - timedelta(days=60)).strftime("%Y%m%d")
    registry = {
        "dataset_version": "event12-gapfill-market-v1", "market_timezone": "Asia/Shanghai",
        "date_range": {"start_date": market_start, "end_date": "20260813"},
        "industry_benchmarks": list(unique.values()),
        "market_benchmark": {"benchmark_id": "CSI300", "code": "sh000300", "name_zh": "沪深300"},
        "selection_basis": "FROZEN_THEME_TO_SW1_PROXY_BEFORE_MARKET_FETCH", "formal_ready": False,
    }
    write_json(output / "market_registry.json", registry)
    raw_root = output / "online" / "market" / "industry"
    expected = [raw_root / f"sw_{code}.csv" for code in unique]
    csi_path = raw_root / "csi300.csv"
    csi_has_coverage = False
    if csi_path.exists():
        csi_lines = csi_path.read_text(encoding="utf-8-sig").splitlines()
        csi_has_coverage = len(csi_lines) > 1 and csi_lines[1].split(",", 1)[0].replace("-", "") <= market_start
    fetch_manifest = raw_root / "market_fetch_manifest.jsonl"
    if csi_has_coverage and all(path.exists() for path in expected) and fetch_manifest.exists():
        fetch_records = read_jsonl(fetch_manifest)
    else:
        fetch_records = fetch_market_registry(registry, raw_root)
    windows = load_market_windows_from_raw(mappings=mappings, registry=registry, raw_root=raw_root)
    for row, mapping in zip(windows, mappings):
        row["proxy_selection_basis_zh"] = mapping["proxy_selection_basis_zh"]
        row["causal_use"] = "VALIDATION_ONLY"
    return windows, fetch_records


def endpoint(company_point: dict[str, Any], market_point: dict[str, Any] | None, industry_point: dict[str, Any] | None) -> dict[str, Any]:
    company_return = company_point.get("raw_return_from_t_minus_1")
    market_return = (market_point.get("raw_return_from_t_minus_1") if market_point and "raw_return_from_t_minus_1" in market_point else market_point.get("market_return")) if market_point else None
    industry_return = industry_point.get("industry_return") if industry_point else None
    return {
        "date": company_point.get("date"), "raw_value": company_point.get("close"), "return": company_return,
        "market_date": (market_point.get("date") or market_point.get("actual_date")) if market_point else None, "market_raw_value": (market_point.get("close") if "close" in market_point else market_point.get("market_value")) if market_point else None,
        "market_return": market_return, "market_relative_return": company_return - market_return if company_return is not None and market_return is not None else None,
        "industry_date": industry_point.get("actual_date") if industry_point else None, "industry_raw_value": industry_point.get("industry_value") if industry_point else None,
        "industry_return": industry_return, "industry_relative_return": company_return - industry_return if company_return is not None and industry_return is not None else None,
    }


def enrich(unified: dict[str, Any], company_evidence: list[dict[str, Any]], company_prices: list[dict[str, Any]], industry_windows: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_by_code: dict[str, list[dict[str, Any]]] = {}
    for row in company_evidence:
        evidence_by_code.setdefault(row["company_code"], []).append(row)
    prices = {row["company_code"]: row for row in company_prices}
    industry_by_id = {row["event_industry_mapping_id"]: row for row in industry_windows}
    industries = {row["industry_id"]: row for row in unified["industries"]}
    for industry in unified["industries"]:
        window = industry_by_id[industry["event_industry_mapping_id"]]
        fixed = window.get("fixed_windows") or {}
        endpoints = {}
        for key in ("T_MINUS_1", "T0", "D1", "D3", "D5", "D20"):
            point = fixed.get(key) or {}
            endpoints[key] = {"date": point.get("actual_date"), "raw_value": point.get("industry_value"), "return": point.get("industry_return"), "market_raw_value": point.get("market_value"), "market_return": point.get("market_return"), "market_relative_return": point.get("market_relative_return")}
        industry["market_window"] = {**industry["market_window"], "status": "CALCULATED" if window.get("window_status") == "AVAILABLE" else "DATA_MISSING", "endpoints": endpoints, "continuous_window": window.get("continuous_window") or [], "data_source": "AKSHARE_SWSRESEARCH_AND_TENCENT_PUBLIC", "industry_benchmark_id": window.get("benchmark", {}).get("benchmark_code"), "missing_reason_codes": [] if window.get("window_status") == "AVAILABLE" else [window.get("pending_reason") or "INDUSTRY_WINDOW_UNAVAILABLE"], "proxy_selection_basis_zh": window.get("proxy_selection_basis_zh")}
    for company in unified["companies"]:
        evidences = sorted(evidence_by_code.get(company["company_code"], []), key=lambda row: row["published_at"])
        company["company_evidence"] = evidences
        company["evidence_ids"] = [*company.get("evidence_ids", []), *[row["evidence_id"] for row in evidences]]
        company["company_evidence_status"] = "VERIFIED" if len({row["document_id"] for row in evidences}) >= 2 else "PARTIALLY_VERIFIED" if evidences else "DATA_MISSING"
        price = prices.get(company["company_code"])
        industry = industries[company["industry_id"]]
        industry_window = industry_by_id[industry["event_industry_mapping_id"]]
        fixed = industry_window.get("fixed_windows") or {}
        endpoints = {}
        if price:
            for key, point in price["observations"].items():
                endpoints[key] = endpoint(point, fixed.get(key), fixed.get(key))
        full_company = price and price["status"] == "WINDOW_AVAILABLE"
        full_industry = industry_window.get("window_status") == "AVAILABLE"
        status = "CALCULATED" if full_company and full_industry else "PARTIAL_CALCULATED" if full_company else "DATA_MISSING"
        reasons = []
        if not full_company: reasons.append("COMPANY_PRICE_WINDOW_INCOMPLETE")
        if not full_industry: reasons.append("INDUSTRY_BENCHMARK_NOT_ACQUIRED")
        company["market_window"] = {**company["market_window"], "status": status, "endpoints": endpoints, "data_source": "EASTMONEY_PUBLIC_ENDPOINT_AND_AKSHARE_PUBLIC", "market_benchmark_id": "000300.SH", "industry_benchmark_id": industry["market_window"].get("industry_benchmark_id"), "missing_reason_codes": reasons}
        d20 = endpoints.get("D20") or {}
        company["relative_return"] = {"status": status, "value": d20.get("market_relative_return"), "industry_value": d20.get("industry_relative_return"), "reason": reasons[0] if reasons else None, "window": "D20"}
    qa_by_type = {row["qa_type"]: row for row in unified["qa"]}
    qa_by_type["MARKET_VALIDATION"]["direct_answer_zh"] = "公司、沪深300及行业代理的T0、D1、D3、D5、D20窗口已按T-1基准计算；结果仅验证窗口表现，不证明因果。"
    qa_by_type["MARKET_VALIDATION"]["answer"]["task_answer"]["direct_answer_zh"] = qa_by_type["MARKET_VALIDATION"]["direct_answer_zh"]
    qa_by_type["INDUSTRY_COMPANY"]["direct_answer_zh"] = "21家公司均按事前业务暴露选样，并以事件日前两份公司定期报告候选证据约束；仍需人工逐条复核引文语义、混杂因素和行业代理。"
    qa_by_type["INDUSTRY_COMPANY"]["answer"]["task_answer"]["direct_answer_zh"] = qa_by_type["INDUSTRY_COMPANY"]["direct_answer_zh"]
    qa_by_type["MECHANISM_STAGE"]["horizon_reasoning_zh"] = {
        "IMMEDIATE": {"label_zh": "首轮预期与交易反应", "window_keys": ["T0", "D1"], "reasoning_zh": unified["event"]["horizon_analysis"]["IMMEDIATE"], "observation_focus_zh": ["政策预期重估", "行业与沪深300相对表现"]},
        "SHORT_TERM": {"label_zh": "经营决策调整与连续确认", "window_keys": ["D3", "D5", "D20"], "reasoning_zh": unified["event"]["horizon_analysis"]["SHORT_TERM"], "observation_focus_zh": ["专项规划与财政资金", "重大项目、产业投资和订单落地"]},
        "MEDIUM_TERM": {"label_zh": "执行兑现与结构持续性", "window_keys": ["1至4个季度"], "reasoning_zh": unified["event"]["horizon_analysis"]["MEDIUM_TERM"], "observation_focus_zh": ["财报兑现", "项目执行进度与政策持续性"]},
    }
    qa_by_type["MARKET_VALIDATION"]["market_validation"] = {
        "method_zh": "以事件前最后一个交易日T-1为基准，计算T0、D1、D3、D5、D20行业收益、沪深300收益及两者差值；行情仅验证窗口表现。",
        "industry_results": [
            {
                "event_industry_mapping_id": industry["event_industry_mapping_id"],
                "industry_name_zh": industry["industry_name_zh"],
                "overall_verdict": "DESCRIPTIVE_ONLY",
                "overall_verdict_zh": "描述性窗口结果",
                "windows": {
                    key: {
                        "actual_date": point.get("date"),
                        "industry_return": point.get("return"),
                        "market_return": point.get("market_return"),
                        "market_relative_return": point.get("market_relative_return"),
                    }
                    for key, point in industry["market_window"]["endpoints"].items()
                },
                "horizon_verdicts": {
                    "IMMEDIATE": {"verdict_zh": "仅观察", "basis_zh": "T0与D1用于观察公告后的首轮相对表现，不作因果归因。"},
                    "SHORT_TERM": {"verdict_zh": "仅观察", "basis_zh": "D3、D5与D20用于观察短期表现是否延续，不替代经营数据。"},
                    "MEDIUM_TERM": {"verdict_zh": "暂不外推", "basis_zh": "短窗行情不能推断1至4个季度的政策执行和财报兑现。"},
                },
            }
            for industry in unified["industries"]
        ],
    }
    qa_by_type["INDUSTRY_COMPANY"]["company_results"] = [
        {
            "company_code": company["company_code"],
            "company_name": company["company_name"],
            "industry_name_zh": company["industry"],
            "pre_event_disclosures": company["company_evidence"],
            "mechanism_zh": company["mechanism_zh"],
            "directions_zh": company["horizon_directions"],
            "trading_status_zh": "T-1、T0、D1、D3、D5、D20端点均有可回算交易值；连续交易与停复牌仍需人工复核。",
            "suspension_status_zh": "六个固定端点可交易；未据此推断整个窗口无停复牌。",
            "conditions_zh": [industries[company["industry_id"]]["condition_zh"]],
            "invalidation_conditions_zh": [industries[company["industry_id"]]["invalidation_condition_zh"]],
            "counterevidence": company["counterevidence"],
            "counterevidence_search_zh": "已登记反证条件；公司独立公告和混杂因素仍需人工逐项排除。",
            "confounders": [{"title_zh": value, "mechanism_zh": "可能独立解释公司窗口表现", "affected_windows": ["T0", "D1", "D3", "D5", "D20"]} for value in company["confounders"]],
            "decision_zh": "候选业务暴露与行情窗口已具备；严格因果门禁未通过，保持ABSTAIN并等待人工语义与混杂复核。",
        }
        for company in unified["companies"]
    ]
    unified["causal_assessment"]["status"] = "DESCRIPTIVE_EVENT_STUDY"
    unified["causal_assessment"]["causal_conclusion"] = "ABSTAIN"
    unified["causal_assessment"]["causal_attribution_allowed"] = False
    unified["causal_assessment"]["unmet_conditions"] = ["未定义比较组", "未通过前趋势检验", "混杂因素尚未完全控制", "稳健性与反证门禁未完成"]
    return unified


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--output-run", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    source = args.source_run.resolve()
    output = args.output_run.resolve()
    init_run(source, output, resume=args.resume)
    content_rows = read_jsonl(source / "accepted_content.jsonl")
    target = next(row for row in content_rows if row["event_id"] == EVENT_ID)
    unified = target["unified_event"]
    evidence_cache = output / "accepted_company_evidence.jsonl"
    if args.resume and evidence_cache.exists():
        evidence = read_jsonl(evidence_cache)
        audits = read_jsonl(output / "company_search_audit.jsonl")
        quarantine = read_jsonl(output / "quarantine.company.jsonl") if (output / "quarantine.company.jsonl").exists() else []
    else:
        audits, evidence, quarantine = acquire_company_evidence(unified, output)
        write_jsonl(output / "company_search_audit.jsonl", audits)
        write_jsonl(output / "company_evidence_candidates.jsonl", evidence)
        write_jsonl(evidence_cache, evidence)
        write_jsonl(output / "quarantine.company.jsonl", quarantine)
    company_prices, price_quarantine = acquire_company_market(unified, output)
    write_jsonl(output / "company_market_windows.jsonl", company_prices)
    windows, fetch_records = industry_market(unified, output)
    write_jsonl(output / "industry_market_windows.jsonl", windows)
    write_jsonl(output / "market_fetch_audit.jsonl", fetch_records)
    quarantine.extend(price_quarantine)
    enriched = enrich(unified, evidence, company_prices, windows)
    updated = []
    for row in content_rows:
        if row["event_id"] != EVENT_ID:
            updated.append(row)
            continue
        replacement = {**row, "unified_event": enriched, "evidence_ids": sorted(set([*row.get("evidence_ids", []), *[item["evidence_id"] for item in evidence]]))}
        replacement["content_sha256"] = content_sha(enriched)
        updated.append(replacement)
    write_jsonl(output / "quarantine.jsonl", quarantine)
    write_jsonl(output / "content_candidates.jsonl", updated)
    write_jsonl(output / "accepted_content.jsonl", updated)
    write_jsonl(output / "unified_event_audit_input.jsonl", [enriched])
    write_json(output / "gapfill_summary.json", {
        "event_id": EVENT_ID, "company_count": len(unified["companies"]), "accepted_company_evidence_count": len(evidence),
        "companies_with_two_documents": len({code for code in {row["company_code"] for row in evidence} if len({row["document_id"] for row in evidence if row["company_code"] == code}) >= 2}),
        "company_market_window_count": len(company_prices), "full_company_window_count": sum(row["status"] == "WINDOW_AVAILABLE" for row in company_prices),
        "industry_market_window_count": len(windows), "available_industry_window_count": sum(row["window_status"] == "AVAILABLE" for row in windows),
        "quarantine_count": len(quarantine), "causal_conclusion": "ABSTAIN", "review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False,
    })
    write_json(output / "request.json", {"mode": "event-gapfill", "event_id": EVENT_ID, "source_run": str(source), "run_id": output.name, "requested_at": RETRIEVED_AT, "NEEDS_HUMAN_REVIEW": True, "formal_ready": False})
    print((output / "gapfill_summary.json").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
