from __future__ import annotations

import unittest


class OfficialEnrichedCandidateTests(unittest.TestCase):
    def test_derives_standalone_q2_from_official_cumulative_facts(self):
        from build_fingoose_macro_event_company_official_enriched_candidate_v1 import derive_standalone_quarter

        q1 = {
            'company_code': '600009.SH', 'report_type': 'q1_2023',
            'metric': 'revenue', 'unit': 'CNY', 'value_decimal': '100.25',
            'source_id': 'q1', 'source_locator': 'q1.pdf:page=2', 'text_sha256': '1' * 64,
        }
        h1 = {
            'company_code': '600009.SH', 'report_type': 'h1_2023',
            'metric': 'revenue', 'unit': 'CNY', 'value_decimal': '260.75',
            'source_id': 'h1', 'source_locator': 'h1.pdf:page=3', 'text_sha256': '2' * 64,
        }

        fact = derive_standalone_quarter('2023Q2', [q1, h1], 'revenue')

        self.assertEqual(fact['value_decimal'], '160.50')
        self.assertEqual(fact['derivation_type'], 'cumulative_difference')
        self.assertEqual(len(fact['evidence_refs']), 2)

    def test_returns_none_when_required_official_report_is_missing(self):
        from build_fingoose_macro_event_company_official_enriched_candidate_v1 import derive_standalone_quarter

        fact = derive_standalone_quarter('2023Q3', [{
            'company_code': '600009.SH', 'report_type': 'q3_2023',
            'metric': 'revenue', 'unit': 'CNY', 'value_decimal': '300',
        }], 'revenue')

        self.assertIsNone(fact)


    def test_risk_page_selection_excludes_accounting_policy_language(self):
        from build_fingoose_macro_event_company_official_enriched_candidate_v1 import _select_risk_page

        selected = _select_risk_page([
            {'page_number': 62, 'statement': '\u6240\u6709\u6743\u4e0a\u7684\u4e3b\u8981\u98ce\u9669\u548c\u62a5\u916c \u4f1a\u8ba1\u653f\u7b56'},
            {'page_number': 12, 'statement': '\u539f\u6750\u6599\u4ef7\u683c\u6ce2\u52a8\u4e0e\u5e02\u573a\u9700\u6c42\u4e0d\u8db3\u53ef\u80fd\u5f71\u54cd\u7ecf\u8425'},
        ])

        self.assertEqual(selected[0]['page_number'], 12)


if __name__ == '__main__':
    unittest.main()
