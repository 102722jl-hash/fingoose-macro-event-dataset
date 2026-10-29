from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work' / 'timeline_fast_candidate_v2'


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]


def anchor_milestones() -> list[dict]:
    return read_jsonl(
        ROOT / 'data' / 'market_event_attribution_v2_candidate'
        / 'event_milestones.jsonl'
    ) + read_jsonl(WORK / 'promotable_milestones.jsonl')


class TwentyFourAnchorCatalogTests(unittest.TestCase):
    def test_catalog_contains_exactly_verified_nodes_and_resolves_milestones(self):
        from build_fingoose_24_anchor_transmission_graphs import (
            STABLE_ANCHOR_FAST_NODE_IDS,
            build_anchor_catalog,
        )

        timeline_nodes = read_jsonl(WORK / 'timeline_nodes.jsonl')
        promotable = anchor_milestones()
        anchors = build_anchor_catalog(timeline_nodes, promotable)

        stable_verified = set(STABLE_ANCHOR_FAST_NODE_IDS)

        pending = {
            row['fast_node_id']
            for row in timeline_nodes
            if row['evidence_status'] == 'PENDING_EVIDENCE'
        }

        self.assertEqual(len(anchors), 24)
        self.assertEqual({row['fast_node_id'] for row in anchors}, stable_verified)
        self.assertEqual({row['evidence_status'] for row in anchors}, {'VERIFIED_EXISTING'})
        self.assertTrue(all(row['milestone_id'] for row in anchors))
        self.assertTrue(all(row['occurred_at'] and row['first_public_at'] for row in anchors))
        self.assertTrue(all(row['source_ids'] for row in anchors))
        self.assertEqual(
            sum(row['activation_mode'] == 'OBSERVATION_ONLY' for row in anchors),
            10,
        )
        self.assertEqual(
            sum(row['activation_mode'] == 'CAUSAL_CANDIDATE' for row in anchors),
            14,
        )
        self.assertEqual(
            {row['fast_node_id'] for row in anchors if not row.get('original_milestone_id')},
            {'fast-event-03-M01', 'fast-event-03-M02', 'fast-event-09-M02'},
        )

        tampered_nodes = copy.deepcopy(timeline_nodes)
        tampered = next(
            row for row in tampered_nodes
            if row['fast_node_id'] == 'fast-event-01-M03'
        )
        tampered['node_action'] = 'STARTS'
        tampered['sequence'] = 99
        tampered['original_milestone_id'] = 'milestone-event-01-1f0d9ae571b0'
        rebuilt = build_anchor_catalog(tampered_nodes, promotable)
        restored = next(
            row for row in rebuilt
            if row['fast_node_id'] == 'fast-event-01-M03'
        )
        self.assertEqual(restored['node_action'], 'OBSERVES')
        self.assertEqual(restored['sequence'], 3)
        self.assertEqual(restored['activation_mode'], 'OBSERVATION_ONLY')
        self.assertEqual(
            restored['milestone_id'],
            'milestone-event-01-81cfcd5e5437',
        )

    def test_dynamic_bindings_cover_causal_anchors_and_isolate_observations(self):
        from build_fingoose_24_anchor_transmission_graphs import (
            build_anchor_catalog,
            build_dynamic_bindings,
        )

        timeline_nodes = read_jsonl(WORK / 'timeline_nodes.jsonl')
        anchors = build_anchor_catalog(
            timeline_nodes,
            anchor_milestones(),
        )
        graphs = read_jsonl(
            ROOT / 'data' / 'market_event_attribution_v2_candidate'
            / 'transmission_graphs.jsonl'
        )
        bindings = build_dynamic_bindings(anchors, graphs)

        known_edges = {
            edge['edge_id']
            for graph in graphs
            for edge in graph['edges']
        }
        causal_ids = {
            row['fast_node_id']
            for row in anchors
            if row['activation_mode'] == 'CAUSAL_CANDIDATE'
        }
        observation_ids = {
            row['fast_node_id']
            for row in anchors
            if row['activation_mode'] == 'OBSERVATION_ONLY'
        }

        self.assertEqual(
            {row['anchor_fast_node_id'] for row in bindings},
            causal_ids,
        )
        self.assertFalse(
            observation_ids & {row['anchor_fast_node_id'] for row in bindings}
        )
        self.assertTrue(all(row['edge_id'] in known_edges for row in bindings))
        self.assertTrue(all(row['binding_status'] == 'PROPOSED' for row in bindings))
        self.assertTrue(all(row['review'] is None for row in bindings))
        self.assertTrue(all(row['anchor_source_ids'] for row in bindings))
        self.assertTrue(all(row['conditions'] for row in bindings))
        self.assertTrue(all(row['invalidation_conditions'] for row in bindings))
        self.assertTrue(all(
            row['anchor_evidence_scope'] == 'FACT_AND_TIME_ONLY'
            for row in bindings
        ))
        expected_overlays = {
            'fast-event-03-M02': {
                'event-03-edge-shock-rate-expectations',
            },
            'fast-event-05-M03': {
                'event-05-edge-shock-banking-stress',
                'event-05-edge-shock-rate-expectations',
                'event-05-edge-shock-safe-haven-demand',
            },
            'fast-event-10-M03': {
                'event-10-edge-shock-global-growth',
                'event-10-edge-shock-safe-haven-demand',
                'event-10-edge-shock-trade-costs',
            },
        }
        for anchor_id, edge_ids in expected_overlays.items():
            selected = {
                row['edge_id']
                for row in bindings
                if row['anchor_fast_node_id'] == anchor_id
            }
            self.assertEqual(selected, edge_ids)
            self.assertTrue(all(
                row['edge_selection_mode'] == 'EXPLICIT_ENTRY_EDGE_OVERLAY'
                for row in bindings
                if row['anchor_fast_node_id'] == anchor_id
            ))

    def test_validation_reports_projection_corruption_as_hard_failures(self):
        from build_fingoose_24_anchor_transmission_graphs import (
            build_anchor_catalog,
            build_dynamic_bindings,
            build_projection_graphs,
            build_source_registry,
            validate_projection,
        )

        timeline_nodes = read_jsonl(WORK / 'timeline_nodes.jsonl')
        anchors = build_anchor_catalog(
            timeline_nodes,
            anchor_milestones(),
        )
        source_graphs = read_jsonl(
            ROOT / 'data' / 'market_event_attribution_v2_candidate'
            / 'transmission_graphs.jsonl'
        )
        graphs = build_projection_graphs(anchors, source_graphs)
        bindings = build_dynamic_bindings(anchors, graphs)
        registry = build_source_registry(ROOT)

        self.assertEqual(
            validate_projection(ROOT, anchors, graphs, bindings, registry),
            [],
        )

        bad_anchors = copy.deepcopy(anchors)
        bad_anchors[0]['evidence_status'] = 'PENDING_EVIDENCE'
        bad_anchors[0]['activation_mode'] = 'CAUSAL_CANDIDATE'
        bad_anchors[1]['anchor_id'] = 'tampered-anchor'
        bad_anchors[1]['milestone_id'] = 'tampered-milestone'

        bad_bindings = copy.deepcopy(bindings)
        bad_bindings[0]['edge_id'] = 'unknown-edge'
        bad_bindings[0]['binding_status'] = 'CONFIRMED'
        bad_bindings[2]['from_node_id'] = 'tampered-node'
        bad_bindings[3]['counterevidence_status'] = 'TAMPERED'
        bad_bindings[4]['event_id'] = 'event-02'
        bad_bindings.append(copy.deepcopy(bad_bindings[1]))
        observation = next(
            row for row in anchors
            if row['activation_mode'] == 'OBSERVATION_ONLY'
        )
        observation_binding = copy.deepcopy(bindings[2])
        observation_binding['binding_id'] = 'binding-observation-corruption'
        observation_binding['anchor_fast_node_id'] = observation['fast_node_id']
        observation_binding['anchor_milestone_id'] = observation['milestone_id']
        bad_bindings.append(observation_binding)

        bad_registry = copy.deepcopy(registry)
        used_source = anchors[0]['source_ids'][0]
        bad_registry[used_source]['sha256'] = '0' * 64

        failures = validate_projection(
            ROOT,
            bad_anchors,
            graphs,
            bad_bindings,
            bad_registry,
        )

        self.assertIn(
            f'PENDING_ANCHOR:{bad_anchors[0]["fast_node_id"]}',
            failures,
        )
        self.assertIn('UNKNOWN_EDGE:unknown-edge', failures)
        self.assertIn(
            f'NON_PROPOSED_BINDING:{bad_bindings[0]["binding_id"]}',
            failures,
        )
        self.assertIn(
            f'DUPLICATE_BINDING_ID:{bad_bindings[1]["binding_id"]}',
            failures,
        )
        self.assertIn(
            f'BINDING_EDGE_PAYLOAD_DRIFT:{bad_bindings[2]["binding_id"]}',
            failures,
        )
        self.assertIn(
            f'BINDING_EDGE_PAYLOAD_DRIFT:{bad_bindings[3]["binding_id"]}',
            failures,
        )
        self.assertIn(
            f'BINDING_ANCHOR_PAYLOAD_DRIFT:{bad_bindings[4]["binding_id"]}',
            failures,
        )
        self.assertIn(
            f'ANCHOR_CONTRACT_DRIFT:{bad_anchors[0]["fast_node_id"]}',
            failures,
        )
        self.assertIn(
            f'ANCHOR_CONTRACT_DRIFT:{bad_anchors[1]["fast_node_id"]}',
            failures,
        )
        self.assertIn(
            f'OBSERVATION_ONLY_BINDING:{observation["fast_node_id"]}',
            failures,
        )
        self.assertIn(f'SOURCE_HASH_MISMATCH:{used_source}', failures)


if __name__ == '__main__':
    unittest.main()
