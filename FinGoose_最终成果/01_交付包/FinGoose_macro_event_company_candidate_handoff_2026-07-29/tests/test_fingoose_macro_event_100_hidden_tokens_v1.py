from __future__ import annotations

import unittest

from tests.test_fingoose_macro_event_100_variations_v1 import MacroEvent100VariationTests


class MacroEvent100HiddenTokenTests(unittest.TestCase):
    def test_validator_does_not_treat_semantic_hash_text_as_hidden_outcome(self):
        from fingoose_macro_event_100_pipeline_v1 import (
            build_final_commentary,
            validate_public_candidate,
        )
        from fingoose_macro_event_100_variations_v1 import build_event_variations

        event = MacroEvent100VariationTests._event()
        record = build_event_variations(event, MacroEvent100VariationTests._windows())[0]
        record['semantic_fingerprint'] = 'f00dd20a' * 8
        record['final_commentary'] = build_final_commentary(event, record)
        manifest = {source['source_id']: source for source in event['sources']}

        self.assertNotIn('HIDDEN_OUTCOME_LEAKAGE', validate_public_candidate(record, manifest))


if __name__ == '__main__':
    unittest.main()
