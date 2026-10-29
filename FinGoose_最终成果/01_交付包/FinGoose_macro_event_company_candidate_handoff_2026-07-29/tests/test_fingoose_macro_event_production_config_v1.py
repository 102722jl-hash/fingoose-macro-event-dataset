import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class MacroEventProductionConfigTests(unittest.TestCase):
    def test_production_config_has_ten_auditable_events_and_pending_human_reviews(self):
        config_path = ROOT / 'configs' / 'fingoose_macro_events_v1.json'
        config = json.loads(config_path.read_text(encoding='utf-8'))

        self.assertEqual(config['expected_event_count'], 10)
        self.assertEqual(config['expected_sample_count'], 40)
        self.assertEqual(len(config['events']), 10)
        self.assertEqual(len({event['event_id'] for event in config['events']}), 10)

        for event in config['events']:
            self.assertTrue(event['occurred_at'])
            self.assertTrue(event['first_public_at'])
            self.assertEqual(len(event['targets']), 4)
            self.assertTrue({'global', 'china'} <= {target['scope'] for target in event['targets']})
            self.assertTrue(all(
                target.get('quote_convention') == 'LOCAL_CURRENCY_PER_USD'
                for target in event['targets'] if target['metric_type'] == 'fx_return_pct'
            ))
            self.assertTrue(any(source['role'] == 'event_fact' and source['tier'] in {1, 2} for source in event['sources']))
            self.assertTrue(any(source['role'] == 'macro_report' and source['tier'] in {1, 2} for source in event['sources']))
            for source in event['sources']:
                snapshot = ROOT / source['local_snapshot_path']
                self.assertTrue(snapshot.is_file(), snapshot)
                self.assertTrue(source['locator']['type'])
                self.assertTrue(source['locator']['value'])
                self.assertEqual(
                    hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                    source['content_sha256'],
                )
            reviews = [target['review'] for target in event['targets'][:3]]
            reviews.append(event['cross_asset_attribution']['review'])
            self.assertTrue(all(review['initial_review']['status'] == 'PENDING' for review in reviews))
    def test_production_build_emits_forty_samples_but_stays_pending_human_review(self):
        from build_fingoose_macro_event_attribution_v1 import build_event_attribution_dataset

        output_root = ROOT / '.test-tmp' / 'macro-event-attribution-v1' / 'production'
        summary = build_event_attribution_dataset(
            ROOT,
            ROOT / 'configs' / 'fingoose_macro_events_v1.json',
            output_root,
        )

        self.assertFalse(summary['formal_ready'])
        self.assertEqual(summary['event_count'], 10)
        self.assertEqual(summary['market_window_count'], 40)
        self.assertEqual(summary['sample_count'], 40)
        self.assertEqual(summary['single_asset_count'], 30)
        self.assertEqual(summary['cross_asset_count'], 10)
        self.assertEqual(summary['hidden_outcome_count'], 40)
        hidden_labels = [
            json.loads(line)
            for line in (output_root / 'hidden_attribution_labels.jsonl').read_text(
                encoding='utf-8',
            ).splitlines()
            if line
        ]
        self.assertEqual(len(hidden_labels), 40)
        self.assertTrue(all(
            row['label_status'] == 'PROVISIONAL' for row in hidden_labels
        ))
        self.assertEqual(summary['gate_failures'], ['INITIAL_REVIEW_REQUIRED', 'SECOND_REVIEW_REQUIRED'])
        public_text = (output_root / 'training_projection.jsonl').read_text(encoding='utf-8')
        self.assertNotIn('"actual_direction"', public_text)



if __name__ == '__main__':
    unittest.main()
