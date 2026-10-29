import csv
import io
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker
from openpyxl import Workbook

from fingoose_commodity_market import (
    MarketDataError,
    TradingCalendar,
    build_continuous_series,
    build_contract_daily_record,
)
from fingoose_commodity_sources import (
    AdapterError,
    SnapshotStore,
    detect_table_format,
    detected_table_content_type,
    merge_contract_revisions,
    merge_source_manifest_revisions,
    parse_dce_table,
    parse_shfe_like,
    parse_trade_data_js,
    read_table_bytes,
)


PROVENANCE = {
    "source_id": "fixture_bundle",
    "source_url": "https://example.invalid/source",
    "provider": "Fixture Provider",
    "retrieved_at": "2026-07-23T09:00:00+08:00",
    "snapshot_id": "FIXTURE-001",
    "content_sha256": "1" * 64,
    "adapter_version": "fixture-adapter-v0.1",
    "license_scope": "unknown",
    "display_allowed": False,
    "redistribution_allowed": False,
}

SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "fingoose_commodity_market_v0.2.schema.json"
)
VALIDATOR = Draft202012Validator(
    json.loads(SCHEMA_PATH.read_text(encoding="utf-8")),
    format_checker=FormatChecker(),
)


def official_daily(prefix="cu", exchange="SHFE"):
    return {
        "o_curinstrument": [
            {
                "PRODUCTGROUPID": prefix,
                "PRODUCTCLASS": "1",
                "PRODUCTID": f"{prefix}_f",
                "PRODUCTNAME": "原油" if prefix == "sc" else "铜",
                "DELIVERYMONTH": "2608",
                "OPENPRICE": 100,
                "HIGHESTPRICE": 105,
                "LOWESTPRICE": 98,
                "CLOSEPRICE": 103,
                "SETTLEMENTPRICE": 102,
                "PRESETTLEMENTPRICE": 99,
                "VOLUME": 1000,
                "OPENINTEREST": 2000,
            },
            {
                "PRODUCTGROUPID": prefix,
                "PRODUCTCLASS": "1",
                "PRODUCTID": f"{prefix}_f",
                "PRODUCTNAME": "原油" if prefix == "sc" else "铜",
                "DELIVERYMONTH": "2609",
                "OPENPRICE": 101,
                "HIGHESTPRICE": 106,
                "LOWESTPRICE": 99,
                "CLOSEPRICE": 104,
                "SETTLEMENTPRICE": 103,
                "PRESETTLEMENTPRICE": 100,
                "VOLUME": 1200,
                "OPENINTEREST": 2200,
            },
            {
                "PRODUCTGROUPID": prefix,
                "PRODUCTCLASS": "1",
                "PRODUCTID": f"{prefix}_f",
                "PRODUCTNAME": "总计",
                "DELIVERYMONTH": "小计",
                "OPENPRICE": "",
            },
            {
                "PRODUCTGROUPID": prefix,
                "PRODUCTCLASS": "1",
                "PRODUCTID": f"{prefix}_tas",
                "PRODUCTNAME": "TAS",
                "DELIVERYMONTH": "2610",
                "OPENPRICE": 100,
            },
        ]
    }


def official_metadata(prefix="cu", raw_exchange="SHFE"):
    return {
        "ContractBaseInfo": [
            {
                "INSTRUMENTID": f"{prefix}2608",
                "TRADINGDAY": "20260722",
                "EXCHANGEID": raw_exchange,
                "EXPIREDATE": "20260817",
            },
            {
                "INSTRUMENTID": f"{prefix}2609",
                "TRADINGDAY": "20260722",
                "EXCHANGEID": raw_exchange,
                "EXPIREDATE": "20260915",
            },
        ]
    }


def normalized_row(day="2026-07-22", code="cu2608", last="2026-08-17"):
    suffix = code[-4:]
    return {
        "commodity_code": "CU",
        "exchange": "SHFE",
        "trade_date": day,
        "contract_code": code,
        "contract_month": f"20{suffix[:2]}-{suffix[2:]}",
        "last_trade_date": last,
        "open": 100.0,
        "high": 105.0,
        "low": 98.0,
        "close": 103.0,
        "settlement": 102.0,
        "pre_settlement": 99.0,
        "volume": 1000,
        "open_interest": 2000,
        "is_trading": True,
    }


def dce_rows():
    return [
        {
            "商品名称": "铁矿石",
            "交割月份": "2608",
            "开盘价": 800,
            "最高价": 820,
            "最低价": 790,
            "收盘价": 810,
            "前结算价": 798,
            "结算价": 805,
            "成交量": 10000,
            "持仓量": 20000,
        },
        {
            "商品名称": "铁矿石",
            "交割月份": "i2609",
            "开盘价": 805,
            "最高价": 825,
            "最低价": 795,
            "收盘价": 815,
            "前结算价": 803,
            "结算价": 810,
            "成交量": 12000,
            "持仓量": 22000,
        },
    ]


def dce_csv_bytes(encoding="utf-8-sig"):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(dce_rows()[0]))
    writer.writeheader()
    writer.writerows(dce_rows())
    return output.getvalue().encode(encoding)


DCE_METADATA = {
    "i2608": {"last_trade_date": "2026-08-14"},
    "i2609": {"last_trade_date": "2026-09-14"},
}


class CommoditySourceTests(unittest.TestCase):
    def test_snapshot_store_streams_file_without_reading_it_whole(self):
        with tempfile.TemporaryDirectory(
            dir=Path(__file__).resolve().parents[1]
        ) as temp:
            root = Path(temp)
            source = root / "large.csv"
            source.write_bytes(b"header\n" + b"x" * 8192)
            store = SnapshotStore(root / "snapshots")

            with patch.object(Path, "read_bytes", side_effect=AssertionError("whole-file read")):
                first = store.store_file(
                    source_id="wind_eod",
                    provider="Wind",
                    source_url="https://www.wind.com.cn/",
                    requested_date="2026-07-23",
                    source_path=source,
                    content_type="text/csv",
                    http_status=None,
                    retrieved_at="2026-07-23T16:21:09+08:00",
                    adapter_version="fingoose-wind-iron-ore-v0.1",
                    chunk_size=1024,
                )
                second = store.store_file(
                    source_id="wind_eod",
                    provider="Wind",
                    source_url="https://www.wind.com.cn/",
                    requested_date="2026-07-23",
                    source_path=source,
                    content_type="text/csv",
                    http_status=None,
                    retrieved_at="2026-07-23T16:21:09+08:00",
                    adapter_version="fingoose-wind-iron-ore-v0.1",
                    chunk_size=1024,
                )

            self.assertEqual(first["content_sha256"], second["content_sha256"])
            self.assertEqual(first["local_path"], second["local_path"])
            self.assertEqual(first["byte_count"], source.stat().st_size)
            self.assertEqual(
                len([item for item in (root / "snapshots").rglob("*") if item.is_file()]),
                1,
            )

    def test_shfe_mapping_filters_aggregate_and_tas(self):
        result = parse_shfe_like(
            official_daily(),
            official_metadata(),
            exchange="SHFE",
            commodity_code="CU",
            trade_date="2026-07-22",
        )
        self.assertEqual([item.row["contract_code"] for item in result.records], [
            "cu2608",
            "cu2609",
        ])
        self.assertEqual(len(result.rejected), 2)
        self.assertEqual(result.records[0].row["settlement"], 102.0)
        self.assertEqual(result.records[0].row["open_interest"], 2000)

    def test_ine_source_overrides_raw_shfe_exchange(self):
        result = parse_shfe_like(
            official_daily(prefix="sc"),
            official_metadata(prefix="sc", raw_exchange="SHFE"),
            exchange="INE",
            commodity_code="SC",
            trade_date="2026-07-22",
        )
        self.assertEqual(result.records[0].row["exchange"], "INE")
        self.assertIn(
            "SOURCE_EXCHANGE_ID_MISMATCH",
            result.records[0].quality_flags,
        )

    def test_missing_contract_metadata_is_rejected(self):
        payload = official_metadata()
        payload["ContractBaseInfo"].pop()
        with self.assertRaisesRegex(AdapterError, "missing ContractBaseInfo"):
            parse_shfe_like(
                official_daily(),
                payload,
                exchange="SHFE",
                commodity_code="CU",
                trade_date="2026-07-22",
            )

    def test_empty_price_row_is_rejected_without_fill(self):
        daily = official_daily()
        daily["o_curinstrument"][0]["SETTLEMENTPRICE"] = ""
        result = parse_shfe_like(
            daily,
            official_metadata(),
            exchange="SHFE",
            commodity_code="CU",
            trade_date="2026-07-22",
        )
        self.assertEqual(len(result.records), 1)
        self.assertIn("missing SETTLEMENTPRICE", result.rejected[0]["reason"])

    def test_missing_pre_settlement_is_rejected_without_fill(self):
        daily = official_daily()
        daily["o_curinstrument"][0]["PRESETTLEMENTPRICE"] = ""
        result = parse_shfe_like(
            daily,
            official_metadata(),
            exchange="SHFE",
            commodity_code="CU",
            trade_date="2026-07-22",
        )
        self.assertEqual(len(result.records), 1)
        self.assertIn("missing PRESETTLEMENTPRICE", result.rejected[0]["reason"])

    def test_declared_wrong_unit_is_rejected(self):
        row = {**normalized_row(), "quote_unit": "CNY_PER_BARREL"}
        with self.assertRaisesRegex(MarketDataError, "must use CNY_PER_TONNE"):
            build_contract_daily_record(row, provenance=PROVENANCE)

    def test_trade_data_js_supports_closed_and_trading_date_lists(self):
        closed = parse_trade_data_js(
            b'var dates={"2026":"20260101,20260216"};',
            exchange="SHFE",
            year=2026,
            coverage_end="2026-01-09",
        )
        self.assertNotIn(date(2026, 1, 1), closed.trading_dates)
        self.assertIn(date(2026, 1, 2), closed.trading_dates)
        self.assertNotIn(date(2026, 1, 3), closed.trading_dates)
        trading = parse_trade_data_js(
            b"var dates={2026:['20260101','20260102','20260105','20260106',"
            b"'20260107','20260108','20260109']};",
            exchange="SHFE",
            year=2026,
            coverage_end="2026-12-31",
        )
        self.assertEqual(trading.coverage_end, date(2026, 1, 9))
        self.assertEqual(len(trading.trading_dates), 7)
    def test_dce_mapping_requires_metadata(self):
        with self.assertRaisesRegex(AdapterError, "missing DCE metadata"):
            parse_dce_table(
                dce_rows(),
                trade_date="2026-07-22",
                metadata={"i2608": DCE_METADATA["i2608"]},
            )

    def test_dce_csv_utf8_and_gb18030(self):
        for encoding in ("utf-8-sig", "gb18030"):
            with self.subTest(encoding=encoding):
                parsed = read_table_bytes(
                    dce_csv_bytes(encoding), f"quotes_{encoding}.csv"
                )
                result = parse_dce_table(
                    parsed,
                    trade_date="2026-07-22",
                    metadata=DCE_METADATA,
                )
                self.assertEqual(len(result.records), 2)

    def test_xlsx_is_detected_by_signature_with_wrong_extension(self):
        buffer = io.BytesIO()
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(list(dce_rows()[0]))
        for row in dce_rows():
            sheet.append(list(row.values()))
        workbook.save(buffer)
        content = buffer.getvalue()
        self.assertEqual(detect_table_format(content), "xlsx")
        self.assertEqual(
            detected_table_content_type(content),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        parsed = read_table_bytes(content, "quotes.csv")
        self.assertEqual(len(parsed), 2)

    def test_html_disguised_as_xls_is_supported(self):
        headers = "".join(f"<th>{name}</th>" for name in dce_rows()[0])
        body = "".join(
            "<tr>" + "".join(f"<td>{value}</td>" for value in row.values()) + "</tr>"
            for row in dce_rows()
        )
        content = f"<html><table><tr>{headers}</tr>{body}</table></html>".encode("utf-8")
        self.assertEqual(detect_table_format(content), "html")
        parsed = read_table_bytes(content, "quotes.xls")
        self.assertEqual(len(parsed), 2)

    def test_legacy_xls_signature_selects_xlrd(self):
        content = bytes.fromhex("D0CF11E0A1B11AE1") + b"fixture"
        table = [list(dce_rows()[0])] + [list(row.values()) for row in dce_rows()]

        class FakeSheet:
            nrows = len(table)

            @staticmethod
            def row_values(index):
                return table[index]

        class FakeBook:
            @staticmethod
            def sheet_by_index(index):
                self.assertEqual(index, 0)
                return FakeSheet()

        with patch(
            "fingoose_commodity_sources.xlrd.open_workbook",
            return_value=FakeBook(),
        ) as reader:
            actual = read_table_bytes(content, "quotes.xlsx")
        self.assertEqual(actual, dce_rows())
        self.assertEqual(reader.call_args.kwargs["file_contents"], content)

    def test_snapshot_store_is_content_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            store = SnapshotStore(Path(temp))
            arguments = {
                "source_id": "fixture",
                "provider": "Fixture",
                "source_url": "https://example.invalid/a",
                "requested_date": "2026-07-22",
                "content": b"same bytes",
                "original_name": "sample.dat",
                "content_type": "application/json",
                "http_status": 200,
                "retrieved_at": "2026-07-23T09:00:00+08:00",
            }
            first = store.store(**arguments)
            second = store.store(**arguments)
            self.assertEqual(first["snapshot_id"], second["snapshot_id"])
            files = [item for item in Path(temp).rglob("*") if item.is_file()]
            self.assertEqual(len(files), 1)

    def test_snapshot_store_accepts_source_specific_adapter_version(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = SnapshotStore(Path(temp)).store(
                source_id="eastmoney_i_main_close",
                provider="Eastmoney",
                source_url="https://push2his.eastmoney.com/example",
                requested_date="2026-07-22",
                content=b'{"data":{}}',
                original_name="i_20260709_20260722.json",
                content_type="application/json",
                http_status=200,
                retrieved_at="2026-07-23T09:00:00+08:00",
                adapter_version="fingoose-eastmoney-main-close-v0.1",
            )
        self.assertEqual(
            manifest["adapter_version"],
            "fingoose-eastmoney-main-close-v0.1",
        )
    def test_source_manifest_revision_is_idempotent_then_increments(self):
        first = {
            "source_id": "fixture",
            "source_url": "https://example.invalid/source",
            "requested_date": "2026-07-22",
            "content_sha256": "1" * 64,
            "adapter_version": "fixture-v1",
            "revision": 1,
            "is_latest": True,
        }
        merged = merge_source_manifest_revisions([], [first])
        same = merge_source_manifest_revisions(merged, [first])
        self.assertEqual(len(same), 1)
        changed = {**first, "content_sha256": "2" * 64}
        revised = merge_source_manifest_revisions(same, [changed])
        self.assertEqual(len(revised), 2)
        self.assertFalse(revised[0]["is_latest"])
        self.assertEqual(revised[1]["revision"], 2)
        self.assertTrue(revised[1]["is_latest"])
    def test_revision_merge_is_idempotent_then_increments(self):
        first = build_contract_daily_record(
            normalized_row(), provenance=PROVENANCE
        )
        merged = merge_contract_revisions([], [first])
        same = merge_contract_revisions(merged, [first])
        self.assertEqual(len(same), 1)
        changed_provenance = {**PROVENANCE, "content_sha256": "2" * 64}
        changed = build_contract_daily_record(
            normalized_row(), provenance=changed_provenance
        )
        revised = merge_contract_revisions(same, [changed])
        self.assertEqual(len(revised), 2)
        self.assertFalse(revised[0]["is_latest"])
        self.assertEqual(revised[1]["revision"], 2)
        self.assertTrue(revised[1]["is_latest"])

    def test_contract_daily_record_passes_schema(self):
        record = build_contract_daily_record(
            normalized_row(), provenance=PROVENANCE
        )
        VALIDATOR.validate(record)
        self.assertEqual(record["quality"]["status"], "review_required")
        invalid = {**record, "pre_settlement": None}
        self.assertTrue(list(VALIDATOR.iter_errors(invalid)))

    def test_calendar_quality_states(self):
        start = date(2026, 1, 5)
        days = [start + timedelta(days=offset) for offset in range(4)]
        rows = []
        for day in days:
            rows.extend(
                [
                    normalized_row(
                        day.isoformat(), "cu2608", "2026-01-12"
                    ),
                    {
                        **normalized_row(
                            day.isoformat(), "cu2609", "2026-04-30"
                        ),
                        "open_interest": 1000,
                    },
                ]
            )
        full_dates = [
            start + timedelta(days=offset)
            for offset in range((date(2026, 4, 30) - start).days + 1)
            if (start + timedelta(days=offset)).weekday() < 5
        ]
        verified = TradingCalendar.from_values(
            "SHFE",
            full_dates,
            coverage_start=start,
            coverage_end=date(2026, 4, 30),
            verified=True,
        )
        continuous, _ = build_continuous_series(
            rows, provenance=PROVENANCE, trading_calendar=verified
        )
        self.assertNotIn(
            "OFFICIAL_TRADING_CALENDAR_MISSING",
            continuous[0]["quality"]["flags"],
        )
        self.assertNotIn(
            "TRADING_CALENDAR_INCOMPLETE",
            continuous[0]["quality"]["flags"],
        )

        partial = TradingCalendar.from_values(
            "SHFE",
            days,
            coverage_start=days[0],
            coverage_end=days[-1],
            verified=False,
        )
        partial_continuous, _ = build_continuous_series(
            rows, provenance=PROVENANCE, trading_calendar=partial
        )
        self.assertIn(
            "TRADING_CALENDAR_UNVERIFIED",
            partial_continuous[0]["quality"]["flags"],
        )
        self.assertIn(
            "TRADING_CALENDAR_INCOMPLETE",
            partial_continuous[0]["quality"]["flags"],
        )


if __name__ == "__main__":
    unittest.main()
