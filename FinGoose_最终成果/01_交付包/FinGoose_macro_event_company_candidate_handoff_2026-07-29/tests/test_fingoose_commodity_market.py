import json
import math
import unittest
from datetime import date, timedelta
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from fingoose_commodity_market import (
    MarketDataError,
    build_continuous_series,
    validate_three_month_forecast,
)


MOCK_PROVENANCE = {
    "source_id": "isolated_mock_fixture",
    "source_url": "https://example.invalid/fingoose-commodity-mock",
    "provider": "FinGoose isolated test",
    "retrieved_at": "2026-07-22T12:00:00+08:00",
    "snapshot_id": "MOCK-COMMODITY-20260722-001",
    "content_sha256": "0" * 64,
    "adapter_version": "isolated-mock-v0.1",
    "license_scope": "unknown",
    "display_allowed": False,
    "redistribution_allowed": False,
}
_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "fingoose_commodity_market_v0.2.schema.json"
)
_SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
_SCHEMA_VALIDATOR = Draft202012Validator(
    _SCHEMA,
    format_checker=FormatChecker(),
)


def business_days(start, count):
    result = []
    current = start
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current)
        current += timedelta(days=1)
    return result


def contract_row(
    day,
    code,
    open_interest,
    *,
    last_trade="2026-12-31",
    price=100.0,
    close=None,
    settlement=None,
):
    prefix = code[:-4]
    month = code[-4:]
    close = price if close is None else close
    settlement = price if settlement is None else settlement
    high = max(price, close, settlement) + 1
    low = min(price, close, settlement) - 1
    return {
        "commodity_code": "CU",
        "exchange": "SHFE",
        "trade_date": day.isoformat(),
        "contract_code": code,
        "contract_month": f"20{month[:2]}-{month[2:]}",
        "last_trade_date": last_trade,
        "open": price,
        "high": high,
        "low": low,
        "close": close,
        "settlement": settlement,
        "pre_settlement": settlement - 0.25,
        "volume": 100,
        "open_interest": open_interest,
        "is_trading": True,
    }


def forecast_series(days, as_of_index, *, settlement_future=1.003, close_future=1.003):
    settlement_index = 100.0
    close_index = 100.0
    result = []
    for offset, day in enumerate(days):
        if offset:
            if offset <= as_of_index:
                daily_factor = 1.001 if offset % 2 else 0.999
                settlement_index *= daily_factor
                close_index *= daily_factor
            else:
                settlement_index *= settlement_future
                close_index *= close_future
        result.append(
            {
                "trade_date": day.isoformat(),
                "settlement_index": settlement_index,
                "close_index": close_index,
            }
        )
    return result


class CommodityMarketTests(unittest.TestCase):
    def test_two_day_confirmation_and_next_day_effective_roll(self):
        days = business_days(date(2026, 1, 5), 4)
        rows = []
        oi = [(100, 90), (100, 110), (100, 120), (90, 130)]
        for day, (old_oi, new_oi) in zip(days, oi):
            rows.extend(
                [
                    contract_row(day, "cu2603", old_oi, price=100),
                    contract_row(
                        day,
                        "cu2604",
                        new_oi,
                        price=200 + (day - days[0]).days,
                    ),
                ]
            )

        continuous, events = build_continuous_series(rows, provenance=MOCK_PROVENANCE)

        rolls = [event for event in events if event["reason"] == "OI_CONFIRM"]
        self.assertEqual(len(rolls), 1)
        self.assertEqual(rolls[0]["signal_date"], days[2].isoformat())
        self.assertEqual(rolls[0]["effective_date"], days[3].isoformat())
        self.assertEqual(rolls[0]["old_open_interest"], 100)
        self.assertEqual(rolls[0]["new_open_interest"], 120)
        self.assertEqual(continuous[2]["active_contract"], "cu2603")
        self.assertEqual(continuous[3]["active_contract"], "cu2604")
        self.assertTrue(continuous[3]["is_roll_effective_date"])
        for record in [*continuous, *events]:
            _SCHEMA_VALIDATOR.validate(record)
            self.assertEqual(record["quality"]["status"], "review_required")
            self.assertIn(
                "OFFICIAL_TRADING_CALENDAR_MISSING",
                record["quality"]["flags"],
            )

    def test_missing_provenance_is_rejected(self):
        row = contract_row(date(2026, 1, 5), "cu2603", 100)
        incomplete = dict(MOCK_PROVENANCE)
        incomplete.pop("content_sha256")

        with self.assertRaisesRegex(MarketDataError, "missing required fields"):
            build_continuous_series([row], provenance=incomplete)

    def test_one_day_open_interest_advantage_does_not_roll(self):
        days = business_days(date(2026, 1, 5), 4)
        rows = []
        oi = [(100, 90), (100, 120), (100, 80), (100, 90)]
        for day, (old_oi, new_oi) in zip(days, oi):
            rows.extend(
                [
                    contract_row(day, "cu2603", old_oi),
                    contract_row(day, "cu2604", new_oi),
                ]
            )

        continuous, events = build_continuous_series(rows, provenance=MOCK_PROVENANCE)

        self.assertFalse(
            any(event["reason"] == "OI_CONFIRM" for event in events)
        )
        self.assertTrue(
            all(item["active_contract"] == "cu2603" for item in continuous)
        )

    def test_forced_expiry_roll_signals_before_effective_date(self):
        days = business_days(date(2026, 1, 5), 7)
        rows = []
        for day in days:
            if day <= date(2026, 1, 12):
                rows.append(
                    contract_row(
                        day,
                        "cu2603",
                        200,
                        last_trade="2026-01-12",
                    )
                )
            rows.append(
                contract_row(
                    day,
                    "cu2604",
                    100,
                    last_trade="2026-04-30",
                    price=110,
                )
            )

        continuous, events = build_continuous_series(rows, provenance=MOCK_PROVENANCE)

        forced = [event for event in events if event["reason"] == "FORCED_EXPIRY"]
        self.assertEqual(len(forced), 1)
        self.assertEqual(forced[0]["signal_date"], days[1].isoformat())
        self.assertEqual(forced[0]["effective_date"], days[2].isoformat())
        self.assertTrue(forced[0]["is_forced"])
        self.assertEqual(continuous[1]["active_contract"], "cu2603")
        self.assertEqual(continuous[2]["active_contract"], "cu2604")

    def test_backward_roll_is_never_allowed(self):
        days = business_days(date(2026, 1, 5), 5)
        rows = []
        oi = [(100, 90), (100, 120), (100, 130), (200, 90), (200, 80)]
        for day, (old_oi, new_oi) in zip(days, oi):
            rows.extend(
                [
                    contract_row(day, "cu2603", old_oi),
                    contract_row(day, "cu2604", new_oi),
                ]
            )

        continuous, events = build_continuous_series(rows, provenance=MOCK_PROVENANCE)

        self.assertEqual(continuous[-1]["active_contract"], "cu2604")
        self.assertEqual(
            len([event for event in events if event["reason"] == "OI_CONFIRM"]),
            1,
        )

    def test_missing_new_contract_on_effective_date_is_rejected(self):
        days = business_days(date(2026, 1, 5), 4)
        rows = []
        oi = [(100, 90), (100, 110), (100, 120), (100, 130)]
        for index, (day, (old_oi, new_oi)) in enumerate(zip(days, oi)):
            rows.append(contract_row(day, "cu2603", old_oi))
            if index != 3:
                rows.append(
                    contract_row(day, "cu2604", new_oi, price=110)
                )

        with self.assertRaisesRegex(MarketDataError, "effective date"):
            build_continuous_series(rows, provenance=MOCK_PROVENANCE)

    def test_invalid_commodity_exchange_is_rejected(self):
        row = contract_row(date(2026, 1, 5), "cu2603", 100)
        row["exchange"] = "DCE"

        with self.assertRaises(MarketDataError):
            build_continuous_series([row], provenance=MOCK_PROVENANCE)

    def test_roll_day_uses_new_contract_own_return(self):
        days = business_days(date(2026, 1, 5), 4)
        rows = []
        new_prices = [200.0, 202.0, 204.0, 206.0]
        oi = [(100, 90), (100, 110), (100, 120), (90, 130)]
        for day, new_price, (old_oi, new_oi) in zip(days, new_prices, oi):
            rows.extend(
                [
                    contract_row(day, "cu2603", old_oi, price=100),
                    contract_row(day, "cu2604", new_oi, price=new_price),
                ]
            )

        continuous, _ = build_continuous_series(rows, provenance=MOCK_PROVENANCE)

        expected_return = 206.0 / 204.0 - 1.0
        self.assertAlmostEqual(
            continuous[3]["settlement_return"], expected_return
        )
        self.assertAlmostEqual(
            continuous[3]["settlement_index"],
            continuous[2]["settlement_index"] * (1.0 + expected_return),
        )

    def test_three_month_forecast_uses_only_pre_cutoff_volatility(self):
        days = business_days(date(2025, 1, 1), 220)
        as_of_index = 80
        series = forecast_series(days, as_of_index)
        altered_future = forecast_series(
            days,
            as_of_index,
            settlement_future=1.01,
            close_future=1.01,
        )

        result = validate_three_month_forecast(
            series, days[as_of_index].isoformat()
        )
        altered_result = validate_three_month_forecast(
            altered_future, days[as_of_index].isoformat()
        )

        self.assertEqual(result["pre_cutoff_observations"], 60)
        self.assertEqual(result["outcome"], "UP")
        self.assertGreater(result["z"], 0.5)
        self.assertAlmostEqual(
            result["sigma_annual"], altered_result["sigma_annual"]
        )
        self.assertEqual(result["quality_status"], "accepted")

    def test_close_settlement_conflict_requires_review(self):
        days = business_days(date(2025, 1, 1), 220)
        as_of_index = 80
        series = forecast_series(
            days,
            as_of_index,
            settlement_future=1.003,
            close_future=0.997,
        )

        result = validate_three_month_forecast(
            series, days[as_of_index].isoformat()
        )

        self.assertEqual(result["settlement_basis"]["outcome"], "UP")
        self.assertEqual(result["close_basis"]["outcome"], "DOWN")
        self.assertTrue(result["basis_disagreement"])
        self.assertEqual(result["quality_status"], "review_required")
        self.assertIn(
            "CLOSE_SETTLEMENT_OUTCOME_CONFLICT",
            result["quality_flags"],
        )

    def test_three_month_window_preserves_month_end(self):
        days = business_days(date(2024, 10, 1), 180)
        as_of = date(2025, 1, 31)
        as_of_index = days.index(as_of)
        series = forecast_series(days, as_of_index)

        result = validate_three_month_forecast(series, as_of)

        self.assertEqual(result["target_date"], "2025-04-30")

    def test_forecast_rejects_history_shorter_than_sixty_returns(self):
        days = business_days(date(2025, 1, 1), 20)
        series = forecast_series(days, 10)

        with self.assertRaisesRegex(MarketDataError, "60 pre-cutoff"):
            validate_three_month_forecast(series, days[10])

    def test_forecast_rejects_missing_three_month_result(self):
        days = business_days(date(2025, 1, 1), 80)
        series = forecast_series(days, 70)

        with self.assertRaisesRegex(MarketDataError, "three-month result"):
            validate_three_month_forecast(series, days[70])


if __name__ == "__main__":
    unittest.main()
