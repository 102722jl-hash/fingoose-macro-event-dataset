from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class BuildCompanyDirectionCandidatesTests(unittest.TestCase):
    def test_build_emits_30_non_label_ai_reviews(self) -> None:
        from build_company_direction_candidates_v2 import build

        with tempfile.TemporaryDirectory(dir=ROOT / "tmp") as temp_dir:
            output = Path(temp_dir)
            summary = build(ROOT, output)
            rows = [
                json.loads(line)
                for line in (output / "direction_assessments.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]

        self.assertEqual(summary["direction_count"], 30)
        self.assertEqual(len(rows), 30)
        self.assertTrue(all(row["review_status"] == "NEEDS_HUMAN_REVIEW" for row in rows))
        self.assertTrue(all(row["hidden_label_eligible"] is False for row in rows))
        self.assertTrue(all(row["price_selection_used"] is False for row in rows))
        self.assertTrue(
            all(
                evidence.get("kind") != "PRICE_OUTCOME"
                for row in rows
                for evidence in row["evidence"]
            )
        )


if __name__ == "__main__":
    unittest.main()
