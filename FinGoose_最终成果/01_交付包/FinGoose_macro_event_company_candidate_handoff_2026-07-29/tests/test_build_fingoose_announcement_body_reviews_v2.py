from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))
CANDIDATE = ROOT / "work/company_impact_high_quality_v2_candidate"


class BuildAnnouncementBodyReviewsTests(unittest.TestCase):
    def test_convertible_bond_halt_is_not_equity_suspension_evidence(self) -> None:
        from build_fingoose_announcement_body_reviews_v2 import disposition_for_announcement

        title = "\u5173\u4e8e\u201c\u968622\u8f6c\u503a\u201d\u8f6c\u80a1\u8fde\u7eed\u505c\u724c\u7684\u63d0\u793a\u6027\u516c\u544a"
        result = disposition_for_announcement(title, "SUSPENSION")

        self.assertEqual(result["instrument_scope"], "CONVERTIBLE_BOND")
        self.assertEqual(result["relevance_decision"], "MINOR_RELEVANCE")
        self.assertEqual(result["severity_candidate"], "MINOR")
        self.assertFalse(result["equity_trading_status_evidence_eligible"])

    def test_quote_selection_returns_page_locator_and_verbatim_text(self) -> None:
        from build_fingoose_announcement_body_reviews_v2 import select_quote

        text = (
            "=== PAGE 1 ===\n\u516c\u53f8\u516c\u544a\u3002\n\n"
            "=== PAGE 2 ===\n\u672c\u6b21\u56de\u8d2d\u8d44\u91d1\u603b\u989d\u4e0d\u4f4e\u4e8e\u4e94\u4ebf\u5143\u4e14\u4e0d\u8d85\u8fc7\u5341\u4ebf\u5143\uff0c"
            "\u53ef\u80fd\u5f71\u54cd\u80a1\u4efd\u4f9b\u6c42\u3002\n"
        )

        quote, locator = select_quote(text, "\u80a1\u4efd\u56de\u8d2d\u516c\u544a", "CAPITAL_RETURN")

        self.assertIn("\u56de\u8d2d\u8d44\u91d1\u603b\u989d", quote)
        self.assertIn(quote, text)
        self.assertEqual(locator, "PDF page 2")

    def test_reviews_cover_all_retrieved_announcements(self) -> None:
        from build_fingoose_announcement_body_reviews_v2 import build_reviews
        from fingoose_company_impact_io_v2 import read_jsonl

        retrievals = read_jsonl(CANDIDATE / "announcement_body_retrieval.jsonl")
        reviews = build_reviews(ROOT, CANDIDATE)

        self.assertEqual(len(reviews), 47)
        self.assertEqual(
            {row["announcement_id"] for row in reviews},
            {row["announcement_id"] for row in retrievals},
        )
        for row in reviews:
            self.assertEqual(row["body_review_status"], "BODY_REVIEWED")
            self.assertTrue(row["original_quote"])
            self.assertTrue(row["body_locator"])
            text = (CANDIDATE / row["text_path"]).read_text(encoding="utf-8")
            self.assertIn(row["original_quote"], text)
            self.assertEqual(row["review_status"], "NEEDS_HUMAN_REVIEW")


if __name__ == "__main__":
    unittest.main()
