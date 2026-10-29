import json
import tempfile
import unittest
from pathlib import Path

from fingoose_mysql_company_enhancement_v1 import (
    MysqlCliQueryRunner,
    build_candidate_records,
    industry_from_table_name,
    resolve_industry_membership,
    select_event_anchors,
    select_financial_baseline,
    summarize_rating_rows,
    write_candidate_bundle,
)


ROOT = Path(__file__).resolve().parents[1]


class AnchorSelectionTests(unittest.TestCase):
    def test_selects_earliest_causal_start_per_event(self):
        rows = [
            {
                "event_id": "event-01",
                "anchor_id": "observation",
                "activation_mode": "OBSERVATION_ONLY",
                "node_action": "OBSERVES",
                "sequence": 1,
                "first_public_at": "2020-03-10T12:00:00+00:00",
                "impact_tags": ["GLOBAL_DEMAND"],
            },
            {
                "event_id": "event-01",
                "anchor_id": "primary",
                "activation_mode": "CAUSAL_CANDIDATE",
                "node_action": "STARTS",
                "sequence": 3,
                "first_public_at": "2020-03-11T16:30:00+00:00",
                "impact_tags": ["GLOBAL_DEMAND", "RISK_APPETITE"],
            },
            {
                "event_id": "event-01",
                "anchor_id": "later",
                "activation_mode": "CAUSAL_CANDIDATE",
                "node_action": "STARTS",
                "sequence": 4,
                "first_public_at": "2020-03-12T00:00:00+00:00",
                "impact_tags": ["LIQUIDITY_STRESS"],
            },
        ]

        selected = select_event_anchors(rows)

        self.assertEqual(selected["event-01"]["anchor_id"], "primary")
        self.assertEqual(selected["event-01"]["anchor_date"], "2020-03-11")


class IndustryMappingTests(unittest.TestCase):
    def test_parses_actual_industry_history_table_names(self):
        self.assertEqual(industry_from_table_name("fr石油石化_history"), "石油石化")
        self.assertIsNone(industry_from_table_name("fr石油石化_模型"))

    def test_marks_zero_one_and_multiple_memberships_explicitly(self):
        self.assertEqual(resolve_industry_membership([])["status"], "UNKNOWN")
        mapped = resolve_industry_membership([{"industry": "石油石化", "source_table": "fr石油石化_history"}])
        self.assertEqual(mapped["status"], "MAPPED")
        self.assertEqual(mapped["industry"], "石油石化")
        ambiguous = resolve_industry_membership([
            {"industry": "石油石化", "source_table": "fr石油石化_history"},
            {"industry": "基础化工", "source_table": "fr基础化工_history"},
        ])
        self.assertEqual(ambiguous["status"], "AMBIGUOUS")
        self.assertEqual(ambiguous["industry"], "UNKNOWN")


class RatingWindowTests(unittest.TestCase):
    def test_deduplicates_identical_payloads_but_retains_same_day_variants(self):
        rows = [
            {
                "RATING_DT": "20220223",
                "S_WRATING_AVG": "1.8",
                "S_WRATING_INSTNUM": "5",
                "S_WRATING_UPGRADE": "1",
                "S_WRATING_DOWNGRADE": "0",
                "S_WRATING_MAINTAIN": "4",
                "S_WRATING_CYCLE": "30",
                "S_EST_PRICE": "7.5",
                "S_EST_PRICEINSTNUM": "1",
            },
            {
                "RATING_DT": "20220223",
                "S_WRATING_AVG": "1.8",
                "S_WRATING_INSTNUM": "5",
                "S_WRATING_UPGRADE": "1",
                "S_WRATING_DOWNGRADE": "0",
                "S_WRATING_MAINTAIN": "4",
                "S_WRATING_CYCLE": "30",
                "S_EST_PRICE": "7.5",
                "S_EST_PRICEINSTNUM": "1",
            },
            {
                "RATING_DT": "20220223",
                "S_WRATING_AVG": "1.7",
                "S_WRATING_INSTNUM": "8",
                "S_WRATING_UPGRADE": "2",
                "S_WRATING_DOWNGRADE": "0",
                "S_WRATING_MAINTAIN": "6",
                "S_WRATING_CYCLE": "90",
                "S_EST_PRICE": "8.0",
                "S_EST_PRICEINSTNUM": "3",
            },
            {
                "RATING_DT": "20220310",
                "S_WRATING_AVG": "1.5",
                "S_WRATING_INSTNUM": "9",
                "S_WRATING_UPGRADE": "3",
                "S_WRATING_DOWNGRADE": "0",
                "S_WRATING_MAINTAIN": "6",
                "S_WRATING_CYCLE": "90",
                "S_EST_PRICE": "8.4",
                "S_EST_PRICEINSTNUM": "4",
            },
        ]

        result = summarize_rating_rows(rows, anchor_date="2022-02-24")

        self.assertEqual(result["raw_row_count"], 4)
        self.assertEqual(result["duplicate_row_count"], 1)
        self.assertEqual(result["distinct_observation_count"], 3)
        self.assertEqual(result["pre_event"]["selected_observation"]["rating_cycle"], 90)
        self.assertEqual(result["post_event"]["selected_observation"]["rating_date"], "2022-03-10")
        self.assertEqual(result["selection_rule"], "LATEST_DATE_THEN_MAX_RATING_INSTITUTION_COUNT")

    def test_emits_explicit_no_window_data(self):
        result = summarize_rating_rows([], anchor_date="2022-02-24")
        self.assertEqual(result["status"], "NO_WINDOW_DATA")
        self.assertIsNone(result["pre_event"]["selected_observation"])
        self.assertIsNone(result["post_event"]["selected_observation"])


class FinancialBaselineTests(unittest.TestCase):
    def test_rejects_post_event_announcements_and_selects_latest_pre_event_record(self):
        rows_by_statement = {
            "BALANCE_SHEET": [
                {"ann_dt": "20240901", "actual_ann_dt": "20240902", "report_period": "20240630", "tot_assets": "100"},
                {"ann_dt": "20241001", "actual_ann_dt": "20241002", "report_period": "20240930", "tot_assets": "110"},
            ],
            "INCOME_STATEMENT": [
                {"ann_dt": "20240830", "actual_ann_dt": "", "report_period": "20240630", "tot_oper_rev": "50"},
            ],
            "CASH_FLOW": [],
        }

        result = select_financial_baseline(rows_by_statement, cutoff_date="2024-09-24")

        self.assertEqual(result["BALANCE_SHEET"]["effective_announcement_date"], "2024-09-02")
        self.assertEqual(result["BALANCE_SHEET"]["metrics"]["tot_assets"], 100.0)
        self.assertEqual(result["CASH_FLOW"]["status"], "NO_PRE_EVENT_DATA")
        self.assertEqual(result["excluded_post_event_count"], 1)


class CandidateBundleTests(unittest.TestCase):
    def test_keeps_every_registry_company_and_never_upgrades_official_evidence(self):
        registry = [
            {"event_id": "event-01", "company_code": "600009.SH", "company_name": "上海机场"},
            {"event_id": "event-02", "company_code": "601857.SH", "company_name": "中国石油"},
        ]
        anchors = {
            "event-01": {"anchor_id": "a1", "anchor_date": "2020-03-11", "impact_tags": ["GLOBAL_DEMAND"]},
            "event-02": {"anchor_id": "a2", "anchor_date": "2022-02-24", "impact_tags": ["ENERGY_SUPPLY"]},
        }
        memberships = {
            "600009.SH": [{"industry": "交通运输", "source_table": "fr交通运输_history"}],
            "601857.SH": [{"industry": "石油石化", "source_table": "fr石油石化_history"}],
        }
        rating_rows = {("event-01", "600009.SH"): [], ("event-02", "601857.SH"): []}
        financial_rows = {("event-01", "600009.SH"): {}, ("event-02", "601857.SH"): {}}

        records = build_candidate_records(registry, anchors, memberships, rating_rows, financial_rows)

        self.assertEqual(len(records["impact_candidates"]), 2)
        self.assertEqual(len(records["rating_windows"]), 2)
        self.assertEqual(len(records["financial_baselines"]), 2)
        self.assertTrue(all(not row["official_company_exposure_verified"] for row in records["impact_candidates"]))
        self.assertTrue(all(row["status"] == "PROPOSED_UNVERIFIED" for row in records["impact_candidates"]))

    def test_writes_hash_manifest_and_candidate_release_boundary(self):
        records = {
            "impact_candidates": [{"candidate_id": "candidate-1"}],
            "rating_windows": [{"rating_window_id": "rating-1"}],
            "financial_baselines": [{"financial_baseline_id": "financial-1"}],
        }
        source_manifest = [{"source_id": "mysql-workspace", "credentials_included": False}]
        validation = {"hard_failures": [], "valid": True}
        summary = {"formal_ready": False, "release_tier": "VENDOR_CANDIDATE"}

        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            output = Path(temp) / "bundle"
            write_candidate_bundle(output, records, source_manifest, validation, summary)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))

            self.assertFalse(manifest["formal_ready"])
            self.assertEqual(manifest["release_tier"], "VENDOR_CANDIDATE")
            self.assertTrue(all(len(item["sha256"]) == 64 for item in manifest["files"]))


class MysqlCliSecurityTests(unittest.TestCase):
    def test_rejects_non_read_only_statements(self):
        runner = MysqlCliQueryRunner(
            mysql_exe=Path("D:/mysql/bin/mysql.exe"),
            login_path="fingoose-codex",
            database="workspace",
        )
        with self.assertRaisesRegex(ValueError, "read-only"):
            runner("UPDATE some_table SET value=1")


if __name__ == "__main__":
    unittest.main()
