from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class CompanyDossierBuilderTests(unittest.TestCase):
    def test_selector_ignores_table_of_contents(self) -> None:
        from fingoose_company_dossier_builder_v2 import select_evidence_passage

        pages = [
            {"page_number": 3, "text": "目录 主营业务 ........................ 15"},
            {"page_number": 15, "text": "公司的主营业务为航空运输服务，并提供相关地面服务。"},
        ]

        selected = select_evidence_passage(pages, ["主营业务"])

        self.assertEqual(selected["page_number"], 15)
        self.assertIn("航空运输服务", selected["original_quote"])

    def test_selector_returns_none_without_keyword_evidence(self) -> None:
        from fingoose_company_dossier_builder_v2 import select_evidence_passage

        selected = select_evidence_passage(
            [{"page_number": 8, "text": "本页没有相关披露。"}],
            ["境外收入"],
        )

        self.assertIsNone(selected)

    def test_selector_returns_bounded_quote_and_matched_terms(self) -> None:
        from fingoose_company_dossier_builder_v2 import select_evidence_passage

        text = "前文。" * 80 + "公司面临原材料价格波动风险，并采取长期采购安排。" + "后文。" * 80
        selected = select_evidence_passage(
            [{"page_number": 25, "text": text}],
            ["原材料价格", "长期采购"],
            quote_limit=180,
        )

        self.assertLessEqual(len(selected["original_quote"]), 180)
        self.assertEqual(selected["matched_terms"], ["原材料价格", "长期采购"])
        self.assertEqual(selected["review_status"], "NEEDS_HUMAN_REVIEW")


if __name__ == "__main__":
    unittest.main()
