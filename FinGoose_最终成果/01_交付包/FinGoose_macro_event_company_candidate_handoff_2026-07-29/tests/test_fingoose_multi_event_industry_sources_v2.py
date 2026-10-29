from __future__ import annotations

import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class MultiEventIndustrySourceRegistryTests(unittest.TestCase):
    def test_registry_uses_auditable_official_sources_for_all_nine_events(self) -> None:
        from fingoose_company_impact_io_v2 import read_jsonl

        rows = read_jsonl(
            ROOT / "configs/industry_impact_v2/multi_event_source_registry.jsonl"
        )
        mappings = read_jsonl(
            ROOT / "work/industry_impact_high_quality_v2_candidate/event_industry_mappings.jsonl"
        )
        valid_ids = {
            row["event_industry_mapping_id"]
            for row in mappings
            if row["event_id"] != "event-01"
        }
        self.assertGreaterEqual(len(rows), 30)
        self.assertEqual(len({row["source_id"] for row in rows}), len(rows))
        self.assertEqual(
            {row["event_id"] for row in rows},
            {f"event-{number:02d}" for number in range(2, 11)},
        )
        event_fact_counts = Counter()
        driver_counts = Counter()
        for row in rows:
            self.assertTrue(row["source_url"].startswith(("http://", "https://")))
            self.assertNotIn("google.com/search", row["source_url"])
            self.assertTrue(row["required_quote"].strip())
            self.assertTrue(row["evidence_locator"].strip())
            self.assertIn(row["usage_boundary"], {"PREDICTION_VISIBLE", "VERIFICATION_ONLY"})
            self.assertTrue(set(row["supports_mapping_ids"]).issubset(valid_ids))
            self.assertTrue(row["supports_mapping_ids"])
            self.assertTrue(row["supports_step_types"])
            if "EVENT_FACT" in row["supports_step_types"]:
                event_fact_counts[row["event_id"]] += 1
            if set(row["supports_step_types"]) & {"OBSERVABLE_DRIVER", "INDUSTRY_OPERATING_VARIABLE"}:
                driver_counts[row["event_id"]] += 1
        self.assertTrue(all(event_fact_counts[f"event-{n:02d}"] >= 1 for n in range(2, 11)))
        self.assertTrue(all(driver_counts[f"event-{n:02d}"] >= 1 for n in range(2, 11)))


if __name__ == "__main__":
    unittest.main()
