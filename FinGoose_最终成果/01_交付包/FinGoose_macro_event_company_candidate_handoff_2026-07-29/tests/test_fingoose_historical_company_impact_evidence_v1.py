from __future__ import annotations

import hashlib
from pathlib import Path
import unittest


class HistoricalCompanyImpactEvidenceTests(unittest.TestCase):
    def test_derives_q2_fact_from_matching_q1_and_h1_cumulative_facts(self):
        from fingoose_historical_company_impact_evidence_v1 import derive_q2_fact

        q1 = {
            'company_code': '601857.SH', 'report_type': 'q1_2022',
            'metric': 'revenue', 'unit': 'CNY_million', 'value': 7793.65,
            'source_id': 'historical-cninfo-601857-sh-q1-2022',
            'source_locator': 'q1.pdf:page=4', 'text_sha256': '1' * 64,
        }
        h1 = {
            'company_code': '601857.SH', 'report_type': 'h1_2022',
            'metric': 'revenue', 'unit': 'CNY_million', 'value': 16114.7,
            'source_id': 'historical-cninfo-601857-sh-h1-2022',
            'source_locator': 'h1.pdf:page=7', 'text_sha256': '2' * 64,
        }

        fact = derive_q2_fact(q1, h1)

        self.assertEqual(fact['period'], '2022Q2')
        self.assertEqual(fact['value'], 8321.05)
        self.assertEqual(fact['calculation']['formula'], 'h1_cumulative - q1_cumulative')
        self.assertEqual(fact['evidence_refs'], [
            {'source_id': q1['source_id'], 'source_locator': q1['source_locator'], 'text_sha256': q1['text_sha256']},
            {'source_id': h1['source_id'], 'source_locator': h1['source_locator'], 'text_sha256': h1['text_sha256']},
        ])

    def test_rejects_q2_derivation_when_metric_or_unit_does_not_match(self):
        from fingoose_historical_company_impact_evidence_v1 import HistoricalEvidenceError, derive_q2_fact

        q1 = {
            'company_code': '601857.SH', 'report_type': 'q1_2022',
            'metric': 'revenue', 'unit': 'CNY_million', 'value': 10,
            'source_id': 'q1', 'source_locator': 'q1.pdf:page=1', 'text_sha256': '1' * 64,
        }
        h1 = {**q1, 'report_type': 'h1_2022', 'metric': 'net_income', 'source_id': 'h1'}

        with self.assertRaisesRegex(HistoricalEvidenceError, 'Q2_FACT_METRIC_MISMATCH'):
            derive_q2_fact(q1, h1)
    def test_preserves_large_currency_difference_as_an_exact_decimal(self):
        from fingoose_historical_company_impact_evidence_v1 import derive_q2_fact

        q1 = {
            'company_code': '601233.SH', 'report_type': 'q1_2022',
            'metric': 'revenue', 'unit': 'CNY', 'value': 12994286185.50,
            'source_id': 'q1', 'source_locator': 'q1.pdf:page=1', 'text_sha256': '1' * 64,
        }
        h1 = {**q1, 'report_type': 'h1_2022', 'value': 29851749801.65,
              'source_id': 'h1', 'source_locator': 'h1.pdf:page=6', 'text_sha256': '2' * 64}

        fact = derive_q2_fact(q1, h1)

        self.assertEqual(fact['value_decimal'], '16857463616.15')
        self.assertEqual(fact['calculation']['result_decimal'], '16857463616.15')
    def test_builds_a_separate_historical_h1_manifest_without_changing_v03_period_rules(self):
        from fingoose_historical_company_impact_evidence_v1 import build_historical_report_manifest

        root = Path(__file__).resolve().parents[1] / '.test-tmp' / 'historical-company-evidence'
        snapshots = root / 'snapshots'
        snapshots.mkdir(parents=True, exist_ok=True)
        pdf = snapshots / 'fixture.pdf'
        body = b'%PDF-1.4 fixture bytes'
        pdf.write_bytes(body)
        row = {
            'company_code': '600346.SH', 'report_type': 'h1_2022',
            'announcement_date': '2022-08-16',
            'source_url': 'https://static.cninfo.com.cn/finalpage/2022-08-16/fixture.PDF',
            'local_snapshot_path': 'snapshots/fixture.pdf',
            'content_sha256': hashlib.sha256(body).hexdigest(), 'page_count': 1,
        }

        manifest = build_historical_report_manifest(row, workspace_root=root, page_count_reader=lambda _: 1)

        self.assertEqual(manifest['report_type'], 'h1_2022')
        self.assertEqual(manifest['evidence_scope'], 'historical_event_impact_only')
        self.assertFalse(manifest['formal_sample_generation_allowed'])

    def test_rejects_vendor_urls_and_hash_mismatch(self):
        from fingoose_historical_company_impact_evidence_v1 import HistoricalEvidenceError, build_historical_report_manifest

        root = Path(__file__).resolve().parents[1] / '.test-tmp' / 'historical-company-evidence-reject'
        root.mkdir(parents=True, exist_ok=True)
        (root / 'fixture.pdf').write_bytes(b'not a vendor source')
        row = {
            'company_code': '600346.SH', 'report_type': 'h1_2022', 'announcement_date': '2022-08-16',
            'source_url': 'https://news.windin.com/bulletin.pdf', 'local_snapshot_path': 'fixture.pdf',
            'content_sha256': '0' * 64, 'page_count': 1,
        }

        with self.assertRaises(HistoricalEvidenceError):
            build_historical_report_manifest(row, workspace_root=root, page_count_reader=lambda _: 1)


if __name__ == '__main__':
    unittest.main()


