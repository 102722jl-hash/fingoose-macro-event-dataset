from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from fingoose_macro_event_dashboard_v1 import (
    MacroEventDashboardRepository,
    _read_jsonl,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_TEMP_ROOT = PROJECT_ROOT / '.test-tmp'


class MacroEventDashboardRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self._temporary_directory = tempfile.TemporaryDirectory(
            dir=TEST_TEMP_ROOT,
            prefix='macro-event-dashboard-',
        )
        self.output_root = Path(self._temporary_directory.name)
        self.reasoning_chain = [
            'MACRO_REPORT',
            'DATA',
            'PERIOD_DESCRIPTION',
            'FACT_TRANSMISSION_CHAIN',
            'MULTI_DATA_TREND_CONFIRMATION',
            'SHORT_TERM_PREDICTION',
        ]
        self.summary = {
            'dataset_version': 'fixture-v1',
            'event_count': 99,
            'sample_count': 99,
            'market_window_count': 99,
            'forecast_reasoning_chain': self.reasoning_chain,
        }
        self._write_json('summary.json', self.summary)
        self._write_jsonl('event_dossiers.jsonl', [{
            'event_id': 'event-01',
            'title': '中国央行宣布降准',
            'occurred_at': '2024-02-05T01:00:00+00:00',
            'category': 'monetary_policy',
        }])
        self._write_jsonl('market_windows.jsonl', [{
            'event_id': 'event-01',
            'market_window_id': 'event-01-csi300',
        }])
        self._write_jsonl('attribution_samples.jsonl', [{
            'event_id': 'event-01',
            'record_id': 'sample-01',
            'review_id': 'review-01',
        }])
        self._write_jsonl('training_projection.jsonl', [{
            'event_id': 'event-01',
            'record_id': 'sample-01',
            'forecast_reasoning_chain': {'sequence': self.reasoning_chain},
        }])
        self._write_jsonl('hidden_forecast_outcomes.jsonl', [{
            'record_id': 'sample-01',
            'outcome_window': 'D20',
        }])
        self._write_jsonl('hidden_attribution_labels.jsonl', [{
            'record_id': 'sample-01',
            'review_id': 'review-01',
            'label': 'PRIMARY_DRIVER',
        }])
        self._write_jsonl('review_records.jsonl', [{
            'event_id': 'event-01',
            'review_id': 'review-01',
            'final_label': 'PRIMARY_DRIVER',
            'second_review': {'status': 'APPROVED'},
            'adjudication': {'status': 'APPROVED'},
        }])
        self._write_jsonl('source_manifest.jsonl', [{
            'event_id': 'event-01',
            'source_id': 'source-01',
            'title': '中文来源',
        }])

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    def _write_json(self, filename: str, payload: dict) -> None:
        (self.output_root / filename).write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding='utf-8',
        )

    def _write_jsonl(self, filename: str, rows: list[dict]) -> None:
        content = ''.join(
            json.dumps(row, ensure_ascii=False) + '\n'
            for row in rows
        )
        (self.output_root / filename).write_text(content, encoding='utf-8')

    def test_overview_recomputes_release_counts_and_distributions(self):
        repository = MacroEventDashboardRepository(self.output_root)

        overview = repository.overview()

        self.assertEqual(overview['persisted'], self.summary)
        self.assertEqual(overview['computed']['event_count'], 1)
        self.assertEqual(overview['computed']['sample_count'], 1)
        self.assertEqual(overview['computed']['market_window_count'], 1)
        self.assertEqual(overview['computed']['completed_second_reviews'], 1)
        self.assertEqual(overview['computed']['completed_adjudications'], 1)
        self.assertEqual(overview['label_distribution'], {'PRIMARY_DRIVER': 1})
        self.assertEqual(overview['year_distribution'], {'2024': 1})
        self.assertEqual(overview['category_distribution'], {'monetary_policy': 1})
        self.assertEqual(overview['reasoning_chain_sequence'], self.reasoning_chain)

    def test_constructor_builds_release_join_indexes(self):
        repository = MacroEventDashboardRepository(self.output_root)

        self.assertEqual(repository.events_by_id['event-01']['title'], '中国央行宣布降准')
        self.assertEqual(repository.samples_by_id['sample-01']['review_id'], 'review-01')
        self.assertEqual(repository.reviews_by_id['review-01']['final_label'], 'PRIMARY_DRIVER')

    def test_missing_required_artifact_names_the_file(self):
        (self.output_root / 'market_windows.jsonl').unlink()

        with self.assertRaisesRegex(FileNotFoundError, 'market_windows.jsonl'):
            MacroEventDashboardRepository(self.output_root)

    def test_read_jsonl_decodes_utf8_and_skips_blank_lines(self):
        path = self.output_root / 'utf8.jsonl'
        path.write_text(
            '\n' + json.dumps({'title': '中国央行宣布降准'}, ensure_ascii=False) + '\n\n',
            encoding='utf-8',
        )

        self.assertEqual(_read_jsonl(path), [{'title': '中国央行宣布降准'}])


if __name__ == '__main__':
    unittest.main()
