from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'configs' / 'fingoose_macro_event_company_candidate_v1.json'
HISTORICAL = ROOT / 'outputs' / 'fingoose_historical_company_impact_v1'
OUTPUT = ROOT / '.test-tmp' / 'fingoose-macro-event-company-enriched-candidate-v1'


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


class EnrichedCandidateBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from build_fingoose_macro_event_company_enriched_candidate_v1 import build_enriched_candidate_dataset

        cls.summary = build_enriched_candidate_dataset(
            CONFIG,
            OUTPUT,
            historical_root=HISTORICAL,
            workspace_root=ROOT,
        )

    def test_all_dossiers_have_identity_and_period_metadata(self):
        dossiers = read_jsonl(OUTPUT / 'company_event_dossiers.jsonl')
        self.assertEqual(len(dossiers), 30)
        self.assertTrue(all(row['industry'] != 'UNKNOWN' for row in dossiers))
        self.assertTrue(all(row['observation_quarter']['value'] != 'UNKNOWN' for row in dossiers))
        self.assertTrue(all(row['next_validation_quarter']['value'] != 'UNKNOWN' for row in dossiers))

    def test_existing_event_02_evidence_is_integrated(self):
        dossiers = {
            (row['event_id'], row['company_code']): row
            for row in read_jsonl(OUTPUT / 'company_event_dossiers.jsonl')
        }
        facts = read_jsonl(OUTPUT / 'company_metric_facts.jsonl')
        event_02_facts = [row for row in facts if row['event_id'] == 'event-02']
        self.assertEqual(sum(row['status'] == 'VERIFIED_EVIDENCE' for row in event_02_facts), 9)
        for code in ('601857.SH', '601233.SH', '600346.SH'):
            row = dossiers[('event-02', code)]
            self.assertEqual(row['business_exposure']['status'], 'VERIFIED_EVIDENCE')
            self.assertNotEqual(row['business_exposure']['value'], 'UNKNOWN')
            self.assertTrue(row['business_exposure']['evidence_refs'])
        self.assertEqual(dossiers[('event-02', '601857.SH')]['industry'], '石油天然气与石化')

    def test_source_manifest_contains_verified_company_snapshots(self):
        sources = read_jsonl(OUTPUT / 'source_manifest.jsonl')
        company_sources = [row for row in sources if row.get('source_kind') == 'historical_company_report']
        self.assertEqual(len(company_sources), 6)
        self.assertTrue(all(row['verification_status'] == 'VERIFIED' for row in company_sources))
        self.assertTrue(all((ROOT / row['local_snapshot_path']).is_file() for row in company_sources))

    def test_unverified_companies_remain_explicitly_pending(self):
        dossiers = read_jsonl(OUTPUT / 'company_event_dossiers.jsonl')
        other = [row for row in dossiers if row['event_id'] != 'event-02']
        self.assertEqual(len(other), 27)
        self.assertTrue(all(row['business_exposure']['status'] == 'PENDING_EVIDENCE' for row in other))
        self.assertTrue(all(row['business_exposure']['value'] == 'UNKNOWN' for row in other))
        self.assertTrue(all(row['evidence_gaps'] for row in other))

    def test_forecast_projection_does_not_gain_post_cutoff_company_evidence(self):
        projection = read_jsonl(OUTPUT / 'company_candidate_training_projection.jsonl')
        event_02_forecasts = [
            row for row in projection
            if row['event_id'] == 'event-02' and row['task_type'] == 'COMPANY_FORECAST'
        ]
        self.assertEqual(len(event_02_forecasts), 3)
        self.assertTrue(all(row['visible_company_evidence'] == [] for row in event_02_forecasts))
        self.assertTrue(all('forecast_labels' not in row for row in event_02_forecasts))

    def test_release_remains_candidate_only(self):
        report = json.loads((OUTPUT / 'validation_report.json').read_text(encoding='utf-8'))
        self.assertTrue(report['candidate_ready'])
        self.assertFalse(report['formal_ready'])
        self.assertEqual(self.summary['release_tier'], 'CANDIDATE')
        self.assertEqual(self.summary['verified_metric_fact_count'], 9)
        self.assertEqual(self.summary['enriched_company_dossier_count'], 3)


class EnrichedDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fingoose_macro_event_dashboard_v1 import MacroEventDashboardRepository

        cls.repository = MacroEventDashboardRepository(
            ROOT / 'outputs' / 'fingoose_macro_event_attribution_v1', OUTPUT,
        )

    def test_pending_association_is_not_presented_as_unsupported(self):
        rows = self.repository.list_companies(event_id='event-01')
        self.assertEqual({row['association'] for row in rows}, {'PENDING_ASSESSMENT'})

    def test_event_02_detail_exposes_financial_values_units_and_sources(self):
        detail = self.repository.company_detail('company-dossier-event-02-601857-sh')
        verified = [row for row in detail['metric_facts'] if row['status'] == 'VERIFIED_EVIDENCE']
        self.assertEqual(len(verified), 3)
        self.assertEqual({row['period'] for row in verified}, {'2022Q2'})
        self.assertEqual({row['unit'] for row in verified}, {'CNY_million'})
        self.assertGreaterEqual(len(detail['sources']), 2)
    def test_page_renders_pending_semantics_units_sources_and_market_windows(self):
        from fingoose_macro_event_dashboard_v1 import INDEX_HTML

        for token in ('PENDING_ASSESSMENT', 'm.unit', 'market_windows', 'evidence_refs'):
            self.assertIn(token, INDEX_HTML)



if __name__ == '__main__':
    unittest.main()
