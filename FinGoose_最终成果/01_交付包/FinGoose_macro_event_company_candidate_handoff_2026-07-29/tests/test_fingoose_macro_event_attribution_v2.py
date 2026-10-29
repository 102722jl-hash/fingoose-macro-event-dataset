import copy
import unittest
from datetime import date, datetime, timedelta, timezone


class V2IdentityAndSchemaTests(unittest.TestCase):
    def test_version_release_tier_and_stable_ids(self):
        from fingoose_macro_event_attribution_v2 import (
            DATASET_VERSION,
            RELEASE_TIER,
            stable_record_id,
        )

        self.assertEqual(DATASET_VERSION, 'fingoose-macro-event-attribution-v2.0')
        self.assertEqual(RELEASE_TIER, 'CANDIDATE')
        first = stable_record_id('milestone', 'event-02', '2024-03-19T03:30:00Z')
        second = stable_record_id('milestone', 'event-02', '2024-03-19T03:30:00Z')
        self.assertEqual(first, second)
        self.assertRegex(first, r'^milestone-event-02-[a-f0-9]{12}$')

    def test_all_v2_record_types_validate_against_draft_2020_12_schemas(self):
        from fingoose_macro_event_attribution_v2 import validate_schema_record

        for record_type, record in self._schema_records().items():
            with self.subTest(record_type=record_type):
                self.assertEqual(validate_schema_record(record_type, record), [])

        bad = copy.deepcopy(self._schema_records()['milestone'])
        bad['milestone_id'] = 'unstable id'
        self.assertTrue(validate_schema_record('milestone', bad))

    def test_milestone_schema_accepts_unscheduled_and_evolving_expectations(self):
        from fingoose_macro_event_attribution_v2 import validate_schema_record

        milestone = self._schema_records()['milestone']
        milestone['expectation'] = {
            'type': 'UNSCHEDULED_SHOCK',
            'consensus': 'UNKNOWN',
            'actual': 'UNKNOWN',
            'surprise': 'UNKNOWN',
        }
        self.assertEqual(validate_schema_record('milestone', milestone), [])

        milestone['expectation'] = {
            'type': 'EVOLVING_EVENT',
            'qualitative_baseline': 'Escalation risk was already visible.',
            'consensus': 'UNKNOWN',
            'actual': 'UNKNOWN',
            'surprise': 'UNKNOWN',
        }
        self.assertEqual(validate_schema_record('milestone', milestone), [])

    @staticmethod
    def _schema_records():
        version = 'fingoose-macro-event-attribution-v2.0'
        evidence = {
            'evidence_id': 'evidence-event-02-a',
            'source_tier': 'A',
            'published_at': '2024-03-19T03:30:00Z',
            'sha256': 'a' * 64,
        }
        review = {
            'reviewer_id': 'analyst-01',
            'reviewed_at': '2024-03-22T00:00:00Z',
            'decision': 'CONFIRMED',
            'notes': 'Evidence and direction reviewed.',
        }
        milestone = {
            'milestone_id': 'milestone-event-02-123456789abc',
            'dataset_version': version,
            'release_tier': 'CANDIDATE',
            'event_id': 'event-02',
            'occurred_at': '2024-03-19T03:30:00Z',
            'first_public_at': '2024-03-19T03:30:00Z',
            'phase': 'INITIAL_SHOCK',
            'fact': 'The decision was published.',
            'sources': [evidence],
            'visibility': 'PUBLIC_PREDICTION',
            'anchor_role': 'PRIMARY',
            'impact_tags': ['MONETARY_POLICY'],
            'expectation': {'type': 'SCHEDULED_RELEASE', 'consensus': 0.0, 'actual': 0.1, 'surprise': 0.1},
        }
        episode = {
            'episode_id': 'episode-event-02-123456789abc',
            'dataset_version': version,
            'release_tier': 'CANDIDATE',
            'event_id': 'event-02',
            'phase': 'INITIAL_SHOCK',
            'start_at': '2024-03-19T03:30:00Z',
            'end_at': '2024-03-21T00:00:00Z',
            'milestone_ids': [milestone['milestone_id']],
            'evidence_coverage': [evidence['evidence_id']],
        }
        graph = {
            'graph_id': 'graph-event-02-123456789abc',
            'dataset_version': version,
            'release_tier': 'CANDIDATE',
            'event_id': 'event-02',
            'as_of_at': '2024-03-22T00:00:00Z',
            'milestone_ids': [milestone['milestone_id']],
            'nodes': [
                {'node_id': 'shock-1', 'layer': 'shock', 'label': 'Policy decision'},
                {'node_id': 'channel-1', 'layer': 'channel', 'label': 'Rate differential'},
                {'node_id': 'intermediate-1', 'layer': 'intermediate', 'label': 'Funding conditions'},
                {'node_id': 'asset-1', 'layer': 'asset', 'label': 'USDJPY'},
            ],
            'edges': [
                V2GraphTests.valid_edge('edge-1', 'shock-1', 'channel-1'),
                V2GraphTests.valid_edge('edge-2', 'channel-1', 'intermediate-1'),
                V2GraphTests.valid_edge('edge-3', 'intermediate-1', 'asset-1'),
            ],
        }
        point = {'date': '2024-03-19', 'value': 101.0}
        window_result = {
            key: ({**point, 'raw_change': 1.0, 'standardized_change': 0.5,
                   'relative_change': None, 'empirical_percentile': None})
            for key in ('T60', 'T20', 'T1', 'D1', 'D3', 'D5', 'D20', 'M3')
        }
        market_window = {
            'market_window_id': 'window-event-02-usdjpy-123456789abc',
            'dataset_version': version,
            'release_tier': 'CANDIDATE',
            'event_id': 'event-02',
            'series_id': 'USDJPY',
            'timezone': 'Asia/Tokyo',
            'metric_type': 'price_return_pct',
            'baseline': {'date': '2024-03-18', 'value': 100.0},
            'estimation': {
                'window': 'PREVIOUS_60_SESSIONS',
                'observation_count': 60,
                'daily_change_stddev': 1.0,
            },
            'observation_source': {
                'path': 'market/fred/USDJPY.csv',
                'sha256': 'a' * 64,
                'hash_verified': True,
            },
            'benchmark_series_id': None,
            'calendar_id': 'XTKS',
            'observation_cutoff': '15:00:00',
            't0': {'date': '2024-03-19', 'alignment_reason': 'IN_SESSION'},
            'windows': window_result,
            'confounder_level': 'CLEAN',
            'challenge_set': False,
            'calculation_basis': 'Prior-session baseline; session offsets.',
        }
        benchmark_case = {
            'case_id': 'case-event-02-123456789abc',
            'dataset_version': version,
            'release_tier': 'CANDIDATE',
            'event_id': 'event-02',
            'forecast_cutoff_at': '2024-03-22T00:00:00Z',
            'tasks': ['TIMELINE_RECONSTRUCTION', 'GRAPH_CONSTRUCTION', 'DIRECTION', 'ABSTENTION'],
            'visible_evidence_ids': ['source-a'],
            'visible_market_windows': ['T60', 'T20', 'T1', 'D1', 'D3'],
            'split': 'EXAMPLE',
            'challenge_set': False,
            'score_eligible': True,
        }
        benchmark_label = {
            'label_id': 'label-event-02-123456789abc',
            'dataset_version': version,
            'release_tier': 'CANDIDATE',
            'case_id': benchmark_case['case_id'],
            'event_id': 'event-02',
            'hidden': True,
            'timeline_labels': [milestone['milestone_id']],
            'graph_edge_labels': ['edge-1', 'edge-2', 'edge-3'],
            'direction_label': 'DOWN',
            'abstention_label': False,
            'verification_windows': ['D5', 'D20'],
        }
        graph['edges'][0]['review'] = review
        return {
            'milestone': milestone,
            'episode': episode,
            'transmission_graph': graph,
            'market_window': market_window,
            'benchmark_case': benchmark_case,
            'benchmark_label': benchmark_label,
        }


class V2ExpectationTests(unittest.TestCase):
    def test_scheduled_release_computes_surprise_but_missing_values_stay_unknown(self):
        from fingoose_macro_event_attribution_v2 import normalize_expectation

        known = normalize_expectation('SCHEDULED_RELEASE', consensus=3.2, actual=3.5)
        unknown = normalize_expectation('SCHEDULED_RELEASE', consensus=None, actual=3.5)

        self.assertAlmostEqual(known['surprise'], 0.3)
        self.assertEqual(unknown, {
            'type': 'SCHEDULED_RELEASE', 'consensus': 'UNKNOWN',
            'actual': 3.5, 'surprise': 'UNKNOWN',
        })

    def test_unscheduled_shock_never_invents_numeric_surprise(self):
        from fingoose_macro_event_attribution_v2 import normalize_expectation

        result = normalize_expectation('UNSCHEDULED_SHOCK', consensus=1.0, actual=2.0)

        self.assertEqual(result, {
            'type': 'UNSCHEDULED_SHOCK', 'consensus': 'UNKNOWN',
            'actual': 'UNKNOWN', 'surprise': 'UNKNOWN',
        })

    def test_evolving_event_preserves_qualitative_baseline_only(self):
        from fingoose_macro_event_attribution_v2 import normalize_expectation

        result = normalize_expectation('EVOLVING_EVENT', qualitative_baseline='Further escalation expected')

        self.assertEqual(result['qualitative_baseline'], 'Further escalation expected')
        self.assertEqual(result['surprise'], 'UNKNOWN')


class V2AlignmentTests(unittest.TestCase):
    def test_alignment_uses_series_timezone_and_observation_cutoff(self):
        from fingoose_macro_event_attribution_v2 import align_series_t0

        sessions = [date(2024, 3, 18), date(2024, 3, 19), date(2024, 3, 20)]
        pre_close = align_series_t0(
            anchor_at='2024-03-19T05:30:00Z',
            timezone_name='Asia/Tokyo',
            sessions=sessions,
            observation_cutoff='15:00:00',
            calendar_id='XTKS',
        )
        post_close = align_series_t0(
            anchor_at='2024-03-19T07:00:00Z',
            timezone_name='Asia/Tokyo',
            sessions=sessions,
            observation_cutoff='15:00:00',
            calendar_id='XTKS',
        )

        self.assertEqual(pre_close['t0_session'], '2024-03-19')
        self.assertEqual(pre_close['alignment_reason'], 'IN_SESSION')
        self.assertEqual(post_close['t0_session'], '2024-03-20')
        self.assertEqual(post_close['alignment_reason'], 'AFTER_CUTOFF')

    def test_holiday_rolls_forward_and_missing_t0_is_explicit(self):
        from fingoose_macro_event_attribution_v2 import align_series_t0

        holiday = align_series_t0(
            anchor_at='2024-03-17T03:00:00Z',
            timezone_name='America/New_York',
            sessions=[date(2024, 3, 15), date(2024, 3, 18), date(2024, 3, 19)],
            observation_cutoff='16:00:00',
            calendar_id='XNYS',
        )
        missing = align_series_t0(
            anchor_at='2024-03-20T20:30:00Z',
            timezone_name='America/New_York',
            sessions=[date(2024, 3, 19), date(2024, 3, 20)],
            observation_cutoff='16:00:00',
            calendar_id='XNYS',
        )

        self.assertEqual(holiday['t0_session'], '2024-03-18')
        self.assertEqual(holiday['alignment_reason'], 'NON_TRADING_DAY')
        self.assertIsNone(missing['t0_session'])
        self.assertEqual(missing['alignment_reason'], 'NO_FUTURE_SESSION')

    def test_exact_observation_cutoff_rolls_to_next_session(self):
        from fingoose_macro_event_attribution_v2 import align_series_t0

        result = align_series_t0(
            anchor_at='2024-03-19T06:00:00Z',
            timezone_name='Asia/Tokyo',
            sessions=[date(2024, 3, 19), date(2024, 3, 20)],
            observation_cutoff='15:00:00',
            calendar_id='XTKS',
        )

        self.assertEqual(result['t0_session'], '2024-03-20')
        self.assertEqual(result['alignment_reason'], 'AT_CUTOFF')


class V2EnhancedWindowTests(unittest.TestCase):
    def test_all_endpoints_include_absolute_and_derived_values(self):
        from fingoose_macro_event_attribution_v2 import compute_enhanced_market_window

        start = date(2023, 10, 2)
        observations = []
        value = 100.0
        for offset in range(190):
            day = start + timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            value += 0.5 if len(observations) % 2 else -0.2
            observations.append({'date': day.isoformat(), 'value': value})
        t0_session = observations[75]['date']
        benchmark = [
            {'date': row['date'], 'value': 200.0 + index * 0.1}
            for index, row in enumerate(observations)
        ]

        result = compute_enhanced_market_window(
            observations=observations,
            t0_session=t0_session,
            metric_type='price_return_pct',
            benchmark_observations=benchmark,
        )

        self.assertEqual(set(result['windows']), {'T60', 'T20', 'T1', 'D1', 'D3', 'D5', 'D20', 'M3'})
        self.assertEqual(result['windows']['T1']['date'], observations[74]['date'])
        self.assertEqual(result['windows']['D1']['date'], observations[75]['date'])
        for point in result['windows'].values():
            self.assertEqual(set(point), {
                'date', 'value', 'raw_change', 'standardized_change',
                'relative_change', 'empirical_percentile',
            })
        self.assertIsNotNone(result['windows']['D20']['empirical_percentile'])

    def test_insufficient_data_returns_null_points_and_statistics(self):
        from fingoose_macro_event_attribution_v2 import compute_enhanced_market_window

        observations = [
            {'date': (date(2024, 3, 18) + timedelta(days=index)).isoformat(), 'value': 100.0 + index}
            for index in range(3)
        ]
        result = compute_enhanced_market_window(
            observations=observations,
            t0_session='2024-03-19',
            metric_type='price_return_pct',
        )

        self.assertIsNone(result['windows']['T60'])
        self.assertIsNone(result['windows']['D20'])
        self.assertIsNone(result['windows']['D1']['standardized_change'])
        self.assertIsNone(result['windows']['D1']['relative_change'])
        self.assertIsNone(result['windows']['D1']['empirical_percentile'])


class V2ConfounderTests(unittest.TestCase):
    def test_material_and_dominant_windows_are_challenge_set_only(self):
        from fingoose_macro_event_attribution_v2 import classify_confounder

        for level in ('CLEAN', 'MINOR', 'UNRESOLVED'):
            self.assertFalse(classify_confounder(level)['challenge_set'])
        self.assertFalse(
            classify_confounder('UNRESOLVED')['eligible_for_clean_attribution_score'])
        for level in ('MATERIAL', 'DOMINANT'):
            result = classify_confounder(level)
            self.assertTrue(result['challenge_set'])
            self.assertFalse(result['eligible_for_clean_attribution_score'])


class V2GraphTests(unittest.TestCase):
    @staticmethod
    def valid_edge(edge_id, source, target):
        return {
            'edge_id': edge_id,
            'from_node_id': source,
            'to_node_id': target,
            'anchor_milestone_id': 'milestone-event-02-123456789abc',
            'expected_path': {'IMMEDIATE': 'UP', 'SHORT_TERM': 'UP', 'MEDIUM_TERM': 'UNKNOWN'},
            'lag': {'minimum': 'PT0S', 'maximum': 'P5D'},
            'conditions': ['No dominant policy offset.'],
            'invalidation_conditions': ['Rate differential widens.'],
            'evidence': [{
                'evidence_id': 'evidence-event-02-a',
                'published_at': '2024-03-20T00:00:00Z',
                'source_tier': 'A',
            }],
            'counterevidence': ['Initial market move may contradict the edge.'],
            'status': 'PROPOSED',
            'confidence': 0.7,
            'review': None,
        }

    def test_valid_layered_acyclic_connected_graph_passes(self):
        from fingoose_macro_event_attribution_v2 import transmission_graph_errors

        graph = V2IdentityAndSchemaTests._schema_records()['transmission_graph']
        self.assertEqual(transmission_graph_errors(graph), [])

    def test_graph_rejects_cycle_orphan_and_future_evidence(self):
        from fingoose_macro_event_attribution_v2 import transmission_graph_errors

        graph = V2IdentityAndSchemaTests._schema_records()['transmission_graph']
        graph['nodes'].append({'node_id': 'asset-orphan', 'layer': 'asset', 'label': 'Orphan'})
        graph['edges'].append(self.valid_edge('edge-cycle', 'asset-1', 'shock-1'))
        graph['edges'][0]['evidence'][0]['published_at'] = '2024-03-23T00:00:00Z'

        errors = transmission_graph_errors(graph)

        self.assertIn('GRAPH_CYCLE', errors)
        self.assertIn('ORPHAN_NODE:asset-orphan', errors)
        self.assertIn('FUTURE_EVIDENCE:edge-1', errors)

    def test_confirmed_edge_requires_completed_review(self):
        from fingoose_macro_event_attribution_v2 import transmission_graph_errors

        graph = V2IdentityAndSchemaTests._schema_records()['transmission_graph']
        graph['edges'][1]['status'] = 'CONFIRMED'
        graph['edges'][1]['review'] = None

        self.assertIn('CONFIRMED_EDGE_REVIEW_REQUIRED:edge-2', transmission_graph_errors(graph))

    def test_graph_requires_nonempty_milestone_directory(self):
        from fingoose_macro_event_attribution_v2 import (
            transmission_graph_errors,
            validate_schema_record,
        )

        graph = V2IdentityAndSchemaTests._schema_records()['transmission_graph']
        graph.pop('milestone_ids')
        self.assertIn(
            'GRAPH_MILESTONE_DIRECTORY_REQUIRED',
            transmission_graph_errors(graph),
        )
        self.assertTrue(validate_schema_record('transmission_graph', graph))




class V2PublicProjectionTests(unittest.TestCase):
    def test_public_projection_removes_hidden_labels_late_windows_and_post_cutoff_evidence(self):
        from fingoose_macro_event_attribution_v2 import build_public_projection

        record = {
            'case_id': 'case-event-02-123456789abc',
            'event_id': 'event-02',
            'forecast_cutoff_at': '2024-03-22T00:00:00Z',
            'labels': {'direction_label': 'UP'},
            'windows': {'D1': {'value': 1}, 'D3': {'value': 2}, 'D5': {'value': 3}, 'D20': {'value': 4}},
            'evidence': [
                {'evidence_id': 'early', 'published_at': '2024-03-21T00:00:00Z'},
                {'evidence_id': 'late', 'published_at': '2024-03-23T00:00:00Z'},
            ],
            'nested': {'hidden_outcome': 'UP'},
            'milestones': [
                {
                    'milestone_id': 'public',
                    'visibility': 'PUBLIC_PREDICTION',
                    'first_public_at': '2024-03-21T00:00:00Z',
                },
                {
                    'milestone_id': 'hidden',
                    'visibility': 'HIDDEN_VALIDATION',
                    'first_public_at': '2024-03-21T00:00:00Z',
                },
            ],
        }

        public = build_public_projection(record)

        self.assertNotIn('labels', public)
        self.assertNotIn('nested', public)
        self.assertEqual(
            [row['milestone_id'] for row in public['milestones']], ['public']
        )
        self.assertEqual(set(public['windows']), {'D1', 'D3'})
        self.assertEqual([row['evidence_id'] for row in public['evidence']], ['early'])

    def test_safety_check_rejects_forbidden_content(self):
        from fingoose_macro_event_attribution_v2 import assert_public_projection_safe

        with self.assertRaisesRegex(ValueError, 'PUBLIC_HIDDEN_FIELD_LEAKAGE'):
            assert_public_projection_safe({'verification_windows': ['D5']})
        with self.assertRaisesRegex(ValueError, 'PUBLIC_HIDDEN_VISIBILITY_LEAKAGE'):
            assert_public_projection_safe(
                {'visibility': 'HIDDEN_VALIDATION'})
        with self.assertRaisesRegex(ValueError, 'PUBLIC_LATE_WINDOW_LEAKAGE'):
            assert_public_projection_safe({'windows': {'D20': {'value': 1}}})


if __name__ == '__main__':
    unittest.main()
