import copy
import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATTACHMENT = Path(
    r'C:\Users\LL\.codex\attachments\64edc179-4c75-4671-ac15-69f02f83a6e2\pasted-text.txt'
)
WORK = ROOT / 'work' / 'timeline_fast_candidate_v2'


class SupplementalTimelineSourceAuditBuildTests(unittest.TestCase):
    def test_build_audit_accepts_three_rejects_known_mismatches_and_keeps_rest_pending(self):
        from build_fingoose_supplemental_timeline_source_audit import build_candidate_audit
        from fingoose_supplemental_timeline_source_audit import parse_attachment_candidates

        candidates = parse_attachment_candidates(ATTACHMENT.read_text(encoding='utf-8'))
        rows = build_candidate_audit(candidates, WORK / 'sources')

        counts = {
            decision: sum(row['decision'] == decision for row in rows)
            for decision in ('ACCEPT', 'REJECT', 'PENDING')
        }
        self.assertEqual(counts, {'ACCEPT': 3, 'REJECT': 6, 'PENDING': 41})
        self.assertEqual(
            {row['attachment_node_id'] for row in rows if row['decision'] == 'ACCEPT'},
            {'fast-event-03-M01', 'fast-event-03-M02', 'fast-event-09-M01'},
        )
        self.assertTrue(all(
            'google.com' not in (row['canonical_url'] or '') for row in rows
        ))
        failed = next(row for row in rows if row['attachment_node_id'] == 'fast-event-04-M01')
        self.assertIsNone(failed['snapshot_path'])
        self.assertIsNone(failed['sha256'])
        self.assertEqual(failed['reason_code'], 'SOURCE_RETRIEVAL_FAILED')
        wrong_document = next(
            row for row in rows if row['attachment_node_id'] == 'fast-event-02-M04'
        )
        self.assertEqual(wrong_document['decision'], 'REJECT')
        self.assertEqual(wrong_document['reason_code'], 'SOURCE_MISMATCH')

    def test_current_node_semantic_targets_are_one_to_one(self):
        from fingoose_supplemental_timeline_source_audit_build_core import SEMANTIC_TARGETS

        current_targets = [
            target for target in SEMANTIC_TARGETS.values()
            if target and target.startswith('fast-event-')
        ]

        self.assertEqual(len(current_targets), len(set(current_targets)))
        self.assertEqual(
            SEMANTIC_TARGETS['fast-event-03-M03'],
            'NEW_NODE_CANDIDATE:event-03:FIRST_HIKE',
        )
        self.assertEqual(
            SEMANTIC_TARGETS['fast-event-06-M04'],
            'NEW_NODE_CANDIDATE:event-06:CUT_EXTENSION',
        )

    def test_upgrades_only_semantically_mapped_current_nodes(self):
        from build_fingoose_supplemental_timeline_source_audit import (
            build_candidate_audit,
            upgrade_timeline_nodes,
        )
        from fingoose_supplemental_timeline_source_audit import parse_attachment_candidates

        candidates = parse_attachment_candidates(ATTACHMENT.read_text(encoding='utf-8'))
        audit = build_candidate_audit(candidates, WORK / 'sources')
        nodes = [
            json.loads(line)
            for line in (WORK / 'timeline_nodes.jsonl').read_text(encoding='utf-8').splitlines()
        ]

        updated = upgrade_timeline_nodes(nodes, audit)

        self.assertEqual(len(updated), 50)
        self.assertEqual(
            sum(row['evidence_status'] == 'VERIFIED_EXISTING' for row in updated), 24
        )
        self.assertEqual(
            sum(row['evidence_status'] == 'PENDING_EVIDENCE' for row in updated), 26
        )
        mapped = {row['fast_node_id']: row for row in updated}
        self.assertEqual(
            mapped['fast-event-03-M01']['source_ids'],
            ['supplemental-fast-event-03-M01'],
        )
        self.assertEqual(
            mapped['fast-event-03-M02']['occurred_at'], '2022-02-10T13:30:00Z'
        )
        self.assertEqual(mapped['fast-event-09-M02']['node_action'], 'OBSERVES')
        self.assertEqual(mapped['fast-event-09-M02']['source_ids'], [
            'supplemental-fast-event-09-M01'
        ])

    def test_regenerated_outputs_are_valid_and_keep_fast_candidate_boundary(self):
        from build_fingoose_supplemental_timeline_source_audit import build_artifacts

        artifacts = build_artifacts(ROOT, ATTACHMENT)

        self.assertEqual(len(artifacts['candidate_source_audit']), 50)
        self.assertEqual(len(artifacts['timeline_nodes']), 50)
        self.assertEqual(len(artifacts['promotable_milestones']), 18)
        self.assertEqual(
            sum(row['evidence_status'] == 'VERIFIED_EXISTING'
                for row in artifacts['timeline_nodes']),
            24,
        )
        self.assertEqual(
            sum(row['evidence_status'] == 'PENDING_EVIDENCE'
                for row in artifacts['timeline_nodes']),
            26,
        )
        self.assertEqual(artifacts['validation_report']['release_tier'], 'FAST_CANDIDATE')
        self.assertFalse(artifacts['validation_report']['formal_ready'])
        self.assertFalse(artifacts['validation_report']['production_dataset_modified'])
        self.assertEqual(artifacts['validation_report']['hard_failures'], [])
        self.assertEqual(artifacts['timeline_gap_report']['pending_evidence_count'], 26)
        self.assertEqual(
            artifacts['validation_report']['supplemental_rejected_count'], 6
        )
        self.assertEqual(
            artifacts['validation_report']['supplemental_pending_count'], 41
        )

        promoted_node_ids = {
            row['fast_node_id'] for row in artifacts['timeline_nodes']
            if row['promotion_eligible']
        }
        self.assertIn('fast-event-09-M02', promoted_node_ids)
        self.assertTrue(all(
            row['evidence_status'] == 'VERIFIED_EXISTING'
            and row['occurred_at']
            and row['first_public_at']
            and row['visibility'] != 'UNRESOLVED'
            and row['source_ids']
            and not row['gap_reason']
            for row in artifacts['timeline_nodes']
            if row['promotion_eligible']
        ))

        work = ROOT / 'work' / 'timeline_fast_candidate_v2'
        for row in artifacts['candidate_source_audit']:
            if row['decision'] != 'ACCEPT':
                continue
            self.assertFalse(row['semantic_alignment_target'].startswith('NEW_NODE_CANDIDATE:'))
            self.assertTrue(row['evidence_locator'])
            self.assertTrue(row['occurred_at_verification']['value'])
            self.assertTrue(row['occurred_at_verification']['locator'])
            self.assertTrue(row['first_public_at_verification']['value'])
            self.assertTrue(row['first_public_at_verification']['locator'])
            snapshot = work / row['snapshot_path']
            self.assertTrue(snapshot.is_file())
            self.assertEqual(hashlib.sha256(snapshot.read_bytes()).hexdigest(), row['sha256'])

    def test_validation_hard_fails_invalid_acceptance_and_illegal_promotion(self):
        from build_fingoose_supplemental_timeline_source_audit import (
            build_artifacts,
            build_validation_report,
        )

        artifacts = build_artifacts(ROOT, ATTACHMENT)
        audit = copy.deepcopy(artifacts['candidate_source_audit'])
        nodes = copy.deepcopy(artifacts['timeline_nodes'])
        accepted = next(row for row in audit if row['decision'] == 'ACCEPT')
        accepted['evidence_locator'] = None
        accepted['sha256'] = '0' * 64
        pending = next(row for row in nodes if row['evidence_status'] == 'PENDING_EVIDENCE')
        pending['promotion_eligible'] = True

        report = build_validation_report(
            ROOT,
            nodes,
            artifacts['timeline_episodes'],
            artifacts['promotable_milestones'],
            audit,
        )

        self.assertIn(
            f'ACCEPTED_EVIDENCE_INCOMPLETE:{accepted["attachment_node_id"]}',
            report['hard_failures'],
        )
        self.assertIn(
            f'ACCEPTED_SNAPSHOT_HASH_MISMATCH:{accepted["attachment_node_id"]}',
            report['hard_failures'],
        )
        self.assertIn(
            f'PROMOTION_GATE:{pending["fast_node_id"]}',
            report['hard_failures'],
        )


if __name__ == '__main__':
    unittest.main()
