from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))
OUTPUT = ROOT / ".test-tmp/package_confounder_integration"


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


class CompanyConfounderPackageIntegrationTests(unittest.TestCase):
    def test_package_contains_full_confounder_closure_ledgers(self) -> None:
        from build_fingoose_company_impact_high_quality_v2 import build

        report = build(ROOT, OUTPUT)

        expected = {
            "announcement_body_reviews.jsonl": 47,
            "company_confounder_search_audits.jsonl": 30,
            "trading_status_reviews.jsonl": 30,
            "company_counterevidence_reviews.jsonl": 30,
            "company_confounder_arguments.jsonl": 30,
            "company_confounders.jsonl": 30,
        }
        for name, count in expected.items():
            self.assertEqual(len(_read_jsonl(OUTPUT / name)), count, name)
        self.assertEqual(report["announcement_body_review_count"], 47)
        self.assertEqual(report["confounder_search_audit_count"], 30)
        self.assertEqual(report["trading_status_review_count"], 30)
        self.assertEqual(report["counterevidence_review_count"], 30)
        self.assertEqual(report["confounder_argument_count"], 30)
        self.assertFalse(report["formal_ready"])
        self.assertEqual(report["sha_gate"], "DEFERRED")


if __name__ == "__main__":
    unittest.main()
