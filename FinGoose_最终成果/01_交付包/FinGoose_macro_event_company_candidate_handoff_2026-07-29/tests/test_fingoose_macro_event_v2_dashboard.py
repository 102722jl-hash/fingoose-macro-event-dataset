from __future__ import annotations

import re
import unittest
from pathlib import Path

from fingoose_macro_event_v2_dashboard import (
    CSS_PATH,
    INDEX_HTML,
    JS_PATH,
    V2DashboardRepository,
)

ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = ROOT / 'data' / 'market_event_attribution_v2_candidate'
CONFIG_PATH = ROOT / 'configs' / 'fingoose_macro_events_v1.json'


class V2DashboardRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repository = V2DashboardRepository(DATA_ROOT, CONFIG_PATH)

    def test_overview_and_event_list_are_candidate_only(self):
        overview = self.repository.overview()
        self.assertEqual(overview['event_count'], 10)
        self.assertEqual(overview['market_window_count'], 40)
        self.assertEqual(overview['release_tier'], 'CANDIDATE')
        self.assertFalse(overview['formal_ready'])

        self.assertNotIn('challenge_event_count', overview)
        events = self.repository.list_events()
        self.assertEqual(len(events), 10)
        self.assertEqual(
            {row['event_id'] for row in events if row['split'] == 'EXAMPLE'},
            {'event-02', 'event-03', 'event-04'},
        )

    def test_event_detail_links_timeline_graph_windows_and_sources(self):
        detail = self.repository.event_detail('event-02')
        self.assertEqual(detail['event']['event_id'], 'event-02')
        self.assertGreaterEqual(len(detail['milestones']), 2)
        self.assertEqual(detail['graph']['event_id'], 'event-02')
        self.assertEqual(len(detail['market_windows']), 4)
        self.assertTrue(detail['sources'])
        self.assertNotIn('benchmark_labels', detail)
        self.assertNotIn('direction_label', str(detail))

        primary = next(
            row for row in detail['milestones'] if row['anchor_role'] == 'PRIMARY'
        )
        branch = self.repository.anchor_detail('event-02', primary['milestone_id'])
        self.assertEqual(branch['milestone']['milestone_id'], primary['milestone_id'])
        self.assertTrue(branch['edges'])
        self.assertEqual(len(branch['market_windows']), 4)

    def test_hidden_event_detail_exposes_inputs_without_reconstructable_labels(self):
        detail = self.repository.event_detail('event-05')
        serialized = str(detail)
        list_row = next(
            row for row in self.repository.list_events()
            if row['event_id'] == 'event-05'
        )
        self.assertNotIn('challenge_set', list_row)
        self.assertEqual(list_row['split'], 'HIDDEN_EVALUATION')

        self.assertTrue(detail['evaluation_restricted'])
        self.assertEqual(detail['milestones'], [])
        self.assertEqual(detail['episodes'], [])
        self.assertEqual(detail['graph']['nodes'], [])
        self.assertEqual(detail['graph']['edges'], [])
        self.assertTrue(detail['evidence_timeline'])
        self.assertNotIn('expected_d3_direction', serialized)
        self.assertNotIn("'attribution'", serialized)
        self.assertNotIn('confounder_level', serialized)
        self.assertNotIn('challenge_set', serialized)

        for row in detail['market_windows']:
            self.assertEqual(
                {name for name, point in row['windows'].items() if point is not None},
                {'T60', 'T20', 'T1'},
            )
        hidden_milestone = next(
            row for row in self.repository.milestones
            if row['event_id'] == 'event-05'
        )
        with self.assertRaises(KeyError):
            self.repository.anchor_detail(
                'event-05', hidden_milestone['milestone_id'])

    def test_window_payload_exposes_before_after_values_and_formula(self):
        detail = self.repository.event_detail('event-03')
        dgs10 = next(
            row for row in detail['market_windows'] if row['series_id'] == 'DGS10'
        )
        self.assertEqual(dgs10['windows']['T1']['date'], '2022-06-14')
        self.assertEqual(dgs10['windows']['T1']['value'], 3.49)
        self.assertEqual(dgs10['windows']['D3']['date'], '2022-06-17')
        self.assertEqual(dgs10['windows']['D3']['value'], 3.25)
        self.assertIn('T-1', dgs10['calculation_basis'])

    def test_page_contract_supports_linked_read_only_workspace(self):
        for token in (
            'event-list',
            'timeline-track',
            'timeline-boundary',
            'graph-branches',
            'market-series-tabs',
            'window-table',
            'evidence-panel',
            'confounder-panel',
            'visibility-filter',
            'fingoose_macro_event_v2_dashboard.js',
        ):
            self.assertIn(token, INDEX_HTML)

        script = JS_PATH.read_text(encoding='utf-8')
        for token in (
            'selectMilestone',
            'renderTimeline',
            'renderGraph',
            'renderMarket',
            'renderEvidence',
            'PUBLIC_PREDICTION',
            'HIDDEN_VALIDATION',
            'raw_change',
            'standardized_change',
            'eventRequestToken',
            'anchorRequestToken',
            'evidence_timeline',
            'first_public_at',
            'try {',
            'finally {',
            'relative_change',
            'empirical_percentile',
        ):
            self.assertIn(token, script)

        stylesheet = CSS_PATH.read_text(encoding='utf-8')
        for token in (
            '.timeline-track',
            '.branch-row',
            '.window-table',
            '@media (max-width: 760px)',
            'overflow-x: auto',
        ):
            self.assertIn(token, stylesheet)


    def test_mobile_timeline_boundary_occupies_its_own_row_without_covering_nodes(self):
        stylesheet = CSS_PATH.read_text(encoding='utf-8')
        desktop, separator, responsive = stylesheet.partition('@media (max-width: 760px)')
        self.assertTrue(separator)
        mobile = responsive.partition('@media (max-width: 430px)')[0]

        self.assertRegex(
            desktop,
            re.compile(r'\.timeline-boundary\s*\{[^}]*position:\s*absolute', re.S),
        )
        self.assertRegex(
            mobile,
            re.compile(
                r'\.timeline-viewport\s*\{[^}]*display:\s*flex;'
                r'[^}]*flex-direction:\s*column',
                re.S,
            ),
        )
        self.assertRegex(
            mobile,
            re.compile(
                r'\.timeline-boundary\s*\{[^}]*position:\s*static;'
                r'[^}]*order:\s*-1',
                re.S,
            ),
        )
        self.assertRegex(
            mobile,
            re.compile(
                r'\.timeline-boundary span\s*\{[^}]*writing-mode:\s*horizontal-tb',
                re.S,
            ),
        )

if __name__ == '__main__':
    unittest.main()
