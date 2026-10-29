from __future__ import annotations

from pathlib import Path
import unittest

from fingoose_macro_event_dashboard_v1 import INDEX_HTML, MacroEventDashboardRepository

ROOT = Path(__file__).resolve().parents[1]
MARKET_ROOT = ROOT / 'outputs' / 'fingoose_macro_event_attribution_v1'
COMPANY_ROOT = ROOT / 'outputs' / 'fingoose_macro_event_company_candidate_v1'


class UnifiedDashboardRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repository = MacroEventDashboardRepository(MARKET_ROOT, COMPANY_ROOT)

    def test_combines_market_and_company_release_counts(self):
        overview = self.repository.overview()
        self.assertEqual(overview['computed']['event_count'], 10)
        self.assertEqual(overview['computed']['sample_count'], 40)
        self.assertEqual(overview['company']['company_dossier_count'], 30)
        self.assertEqual(overview['company']['candidate_sample_count'], 60)
        self.assertEqual(overview['company']['company_metric_fact_count'], 120)
        self.assertTrue(overview['company']['candidate_ready'])
        self.assertFalse(overview['company']['formal_ready'])

    def test_event_detail_joins_four_market_samples_and_three_companies(self):
        detail = self.repository.event_detail('event-01')
        self.assertEqual(len(detail['market_samples']), 4)
        self.assertEqual(len(detail['company_dossiers']), 3)
        self.assertEqual({row['event_id'] for row in detail['company_dossiers']}, {'event-01'})

    def test_company_filters_and_detail_cover_required_audit_data(self):
        rows = self.repository.list_companies(
            event_id='event-01', company_query='600009', association='UNSUPPORTED',
            direction='UNCERTAIN', evidence_status='PARTIAL_EVIDENCE',
            review_status='SECOND_REVIEW_REQUIRED',
        )
        self.assertEqual(len(rows), 1)
        detail = self.repository.company_detail(rows[0]['dossier_id'])
        self.assertEqual(len(detail['metric_facts']), 4)
        self.assertEqual(detail['stock_window']['status'], 'PENDING_EVIDENCE')
        self.assertEqual(detail['attribution_sample']['association'], 'UNSUPPORTED')
        self.assertEqual(
            {row['value'] for row in detail['forecast_sample']['forecast_labels']},
            {'INCONCLUSIVE'},
        )
        self.assertTrue(detail['evidence_gaps'])
        self.assertEqual(detail['review']['initial_reviewer_id'], 'reviewer-user-01')
        self.assertEqual(detail['review']['review_status'], 'SECOND_REVIEW_REQUIRED')
        self.assertTrue(detail['sources'])

    def test_page_contract_contains_four_views_filters_and_chain_drilldown(self):
        for token in (
            '\u6570\u636e\u96c6\u6982\u89c8', '\u5e02\u573a\u5f52\u56e0',
            '\u516c\u53f8\u5f71\u54cd', '\u5ba1\u6838\u8bb0\u5f55',
            'event-filter', 'company-filter', 'association-filter', 'direction-filter',
            'evidence-filter', 'review-filter', 'chain-node-detail',
        ):
            self.assertIn(token, INDEX_HTML)

    def test_page_uses_chinese_labels_for_visible_dataset_values(self):
        for token in (
            '候选训练版', '尚未达到正式版',
            '主要驱动因素', '贡献因素', '弱关联', '不支持',
            '单资产归因与预测', '跨资产归因与预测',
            '重大事件', '行业与宏观变量', '公司业务暴露',
            '经营指标', '财务结果', '竞争解释', '归因或预测',
            '未知', '收入动量', '利润状态', '核心经营指标',
        ):
            self.assertIn(token, INDEX_HTML)
        for token in ('>CANDIDATE<', '>FORMAL READY: FALSE<'):
            self.assertNotIn(token, INDEX_HTML)

if __name__ == '__main__':
    unittest.main()
