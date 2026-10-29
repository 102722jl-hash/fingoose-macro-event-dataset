from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


def mapping() -> dict[str, object]:
    return {
        "mapping_id": "mapping-test",
        "event_id": "event-02",
        "company_id": "company-test",
        "anchor_id": "anchor-test",
        "binding_id": "binding-test",
    }


class CompanyImpactDirectionTests(unittest.TestCase):
    def test_ai_direction_never_becomes_truth(self) -> None:
        from fingoose_company_impact_direction_v2 import build_direction

        row = build_direction(
            mapping(),
            horizons={"IMMEDIATE": "MIXED", "SHORT_TERM": "NEGATIVE", "MEDIUM_TERM": "UNKNOWN"},
            mechanism="能源成本上升与产品价差变化并存。",
            claim_ids=["claim-1"],
        )

        self.assertEqual(row["review_origin"], "AI_DESK_REVIEW")
        self.assertEqual(row["review_status"], "NEEDS_HUMAN_REVIEW")
        self.assertFalse(row["hidden_label_eligible"])
        self.assertFalse(row["formal_ready"])

    def test_post_event_price_cannot_support_direction(self) -> None:
        from fingoose_company_impact_direction_v2 import build_direction

        with self.assertRaisesRegex(ValueError, "POST_EVENT_PRICE_LEAKAGE"):
            build_direction(
                mapping(),
                horizons={"IMMEDIATE": "POSITIVE"},
                mechanism="价格上涨。",
                claim_ids=[],
                evidence=[{"kind": "PRICE_OUTCOME"}],
            )

    def test_missing_claims_force_unknown_horizons(self) -> None:
        from fingoose_company_impact_direction_v2 import build_direction

        row = build_direction(
            mapping(),
            horizons={"IMMEDIATE": "POSITIVE", "SHORT_TERM": "POSITIVE"},
            mechanism=None,
            claim_ids=[],
        )

        self.assertEqual(
            row["horizons"],
            {"IMMEDIATE": "UNKNOWN", "SHORT_TERM": "UNKNOWN", "MEDIUM_TERM": "UNKNOWN"},
        )


if __name__ == "__main__":
    unittest.main()
