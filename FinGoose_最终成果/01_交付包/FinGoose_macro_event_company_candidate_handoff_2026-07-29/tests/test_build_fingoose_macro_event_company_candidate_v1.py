from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'configs' / 'fingoose_macro_event_company_candidate_v1.json'
OUTPUT = ROOT / '.test-tmp' / 'fingoose-macro-event-company-candidate-v1'


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


class CandidateCompanyBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from build_fingoose_macro_event_company_candidate_v1 import build_candidate_dataset

        cls.summary = build_candidate_dataset(CONFIG, OUTPUT, workspace_root=ROOT)

    def test_writes_required_candidate_artifacts_and_counts(self):
        required = {
            'summary.json', 'company_event_dossiers.jsonl', 'company_metric_facts.jsonl',
            'company_stock_windows.jsonl', 'company_attribution_samples.jsonl',
            'company_forecast_samples.jsonl', 'company_candidate_training_projection.jsonl',
            'company_candidate_hidden_labels.jsonl', 'company_hidden_outcomes.jsonl',
            'company_review_records.jsonl', 'company_evidence_gaps.jsonl',
            'candidate_company_registry.jsonl', 'source_manifest.jsonl', 'rejected.jsonl',
            'validation_report.json',
        }
        self.assertEqual(required, {path.name for path in OUTPUT.iterdir() if path.is_file()})
        self.assertEqual(self.summary['release_tier'], 'CANDIDATE')
        self.assertTrue(self.summary['candidate_ready'])
        self.assertFalse(self.summary['formal_ready'])
        self.assertEqual(self.summary['event_count'], 10)
        self.assertEqual(self.summary['company_dossier_count'], 30)
        self.assertEqual(self.summary['attribution_sample_count'], 30)
        self.assertEqual(self.summary['forecast_sample_count'], 30)
        self.assertEqual(self.summary['candidate_sample_count'], 60)

    def test_each_event_has_exactly_three_companies_and_structured_chain(self):
        dossiers = read_jsonl(OUTPUT / 'company_event_dossiers.jsonl')
        counts: dict[str, int] = {}
        expected_nodes = [
            'MAJOR_EVENT', 'INDUSTRY_MACRO_VARIABLE', 'COMPANY_BUSINESS_EXPOSURE',
            'OPERATING_METRIC', 'FINANCIAL_RESULT', 'COMPETING_EXPLANATION',
            'ATTRIBUTION_OR_FORECAST',
        ]
        for dossier in dossiers:
            counts[dossier['event_id']] = counts.get(dossier['event_id'], 0) + 1
            chain = dossier['transmission_chain']
            self.assertEqual([node['node_type'] for node in chain['nodes']], expected_nodes)
            self.assertEqual(len(chain['edges']), 6)
            for node in chain['nodes']:
                self.assertIn('evidence_refs', node)
                if node['status'] == 'PENDING_EVIDENCE':
                    self.assertEqual(node['value'], 'UNKNOWN')
                    self.assertEqual(node['evidence_refs'], [])
                    self.assertTrue(node['gap_reason'])
        self.assertEqual(counts, {f'event-{index:02d}': 3 for index in range(1, 11)})

    def test_dossiers_expose_required_candidate_fields_and_pending_metric_facts(self):
        dossiers = read_jsonl(OUTPUT / 'company_event_dossiers.jsonl')
        facts = read_jsonl(OUTPUT / 'company_metric_facts.jsonl')
        required = {
            'event_id', 'company_code', 'company_name', 'industry',
            'business_exposure', 'observation_quarter', 'next_validation_quarter',
            'transmission_chain', 'competing_explanations', 'evidence_status',
            'evidence_gaps', 'confidence', 'review_status',
        }
        self.assertEqual(len(dossiers), 30)
        self.assertTrue(all(required <= set(row) for row in dossiers))
        self.assertTrue(all(row['business_exposure']['status'] == 'PENDING_EVIDENCE' for row in dossiers))
        self.assertTrue(all(row['business_exposure']['value'] == 'UNKNOWN' for row in dossiers))
        self.assertTrue(all(row['evidence_gaps'] for row in dossiers))
        self.assertEqual(len(facts), 120)
        self.assertEqual(
            {row['metric_type'] for row in facts},
            {'REVENUE', 'GROSS_MARGIN', 'NET_PROFIT', 'OPERATING_CASH_FLOW'},
        )
        self.assertTrue(all(row['status'] == 'PENDING_EVIDENCE' for row in facts))
        self.assertTrue(all(row['value'] == 'UNKNOWN' for row in facts))
        self.assertTrue(all(row['evidence_refs'] == [] for row in facts))
        self.assertTrue(all(row['gap_reason'] for row in facts))

    def test_gaps_reviews_and_public_forecast_projection_are_explicit(self):
        dossiers = read_jsonl(OUTPUT / 'company_event_dossiers.jsonl')
        gaps = read_jsonl(OUTPUT / 'company_evidence_gaps.jsonl')
        reviews = read_jsonl(OUTPUT / 'company_review_records.jsonl')
        projection = read_jsonl(OUTPUT / 'company_candidate_training_projection.jsonl')
        forbidden = {
            'actual_value', 'actual_results', 'future_source_id', 'future_source_ids',
            'D5', 'D20', 'retrospective_attribution', 'association_label', 'forecast_labels',
        }

        self.assertEqual(len(reviews), 30)
        self.assertEqual({row['initial_reviewer_id'] for row in reviews}, {'reviewer-user-01'})
        self.assertTrue(all(row['review_status'] in {
            'AI_INITIAL_REVIEW_COMPLETED', 'SECOND_REVIEW_REQUIRED', 'PENDING_EVIDENCE',
            'REJECTED', 'VERIFIED',
        } for row in reviews))
        self.assertTrue(all(row['review_status'] == 'SECOND_REVIEW_REQUIRED' for row in reviews))
        self.assertTrue(all('LOW_CONFIDENCE' in row['second_review_trigger_reasons'] for row in reviews))
        self.assertTrue(all(row['second_review'] is None for row in reviews))
        self.assertTrue(all(row['adjudication'] is None for row in reviews))
        self.assertTrue(gaps)
        self.assertTrue(all(row['gap_reason'] for row in gaps))

        def assert_safe(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden & set(value))
                for item in value.values():
                    assert_safe(item)
            elif isinstance(value, list):
                for item in value:
                    assert_safe(item)

        self.assertEqual(len(projection), 60)
        for row in projection:
            assert_safe(row)
        forecast_rows = [row for row in projection if row['task_type'] == 'COMPANY_FORECAST']
        self.assertEqual(len(forecast_rows), 30)
        self.assertTrue(all(row['visible_windows'] == ['D1', 'D3'] for row in forecast_rows))
        self.assertTrue(all(row['projection_source'] == 'INDEPENDENT_CUTOFF_SNAPSHOT' for row in forecast_rows))

    def test_internal_forecast_samples_use_conservative_candidate_labels(self):
        samples = read_jsonl(OUTPUT / 'company_forecast_samples.jsonl')
        self.assertEqual(len(samples), 30)
        expected = {
            'REVENUE_MOMENTUM': 'INCONCLUSIVE',
            'PROFIT_STATE': 'INCONCLUSIVE',
            'OPERATING_METRIC': 'INCONCLUSIVE',
        }
        for sample in samples:
            self.assertEqual(
                {row['label_type']: row['value'] for row in sample['forecast_labels']},
                expected,
            )

    def test_validation_report_records_candidate_not_formal_readiness(self):
        report = json.loads((OUTPUT / 'validation_report.json').read_text(encoding='utf-8'))
        self.assertTrue(report['candidate_ready'])
        self.assertFalse(report['formal_ready'])
        self.assertEqual(report['errors'], [])
        self.assertTrue(report['checks']['public_projection_leakage_free'])
        self.assertTrue(report['checks']['protected_output_roots_not_targeted'])

class ApprovedPilotRosterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from build_fingoose_macro_event_company_candidate_v1 import build_candidate_dataset

        build_candidate_dataset(CONFIG, OUTPUT, workspace_root=ROOT)

    def test_approved_pilot_company_roster_is_locked(self):
        dossiers = read_jsonl(OUTPUT / 'company_event_dossiers.jsonl')
        actual = {
            event_id: {
                (row['company_code'], row['company_name'])
                for row in dossiers if row['event_id'] == event_id
            }
            for event_id in ('event-01', 'event-02', 'event-05')
        }
        self.assertEqual(actual, {
            'event-01': {
                ('600009.SH', '\u4e0a\u6d77\u673a\u573a'),
                ('601111.SH', '\u4e2d\u56fd\u56fd\u822a'),
                ('002030.SZ', '\u8fbe\u5b89\u57fa\u56e0'),
            },
            'event-02': {
                ('601857.SH', '\u4e2d\u56fd\u77f3\u6cb9'),
                ('601233.SH', '\u6850\u6606\u80a1\u4efd'),
                ('600346.SH', '\u6052\u529b\u77f3\u5316'),
            },
            'event-05': {
                ('002432.SZ', '\u4e5d\u5b89\u533b\u7597'),
                ('300482.SZ', '\u4e07\u5b5a\u751f\u7269'),
                ('688235.SH', '\u767e\u6d4e\u795e\u5dde'),
            },
        })
if __name__ == '__main__':
    unittest.main()
