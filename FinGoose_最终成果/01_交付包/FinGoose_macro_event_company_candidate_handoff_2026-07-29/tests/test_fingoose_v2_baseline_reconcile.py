from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BaselineReconcileTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary.name)
        self.data = self.root / 'data'
        self.data.mkdir()
        (self.data / 'event_milestones.jsonl').write_text(
            '{"event_id":"event-01"}\n{"event_id":"event-02"}\n',
            encoding='utf-8',
        )
        (self.data / 'event_episodes.jsonl').write_text(
            '{"episode_id":"episode-01"}\n', encoding='utf-8'
        )
        self.manifest = {
            'dataset_version': 'candidate-test',
            'release_tier': 'CANDIDATE',
            'schema_version': '2020-12',
            'generated_at': '2026-07-30T00:00:00+00:00',
            'files': [
                {
                    'path': 'event_episodes.jsonl',
                    'sha256': sha256(self.data / 'event_episodes.jsonl'),
                    'record_count': 1,
                },
                {
                    'path': 'event_milestones.jsonl',
                    'sha256': sha256(self.data / 'event_milestones.jsonl'),
                    'record_count': 2,
                },
            ],
            'counts': {'events': 2, 'milestones': 2, 'episodes': 1},
        }
        self.manifest_path = self.data / 'manifest.json'
        self.write_manifest()

    def tearDown(self):
        self._temporary.cleanup()

    def write_manifest(self):
        self.manifest_path.write_text(
            json.dumps(self.manifest, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )

    def test_valid_manifest_is_ready_for_baseline_approval(self):
        from fingoose_v2_baseline_reconcile import audit_manifest

        result = audit_manifest(self.data, self.manifest_path)

        self.assertEqual(result['status'], 'READY_FOR_BASELINE_APPROVAL')
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['rebuilt_manifest'], self.manifest)

    def test_hash_mismatch_blocks(self):
        from fingoose_v2_baseline_reconcile import audit_manifest

        self.manifest['files'][0]['sha256'] = '0' * 64
        self.write_manifest()

        result = audit_manifest(self.data, self.manifest_path)

        self.assertIn('HASH_MISMATCH:event_episodes.jsonl', result['errors'])
        self.assertEqual(result['status'], 'BLOCKED')

    def test_record_count_mismatch_blocks(self):
        from fingoose_v2_baseline_reconcile import audit_manifest

        self.manifest['files'][1]['record_count'] = 3
        self.write_manifest()

        result = audit_manifest(self.data, self.manifest_path)

        self.assertIn('RECORD_COUNT_MISMATCH:event_milestones.jsonl', result['errors'])

    def test_missing_file_blocks(self):
        from fingoose_v2_baseline_reconcile import audit_manifest

        (self.data / 'event_episodes.jsonl').unlink()

        result = audit_manifest(self.data, self.manifest_path)

        self.assertIn('MISSING_FILE:event_episodes.jsonl', result['errors'])

    def test_path_escape_blocks_without_reading_outside_data_root(self):
        from fingoose_v2_baseline_reconcile import audit_manifest

        outside = self.root / 'outside.jsonl'
        outside.write_text('{}\n', encoding='utf-8')
        self.manifest['files'].append({
            'path': '../outside.jsonl',
            'sha256': sha256(outside),
            'record_count': 1,
        })
        self.write_manifest()

        result = audit_manifest(self.data, self.manifest_path)

        self.assertIn('PATH_ESCAPE:../outside.jsonl', result['errors'])

    def test_write_reconciliation_keeps_data_tree_unchanged(self):
        from fingoose_v2_baseline_reconcile import audit_manifest, write_reconciliation

        before = {path.name: sha256(path) for path in self.data.iterdir()}
        result = audit_manifest(self.data, self.manifest_path)
        output = self.root / 'work'

        write_reconciliation(result, output, frozen_manifest_sha256='f' * 64)

        after = {path.name: sha256(path) for path in self.data.iterdir()}
        self.assertEqual(after, before)
        self.assertTrue((output / 'manifest.rebuilt.json').is_file())
        transition = json.loads((output / 'baseline_transition.json').read_text('utf-8'))
        self.assertEqual(transition['status'], 'READY_FOR_BASELINE_APPROVAL')
        self.assertEqual(transition['frozen_manifest_sha256'], 'f' * 64)


if __name__ == '__main__':
    unittest.main()