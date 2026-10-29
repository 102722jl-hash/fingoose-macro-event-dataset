from __future__ import annotations

import unittest


class MacroEvent100CandidateTests(unittest.TestCase):
    def test_validate_candidate_requires_two_supporting_observations_and_counterevidence(self):
        from fingoose_macro_event_100_candidate_v1 import validate_candidate_record

        record = {
            'supporting_observations': [{'series_id': 'SP500'}],
            'counterevidence': [],
            'review_status': 'PENDING_HUMAN_REVIEW',
        }

        errors = validate_candidate_record(record, {})

        self.assertIn('SUPPORTING_OBSERVATIONS_INSUFFICIENT', errors)
        self.assertIn('COUNTEREVIDENCE_REQUIRED', errors)


if __name__ == '__main__':
    unittest.main()
