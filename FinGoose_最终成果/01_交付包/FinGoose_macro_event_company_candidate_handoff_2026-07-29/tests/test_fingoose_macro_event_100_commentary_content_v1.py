from __future__ import annotations

import unittest

from tests.test_fingoose_macro_event_100_variations_v1 import MacroEvent100VariationTests


class MacroEvent100CommentaryContentTests(unittest.TestCase):
    def test_commentary_includes_prediction_before_the_length_limit(self):
        from fingoose_macro_event_100_pipeline_v1 import build_final_commentary
        from fingoose_macro_event_100_variations_v1 import build_event_variations

        event = MacroEvent100VariationTests._event()
        record = build_event_variations(event, MacroEvent100VariationTests._windows())[0]
        commentary = build_final_commentary(event, record)

        self.assertIn('短期判断', commentary)
        self.assertIn(record['short_horizon_prediction']['target_series_id'], commentary)
        self.assertLessEqual(len(commentary), 300)


if __name__ == '__main__':
    unittest.main()
