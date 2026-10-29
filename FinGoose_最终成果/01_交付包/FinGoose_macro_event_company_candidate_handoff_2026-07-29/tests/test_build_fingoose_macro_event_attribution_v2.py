from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob('*'))
        if path.is_file()
    }


class V2BuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from build_fingoose_macro_event_attribution_v2 import build_dataset

        cls.v1_root = ROOT / 'data' / 'market_event_attribution_v1'
        cls.v1_before = tree_hashes(cls.v1_root)
        cls.production_root = ROOT / 'data' / 'market_event_attribution_v2_candidate'
        cls.production_before = tree_hashes(cls.production_root)
        cls._temporary_directory = tempfile.TemporaryDirectory()
        cls.temporary_root = Path(cls._temporary_directory.name)
        cls.output = cls.temporary_root / 'candidate'
        cls.release_manifest = cls.temporary_root / 'V2_RELEASE_MANIFEST.json'
        build_dataset(
            config_path=ROOT / 'configs' / 'fingoose_macro_events_v1.json',
            v1_market_root=cls.v1_root,
            evidence_root=ROOT / 'evidence_snapshots' / 'macro_event_attribution_v1',
            output_root=cls.output,
            generated_at='2026-07-30T05:10:08+00:00',
            release_manifest_path=cls.release_manifest,
        )

    @classmethod
    def tearDownClass(cls):
        cls._temporary_directory.cleanup()


    def test_emits_complete_candidate_layout_and_preserves_v1(self):
        expected = {
            'event_milestones.jsonl',
            'event_episodes.jsonl',
            'transmission_graphs.jsonl',
            'market_windows.jsonl',
            'benchmark_cases.jsonl',
            'hidden/benchmark_labels.jsonl',
            'source_manifest.jsonl',
            'summary.json',
            'validation_report.json',
            'manifest.json',
        }
        actual = {
            path.relative_to(self.output).as_posix()
            for path in self.output.rglob('*')
            if path.is_file()
        }
        self.assertEqual(actual, expected)
        self.assertEqual(tree_hashes(self.v1_root), self.v1_before)
        self.assertEqual(tree_hashes(self.production_root), self.production_before)

        summary = json.loads((self.output / 'summary.json').read_text(encoding='utf-8'))
        self.assertEqual(summary['dataset_version'], 'fingoose-macro-event-attribution-v2.0')
        self.assertEqual(summary['release_tier'], 'CANDIDATE')
        self.assertFalse(summary['formal_ready'])
        self.assertEqual(summary['event_count'], 10)
        self.assertEqual(summary['hidden_evaluation_event_count'], 3)
        self.assertEqual(summary['challenge_case_count'], 4)
        self.assertEqual(summary['market_window_count'], 40)
        release_manifest = json.loads(
            self.release_manifest.read_text(encoding='utf-8')
        )
        release_files = {
            item['path']: item for item in release_manifest['files']
        }
        for relative in ('README_V2.md', 'START_UI_V2.ps1', 'schemas/fingoose_macro_event_milestone_v2.schema.json'):
            self.assertIn(relative, release_files)
            path = ROOT / relative
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                release_files[relative]['sha256'],
            )


    def test_all_records_validate_and_graphs_are_proposals(self):
        from fingoose_macro_event_attribution_v2 import (
            transmission_graph_errors,
            validate_schema_record,
        )

        mapping = {
            'event_milestones.jsonl': 'milestone',
            'event_episodes.jsonl': 'episode',
            'transmission_graphs.jsonl': 'transmission_graph',
            'market_windows.jsonl': 'market_window',
            'benchmark_cases.jsonl': 'benchmark_case',
            'hidden/benchmark_labels.jsonl': 'benchmark_label',
        }
        for relative, record_type in mapping.items():
            records = read_jsonl(self.output / relative)
            self.assertTrue(records, relative)
            for record in records:
                self.assertEqual(validate_schema_record(record_type, record), [], record)

        for graph in read_jsonl(self.output / 'transmission_graphs.jsonl'):
            self.assertEqual(transmission_graph_errors(graph), [], graph['event_id'])
            self.assertTrue(all(edge['status'] == 'PROPOSED' for edge in graph['edges']))
            self.assertTrue(all(edge['review'] is None for edge in graph['edges']))

        validation = json.loads(
            (self.output / 'validation_report.json').read_text(encoding='utf-8')
        )
        self.assertEqual(validation['cross_record_errors'], [])
        self.assertFalse(validation['hard_failures']['cross_record_invalid'])

    def test_examples_hidden_split_and_public_boundary(self):
        cases = read_jsonl(self.output / 'benchmark_cases.jsonl')
        labels = read_jsonl(self.output / 'hidden' / 'benchmark_labels.jsonl')
        sources = read_jsonl(self.output / 'source_manifest.jsonl')
        source_by_id = {
            (row['event_id'], row['evidence_id']): row for row in sources
        }

        self.assertEqual(
            {case['event_id'] for case in cases if case['split'] == 'EXAMPLE'},
            {'event-02', 'event-03', 'event-04'},
        )
        self.assertEqual(
            {case['event_id'] for case in cases if case['split'] == 'HIDDEN_EVALUATION'},
            {'event-06', 'event-08', 'event-09'},
        )
        self.assertEqual(
            {case['event_id'] for case in cases if case['split'] == 'CHALLENGE'},
            {'event-01', 'event-05', 'event-07', 'event-10'},
        )
        self.assertEqual(len(labels), 10)
        for case in cases:
            self.assertNotIn('visible_milestone_ids', case)
            self.assertTrue(case['visible_evidence_ids'])
            cutoff = case['forecast_cutoff_at']
            for evidence_id in case['visible_evidence_ids']:
                source = source_by_id[(case['event_id'], evidence_id)]
                self.assertLessEqual(source['published_at'], cutoff)
            self.assertNotIn('D5', case['visible_market_windows'])
            self.assertNotIn('D20', case['visible_market_windows'])
            self.assertNotIn('M3', case['visible_market_windows'])
            if case['split'] != 'EXAMPLE':
                self.assertEqual(
                    case['visible_market_windows'], ['T60', 'T20', 'T1'])

        by_event = {case['event_id']: case for case in cases}
        self.assertTrue(by_event['event-03']['challenge_set'])
        self.assertFalse(by_event['event-03']['score_eligible'])
        self.assertFalse(by_event['event-08']['challenge_set'])
        self.assertFalse(by_event['event-08']['score_eligible'])
        self.assertTrue(by_event['event-06']['score_eligible'])
        validation = json.loads(
            (self.output / 'validation_report.json').read_text(encoding='utf-8')
        )
        self.assertFalse(validation['hard_failures']['public_hidden_leakage'])
        self.assertFalse(validation['hard_failures']['non_recomputable_window'])
        self.assertEqual(validation['public_projection_errors'], [])
        notes = ' '.join(validation['notes'])
        self.assertNotIn('null', notes)
        self.assertIn('FRED', notes)
        self.assertIn('SHA-256', notes)


    def test_pilot_timelines_preserve_known_evidence_limits(self):
        milestones = read_jsonl(self.output / 'event_milestones.jsonl')
        grouped = {
            event_id: [row for row in milestones if row['event_id'] == event_id]
            for event_id in ('event-02', 'event-03', 'event-04')
        }
        event02_primary = next(row for row in grouped['event-02'] if row['anchor_role'] == 'PRIMARY')
        self.assertEqual(event02_primary['occurred_at'], '2022-02-24T05:00:00+00:00')
        self.assertIn('NATO', event02_primary['fact'])

        event03_hidden = [row for row in grouped['event-03'] if row['visibility'] == 'HIDDEN_VALIDATION']
        self.assertTrue(any(row['first_public_at'] == '2022-06-17T15:00:00+00:00' for row in event03_hidden))
        event03_primary = next(row for row in grouped['event-03'] if row['anchor_role'] == 'PRIMARY')
        self.assertEqual(event03_primary['expectation']['consensus'], 'UNKNOWN')

        event04_primary = next(row for row in grouped['event-04'] if row['anchor_role'] == 'PRIMARY')
        self.assertIn('provisional', event04_primary['fact'])
        self.assertEqual(event04_primary['expectation']['type'], 'EVOLVING_EVENT')

    def test_pilot_primary_and_secondary_anchors_drive_distinct_graph_edges(self):
        milestones = read_jsonl(self.output / 'event_milestones.jsonl')
        graphs = {
            row['event_id']: row
            for row in read_jsonl(self.output / 'transmission_graphs.jsonl')
        }
        for event_id in ('event-02', 'event-03', 'event-04'):
            event_milestones = [
                row for row in milestones if row['event_id'] == event_id
            ]
            primary = next(row for row in event_milestones if row['anchor_role'] == 'PRIMARY')
            secondary = next(row for row in event_milestones if row['anchor_role'] == 'SECONDARY')
            anchors = {edge['anchor_milestone_id'] for edge in graphs[event_id]['edges']}
            self.assertIn(primary['milestone_id'], anchors)
            self.assertIn(secondary['milestone_id'], anchors)

    def test_episodes_aggregate_milestones_by_event_and_phase(self):
        from build_fingoose_macro_event_attribution_v2 import _build_episodes

        rows = [
            {
                'milestone_id': 'milestone-event-02-000000000001',
                'event_id': 'event-02',
                'phase': 'ESCALATION',
                'occurred_at': '2022-02-24T05:00:00+00:00',
                'sources': [{'evidence_id': 'source-a'}],
            },
            {
                'milestone_id': 'milestone-event-02-000000000002',
                'event_id': 'event-02',
                'phase': 'ESCALATION',
                'occurred_at': '2022-02-26T18:00:00+00:00',
                'sources': [
                    {'evidence_id': 'source-a'},
                    {'evidence_id': 'source-b'},
                ],
            },
            {
                'milestone_id': 'milestone-event-02-000000000003',
                'event_id': 'event-02',
                'phase': 'POLICY_RESPONSE',
                'occurred_at': '2022-02-27T09:00:00+00:00',
                'sources': [{'evidence_id': 'source-c'}],
            },
        ]

        episodes = _build_episodes(rows)

        self.assertEqual(len(episodes), 2)
        escalation = next(
            row for row in episodes if row['phase'] == 'ESCALATION'
        )
        self.assertEqual(escalation['start_at'], '2022-02-24T05:00:00+00:00')
        self.assertEqual(escalation['end_at'], '2022-02-26T18:00:00+00:00')
        self.assertEqual(
            escalation['milestone_ids'],
            [
                'milestone-event-02-000000000001',
                'milestone-event-02-000000000002',
            ],
        )
        self.assertEqual(escalation['evidence_coverage'], ['source-a', 'source-b'])

    def test_windows_have_absolute_values_formula_and_manifest_hashes(self):
        windows = read_jsonl(self.output / 'market_windows.jsonl')
        self.assertEqual(len(windows), 40)
        relative_count = 0
        for row in windows:
            self.assertIn('T-1', row['calculation_basis'])
            self.assertEqual(row['baseline'], {
                'date': row['windows']['T1']['date'],
                'value': row['windows']['T1']['value'],
            })
            self.assertEqual(row['estimation']['window'], 'PREVIOUS_60_SESSIONS')
            self.assertEqual(row['estimation']['observation_count'], 60)
            self.assertIsNotNone(row['estimation']['daily_change_stddev'])
            self.assertTrue(row['observation_source']['hash_verified'])
            self.assertIsNotNone(row['windows']['T60'])
            self.assertIsNotNone(row['windows']['T20'])
            self.assertEqual(
                set(row['windows']),
                {'T60', 'T20', 'T1', 'D1', 'D3', 'D5', 'D20', 'M3'},
            )
            for point in row['windows'].values():
                if point is not None:
                    self.assertIn('date', point)
                    self.assertIn('value', point)
                    self.assertIn('raw_change', point)

                    self.assertIsNotNone(point['standardized_change'])
                    if point['date'] != row['baseline']['date']:
                        self.assertIsNotNone(point['empirical_percentile'])
                    if point['relative_change'] is not None:
                        relative_count += 1
        self.assertGreater(relative_count, 0)
        manifest = json.loads((self.output / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['dataset_version'], 'fingoose-macro-event-attribution-v2.0')
        for item in manifest['files']:
            path = self.output / item['path']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item['sha256'])
            self.assertEqual(
                sum(1 for line in path.read_text(encoding='utf-8').splitlines() if line.strip()),
                item['record_count'],
            )


if __name__ == '__main__':
    unittest.main()

