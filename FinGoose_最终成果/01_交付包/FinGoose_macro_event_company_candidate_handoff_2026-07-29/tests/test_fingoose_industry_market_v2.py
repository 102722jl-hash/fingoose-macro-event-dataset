from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


def _sessions() -> list[str]:
    current = date(2020, 2, 13)
    end = date(2020, 6, 12)
    rows = []
    while current <= end:
        if current.weekday() < 5 and current != date(2020, 4, 6):
            rows.append(current.isoformat())
        current += timedelta(days=1)
    return rows


def test_industry_window_uses_common_sessions_and_reproducible_formulas() -> None:
    from fingoose_industry_market_v2 import build_industry_market_window

    sessions = _sessions()
    industry_rows = [
        {"date": session, "close": 100.0 + index}
        for index, session in enumerate(sessions)
    ]
    market_rows = [
        {"date": session, "close": 200.0 + index * 0.5}
        for index, session in enumerate(sessions)
    ]
    window = build_industry_market_window(
        mapping_id="event-industry-event-01-801170",
        event_at="2020-03-11T16:30:00+00:00",
        industry_rows=industry_rows,
        market_rows=market_rows,
        driver_observations=[
            {"period": "2020-03", "value": -52.9, "unit": "%同比"}
        ],
    )
    self_t_minus_1 = window["fixed_windows"]["T_MINUS_1"]
    assert window["t0_alignment"]["T0"] == "2020-03-12"
    assert self_t_minus_1["actual_date"] == "2020-03-11"
    assert window["fixed_windows"]["D3"]["actual_date"] == "2020-03-17"
    assert window["fixed_windows"]["D20"]["actual_date"] == "2020-04-10"
    assert window["fixed_windows"]["M3"]["actual_date"] == "2020-06-12"
    assert window["continuous_window"][0]["actual_date"] == "2020-02-13"

    industry_t_minus_1 = self_t_minus_1["industry_value"]
    first = window["continuous_window"][0]
    assert first["industry_normalized"] == 100 * industry_rows[0]["close"] / industry_t_minus_1

    d1 = window["fixed_windows"]["D1"]
    expected = (
        d1["industry_value"] / industry_t_minus_1 - 1
    ) - (
        d1["market_value"] / self_t_minus_1["market_value"] - 1
    )
    assert abs(d1["market_relative_return"] - expected) < 1e-12
    assert window["window_status"] == "AVAILABLE"


def test_industry_window_keeps_missing_data_pending_instead_of_zero() -> None:
    from fingoose_industry_market_v2 import build_industry_market_window

    result = build_industry_market_window(
        mapping_id="event-industry-event-01-801170",
        event_at="2020-03-11T16:30:00+00:00",
        industry_rows=[],
        market_rows=[],
        driver_observations=[],
    )
    assert result["window_status"] == "DATA_PENDING"
    assert result["fixed_windows"] == {}
    assert result["continuous_window"] == []
    assert result["pending_reason"] == "NO_COMMON_TRADING_SESSIONS"

def test_market_provider_call_retries_transient_failures() -> None:
    from fingoose_industry_market_v2 import call_with_retries

    attempts = []

    def transient_operation():
        attempts.append(len(attempts) + 1)
        if len(attempts) < 3:
            raise RuntimeError("transient content decoding failure")
        return "available"

    assert call_with_retries(transient_operation, attempts=3) == "available"
    assert attempts == [1, 2, 3]

def test_sw_provider_disables_brotli_without_mutating_requests_module() -> None:
    from types import SimpleNamespace

    from fingoose_industry_market_v2 import fetch_sw_history

    seen_headers = []
    def original_get(*args, **kwargs):
        seen_headers.append(dict(kwargs.get("headers") or {}))
        return "response"
    requests_module = SimpleNamespace(get=original_get)

    class AkModule:
        @staticmethod
        def index_hist_sw(*, symbol, period):
            requests_module.get(
                "https://example.invalid/sw",
                headers={"User-Agent": "provider-agent"},
            )
            return {"symbol": symbol, "period": period}

    result = fetch_sw_history(
        AkModule(),
        "801150",
        requests_module=requests_module,
    )

    assert result == {"symbol": "801150", "period": "day"}
    assert requests_module.get is original_get
    assert seen_headers == [{"User-Agent": "provider-agent", "Accept-Encoding": "gzip, deflate"}]
