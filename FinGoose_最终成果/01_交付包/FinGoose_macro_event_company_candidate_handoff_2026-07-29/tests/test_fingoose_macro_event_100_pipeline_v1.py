from __future__ import annotations

import unittest

from tests.test_fingoose_macro_event_100_variations_v1 import MacroEvent100VariationTests


class MacroEvent100PipelineTests(unittest.TestCase):
    def test_public_commentary_is_chinese_and_hidden_outcome_isolated(self):
        from fingoose_macro_event_100_pipeline_v1 import (
            build_final_commentary,
            validate_public_candidate,
        )
        from fingoose_macro_event_100_variations_v1 import build_event_variations

        event = MacroEvent100VariationTests._event()
        record = build_event_variations(event, MacroEvent100VariationTests._windows())[0]
        record['final_commentary'] = build_final_commentary(event, record)
        manifest = {source['source_id']: source for source in event['sources']}

        self.assertGreaterEqual(len(record['final_commentary']), 150)
        self.assertLessEqual(len(record['final_commentary']), 300)
        self.assertTrue(any('\u4e00' <= char <= '\u9fff' for char in record['final_commentary']))
        self.assertNotIn('D20', record['final_commentary'])
        self.assertEqual(validate_public_candidate(record, manifest), [])

    def test_public_validator_rejects_hidden_outcome_token_and_future_evidence(self):
        from fingoose_macro_event_100_pipeline_v1 import validate_public_candidate
        from fingoose_macro_event_100_variations_v1 import build_event_variations

        event = MacroEvent100VariationTests._event()
        record = build_event_variations(event, MacroEvent100VariationTests._windows())[0]
        record['final_commentary'] = '这是含有实际结果的错误短评 actual_direction=UP。'
        record['forecast_as_of_at'] = '2024-03-17T23:59:59+00:00'
        manifest = {source['source_id']: source for source in event['sources']}

        errors = validate_public_candidate(record, manifest)

        self.assertIn('HIDDEN_OUTCOME_LEAKAGE', errors)
        self.assertIn('FUTURE_VISIBLE_EVIDENCE', errors)


if __name__ == '__main__':
    unittest.main()
