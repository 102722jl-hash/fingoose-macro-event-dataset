from __future__ import annotations

import copy
import unittest


def metric_fact(**overrides):
    fact = {
        'company_code': '600000.SH',
        'metric': 'revenue',
        'unit': 'CNY_million',
        'currency': 'CNY',
        'period': '2024H1',
        'value': '300.30',
        'evidence_refs': [{'source_id': 'cninfo-h1', 'source_locator': 'h1.pdf:page=3'}],
    }
    fact.update(overrides)
    return fact


class CompanyMetricCalculationTests(unittest.TestCase):
    def test_derives_exact_standalone_quarter_and_preserves_provenance(self):
        from fingoose_macro_event_company_v1 import derive_standalone_quarter

        current = metric_fact()
        prior = metric_fact(
            period='2024Q1', value='100.10',
            evidence_refs=[{'source_id': 'cninfo-q1', 'source_locator': 'q1.pdf:page=2'}],
        )

        result = derive_standalone_quarter(current, prior)

        self.assertEqual(result['period'], '2024Q2')
        self.assertEqual(result['value_decimal'], '200.20')
        self.assertEqual(result['calculation']['formula'], 'current_cumulative - prior_cumulative')
        self.assertEqual(result['evidence_refs'], current['evidence_refs'] + prior['evidence_refs'])

    def test_rejects_incompatible_or_non_finite_cumulative_facts(self):
        from fingoose_macro_event_company_v1 import derive_standalone_quarter

        current = metric_fact()
        prior = metric_fact(period='2024Q1', value='100')
        for field, bad_value in (
            ('company_code', '600001.SH'), ('metric', 'net_income'),
            ('unit', 'CNY'), ('currency', 'USD'), ('period', '2023Q4'),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    derive_standalone_quarter(current, {**prior, field: bad_value})
        with self.assertRaisesRegex(ValueError, 'FINITE'):
            derive_standalone_quarter(metric_fact(value='NaN'), prior)

    def test_calculates_yoy_and_qoq_and_marks_zero_base_uncomputable(self):
        from fingoose_macro_event_company_v1 import calculate_period_comparison

        current = metric_fact(period='2024Q2', value='120')
        yoy = calculate_period_comparison(current, metric_fact(period='2023Q2', value='100'))
        qoq = calculate_period_comparison(current, metric_fact(period='2024Q1', value='80'))
        zero = calculate_period_comparison(current, metric_fact(period='2023Q2', value='0'))

        self.assertEqual((yoy['comparison_type'], yoy['change_pct_decimal']), ('YOY', '20.0'))
        self.assertEqual((qoq['comparison_type'], qoq['change_pct_decimal']), ('QOQ', '50.0'))
        self.assertFalse(zero['computable'])
        self.assertIsNone(zero['change_pct'])
        self.assertEqual(zero['reason'], 'ZERO_COMPARISON_BASE')

    def test_period_comparison_rejects_unit_and_currency_mismatch(self):
        from fingoose_macro_event_company_v1 import calculate_period_comparison

        current = metric_fact(period='2024Q2')
        for field, value in (('unit', 'CNY'), ('currency', 'USD')):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    calculate_period_comparison(
                        current, metric_fact(period='2023Q2', **{field: value}),
                    )


class CompanyStockWindowTests(unittest.TestCase):
    def test_uses_last_common_valid_pre_t0_baseline_and_company_sessions(self):
        from fingoose_macro_event_company_v1 import compute_company_stock_window

        company = [
            {'date': '2024-01-02', 'value': 100},
            {'date': '2024-01-03', 'value': 101},
            {'date': '2024-01-04', 'value': 'NaN'},
            {'date': '2024-01-05', 'value': 103},
            {'date': '2024-01-08', 'value': None},  # suspension
            {'date': '2024-01-09', 'value': 106},
            {'date': '2024-01-10', 'value': 108},
            {'date': '2024-01-11', 'value': 110},
        ]
        benchmark = [
            {'date': '2024-01-02', 'value': 200},
            {'date': '2024-01-03', 'value': 202},
            {'date': '2024-01-04', 'value': 204},
            {'date': '2024-01-05', 'value': 206},
            {'date': '2024-01-08', 'value': 208},
            {'date': '2024-01-09', 'value': 212},
            {'date': '2024-01-10', 'value': 216},
            {'date': '2024-01-11', 'value': 220},
        ]

        result = compute_company_stock_window(company, benchmark, '2024-01-04')

        self.assertEqual(result['baseline']['date'], '2024-01-03')
        self.assertEqual(result['windows']['D1']['end_date'], '2024-01-05')
        self.assertEqual(result['windows']['D3']['end_date'], '2024-01-10')
        self.assertAlmostEqual(result['windows']['D1']['company_return_pct'], (103 / 101 - 1) * 100)
        self.assertAlmostEqual(result['windows']['D1']['benchmark_return_pct'], (206 / 202 - 1) * 100)
        self.assertAlmostEqual(
            result['windows']['D1']['relative_abnormal_return_pct'],
            result['windows']['D1']['company_return_pct'] - result['windows']['D1']['benchmark_return_pct'],
        )
        self.assertIsNone(result['windows']['D5'])
        self.assertIsNone(result['windows']['D20'])

    def test_rejects_missing_common_baseline_and_does_not_emit_financial_attribution(self):
        from fingoose_macro_event_company_v1 import compute_company_stock_window

        with self.assertRaisesRegex(ValueError, 'COMMON_BASELINE'):
            compute_company_stock_window(
                [{'date': '2024-01-03', 'value': 100}],
                [{'date': '2024-01-02', 'value': 200}],
                '2024-01-04',
            )
        result = compute_company_stock_window(
            [{'date': '2024-01-02', 'value': 100}, {'date': '2024-01-04', 'value': 101}],
            [{'date': '2024-01-02', 'value': 200}, {'date': '2024-01-04', 'value': 201}],
            '2024-01-04',
        )
        self.assertNotIn('financial_attribution', result)
        self.assertNotIn('operating_result', result)


class CompanySchemaTests(unittest.TestCase):
    def test_all_six_schemas_are_valid_draft_2020_12(self):
        import json
        from pathlib import Path
        from jsonschema import Draft202012Validator

        schema_dir = Path(__file__).resolve().parents[1] / 'schemas'
        names = ('event_dossier', 'metric_fact', 'stock_window', 'attribution_sample', 'forecast_sample', 'review_record')
        for name in names:
            with self.subTest(name=name):
                schema = json.loads((schema_dir / f'fingoose_company_{name}_v1.schema.json').read_text(encoding='utf-8'))
                self.assertEqual(schema['$schema'], 'https://json-schema.org/draft/2020-12/schema')
                Draft202012Validator.check_schema(schema)

    def test_dossier_schema_enforces_code_tier_quarter_labels_and_full_chain(self):
        from fingoose_macro_event_company_v1 import validate_schema_record

        dossier = {
            'dossier_id': 'company-dossier-event-01-600000-sh',
            'dataset_version': 'fingoose-macro-event-company-v1.0',
            'event_id': 'event-01', 'company_code': '600000.SH', 'company_name': 'Example Bank',
            'source_tier': 'TIER_1', 'observation_quarter': '2024Q2',
            'association': 'VERIFIED_ASSOCIATION', 'direction': 'MIXED',
            'transmission_chain': ['重大事件', '行业/宏观变量', '公司业务暴露', '经营指标', '财务结果', '竞争解释'],
        }
        self.assertEqual(validate_schema_record('event_dossier', dossier), [])
        for field, value in (
            ('company_code', '600000.BJ'), ('source_tier', 'TIER_4'),
            ('observation_quarter', '2024H1'), ('association', 'PRIMARY_DRIVER'),
            ('direction', 'FLAT'), ('transmission_chain', dossier['transmission_chain'][:-1]),
        ):
            with self.subTest(field=field):
                self.assertTrue(validate_schema_record('event_dossier', {**dossier, field: value}))

    def test_forecast_schema_requires_three_distinct_prediction_label_types(self):
        from fingoose_macro_event_company_v1 import validate_schema_record

        sample = {
            'record_id': 'company-forecast-event-01-600000-sh',
            'dataset_version': 'fingoose-macro-event-company-v1.0',
            'event_id': 'event-01', 'company_code': '600000.SH',
            'forecast_as_of_at': '2024-01-05T23:59:59+08:00',
            'visible_windows': ['D1', 'D3'],
            'forecast_labels': [
                {'label_type': 'REVENUE', 'direction': 'UP'},
                {'label_type': 'PROFIT', 'direction': 'DOWN'},
                {'label_type': 'OPERATING_CASH_FLOW', 'direction': 'UNCERTAIN'},
            ],
        }
        self.assertEqual(validate_schema_record('forecast_sample', sample), [])
        self.assertTrue(validate_schema_record('forecast_sample', {**sample, 'forecast_labels': sample['forecast_labels'][:2]}))


def review_fixture():
    dimensions = {
        'temporal_alignment': 'SUPPORTED', 'business_exposure': 'SUPPORTED',
        'operating_financial_link': 'SUPPORTED', 'competing_explanations': 'LIMITED',
    }
    return {
        'confidence': 'MEDIUM', 'core_dimensions': dimensions,
        'quarter_differencing_used': False, 'event_channel_explicitly_disclosed': True,
        'leakage_anomalies': [],
        'initial_review': {
            'reviewer_id': 'reviewer-user-01', 'status': 'APPROVED',
            'label': 'VERIFIED_ASSOCIATION', 'confidence': 'MEDIUM',
            'core_dimensions': copy.deepcopy(dimensions),
        },
        'second_review': None, 'adjudication': None,
    }


class CompanyReviewTests(unittest.TestCase):
    def test_all_risk_conditions_trigger_second_review(self):
        from fingoose_macro_event_company_v1 import company_second_review_trigger_reasons

        cases = (
            ({'confidence': 'LOW'}, 'LOW_CONFIDENCE'),
            ({'core_dimensions': {**review_fixture()['core_dimensions'], 'business_exposure': 'UNKNOWN'}}, 'CORE_DIMENSION_UNKNOWN'),
            ({'core_dimensions': {**review_fixture()['core_dimensions'], 'temporal_alignment': 'CONTRADICTED'}}, 'CORE_DIMENSION_CONTRADICTED'),
            ({'core_dimensions': {**review_fixture()['core_dimensions'], 'competing_explanations': 'STRONG'}}, 'STRONG_COMPETING_EXPLANATION'),
            ({'quarter_differencing_used': True}, 'QUARTER_DIFFERENCING'),
            ({'event_channel_explicitly_disclosed': False}, 'EVENT_CHANNEL_NOT_EXPLICITLY_DISCLOSED'),
            ({'leakage_anomalies': ['future-source-id']}, 'LEAKAGE_ANOMALY'),
        )
        for update, reason in cases:
            with self.subTest(reason=reason):
                review = review_fixture()
                review.update(update)
                self.assertIn(reason, company_second_review_trigger_reasons(review))

    def test_initial_user_reviewer_is_valid_and_second_reviewer_must_be_independent(self):
        from fingoose_macro_event_company_v1 import company_review_errors

        review = review_fixture()
        self.assertEqual(company_review_errors(review), [])
        review['confidence'] = 'LOW'
        self.assertIn('SECOND_REVIEW_REQUIRED', company_review_errors(review))
        review['second_review'] = {**copy.deepcopy(review['initial_review']), 'reviewer_id': 'reviewer-user-01'}
        self.assertIn('SECOND_REVIEWER_NOT_INDEPENDENT', company_review_errors(review))

    def test_disagreement_requires_independent_adjudication(self):
        from fingoose_macro_event_company_v1 import company_review_errors, resolve_company_review

        review = review_fixture()
        review['confidence'] = 'LOW'
        review['second_review'] = {**copy.deepcopy(review['initial_review']), 'reviewer_id': 'reviewer-user-02', 'label': 'WEAK_RELATION'}
        self.assertIn('ADJUDICATION_REQUIRED', company_review_errors(review))
        review['adjudication'] = {**copy.deepcopy(review['initial_review']), 'reviewer_id': 'reviewer-user-03', 'label': 'CONTRIBUTING_ASSOCIATION'}
        self.assertEqual(company_review_errors(review), [])
        self.assertEqual(resolve_company_review(review)['label'], 'CONTRIBUTING_ASSOCIATION')
class CompanyForecastProjectionTests(unittest.TestCase):
    def cutoff_snapshot(self):
        return {
            'snapshot_kind': 'INDEPENDENT_CUTOFF_SNAPSHOT',
            'record_id': 'company-forecast-event-01-600000-sh',
            'dataset_version': 'fingoose-macro-event-company-v1.0',
            'event_id': 'event-01', 'company_code': '600000.SH',
            'forecast_as_of_at': '2024-01-05T23:59:59+08:00',
            'event_materials': [{'source_id': 'event-official-1', 'published_at': '2024-01-02T09:00:00+08:00'}],
            'industry_materials': [{'source_id': 'industry-official-1', 'published_at': '2024-01-03T09:00:00+08:00'}],
            'company_materials': [{'source_id': 'company-disclosure-1', 'published_at': '2024-01-04T09:00:00+08:00'}],
            'stock_windows': {'D1': {'return_pct': 1.0}, 'D3': {'return_pct': 2.0}},
            'visible_windows': ['D1', 'D3'],
            'forecast_labels': [
                {'label_type': 'REVENUE', 'direction': 'UP'},
                {'label_type': 'PROFIT', 'direction': 'DOWN'},
                {'label_type': 'OPERATING_CASH_FLOW', 'direction': 'UNCERTAIN'},
            ],
            'transmission_chain': ['重大事件', '行业/宏观变量', '公司业务暴露', '经营指标', '财务结果', '竞争解释'],
        }

    def test_builds_from_independent_snapshot_without_mutating_input(self):
        from fingoose_macro_event_company_v1 import build_company_forecast_projection

        snapshot = self.cutoff_snapshot()
        original = copy.deepcopy(snapshot)
        result = build_company_forecast_projection(snapshot)

        self.assertEqual(snapshot, original)
        self.assertEqual(result['visible_windows'], ['D1', 'D3'])
        self.assertEqual(set(result['stock_windows']), {'D1', 'D3'})
        self.assertEqual(result['projection_source'], 'INDEPENDENT_CUTOFF_SNAPSHOT')

    def test_recursively_rejects_future_and_retrospective_leakage(self):
        from fingoose_macro_event_company_v1 import build_company_forecast_projection

        bad_updates = (
            {'company_materials': [{'source_id': 'future-report', 'published_at': '2024-01-06T00:00:00+08:00'}]},
            {'actual_value': 123},
            {'nested': {'future_source_id': 'cninfo-next-quarter'}},
            {'stock_windows': {'D1': {}, 'D3': {}, 'D5': {}}},
            {'nested': {'D20': {'return_pct': 9.0}}},
            {'next_quarter_results': {'profit': 1}},
            {'retrospective_attribution': 'verified after results'},
        )
        for update in bad_updates:
            with self.subTest(update=update):
                with self.assertRaisesRegex(ValueError, 'LEAKAGE|FUTURE'):
                    build_company_forecast_projection({**self.cutoff_snapshot(), **update})

    def test_rejects_post_event_dossier_even_if_obvious_fields_were_removed(self):
        from fingoose_macro_event_company_v1 import build_company_forecast_projection

        sanitized = self.cutoff_snapshot()
        sanitized['snapshot_kind'] = 'POST_EVENT_DOSSIER'
        with self.assertRaisesRegex(ValueError, 'INDEPENDENT_CUTOFF_SNAPSHOT_REQUIRED'):
            build_company_forecast_projection(sanitized)


def release_records(size=9):
    reviews = []
    for index in range(size):
        review = review_fixture()
        review['review_id'] = f'review-{index:02d}'
        reviews.append(review)
    associations = (['VERIFIED_ASSOCIATION'] * size if size == 9 else
                    ['VERIFIED_ASSOCIATION'] * 10 + ['CONTRIBUTING_ASSOCIATION'] * 10 +
                    ['WEAK_RELATION'] * 5 + ['UNSUPPORTED'] * 5)
    directions = (['UP'] * size if size == 9 else ['UP'] * 15 + ['DOWN'] * 15)
    attribution = [
        {'record_id': f'attribution-{index:02d}', 'association': associations[index], 'direction': directions[index]}
        for index in range(size)
    ]
    return {
        'dossiers': [{'dossier_id': f'dossier-{index:02d}'} for index in range(size)],
        'attribution_samples': attribution,
        'forecast_samples': [{'record_id': f'forecast-{index:02d}'} for index in range(size)],
        'review_records': reviews,
        'training_projection': [{'record_id': f'public-{index:02d}', 'visible_windows': ['D1', 'D3']} for index in range(size * 2)],
        'leakage_findings': [], 'rejected': [],
    }


class CompanyReleaseGateTests(unittest.TestCase):
    def test_pilot_and_formal_counts_can_be_ready(self):
        from fingoose_macro_event_company_v1 import validate_company_release

        pilot = validate_company_release(release_records(9), pilot_mode=True)
        formal = validate_company_release(release_records(30), pilot_mode=False)

        self.assertTrue(pilot['formal_ready'])
        self.assertEqual((pilot['dossier_count'], pilot['sample_count']), (9, 18))
        self.assertTrue(formal['formal_ready'])
        self.assertTrue(formal['gates']['label_distribution'])

    def test_any_count_review_leakage_or_distribution_failure_blocks_release(self):
        from fingoose_macro_event_company_v1 import validate_company_release

        cases = []
        count_bad = release_records(9)
        count_bad['forecast_samples'].pop()
        cases.append(count_bad)
        review_bad = release_records(9)
        review_bad['review_records'][0]['initial_review']['status'] = 'PENDING'
        cases.append(review_bad)
        leakage_bad = release_records(9)
        leakage_bad['training_projection'][0]['actual_value'] = 1
        cases.append(leakage_bad)
        distribution_bad = release_records(30)
        for sample in distribution_bad['attribution_samples']:
            sample.update(association='VERIFIED_ASSOCIATION', direction='UP')
        cases.append(distribution_bad)

        for index, records in enumerate(cases):
            with self.subTest(index=index):
                result = validate_company_release(records, pilot_mode=index < 3)
                self.assertFalse(result['formal_ready'])
                self.assertTrue(result['gate_failures'])
class CompanyContractHardeningTests(unittest.TestCase):
    def test_exact_calculations_accept_value_decimal_as_canonical_input(self):
        from fingoose_macro_event_company_v1 import calculate_period_comparison, derive_standalone_quarter

        current = metric_fact(period='2024H1', value_decimal='300.30')
        prior = metric_fact(period='2024Q1', value_decimal='100.10')
        current.pop('value')
        prior.pop('value')
        derived = derive_standalone_quarter(current, prior)
        compared = calculate_period_comparison(
            {**derived, 'period': '2024Q2'},
            {**prior, 'period': '2023Q2', 'value_decimal': '100.10'},
        )
        self.assertEqual(derived['value_decimal'], '200.20')
        self.assertEqual(compared['change_pct_decimal'], '100')

    def test_stock_window_names_csi300_values_explicitly(self):
        from fingoose_macro_event_company_v1 import compute_company_stock_window

        result = compute_company_stock_window(
            [{'date': '2024-01-02', 'close': 100}, {'date': '2024-01-03', 'close': 110}],
            [{'date': '2024-01-02', 'close': 200}, {'date': '2024-01-03', 'close': 204}],
            '2024-01-03',
        )
        self.assertEqual(result['windows']['D1']['csi300_return_pct'], result['windows']['D1']['benchmark_return_pct'])
        self.assertEqual(result['baseline']['csi300_close'], 200)

    def test_forecast_rejects_prefix_and_string_window_leakage(self):
        from fingoose_macro_event_company_v1 import build_company_forecast_projection

        base = CompanyForecastProjectionTests().cutoff_snapshot()
        for update in (
            {'actual_profit': 1}, {'future_financial_report': {}},
            {'retrospective_conclusion': 'known later'}, {'nested': ['D20']},
        ):
            with self.subTest(update=update):
                with self.assertRaisesRegex(ValueError, 'LEAKAGE|FUTURE'):
                    build_company_forecast_projection({**base, **update})


if __name__ == '__main__':
    unittest.main()
