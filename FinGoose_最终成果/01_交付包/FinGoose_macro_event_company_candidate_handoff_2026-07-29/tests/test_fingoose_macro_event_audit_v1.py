from __future__ import annotations

import unittest


class MacroEventAuditTests(unittest.TestCase):
    def test_display_id_explains_event_variant_target_and_channel(self):
        from fingoose_macro_event_audit_v1 import build_display_id

        self.assertEqual(
            build_display_id(
                event_id='event-01',
                record_id='macro-event-100-v1-event-01-01',
                sample_kind='single_target',
                target_series_ids=['SP500'],
                channel='RISK_APPETITE',
            ),
            'E01-S01 | 单目标 | SP500 | 风险偏好',
        )

    def test_audit_sample_maps_each_public_claim_to_locatable_visible_evidence(self):
        from fingoose_macro_event_audit_v1 import build_audit_sample, validate_audit_sample

        sample = {
            'record_id': 'macro-event-100-v1-event-01-01',
            'event_id': 'event-01',
            'sample_kind': 'single_target',
            'target_series_ids': ['SP500'],
            'forecast_as_of_at': '2020-03-13T23:59:59+00:00',
            'visible_evidence_ids': ['event-source', 'report-source'],
            'period_comparison': {
                'start_date': '2020-03-11',
                'end_date': '2020-03-13',
                'summary': 'First three sessions.',
            },
            'fact_transmission_chain': {
                'selected_channel': 'RISK_APPETITE',
                'nodes': [
                    {'node_id': 'n1', 'node_type': 'event', 'statement': 'Event occurred.'},
                    {'node_id': 'n2', 'node_type': 'mechanism', 'statement': 'Risk appetite weakened.'},
                    {'node_id': 'n3', 'node_type': 'market', 'statement': 'Equities repriced.'},
                ],
                'edges': [
                    {'from_node_id': 'n1', 'to_node_id': 'n2', 'relation': 'CHANGES_EXPECTATIONS'},
                    {'from_node_id': 'n2', 'to_node_id': 'n3', 'relation': 'TRANSMITS_TO'},
                ],
            },
            'supporting_observations': [
                {'series_id': 'SP500', 'series_name': 'S&P 500', 'd1_change': -2.0, 'd3_change': -4.0, 'period_end_date': '2020-03-13'},
                {'series_id': 'VIXCLS', 'series_name': 'VIX', 'd1_change': 5.0, 'd3_change': 8.0, 'period_end_date': '2020-03-13'},
            ],
            'counterevidence': ['Oil shock also mattered.'],
            'short_horizon_prediction': {
                'target_series_id': 'SP500', 'direction': 'DOWN', 'confidence': 'MEDIUM',
            },
            'review_status': 'PENDING_HUMAN_REVIEW',
        }
        manifest = {
            'event-source': {
                'source_id': 'event-source', 'title': 'Official event', 'publisher': 'Official body',
                'source_url': 'https://official.example/event', 'published_at': '2020-03-11T12:00:00+00:00',
                'locator': {'type': 'html_text', 'value': 'Event occurred.'}, 'content_sha256': 'a' * 64,
                'summary': 'Event occurred.',
            },
            'report-source': {
                'source_id': 'report-source', 'title': 'Official report', 'publisher': 'Official body',
                'source_url': 'https://official.example/report', 'published_at': '2020-03-12T12:00:00+00:00',
                'locator': {'type': 'pdf_page', 'value': '2'}, 'content_sha256': 'b' * 64,
                'summary': 'Risk conditions weakened.',
            },
        }

        audited = build_audit_sample(sample, manifest)

        self.assertEqual(audited['display_id'], 'E01-S01 | 单目标 | SP500 | 风险偏好')
        self.assertEqual(
            {claim['claim_type'] for claim in audited['claims']},
            {'event_fact', 'data_observation', 'transmission_assessment', 'prediction', 'counterevidence'},
        )
        self.assertTrue(all(claim['evidence_refs'] for claim in audited['claims']))
        self.assertEqual(validate_audit_sample(audited, manifest), [])
        manifest['event-source']['content_sha256'] = 'a' * 30 + 'd20' + 'a' * 31
        audited['claims'][0]['evidence_refs'][0]['content_sha256'] = manifest['event-source']['content_sha256']
        self.assertNotIn('HIDDEN_VALIDATION_LEAK', validate_audit_sample(audited, manifest))

    def test_company_impact_requires_three_evidence_segments_and_counterevidence(self):
        from fingoose_macro_event_audit_v1 import build_company_impact_link

        incomplete = build_company_impact_link(
            event_id='event-01', company_code='000002.SZ', company_name='China Vanke',
            event_evidence_ids=['event-source'], industry_evidence_ids=['industry-source'],
            company_evidence_ids=[], counterevidence_ids=['counter-source'],
            manifest={}, period={'start_date': '2020-03-01', 'end_date': '2020-06-30'},
            impact_metric='revenue', impact_direction='DOWN', transmission_summary='Test chain.',
        )
        self.assertEqual(incomplete['association_status'], 'INSUFFICIENT_EVIDENCE')

        verified = build_company_impact_link(
            event_id='event-01', company_code='000002.SZ', company_name='China Vanke',
            event_evidence_ids=['event-source'], industry_evidence_ids=['industry-source'],
            company_evidence_ids=['company-source'], counterevidence_ids=['counter-source'],
            manifest={source_id: {'source_id': source_id} for source_id in (
                'event-source', 'industry-source', 'company-source', 'counter-source',
            )},
            period={'start_date': '2020-03-01', 'end_date': '2020-06-30'},
            impact_metric='revenue', impact_direction='DOWN', transmission_summary='Test chain.',
        )
        self.assertEqual(verified['association_status'], 'VERIFIED')


if __name__ == '__main__':
    unittest.main()
