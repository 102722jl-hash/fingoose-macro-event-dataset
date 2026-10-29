import csv
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from fingoose_macro_event_company_vendor_enhancement_v1 import (
    PRIORITY_SYMBOLS,
    _build_computed_window,
    build_vendor_enhancement,
    normalize_numeric_text,
    require_futures_calendar_scope,
)


ROOT = Path(__file__).resolve().parents[1]


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def fixture_inputs(root: Path) -> dict[str, Path]:
    calendar = root / "calendar.csv"
    dates = []
    current = date(2021, 10, 1)
    while current <= date(2023, 6, 30):
        if current.weekday() < 5:
            dates.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    write_csv(
        calendar,
        ["OBJECT_ID", "TRADE_DAYS", "S_INFO_EXCHMARKET", "OPDATE", "OPMODE"],
        [
            {"OBJECT_ID": str(index), "TRADE_DAYS": day, "S_INFO_EXCHMARKET": "DCE", "OPDATE": "", "OPMODE": "0"}
            for index, day in enumerate(dates)
        ],
    )

    metadata = root / "description.csv"
    write_csv(
        metadata,
        [
            "OBJECT_ID", "S_INFO_WINDCODE", "S_INFO_CODE", "S_INFO_NAME",
            "S_INFO_ENAME", "FS_INFO_SCCODE", "FS_INFO_TYPE", "FS_INFO_CCTYPE",
            "S_INFO_EXCHMARKET", "S_INFO_LISTDATE", "S_INFO_DELISTDATE",
            "FS_INFO_DLMONTH", "FS_INFO_LPRICE", "FS_INFO_LTDLDATE",
            "S_INFO_FULLNAME", "S_INFO_VOUCHERDATE", "S_INFO_PAYMENTDATE",
            "OPDATE", "OPMODE", "SEC_ID", "FS_INFO_TYPE1", "S_INFO_TRADE",
        ],
        [
            {
                "OBJECT_ID": symbol, "S_INFO_WINDCODE": f"{symbol}2205.DCE",
                "S_INFO_CODE": f"{symbol}2205", "S_INFO_NAME": symbol,
                "S_INFO_ENAME": symbol, "FS_INFO_SCCODE": symbol, "FS_INFO_TYPE": "1",
                "FS_INFO_CCTYPE": "", "S_INFO_EXCHMARKET": "DCE",
                "S_INFO_LISTDATE": "20210501", "S_INFO_DELISTDATE": "20220520",
                "FS_INFO_DLMONTH": "202205", "FS_INFO_LPRICE": "", "FS_INFO_LTDLDATE": "20220520",
                "S_INFO_FULLNAME": symbol, "S_INFO_VOUCHERDATE": "", "S_INFO_PAYMENTDATE": "",
                "OPDATE": "", "OPMODE": "0", "SEC_ID": symbol, "FS_INFO_TYPE1": "2", "S_INFO_TRADE": "0",
            }
            for symbol in PRIORITY_SYMBOLS
        ],
    )

    eod = root / "eod.csv"
    write_csv(
        eod,
        [
            "OBJECT_ID", "S_INFO_WINDCODE", "TRADE_DT", "S_DQ_PRESETTLE",
            "S_DQ_OPEN", "S_DQ_HIGH", "S_DQ_LOW", "S_DQ_CLOSE", "S_DQ_SETTLE",
            "S_DQ_VOLUME", "S_DQ_AMOUNT", "S_DQ_OI", "S_DQ_CHANGE",
            "S_DQ_OICHANGE", "FS_INFO_TYPE", "OPDATE", "OPMODE",
        ],
        [{
            "OBJECT_ID": "1", "S_INFO_WINDCODE": "I2608.DCE", "TRADE_DT": "20260709",
            "S_DQ_PRESETTLE": "790", "S_DQ_OPEN": "792", "S_DQ_HIGH": "800",
            "S_DQ_LOW": "785", "S_DQ_CLOSE": "798", "S_DQ_SETTLE": "796",
            "S_DQ_VOLUME": "1000", "S_DQ_AMOUNT": "100", "S_DQ_OI": "2000",
            "S_DQ_CHANGE": "8", "S_DQ_OICHANGE": "10", "FS_INFO_TYPE": "2",
            "OPDATE": "", "OPMODE": "0",
        }],
    )

    registry = root / "registry.jsonl"
    companies = {
        "event-02": [("601857.SH", "中国石油"), ("601233.SH", "桐昆股份"), ("600346.SH", "恒力石化")],
        "event-06": [("601857.SH", "中国石油"), ("600028.SH", "中国石化"), ("000301.SZ", "东方盛虹")],
    }
    write_jsonl(
        registry,
        [
            {"event_id": event_id, "company_code": code, "company_name": name}
            for event_id, values in companies.items()
            for code, name in values
        ],
    )
    numeric = root / "answer_evaluation.distill.jsonl"
    write_jsonl(
        numeric,
        [
            {"id": "a", "messages": [{"role": "assistant", "content": "6,823"}], "metadata": {"expected_answer": "6823.0"}},
            {"id": "b", "messages": [{"role": "assistant", "content": "(154)"}], "metadata": {"expected_answer": "-154"}},
            {"id": "c", "messages": [{"role": "assistant", "content": "12.5%"}], "metadata": {"expected_answer": "12.5"}},
        ],
    )
    docs = {}
    for name in ("calendar", "description", "eod"):
        path = root / f"{name}.pdf"
        path.write_bytes(b"%PDF-1.4\nfixture\n%%EOF\n")
        docs[name] = path
    return {
        "calendar_path": calendar,
        "metadata_path": metadata,
        "eod_path": eod,
        "calendar_dictionary_path": docs["calendar"],
        "metadata_dictionary_path": docs["description"],
        "eod_dictionary_path": docs["eod"],
        "candidate_registry_path": registry,
        "numeric_evaluation_path": numeric,
    }


class VendorEnhancementTests(unittest.TestCase):
    def test_builds_isolated_pending_archive_bundle(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            root = Path(temp)
            kwargs = fixture_inputs(root)
            protected = [root / "protected-a", root / "protected-b"]
            for path in protected:
                path.mkdir()
                (path / "marker.txt").write_text("unchanged", encoding="utf-8")

            summary = build_vendor_enhancement(
                output_root=root / "output",
                protected_roots=protected,
                **kwargs,
            )

            self.assertEqual(summary["release_tier"], "CANDIDATE")
            self.assertTrue(summary["candidate_ready"])
            self.assertFalse(summary["formal_ready"])
            self.assertEqual(summary["event_count"], 2)
            self.assertEqual(summary["priority_symbol_count"], 8)
            self.assertEqual(summary["window_request_count"], 16)
            self.assertEqual(summary["computed_window_count"], 0)
            self.assertEqual(summary["pending_archive_count"], 16)
            self.assertEqual(summary["company_enhancement_candidate_count"], 6)
            self.assertEqual(summary["numeric_evaluation_record_count"], 3)
            self.assertEqual(summary["base_company_dossier_count"], 30)
            self.assertEqual(summary["base_candidate_sample_count"], 60)
            self.assertEqual(summary["enhancement_company_sample_count"], 0)
            self.assertTrue(summary["protected_outputs_unchanged"])
            self.assertEqual((protected[0] / "marker.txt").read_text(encoding="utf-8"), "unchanged")

            requests = read_jsonl(root / "output" / "event_futures_window_requests.jsonl")
            self.assertTrue(all(item["status"] == "PENDING_ARCHIVE" for item in requests))
            self.assertTrue(all(item["actual_values"] == {} for item in requests))
            self.assertTrue(all(item["formal_source_status"] == "OFFICIAL_CROSSCHECK_REQUIRED" for item in requests))
            self.assertEqual((root / "output" / "event_futures_windows.jsonl").read_text(encoding="utf-8"), "")

            sources = read_jsonl(root / "output" / "vendor_source_manifest.jsonl")
            vendor_sources = [item for item in sources if item["source_class"] == "LICENSED_VENDOR_DATA"]
            self.assertEqual(len(vendor_sources), 6)
            for source in vendor_sources:
                self.assertEqual(source["verification_status"], "VENDOR_VERIFIED")
                self.assertEqual(source["formal_source_status"], "OFFICIAL_CROSSCHECK_REQUIRED")
                self.assertRegex(source["content_sha256"], r"^[0-9a-f]{64}$")

            calendar_profile = json.loads((root / "output" / "futures_calendar_profile.json").read_text(encoding="utf-8"))
            self.assertEqual(calendar_profile["allowed_exchange"], "DCE")
            self.assertEqual(calendar_profile["forbidden_as_equity_calendar"], ["SSE", "SZSE"])

            report = json.loads((root / "output" / "validation_report.json").read_text(encoding="utf-8"))
            self.assertTrue(report["passed"])
            self.assertTrue(report["checks"]["numeric_dataset_isolated"])
            self.assertTrue(report["checks"]["historical_values_not_fabricated"])

    def test_computed_window_compounds_daily_returns_across_contract_changes(self):
        days = [f"2022-01-{index + 1:02d}" for index in range(81)]
        spec = {
            "required_sessions": days,
            "baseline_session": days[59],
            "d1_session": days[60],
            "d3_session": days[62],
            "d5_session": days[64],
            "d20_session": days[79],
        }
        daily = {
            day: {
                "contract_code": "EG2205.DCE" if index < 65 else "EG2209.DCE",
                "daily_return": (0.01 if index % 2 == 0 else -0.01) if index < 60 else 0.01,
                "source_line": index + 2,
                "candidate_contract_count": 2,
            }
            for index, day in enumerate(days)
        }
        request = {"request_id": "window", "event_id": "event-02", "series_id": "EG.DCE"}
        result = _build_computed_window(request, spec, daily, "a" * 64)
        self.assertIsNotNone(result)
        self.assertEqual(result["window_changes_pct"]["D1"], 1.0)
        self.assertEqual(result["window_changes_pct"]["D3"], 3.0301)
        self.assertEqual(result["window_changes_pct"]["D5"], 5.10100501)
        self.assertEqual(len(result["calculation_trace"]), 81)
        self.assertEqual(result["calculation_trace"][65]["selected_contract"], "EG2209.DCE")
    def test_calendar_scope_rejects_equity_market_use(self):
        self.assertEqual(require_futures_calendar_scope("DCE"), "DCE")
        with self.assertRaisesRegex(ValueError, "cannot be used"):
            require_futures_calendar_scope("SSE")
        with self.assertRaisesRegex(ValueError, "cannot be used"):
            require_futures_calendar_scope("SZSE")

    def test_numeric_normalizer_handles_units_negatives_and_percent(self):
        self.assertEqual(normalize_numeric_text("6,823"), [6823.0])
        self.assertEqual(normalize_numeric_text("(154)"), [-154.0])
        self.assertEqual(normalize_numeric_text("12.5%"), [12.5])
        self.assertEqual(normalize_numeric_text("1.25 million"), [1250000.0])


if __name__ == "__main__":
    unittest.main()
