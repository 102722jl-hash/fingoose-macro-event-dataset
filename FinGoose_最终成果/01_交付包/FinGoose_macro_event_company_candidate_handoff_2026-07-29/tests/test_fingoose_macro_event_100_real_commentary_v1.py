from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MacroEvent100RealCommentaryTests(unittest.TestCase):
    def test_real_event_commentary_retains_prediction_and_counterevidence(self):
        from build_fingoose_macro_event_attribution_v1 import _market_window
        from fingoose_macro_event_100_pipeline_v1 import build_final_commentary
        from fingoose_macro_event_100_variations_v1 import build_event_variations

        event = json.loads((ROOT / 'configs' / 'fingoose_macro_events_v1.json').read_text(encoding='utf-8'))['events'][0]
        windows = {
            target['series_id']: _market_window(ROOT, event, target)
            for target in event['targets']
        }
        record = build_event_variations(event, windows)[0]
        commentary = build_final_commentary(event, record)

        self.assertIn('短期判断', commentary)
        self.assertIn(record['short_horizon_prediction']['target_series_id'], commentary)
        self.assertIn('反证', commentary)
        self.assertTrue(150 <= len(commentary) <= 300)


if __name__ == '__main__':
    unittest.main()
