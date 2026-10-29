import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fingoose_commodity_exchange_adapter import TARGET_DATES, build_snapshot
from fingoose_commodity_sources import download, parse_json_bytes
from tests.test_fingoose_commodity_sources import (
    dce_csv_bytes,
    official_daily,
    official_metadata,
)


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def official_payload(exchange, trade_date, *, metadata):
    prefixes = ("cu", "au") if exchange == "SHFE" else ("sc",)
    raw_exchange = "SHFE"
    if metadata:
        rows = []
        for prefix in prefixes:
            payload = official_metadata(prefix=prefix, raw_exchange=raw_exchange)
            for row in payload["ContractBaseInfo"]:
                row["TRADINGDAY"] = trade_date.replace("-", "")
            rows.extend(payload["ContractBaseInfo"])
        return {"ContractBaseInfo": rows}
    rows = []
    for prefix in prefixes:
        rows.extend(official_daily(prefix=prefix)["o_curinstrument"])
    return {"o_curinstrument": rows}


def fake_download(url, timeout=30):
    del timeout
    if url.endswith("trade-data.js"):
        return (
            b'var dates={"2026":"20260101,20260216,20261001"};',
            "application/javascript",
            200,
        )
    match = re.search(r"(20\d{6})\.dat$", url)
    if not match:
        raise AssertionError(f"unexpected fixture URL: {url}")
    compact = match.group(1)
    trade_date = f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"
    exchange = "INE" if "ine.cn" in url else "SHFE"
    payload = official_payload(
        exchange,
        trade_date,
        metadata="ContractBaseInfo" in url,
    )
    return json_bytes(payload), "application/json", 200


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_dce_inputs(root):
    daily = root / "dce" / "daily"
    daily.mkdir(parents=True)
    for trade_date in TARGET_DATES:
        compact = trade_date.replace("-", "")
        (daily / f"dce_{compact}.csv").write_bytes(dce_csv_bytes())
    metadata = root / "dce" / "contract_metadata.csv"
    metadata.write_text(
        "contract_code,last_trade_date,source_url,retrieved_at\n"
        "i2608,2026-08-14,https://www.dce.com.cn/contracts/i2608,2026-07-23T09:00:00+08:00\n"
        "i2609,2026-09-14,https://www.dce.com.cn/contracts/i2609,2026-07-23T09:00:00+08:00\n",
        encoding="utf-8",
    )
    return daily, metadata


class CommodityExchangeAdapterTests(unittest.TestCase):
    def run_bundle(self, root, *, with_dce):
        snapshot_dir = root / "snapshots"
        output_dir = root / "outputs"
        if with_dce:
            daily_dir, metadata = write_dce_inputs(root)
        else:
            daily_dir = root / "missing_dce" / "daily"
            metadata = root / "missing_dce" / "contract_metadata.csv"
        with patch(
            "fingoose_commodity_exchange_adapter.download",
            side_effect=fake_download,
        ):
            summary = build_snapshot(
                snapshot_dir=snapshot_dir,
                output_dir=output_dir,
                dce_daily_dir=daily_dir,
                dce_metadata=metadata,
            )
        return summary, output_dir, snapshot_dir

    def test_missing_dce_emits_three_commodity_blocked_bundle_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, output_dir, snapshot_dir = self.run_bundle(root, with_dce=False)
            self.assertEqual(first["status"], "blocked")
            self.assertEqual(first["complete_commodities"], ["CU", "AU", "SC"])
            self.assertEqual(first["continuous_record_count"], 30)
            self.assertGreaterEqual(first["roll_event_count"], 3)
            self.assertEqual(first["manifest_count"], 42)
            self.assertFalse(first["forecast_labels_generated"])
            self.assertEqual(first["p0_status"], "blocked")
            contracts = read_jsonl(output_dir / "commodity_contract_daily.jsonl")
            self.assertEqual(len(contracts), 60)
            self.assertTrue(all(item["pre_settlement"] is not None for item in contracts))
            self.assertTrue(
                all(item["quality"]["status"] == "review_required" for item in contracts)
            )
            raw_files_before = len([item for item in snapshot_dir.rglob("*") if item.is_file()])
            second, _, _ = self.run_bundle(root, with_dce=False)
            raw_files_after = len([item for item in snapshot_dir.rglob("*") if item.is_file()])
            self.assertEqual(second["manifest_history_count"], first["manifest_history_count"])
            self.assertEqual(second["all_revision_record_count"], first["all_revision_record_count"])
            self.assertEqual(raw_files_after, raw_files_before)

    def test_complete_dce_bundle_meets_research_candidate_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            summary, output_dir, _ = self.run_bundle(Path(temp), with_dce=True)
            self.assertEqual(summary["status"], "research_candidate")
            self.assertEqual(summary["complete_commodities"], ["CU", "AU", "SC", "I"])
            self.assertEqual(summary["latest_contract_record_count"], 80)
            self.assertEqual(summary["continuous_record_count"], 40)
            self.assertGreaterEqual(summary["roll_event_count"], 4)
            self.assertEqual(summary["manifest_count"], 53)
            self.assertEqual(summary["p0_status"], "blocked")
            self.assertFalse(summary["forecast_labels_generated"])
            manifests = read_jsonl(output_dir / "source_manifest.jsonl")
            dce_daily = [item for item in manifests if item["source_id"] == "dce_daily_manual"]
            self.assertEqual(len(dce_daily), 10)
            self.assertTrue(all(item["content_type"] == "text/csv" for item in dce_daily))

    @unittest.skipUnless(
        os.environ.get("FINGOOSE_RUN_NETWORK_TESTS") == "1",
        "set FINGOOSE_RUN_NETWORK_TESTS=1 for official network integration",
    )
    def test_official_network_endpoint_is_json(self):
        content, content_type, status = download(
            "https://www.shfe.com.cn/data/tradedata/future/dailydata/kx20260722.dat"
        )
        self.assertEqual(status, 200)
        self.assertIn("json", content_type.lower())
        payload = parse_json_bytes(content, "SHFE network integration")
        self.assertIsInstance(payload.get("o_curinstrument"), list)


if __name__ == "__main__":
    unittest.main()