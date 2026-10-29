"""CNINFO official-report intake helpers for company-impact v2."""

from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping


CNINFO_STATIC_BASE = "https://static.cninfo.com.cn/"
CHINA_STANDARD_TIME = timezone(timedelta(hours=8))


def build_cninfo_query_fields(
    *,
    company_name: str,
    start_date: str,
    end_date: str,
) -> dict[str, str]:
    return {
        "pageNum": "1",
        "pageSize": "100",
        "column": "sse",
        "tabName": "fulltext",
        "plate": "",
        "stock": "",
        "searchkey": company_name,
        "secid": "",
        "category": "category_ndbg_szsh;category_bndbg_szsh",
        "trade": "",
        "seDate": f"{start_date}~{end_date}",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }


def _plain_title(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", "", text)


def _published_date(value: object) -> str:
    milliseconds = int(value)
    return datetime.fromtimestamp(
        milliseconds / 1000,
        tz=CHINA_STANDARD_TIME,
    ).date().isoformat()


def _source_class(title: str) -> str | None:
    if re.fullmatch(r"\d{4}年年度报告(?:（[^）]+）)?", title):
        return "ANNUAL_REPORT"
    if re.fullmatch(r"\d{4}年半年度报告(?:（[^）]+）)?", title):
        return "INTERIM_REPORT"
    return None


def parse_cninfo_payload(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in payload.get("announcements") or []:
        title = _plain_title(raw.get("announcementTitle"))
        adjunct_url = str(raw.get("adjunctUrl") or "").lstrip("/")
        source_url = (
            adjunct_url
            if adjunct_url.startswith(("http://", "https://"))
            else CNINFO_STATIC_BASE + adjunct_url
        )
        rows.append(
            {
                "announcement_id": str(raw.get("announcementId") or ""),
                "document_title": title,
                "company_code": str(raw.get("secCode") or ""),
                "company_name": str(raw.get("secName") or ""),
                "org_id": str(raw.get("orgId") or ""),
                "published_at": _published_date(raw.get("announcementTime")),
                "published_at_precision": "DATE",
                "source_class": _source_class(title),
                "source_url": source_url,
            }
        )
    return rows


def select_target_reports(
    *,
    parse_payload: Mapping[str, Any],
    company_code: str,
    annual_year: int,
    interim_year: int,
    cutoff_at: str,
) -> dict[str, dict[str, Any]]:
    cutoff_date = date.fromisoformat(cutoff_at[:10])
    wanted_titles = {
        "ANNUAL_REPORT": f"{annual_year}年年度报告",
        "INTERIM_REPORT": f"{interim_year}年半年度报告",
    }
    selected: dict[str, dict[str, Any]] = {}
    for row in parse_cninfo_payload(parse_payload):
        if row["company_code"] != company_code:
            continue
        source_class = row["source_class"]
        if source_class not in wanted_titles:
            continue
        if row["document_title"] != wanted_titles[source_class]:
            continue
        if date.fromisoformat(row["published_at"]) >= cutoff_date:
            continue
        selected.setdefault(source_class, row)
    return selected
