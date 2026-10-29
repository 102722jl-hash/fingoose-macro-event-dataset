from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BuildMacroEvent100CandidateTests(unittest.TestCase):
    def test_build_writes_one_hundred_pending_candidates_and_isolated_outcomes(self):
        from build_fingoose_macro_event_100_candidate_v1 import build_macro_event_100_dataset

        output_root = ROOT / '.test-tmp' / 'macro-event-100-e2e'
        output_root.mkdir(parents=True, exist_ok=True)
        summary = build_macro_event_100_dataset(
            ROOT,
            ROOT / 'configs' / 'fingoose_macro_events_v1.json',
            output_root,
        )
        records = self._read_jsonl(output_root / 'macro_candidates.jsonl')
        hidden = self._read_jsonl(output_root / 'hidden_outcomes.jsonl')

        self.assertEqual((summary['event_count'], summary['sample_count']), (10, 100))
        self.assertEqual(summary['samples_per_event'], 10)
        self.assertEqual(len(records), 100)
        self.assertEqual(len(hidden), 100)
        self.assertEqual(summary['rejected_count'], 0)
        self.assertTrue(summary['ready_for_human_review'])
        self.assertTrue(all(row['review_status'] == 'PENDING_HUMAN_REVIEW' for row in records))
        self.assertNotIn('actual_direction', json.dumps(records, ensure_ascii=True))
        self.assertNotIn('D20', json.dumps(records, ensure_ascii=True))

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


if __name__ == '__main__':
    unittest.main()


