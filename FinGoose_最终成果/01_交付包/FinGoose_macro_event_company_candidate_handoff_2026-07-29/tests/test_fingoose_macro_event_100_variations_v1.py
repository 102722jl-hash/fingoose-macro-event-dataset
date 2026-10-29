from __future__ import annotations

from collections import Counter
import unittest


class MacroEvent100VariationTests(unittest.TestCase):
    def test_build_event_variations_emits_ten_distinct_quota_controlled_records(self):
        from fingoose_macro_event_100_variations_v1 import build_event_variations

        records = build_event_variations(self._event(), self._windows())

        self.assertEqual(len(records), 10)
        self.assertEqual(Counter(row['sample_kind'] for row in records), {
            'single_target': 4,
            'cross_asset': 2,
            'channel_check': 2,
            'counterfactual': 2,
        })
        self.assertEqual(len({row['semantic_fingerprint'] for row in records}), 10)
        self.assertTrue(all(
            len(row['supporting_observations']) >= 2
            and row['counterevidence']
            and row['review_status'] == 'PENDING_HUMAN_REVIEW'
            for row in records
        ))

    @staticmethod
    def _event():
        targets = []
        for index, series_id in enumerate(('SP500', 'VIXCLS', 'DCOILWTICO', 'DEXCHUS')):
            targets.append({
                'series_id': series_id,
                'series_name': series_id,
                'scope': 'china' if index == 3 else 'global',
                'expected_d3_direction': 'UP' if index == 1 else 'DOWN',
                'attribution': {
                    'label': 'CONTRIBUTING_FACTOR',
                    'confidence': 'MEDIUM',
                    'channels': ['RISK_APPETITE', 'GLOBAL_DEMAND'],
                    'counterevidence': [f'Competing explanation for {series_id}.'],
                },
                'short_term_prediction': {
                    'direction': 'UP' if index == 1 else 'DOWN',
                    'confidence': 'MEDIUM',
                    'invalidation_conditions': ['The transmission weakens.'],
                },
            })
        return {
            'event_id': 'event-01',
            'title': 'Fixture macro event',
            'candidate_channels': ['RISK_APPETITE', 'GLOBAL_DEMAND'],
            'sources': [
                {'source_id': 'event-source', 'published_at': '2024-03-19T04:00:00+00:00'},
                {'source_id': 'report-source', 'published_at': '2024-03-18T10:00:00+00:00'},
            ],
            'period_summary': 'First three tradable sessions after the event.',
            'transmission_nodes': [
                {'node_id': 'n1', 'node_type': 'event', 'statement': 'Event.'},
                {'node_id': 'n2', 'node_type': 'mechanism', 'statement': 'Mechanism.'},
                {'node_id': 'n3', 'node_type': 'market', 'statement': 'Market.'},
            ],
            'transmission_edges': [
                {'from_node_id': 'n1', 'to_node_id': 'n2', 'relation': 'CAUSES'},
                {'from_node_id': 'n2', 'to_node_id': 'n3', 'relation': 'TRANSMITS_TO'},
            ],
            'targets': targets,
            'cross_asset_attribution': {
                'label': 'CONTRIBUTING_FACTOR',
                'confidence': 'MEDIUM',
                'channels': ['RISK_APPETITE', 'GLOBAL_DEMAND'],
                'counterevidence': ['Cross-asset confirmation can break down.'],
                'short_term_prediction': {
                    'direction': 'DOWN',
                    'confidence': 'MEDIUM',
                    'invalidation_conditions': ['The correlation breaks down.'],
                },
            },
        }

    @staticmethod
    def _windows():
        return {
            series_id: {
                'market_window_id': f'event-01-{series_id.lower()}',
                't0_session': '2024-03-19',
                'windows': {
                    'D1': {'change': 1.0, 'end_date': '2024-03-19'},
                    'D3': {'change': 2.0, 'end_date': '2024-03-21'},
                    'D20': {'change': 3.0, 'end_date': '2024-04-15'},
                },
            }
            for series_id in ('SP500', 'VIXCLS', 'DCOILWTICO', 'DEXCHUS')
        }


if __name__ == '__main__':
    unittest.main()
