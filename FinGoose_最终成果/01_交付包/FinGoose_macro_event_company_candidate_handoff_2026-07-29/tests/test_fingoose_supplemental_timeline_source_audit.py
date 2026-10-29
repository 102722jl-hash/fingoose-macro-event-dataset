import hashlib
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATTACHMENT = Path(
    r'C:\Users\LL\.codex\attachments\64edc179-4c75-4671-ac15-69f02f83a6e2\pasted-text.txt'
)


class SupplementalTimelineSourceParserTests(unittest.TestCase):
    def test_parses_exactly_fifty_markdown_candidates_and_ignores_example_json(self):
        from fingoose_supplemental_timeline_source_audit import parse_attachment_candidates

        rows = parse_attachment_candidates(ATTACHMENT.read_text(encoding='utf-8'))

        self.assertEqual(len(rows), 50)
        self.assertEqual(len({row['attachment_node_id'] for row in rows}), 50)
        self.assertEqual(
            {event_id: sum(row['attachment_event_id'] == event_id for row in rows)
             for event_id in sorted({row['attachment_event_id'] for row in rows})},
            {f'event-{index:02d}': 5 for index in range(1, 11)},
        )
        self.assertEqual(rows[0]['attachment_node_id'], 'fast-event-01-M01')
        self.assertEqual(rows[-1]['attachment_node_id'], 'fast-event-10-M05')

    def test_preserves_parentheses_inside_direct_url(self):
        from fingoose_supplemental_timeline_source_audit import parse_attachment_candidates

        row = parse_attachment_candidates(ATTACHMENT.read_text(encoding='utf-8'))[0]

        self.assertTrue(row['candidate_url'].endswith('(2019-ncov)'))
        self.assertEqual(row['candidate_url'], row['canonical_url'])

    def test_unwraps_google_q_and_percent_decodes_official_url(self):
        from fingoose_supplemental_timeline_source_audit import canonicalize_candidate_url

        self.assertEqual(
            canonicalize_candidate_url(
                'https://www.google.com/url?sa=E&source=gmail&q='
                'https://www.jtuc-rengo.org/news/news.cgi%3Fid%3D20240315'
            ),
            'https://www.jtuc-rengo.org/news/news.cgi?id=20240315',
        )
        self.assertEqual(
            canonicalize_candidate_url(
                'https://www.google.com/search?q=https://www.sec.gov/Archives/example.htm'
            ),
            'https://www.sec.gov/Archives/example.htm',
        )
        self.assertIsNone(canonicalize_candidate_url('https://www.google.com/search?q=not-a-url'))
        self.assertIsNone(canonicalize_candidate_url('http.mofcom.gov.cn/broken'))


class SupplementalTimelineSourceAuditPolicyTests(unittest.TestCase):
    def test_event_ten_section_301_candidates_are_forced_event_mismatch(self):
        from fingoose_supplemental_timeline_source_audit import apply_audit_policy

        candidate = {
            'attachment_node_id': 'fast-event-10-M01',
            'attachment_event_id': 'event-10',
            'label': '301 tariff action',
            'claimed_quote': 'increasing tariffs on imports from China',
            'candidate_url': 'https://ustr.gov/example',
            'canonical_url': 'https://ustr.gov/example',
            'claimed_at': '2024-05-14T09:00:00Z',
        }
        review = {
            'decision': 'ACCEPT',
            'fact_status': 'VERIFIED',
            'occurred_at_status': 'VERIFIED',
            'first_public_at_status': 'VERIFIED',
            'snapshot_path': 'sources/example.html',
            'sha256': 'a' * 64,
        }

        audited = apply_audit_policy(candidate, review)

        self.assertEqual(audited['decision'], 'REJECT')
        self.assertEqual(audited['reason_code'], 'EVENT_MISMATCH')
        self.assertEqual(audited['semantic_alignment_target'], None)

    def test_market_outcome_candidate_is_observes_only(self):
        from fingoose_supplemental_timeline_source_audit import apply_audit_policy

        candidate = {
            'attachment_node_id': 'fast-event-08-M05',
            'attachment_event_id': 'event-08',
            'label': '套利交易平仓暴跌',
            'claimed_quote': 'Nikkei 225 index dropped 12.4 percent',
            'candidate_url': 'https://www.jpx.co.jp/example.html',
            'canonical_url': 'https://www.jpx.co.jp/example.html',
            'claimed_at': '2024-08-05T06:00:00Z',
        }

        audited = apply_audit_policy(candidate, {})

        self.assertEqual(audited['node_action_constraint'], 'OBSERVES')
        self.assertFalse(audited['can_prove_transmission'])

    def test_accept_requires_snapshot_hash_and_both_time_checks(self):
        from fingoose_supplemental_timeline_source_audit import apply_audit_policy

        candidate = {
            'attachment_node_id': 'fast-event-05-M05',
            'attachment_event_id': 'event-05',
            'label': 'FDIC receivership',
            'claimed_quote': 'assumes all deposits',
            'candidate_url': 'https://www.fdic.gov/example.html',
            'canonical_url': 'https://www.fdic.gov/example.html',
            'claimed_at': '2023-05-01T07:30:00Z',
        }
        incomplete = {
            'decision': 'ACCEPT',
            'fact_status': 'VERIFIED',
            'occurred_at_status': 'VERIFIED',
            'first_public_at_status': 'UNVERIFIED',
            'snapshot_path': None,
            'sha256': None,
        }

        audited = apply_audit_policy(candidate, incomplete)

        self.assertEqual(audited['decision'], 'PENDING')
        self.assertEqual(audited['reason_code'], 'INSUFFICIENT_PROMOTION_EVIDENCE')

    def test_accept_requires_nonempty_values_and_locators_for_both_verified_times(self):
        from fingoose_supplemental_timeline_source_audit import apply_audit_policy

        candidate = {
            'attachment_node_id': 'fast-event-05-M05',
            'attachment_event_id': 'event-05',
            'label': 'FDIC receivership',
            'claimed_quote': 'assumes all deposits',
            'candidate_url': 'https://www.fdic.gov/example.html',
            'canonical_url': 'https://www.fdic.gov/example.html',
            'claimed_at': '2023-05-01T07:30:00Z',
        }
        review = {
            'decision': 'ACCEPT',
            'fact_status': 'VERIFIED',
            'occurred_at_status': 'VERIFIED',
            'occurred_at': None,
            'occurred_at_locator': None,
            'first_public_at_status': 'VERIFIED',
            'first_public_at': None,
            'first_public_at_locator': None,
            'evidence_quote': 'assumes all deposits',
            'evidence_locator': 'snapshot line 10',
            'publisher': 'Federal Deposit Insurance Corporation',
            'source_tier': 'A',
            'snapshot_path': 'sources/example.html',
            'sha256': 'a' * 64,
            'semantic_alignment_target': 'fast-event-05-M05',
        }

        audited = apply_audit_policy(candidate, review)

        self.assertEqual(audited['decision'], 'PENDING')
        self.assertEqual(audited['reason_code'], 'INSUFFICIENT_PROMOTION_EVIDENCE')

    def test_snapshot_hash_is_verified_against_local_bytes(self):
        from fingoose_supplemental_timeline_source_audit import verify_snapshot

        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / 'source.html'
            snapshot.write_bytes(b'official source')
            digest = hashlib.sha256(b'official source').hexdigest()

            self.assertTrue(verify_snapshot(snapshot, digest))
            self.assertFalse(verify_snapshot(snapshot, '0' * 64))
            self.assertFalse(verify_snapshot(snapshot.with_name('missing.html'), digest))


class SupplementalTimelineSourceAuditOutputTests(unittest.TestCase):
    def test_jsonl_writer_is_utf8_and_deterministic(self):
        from fingoose_supplemental_timeline_source_audit import write_jsonl

        rows = [{'b': 2, 'a': '证据'}, {'a': 1}]
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'rows.jsonl'
            write_jsonl(target, rows)
            first = target.read_bytes()
            write_jsonl(target, rows)

            self.assertEqual(first, target.read_bytes())
            self.assertEqual(
                [json.loads(line) for line in target.read_text(encoding='utf-8').splitlines()],
                rows,
            )


if __name__ == '__main__':
    unittest.main()
