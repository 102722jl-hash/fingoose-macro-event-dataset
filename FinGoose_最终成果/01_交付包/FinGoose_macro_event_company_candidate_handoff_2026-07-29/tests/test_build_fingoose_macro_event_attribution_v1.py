import csv
import hashlib
import json
import unittest
from datetime import date, timedelta
from pathlib import Path


class MacroEventDatasetBuilderTests(unittest.TestCase):
    def test_fred_csv_reader_uses_series_column_and_skips_missing_values(self):
        from build_fingoose_macro_event_attribution_v1 import _read_observations

        root = self._test_root('fred-reader')
        path = root / 'fred.csv'
        path.write_text('observation_date,DGS10\n2024-01-02,3.95\n2024-01-03,.\n', encoding='utf-8')

        rows = _read_observations(path)

        self.assertEqual(rows, [{'date': '2024-01-02', 'value': 3.95}])

    def test_builder_emits_three_single_one_cross_and_hidden_forecast_outcomes(self):

        from build_fingoose_macro_event_attribution_v1 import build_event_attribution_dataset
        root = self._test_root('builder-success')
        config_path = self._write_fixture(root)
        summary = build_event_attribution_dataset(root, config_path, root / 'outputs')

        self.assertTrue(summary['formal_ready'])
        self.assertEqual((summary['event_count'], summary['market_window_count']), (1, 4))
        self.assertEqual((summary['sample_count'], summary['single_asset_count'], summary['cross_asset_count']), (4, 3, 1))
        public_rows = self._read_jsonl(root / 'outputs' / 'training_projection.jsonl')
        hidden_rows = self._read_jsonl(root / 'outputs' / 'hidden_forecast_outcomes.jsonl')
        self.assertEqual((len(public_rows), len(hidden_rows)), (4, 4))
        self.assertNotIn('hidden_forecast_outcome', json.dumps(public_rows))
        self.assertTrue(all(row['forecast_reasoning_chain']['sequence'][-1] == 'SHORT_TERM_PREDICTION' for row in public_rows))
        dossier = self._read_jsonl(root / 'outputs' / 'event_dossiers.jsonl')[0]
        self.assertEqual(dossier['occurred_at'], '2024-03-19T04:00:00+00:00')
        self.assertEqual(dossier['first_public_at'], '2024-03-19T04:00:00+00:00')
        market_rows = self._read_jsonl(root / 'outputs' / 'market_windows.jsonl')
        fx_series = [row['series'] for row in market_rows if row['metric_type'] == 'fx_return_pct']
        self.assertEqual(len(fx_series), 1)
        self.assertEqual(fx_series[0]['quote_convention'], 'LOCAL_CURRENCY_PER_USD')
        reviews = self._read_jsonl(root / 'outputs' / 'review_records.jsonl')
        low_confidence = next(row for row in reviews if row['confidence'] == 'LOW')
        self.assertEqual(low_confidence['second_review_trigger_reasons'], ['LOW_CONFIDENCE'])

    def test_builder_rejects_tier_three_only_event_and_unfinished_second_review(self):
        from build_fingoose_macro_event_attribution_v1 import build_event_attribution_dataset

        root = self._test_root('builder-rejection')
        config_path = self._write_fixture(root)
        config = json.loads(config_path.read_text(encoding='utf-8'))
        config['events'][0]['sources'][0]['tier'] = 3
        config['events'][0]['targets'][2]['review']['second_review'] = None
        config_path.write_text(json.dumps(config), encoding='utf-8')

        summary = build_event_attribution_dataset(root, config_path, root / 'outputs')

        self.assertFalse(summary['formal_ready'])
        self.assertIn('EVENT_REQUIRES_TIER_1_OR_2_SOURCE', summary['gate_failures'])
        self.assertIn('SECOND_REVIEW_REQUIRED', summary['gate_failures'])

    @staticmethod
    def _test_root(name):
        root = Path('.test-tmp') / 'macro-event-attribution-v1' / name
        root.mkdir(parents=True, exist_ok=True)
        return root

    @staticmethod
    def _read_jsonl(path):
        return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]

    @classmethod
    def _write_fixture(cls, root):
        source_dir = root / 'inputs' / 'sources'
        market_dir = root / 'inputs' / 'market'
        source_dir.mkdir(parents=True, exist_ok=True)
        market_dir.mkdir(parents=True, exist_ok=True)
        sources = []
        for source_id, role, published_at in (
            ('event-source', 'event_fact', '2024-03-19T04:00:00+00:00'),
            ('report-1', 'macro_report', '2024-03-18T10:00:00+00:00'),
        ):
            snapshot = source_dir / f'{source_id}.txt'
            content = f'Archived public source for {source_id}.\n'.encode()
            snapshot.write_bytes(content)
            sources.append({
                'source_id': source_id, 'role': role, 'tier': 1 if role == 'event_fact' else 2,
                'publisher': 'Fixture Institution', 'title': source_id,
                'source_url': f'https://example.org/{source_id}', 'published_at': published_at,
                'local_snapshot_path': snapshot.relative_to(root).as_posix(),
                'content_sha256': hashlib.sha256(content).hexdigest(),
                'locator': {'type': 'text', 'value': 'entire fixture'},
                'summary': 'Policy and macro conditions are relevant to the event transmission.',
            })
        targets = cls._write_market_targets(root, market_dir)
        config_path = root / 'config.json'
        config_path.write_text(json.dumps(cls._config(sources, targets)), encoding='utf-8')
        return config_path

    @staticmethod
    def _write_market_targets(root, market_dir):
        targets = []
        labels = ['PRIMARY_DRIVER', 'CONTRIBUTING_FACTOR', 'WEAK_RELATION', 'UNSUPPORTED']
        confidences = ['HIGH', 'MEDIUM', 'LOW', 'MEDIUM']
        for target_index in range(4):
            series_id = f'SERIES{target_index + 1}'
            path = market_dir / f'{series_id}.csv'
            with path.open('w', encoding='utf-8', newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow(['date', 'value'])
                value = 100 + target_index
                day = date(2023, 12, 1)
                for offset in range(150):
                    current = day + timedelta(days=offset)
                    if current.weekday() < 5:
                        value += 0.2 + (offset % 3) * 0.05
                        writer.writerow([current.isoformat(), round(value, 4)])
            low_or_disputed = confidences[target_index] == 'LOW'
            targets.append({
                'series_id': series_id,
                'series_name': f'Series {target_index + 1}',
                'scope': 'china' if target_index == 3 else 'global',
                'metric_type': 'fx_return_pct' if target_index == 3 else 'price_return_pct',
                'quote_convention': 'LOCAL_CURRENCY_PER_USD' if target_index == 3 else None,
                'market_timezone': 'UTC',
                'market_close_hour': 16,
                'observation_path': path.relative_to(root).as_posix(),
                'expected_d3_direction': 'UP',
                'attribution': {
                    'label': labels[target_index],
                    'confidence': confidences[target_index],
                    'channels': ['RATE_DIFFERENTIAL'],
                    'counterevidence': ['Other macro releases may explain part of the move.'],
                },
                'short_term_prediction': {
                    'direction': 'UP', 'confidence': 'MEDIUM',
                    'invalidation_conditions': ['The observed transmission reverses.'],
                },
                'review': {
                    'initial_review': {
                        'reviewer_id': 'analyst-1',
                        'status': 'APPROVED',
                        'reviewed_at': '2024-03-20T10:00:00+00:00',
                        'comments': 'The fixture evidence and all core dimensions were reviewed.',
                        'label': labels[target_index],
                        'confidence': confidences[target_index],
                        'core_dimensions': {
                            'temporal_alignment': 'SUPPORTED',
                            'abnormal_movement': 'SUPPORTED',
                            'transmission_mechanism': 'SUPPORTED',
                            'competing_explanations': (
                                'MIXED' if low_or_disputed else 'LIMITED'
                            ),
                        },
                    },
                    'second_review': {
                        'reviewer_id': 'analyst-2',
                        'status': 'APPROVED',
                        'reviewed_at': '2024-03-20T11:00:00+00:00',
                        'comments': 'An independent fixture review reached the same verdict.',
                        'label': labels[target_index],
                        'confidence': confidences[target_index],
                        'core_dimensions': {
                            'temporal_alignment': 'SUPPORTED',
                            'abnormal_movement': 'SUPPORTED',
                            'transmission_mechanism': 'SUPPORTED',
                            'competing_explanations': 'MIXED',
                        },
                    } if low_or_disputed else None,
                    'core_dimensions': {
                        'temporal_alignment': 'SUPPORTED',
                        'abnormal_movement': 'SUPPORTED',
                        'transmission_mechanism': 'SUPPORTED',
                        'competing_explanations': 'MIXED' if low_or_disputed else 'LIMITED',
                    },
                },
            })
        return targets

    @staticmethod
    def _config(sources, targets):
        return {
            'dataset_version': 'fingoose-macro-event-attribution-v1.0',
            'expected_event_count': 1,
            'expected_sample_count': 4,
            'events': [{
                'event_id': 'event-01',
                'title': 'Fixture policy normalization event',
                'category': 'monetary_policy',
                'anchor_at': '2024-03-19T04:00:00+00:00',
                'phase': 'announcement',
                'candidate_channels': ['RATE_DIFFERENTIAL', 'RISK_APPETITE'],
                'sources': sources,
                'period_summary': 'The first three tradable sessions after the event.',
                'transmission_nodes': [
                    {'node_id': 'n1', 'node_type': 'event', 'statement': 'The policy regime changed.'},
                    {'node_id': 'n2', 'node_type': 'mechanism', 'statement': 'Rate expectations adjusted.'},
                    {'node_id': 'n3', 'node_type': 'market', 'statement': 'Multiple markets repriced.'},
                ],
                'transmission_edges': [
                    {'from_node_id': 'n1', 'to_node_id': 'n2', 'relation': 'CAUSES'},
                    {'from_node_id': 'n2', 'to_node_id': 'n3', 'relation': 'TRANSMITS_TO'},
                ],
                'targets': targets,
                'cross_asset_attribution': {
                    'label': 'UNSUPPORTED',
                    'confidence': 'MEDIUM',
                    'channels': ['RISK_APPETITE'],
                    'counterevidence': ['Cross-asset moves were not fully aligned.'],
                    'forecast_target_series_id': 'SERIES1',
                    'short_term_prediction': {
                        'direction': 'UP', 'confidence': 'MEDIUM',
                        'invalidation_conditions': ['Cross-asset confirmation weakens.'],
                    },
                    'review': {
                        'initial_review': {
                            'reviewer_id': 'analyst-1',
                            'status': 'APPROVED',
                            'reviewed_at': '2024-03-20T10:00:00+00:00',
                            'comments': 'The fixture evidence and all core dimensions were reviewed.',
                            'label': 'UNSUPPORTED',
                            'confidence': 'MEDIUM',
                            'core_dimensions': {
                                'temporal_alignment': 'SUPPORTED',
                                'abnormal_movement': 'SUPPORTED',
                                'transmission_mechanism': 'SUPPORTED',
                                'competing_explanations': 'LIMITED',
                            },
                        },
                        'second_review': None,
                        'core_dimensions': {
                            'temporal_alignment': 'SUPPORTED',
                            'abnormal_movement': 'SUPPORTED',
                            'transmission_mechanism': 'SUPPORTED',
                            'competing_explanations': 'LIMITED',
                        },
                    },
                },
            }],
        }


if __name__ == '__main__':
    unittest.main()
