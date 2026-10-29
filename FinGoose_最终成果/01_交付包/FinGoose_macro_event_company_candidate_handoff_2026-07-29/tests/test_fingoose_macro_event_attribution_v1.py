import copy
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


class MacroEventMarketWindowTests(unittest.TestCase):
    def test_after_close_event_uses_next_session_and_previous_close_as_baseline(self):
        from fingoose_macro_event_attribution_v1 import align_event_session

        sessions = [date(2024, 3, 18), date(2024, 3, 19), date(2024, 3, 20)]

        result = align_event_session(
            anchor_at=datetime(2024, 3, 19, 17, 30, tzinfo=timezone.utc),
            sessions=sessions,
            market_close_hour=16,
        )

        self.assertEqual(result['baseline_session'], '2024-03-19')
        self.assertEqual(result['t0_session'], '2024-03-20')

    def test_price_windows_use_prior_close_and_sixty_session_volatility(self):
        from fingoose_macro_event_attribution_v1 import compute_market_windows

        start = date(2024, 1, 1)
        observations = []
        value = 100.0
        for offset in range(90):
            day = start + timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            value += 1.0
            observations.append({'date': day.isoformat(), 'value': value})
        anchor_session = observations[61]['date']

        result = compute_market_windows(
            observations=observations,
            t0_session=anchor_session,
            metric_type='price_return_pct',
        )

        self.assertEqual(result['baseline']['date'], observations[60]['date'])
        self.assertEqual(set(result['windows']), {'D1', 'D3', 'D5', 'D20', 'M3'})
        self.assertAlmostEqual(result['windows']['D1']['change'], 100 / observations[60]['value'], places=6)
        self.assertIsNone(result['windows']['M3'])
        self.assertGreater(result['estimation']['observation_count'], 0)

    def test_yield_windows_are_reported_in_basis_points(self):
        from fingoose_macro_event_attribution_v1 import compute_market_windows

        observations = [
            {'date': (date(2024, 1, 1) + timedelta(days=index)).isoformat(), 'value': 3.0 + index * 0.01}
            for index in range(85)
        ]

        result = compute_market_windows(
            observations=observations,
            t0_session=observations[61]['date'],
            metric_type='yield_basis_points',
        )

        self.assertAlmostEqual(result['windows']['D1']['change'], 1.0, places=6)
        self.assertEqual(result['change_unit'], 'basis_points')


class MacroEventReasoningChainTests(unittest.TestCase):
    def test_chain_requires_report_period_transmission_and_multiple_confirmations(self):
        from fingoose_macro_event_attribution_v1 import build_forecast_reasoning_chain

        chain = build_forecast_reasoning_chain(
            forecast_as_of_at='2024-03-22T23:59:59+08:00',
            report_evidence=[{
                'evidence_id': 'report-1',
                'published_at': '2024-03-18T10:00:00+08:00',
                'summary': 'Policy normalization may strengthen the yen and affect risk appetite.',
            }],
            period_description={
                'start_date': '2024-03-19',
                'end_date': '2024-03-22',
                'summary': 'The first three tradable sessions after the policy decision.',
            },
            transmission_nodes=[
                {'node_id': 'n1', 'node_type': 'event', 'statement': 'Negative rates ended.'},
                {'node_id': 'n2', 'node_type': 'mechanism', 'statement': 'Rate differentials may narrow.'},
                {'node_id': 'n3', 'node_type': 'market', 'statement': 'The yen response tests the channel.'},
            ],
            transmission_edges=[
                {'from_node_id': 'n1', 'to_node_id': 'n2', 'relation': 'CAUSES'},
                {'from_node_id': 'n2', 'to_node_id': 'n3', 'relation': 'TRANSMITS_TO'},
            ],
            trend_confirmations=[
                {'series_id': 'DEXJPUS', 'window': 'D3', 'alignment': 'SUPPORTS'},
                {'series_id': 'DGS10', 'window': 'D3', 'alignment': 'CONTRADICTS'},
            ],
            short_term_prediction={
                'target_series_id': 'DEXJPUS',
                'horizon': 'D20',
                'direction': 'DOWN',
                'confidence': 'MEDIUM',
                'invalidation_conditions': ['Rate differentials widen again.'],
            },
        )

        self.assertEqual(chain['sequence'], [
            'MACRO_REPORT', 'DATA', 'PERIOD_DESCRIPTION', 'FACT_TRANSMISSION_CHAIN',
            'MULTI_DATA_TREND_CONFIRMATION', 'SHORT_TERM_PREDICTION',
        ])
        self.assertEqual(chain['trend_confirmation']['series_count'], 2)

    def test_chain_rejects_future_report_and_single_series_confirmation(self):
        from fingoose_macro_event_attribution_v1 import build_forecast_reasoning_chain

        kwargs = self._valid_chain_kwargs()
        kwargs['report_evidence'][0]['published_at'] = '2024-03-23T00:00:00+08:00'
        kwargs['trend_confirmations'] = kwargs['trend_confirmations'][:1]

        with self.assertRaisesRegex(ValueError, 'FUTURE_REPORT_EVIDENCE'):
            build_forecast_reasoning_chain(**kwargs)

        kwargs = self._valid_chain_kwargs()
        kwargs['trend_confirmations'] = kwargs['trend_confirmations'][:1]
        with self.assertRaisesRegex(ValueError, 'MULTI_DATA_CONFIRMATION_REQUIRED'):
            build_forecast_reasoning_chain(**kwargs)

    @staticmethod
    def _valid_chain_kwargs():
        return {
            'forecast_as_of_at': '2024-03-22T23:59:59+08:00',
            'report_evidence': [{
                'evidence_id': 'report-1',
                'published_at': '2024-03-18T10:00:00+08:00',
                'summary': 'A report summary.',
            }],
            'period_description': {
                'start_date': '2024-03-19', 'end_date': '2024-03-22', 'summary': 'Period.',
            },
            'transmission_nodes': [
                {'node_id': 'n1', 'node_type': 'event', 'statement': 'Event.'},
                {'node_id': 'n2', 'node_type': 'mechanism', 'statement': 'Mechanism.'},
                {'node_id': 'n3', 'node_type': 'market', 'statement': 'Market.'},
            ],
            'transmission_edges': [
                {'from_node_id': 'n1', 'to_node_id': 'n2', 'relation': 'CAUSES'},
                {'from_node_id': 'n2', 'to_node_id': 'n3', 'relation': 'TRANSMITS_TO'},
            ],
            'trend_confirmations': [
                {'series_id': 'a', 'window': 'D3', 'alignment': 'SUPPORTS'},
                {'series_id': 'b', 'window': 'D3', 'alignment': 'SUPPORTS'},
            ],
            'short_term_prediction': {
                'target_series_id': 'a', 'horizon': 'D20', 'direction': 'UP',
                'confidence': 'MEDIUM', 'invalidation_conditions': ['Condition.'],
            },
        }


class MacroEventReviewAndSchemaTests(unittest.TestCase):
    def test_pending_human_review_is_schema_valid_but_not_release_ready(self):
        from fingoose_macro_event_attribution_v1 import review_errors, validate_schema_record

        review = {
            'review_id': 'review-event-01-single-a',
            'dataset_version': 'fingoose-macro-event-attribution-v1.0',
            'event_id': 'event-01',
            'initial_review': {'reviewer_id': 'PENDING_HUMAN', 'status': 'PENDING'},
            'second_review': None,
            'adjudication': None,
            'second_review_trigger_reasons': [],
            'final_label': 'CONTRIBUTING_FACTOR',
            'confidence': 'MEDIUM',
            'core_dimensions': {
                'temporal_alignment': 'SUPPORTED',
                'abnormal_movement': 'SUPPORTED',
                'transmission_mechanism': 'SUPPORTED',
                'competing_explanations': 'LIMITED',
            },
        }

        self.assertEqual(validate_schema_record('review_record', review), [])
        self.assertIn('INITIAL_REVIEW_REQUIRED', review_errors(review))

    def test_second_review_trigger_reasons_are_explicit(self):
        from fingoose_macro_event_attribution_v1 import second_review_trigger_reasons

        review = {
            'confidence': 'LOW',
            'core_dimensions': {
                'temporal_alignment': 'UNKNOWN',
                'abnormal_movement': 'CONTRADICTED',
                'transmission_mechanism': 'SUPPORTED',
                'competing_explanations': 'STRONG',
            },
        }

        self.assertEqual(second_review_trigger_reasons(review), [
            'LOW_CONFIDENCE', 'STRONG_COMPETING_EXPLANATION',
            'CORE_DIMENSION_UNKNOWN', 'CORE_DIMENSION_CONTRADICTED',
        ])

    def test_low_confidence_and_strong_competitor_require_completed_second_review(self):
        from fingoose_macro_event_attribution_v1 import review_errors

        review = {
            'initial_review': {'reviewer_id': 'analyst-1', 'status': 'APPROVED'},
            'final_label': 'CONTRIBUTING_FACTOR',
            'confidence': 'LOW',
            'core_dimensions': {
                'temporal_alignment': 'SUPPORTED',
                'abnormal_movement': 'SUPPORTED',
                'transmission_mechanism': 'SUPPORTED',
                'competing_explanations': 'STRONG',
            },
            'second_review': None,
        }

        self.assertIn('SECOND_REVIEW_REQUIRED', review_errors(review))
        review['second_review'] = {'reviewer_id': 'analyst-2', 'status': 'APPROVED'}
        self.assertNotIn('SECOND_REVIEW_REQUIRED', review_errors(review))

    def test_public_projection_rejects_hidden_d20_outcome(self):
        from fingoose_macro_event_attribution_v1 import assert_public_projection_safe

        projection = {'record_id': 'sample-1', 'forecast_reasoning_chain': {'hidden_outcome': {'direction': 'UP'}}}

        with self.assertRaisesRegex(ValueError, 'PUBLIC_HIDDEN_FIELD_LEAKAGE'):
            assert_public_projection_safe(projection)

    def test_schema_accepts_complete_minimal_sample(self):
        from fingoose_macro_event_attribution_v1 import validate_schema_record

        sample = self._sample()
        errors = validate_schema_record('attribution_sample', sample)

        self.assertEqual(errors, [])

    @staticmethod
    def _sample():
        chain = MacroEventReasoningChainTests._valid_chain_kwargs()
        from fingoose_macro_event_attribution_v1 import build_forecast_reasoning_chain
        return {
            'record_id': 'macro-event-v1-event-01-single-a',
            'dataset_version': 'fingoose-macro-event-attribution-v1.0',
            'event_id': 'event-01',
            'task_type': 'single_asset_attribution_forecast',
            'target_series_ids': ['a'],
            'as_of_at': '2024-04-16T23:59:59+08:00',
            'forecast_as_of_at': chain['forecast_as_of_at'],
            'visible_evidence_ids': ['event-source', 'report-1'],
            'market_window_ids': ['event-01-a'],
            'attribution': {
                'label': 'CONTRIBUTING_FACTOR',
                'confidence': 'MEDIUM',
                'channels': ['RATE_DIFFERENTIAL'],
                'counterevidence': ['A competing explanation.'],
            },
            'forecast_reasoning_chain': build_forecast_reasoning_chain(**chain),
            'review_id': 'review-sample-1',
        }


if __name__ == '__main__':
    unittest.main()
