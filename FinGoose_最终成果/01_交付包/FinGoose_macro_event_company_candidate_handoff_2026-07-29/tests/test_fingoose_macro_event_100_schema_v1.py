from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.test_fingoose_macro_event_100_variations_v1 import MacroEvent100VariationTests


ROOT = Path(__file__).resolve().parents[1]


class MacroEvent100SchemaTests(unittest.TestCase):
    def test_generated_public_candidate_matches_strict_schema(self):
        import jsonschema
        from fingoose_macro_event_100_pipeline_v1 import build_final_commentary
        from fingoose_macro_event_100_variations_v1 import build_event_variations

        schema = json.loads((ROOT / 'schemas' / 'fingoose_macro_event_100_candidate_v1.schema.json').read_text(encoding='utf-8'))
        event = MacroEvent100VariationTests._event()
        record = build_event_variations(event, MacroEvent100VariationTests._windows())[0]
        record['final_commentary'] = build_final_commentary(event, record)

        jsonschema.Draft202012Validator(schema).validate(record)


if __name__ == '__main__':
    unittest.main()
