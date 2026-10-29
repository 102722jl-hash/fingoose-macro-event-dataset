from __future__ import annotations

import copy
import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work' / 'timeline_fast_candidate_v2'


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]


class TimelineFastCandidateReconciliationTests(unittest.TestCase):
    def test_reconciliation_produces_recomputable_three_layer_state(self):
        from reconcile_fingoose_timeline_fast_candidate_v2 import reconcile_workbook

        artifacts = reconcile_workbook(ROOT)
        audit = artifacts['candidate_source_audit']
        manifest = artifacts['candidate_source_manifest']
        nodes = artifacts['timeline_nodes']
        report = artifacts['validation_report']

        self.assertEqual(Counter(row['decision'] for row in audit), {
            'ACCEPTED': 25,
            'PENDING': 23,
            'REJECTED': 2,
        })
        self.assertEqual(
            Counter(row['evidence_status'] for row in nodes),
            {'VERIFIED_EXISTING': 42, 'PENDING_EVIDENCE': 8},
        )
        self.assertEqual(len(artifacts['promotable_milestones']), 18)
        self.assertNotIn(
            'milestone-event-02-a15f1fe4410d',
            {row['milestone_id'] for row in artifacts['promotable_milestones']},
        )
        self.assertEqual(report['hard_failures'], [])
        self.assertEqual(report['verified_existing_count'], 42)
        self.assertEqual(report['pending_evidence_count'], 8)
        self.assertEqual(report['supplemental_accepted_count'], 25)
        self.assertEqual(report['supplemental_rejected_count'], 2)
        self.assertEqual(report['supplemental_pending_count'], 23)

        manifest_by_node = {row['attachment_node_id']: row for row in manifest}
        work = ROOT / 'work' / 'timeline_fast_candidate_v2'
        for row in audit:
            self.assertIn(row['decision'], {'ACCEPTED', 'REJECTED', 'PENDING'})
            mirrored = manifest_by_node[row['attachment_node_id']]
            self.assertEqual(mirrored['decision'], row['decision'])
            self.assertEqual(mirrored['snapshot_path'], row.get('snapshot_path'))
            self.assertEqual(mirrored['sha256'], row.get('sha256'))
            if row['decision'] != 'ACCEPTED':
                continue
            snapshot = work / row['snapshot_path']
            self.assertTrue(snapshot.is_file())

            self.assertTrue(row['evidence_locator'])
            self.assertTrue(row['occurred_at_verification']['value'])
            self.assertTrue(row['occurred_at_verification']['locator'])
            self.assertTrue(row['first_public_at_verification']['value'])
            self.assertTrue(row['first_public_at_verification']['locator'])

        pending_ids = {
            row['fast_node_id']
            for row in nodes
            if row['evidence_status'] == 'PENDING_EVIDENCE'
        }
        self.assertEqual(pending_ids, {
            'fast-event-02-M01',
            'fast-event-05-M01',
            'fast-event-05-M04',
            'fast-event-06-M01',
            'fast-event-07-M05',
            'fast-event-10-M01',
            'fast-event-10-M04',
            'fast-event-10-M05',
        })
        self.assertTrue(all(row['source_ids'] for row in nodes
                            if row['evidence_status'] == 'VERIFIED_EXISTING'))
        self.assertTrue(all(not row['source_ids'] for row in nodes
                            if row['evidence_status'] == 'PENDING_EVIDENCE'))
        self.assertTrue(all(row['visibility'] in {
            'PUBLIC_PREDICTION', 'HIDDEN_VALIDATION', 'UNRESOLVED'
        } for row in nodes))

    def test_invalid_supplemental_updates_restore_production_backed_nodes(self):
        from reconcile_fingoose_timeline_fast_candidate_v2 import reconcile_workbook

        artifacts = reconcile_workbook(ROOT)
        nodes = {row['fast_node_id']: row for row in artifacts['timeline_nodes']}
        production = {
            row['milestone_id']: row
            for row in read_jsonl(
                ROOT / 'data' / 'market_event_attribution_v2_candidate'
                / 'event_milestones.jsonl'
            )
        }
        restored_ids = {
            'fast-event-01-M04',
            'fast-event-02-M03',
            'fast-event-05-M02',
            'fast-event-05-M03',
            'fast-event-10-M02',
        }

        for fast_node_id in restored_ids:
            node = nodes[fast_node_id]
            milestone = production[node['original_milestone_id']]
            self.assertEqual(node['fact'], milestone['fact'])
            self.assertEqual(node['occurred_at'], milestone['occurred_at'])
            self.assertEqual(node['first_public_at'], milestone['first_public_at'])
            self.assertEqual(
                node['source_ids'],
                [source['evidence_id'] for source in milestone['sources']],
            )

    def test_validation_rejects_snapshot_source_manifest_episode_and_report_drift(self):
        from reconcile_fingoose_timeline_fast_candidate_v2 import (
            reconcile_workbook,
            validate_workbook,
        )

        artifacts = reconcile_workbook(ROOT)
        tampered = copy.deepcopy(artifacts)

        accepted = next(
            row for row in tampered['candidate_source_audit']
            if row['decision'] == 'ACCEPTED'
        )
        accepted['snapshot_path'] = 'sources/does-not-exist.html'
        verified = next(
            row for row in tampered['timeline_nodes']
            if row['evidence_status'] == 'VERIFIED_EXISTING'
        )
        verified['source_ids'] = []
        tampered['candidate_source_manifest'][0]['decision'] = 'PENDING'
        tampered['timeline_episodes'][0]['verified_count'] += 1
        tampered['timeline_gap_report']['pending_evidence_count'] += 1

        failures = validate_workbook(ROOT, tampered)

        self.assertIn(
            f'ACCEPTED_SNAPSHOT_MISSING:{accepted["attachment_node_id"]}',
            failures,
        )
        self.assertIn(f'VERIFIED_SOURCE_REQUIRED:{verified["fast_node_id"]}', failures)
        self.assertIn('AUDIT_MANIFEST_STATE_DRIFT:fast-event-01-M01', failures)
        self.assertTrue(any(item.startswith('EPISODE_AGGREGATE_DRIFT:') for item in failures))
        self.assertIn('GAP_REPORT_COUNT_DRIFT:pending_evidence_count', failures)

    def test_episode_aggregates_are_derived_from_current_nodes(self):
        from reconcile_fingoose_timeline_fast_candidate_v2 import reconcile_workbook

        artifacts = reconcile_workbook(ROOT)
        nodes = artifacts['timeline_nodes']
        for episode in artifacts['timeline_episodes']:
            members = [
                row for row in nodes
                if row['fast_node_id'] in episode['fast_node_ids']
            ]
            self.assertEqual(
                episode['verified_count'],
                sum(row['evidence_status'] == 'VERIFIED_EXISTING' for row in members),
            )
            self.assertEqual(
                episode['pending_count'],
                sum(row['evidence_status'] == 'PENDING_EVIDENCE' for row in members),
            )
            self.assertEqual(
                episode['evidence_coverage'],
                list(dict.fromkeys(
                    source_id for row in members for source_id in row['source_ids']
                )),
            )


if __name__ == '__main__':
    unittest.main()
