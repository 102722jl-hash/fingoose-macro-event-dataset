"""Isolated Eastmoney iron-ore vendor-main parsing and revision helpers."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode

from fingoose_commodity_sources import AdapterError, json_bytes, sha256


EASTMONEY_ADAPTER_VERSION = "fingoose-eastmoney-main-close-v0.1"
EASTMONEY_ENDPOINT = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
LOCKED_QUALITY_FLAGS = (
    "VENDOR_MAIN_ALGORITHM_UNKNOWN",
    "CONTRACT_MAPPING_MISSING",
    "OPEN_INTEREST_MISSING",
    "SETTLEMENT_MISSING",
    "LICENSE_SCOPE_UNKNOWN",
)


def build_eastmoney_url(begin: str, end: str) -> str:
    for value, name in ((begin, "begin"), (end, "end")):
        if len(value) != 8 or not value.isdigit():
            raise AdapterError(f"{name} must be YYYYMMDD")
    query = urlencode(
        {
            "secid": "114.im",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "101",
            "fqt": "1",
            "beg": begin,
            "end": end,
        }
    )
    return f"{EASTMONEY_ENDPOINT}?{query}"


def _number(value: str, field: str, *, integer: bool = False) -> int | float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise AdapterError(f"invalid {field}: {value!r}") from exc
    if integer:
        if number < 0 or not number.is_integer():
            raise AdapterError(f"{field} must be a non-negative integer")
        return int(number)
    if number <= 0:
        raise AdapterError(f"{field} must be positive")
    return number


def _amount(value: str) -> float | None:
    if value in {"", "-", "null", "None"}:
        return None
    try:
        number = float(value)
    except ValueError as exc:
        raise AdapterError(f"invalid amount: {value!r}") from exc
    if number < 0:
        raise AdapterError("amount must be non-negative")
    return number


def parse_eastmoney_klines(
    content: bytes | str | Mapping[str, Any],
    *,
    retrieved_at: str,
    reject_retrieval_day: bool = True,
) -> list[dict[str, Any]]:
    if isinstance(content, Mapping):
        payload = dict(content)
    else:
        try:
            payload = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdapterError("invalid Eastmoney JSON response") from exc
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise AdapterError("Eastmoney response has no data object")
    if data.get("code") != "im" or data.get("market") != 114:
        raise AdapterError("Eastmoney response is not market 114 code im")
    klines = data.get("klines")
    if not isinstance(klines, list):
        raise AdapterError("Eastmoney response has no kline list")
    try:
        retrieval_date = datetime.fromisoformat(retrieved_at).date()
    except ValueError as exc:
        raise AdapterError("retrieved_at must be an ISO 8601 date-time") from exc

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in klines:
        if not isinstance(raw, str):
            raise AdapterError("Eastmoney kline must be a CSV string")
        values = raw.split(",")
        if len(values) != 11:
            raise AdapterError("Eastmoney kline must contain exactly 11 fields")
        trade_date = values[0]
        try:
            parsed_date = date.fromisoformat(trade_date)
        except ValueError as exc:
            raise AdapterError(f"invalid trade_date: {trade_date}") from exc
        if parsed_date > retrieval_date:
            raise AdapterError(f"future trade_date rejected: {trade_date}")
        if reject_retrieval_day and parsed_date == retrieval_date:
            raise AdapterError(f"retrieval-day bar rejected: {trade_date}")
        if trade_date in seen:
            raise AdapterError(f"duplicate trade_date rejected: {trade_date}")
        seen.add(trade_date)

        opening = float(_number(values[1], "open"))
        closing = float(_number(values[2], "close"))
        high = float(_number(values[3], "high"))
        low = float(_number(values[4], "low"))
        volume = int(_number(values[5], "volume", integer=True))
        amount = _amount(values[6])
        if low > min(opening, closing) or high < max(opening, closing) or low > high:
            raise AdapterError(f"invalid OHLC relationship for {trade_date}")
        rows.append(
            {
                "trade_date": trade_date,
                "open": opening,
                "high": high,
                "low": low,
                "close": closing,
                "volume": volume,
                "amount": amount,
            }
        )
    return sorted(rows, key=lambda item: item["trade_date"])


def _record_id(record: Mapping[str, Any]) -> str:
    payload = {
        key: value
        for key, value in record.items()
        if key not in {"record_id", "quality"}
    }
    return "FGVND-" + sha256(json_bytes(payload))[:20].upper()


def build_vendor_record(
    row: Mapping[str, Any],
    *,
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    record = {
        "schema_version": "fingoose-commodity-vendor-main-v0.2",
        "record_type": "vendor_main_close_daily",
        "record_id": "",
        "trade_date": str(row["trade_date"]),
        "commodity": "I",
        "vendor_main_code": "im",
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
        "volume": int(row["volume"]),
        "amount": None if row.get("amount") is None else float(row["amount"]),
        "currency": "CNY",
        "quote_unit": "CNY_PER_TONNE",
        "source_role": "vendor_main_close_candidate",
        "price_basis": "close",
        "revision": 1,
        "is_latest": True,
        "provenance": dict(provenance),
        "quality": {
            "status": "review_required",
            "flags": list(LOCKED_QUALITY_FLAGS),
            "notes": None,
        },
    }
    record["record_id"] = _record_id(record)
    return record


def _signature(record: Mapping[str, Any]) -> str:
    payload = {
        key: value
        for key, value in record.items()
        if key not in {"record_id", "revision", "is_latest", "quality"}
    }
    provenance = dict(payload["provenance"])
    provenance.pop("retrieved_at", None)
    payload["provenance"] = provenance
    return sha256(json_bytes(payload))


def _refresh_id(record: dict[str, Any]) -> None:
    record["record_id"] = _record_id(record)


def merge_vendor_revisions(
    existing: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    merged = [dict(item) for item in existing]
    by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for record in merged:
        key = (
            str(record["trade_date"]),
            str(record["commodity"]),
            str(record["vendor_main_code"]),
        )
        by_key.setdefault(key, []).append(record)
    for candidate_value in candidates:
        candidate = dict(candidate_value)
        key = (
            str(candidate["trade_date"]),
            str(candidate["commodity"]),
            str(candidate["vendor_main_code"]),
        )
        history = by_key.setdefault(key, [])
        latest_items = [item for item in history if item.get("is_latest")]
        if len(latest_items) > 1:
            raise AdapterError(f"multiple latest vendor records for {key}")
        latest = latest_items[0] if latest_items else None
        if latest is not None and _signature(latest) == _signature(candidate):
            continue
        if latest is not None:
            latest["is_latest"] = False
            _refresh_id(latest)
        candidate["revision"] = max(
            (int(item.get("revision", 0)) for item in history), default=0
        ) + 1
        candidate["is_latest"] = True
        _refresh_id(candidate)
        merged.append(candidate)
        history.append(candidate)
    return sorted(
        merged,
        key=lambda item: (item["trade_date"], int(item["revision"])),
    )