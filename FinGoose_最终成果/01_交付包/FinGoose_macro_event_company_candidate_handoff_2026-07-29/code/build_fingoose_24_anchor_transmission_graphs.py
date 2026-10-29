"""Build an isolated dynamic transmission projection for 24 verified anchors."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from fingoose_macro_event_attribution_v2 import (
    transmission_graph_errors,
    validate_schema_record,
)


STABLE_ANCHOR_ACTIONS = {
    'fast-event-01-M03': 'OBSERVES',
    'fast-event-01-M04': 'STARTS',
    'fast-event-02-M01': 'OBSERVES',
    'fast-event-02-M03': 'STARTS',
    'fast-event-02-M04': 'AMPLIFIES',
    'fast-event-03-M01': 'OBSERVES',
    'fast-event-03-M02': 'AMPLIFIES',
    'fast-event-03-M03': 'STARTS',
    'fast-event-03-M05': 'OBSERVES',
    'fast-event-04-M03': 'STARTS',
    'fast-event-04-M04': 'OBSERVES',
    'fast-event-05-M02': 'STARTS',
    'fast-event-05-M03': 'WEAKENS',
    'fast-event-06-M02': 'OBSERVES',
    'fast-event-06-M03': 'STARTS',
    'fast-event-07-M01': 'STARTS',
    'fast-event-07-M02': 'OBSERVES',
    'fast-event-08-M02': 'OBSERVES',
    'fast-event-08-M04': 'STARTS',
    'fast-event-09-M01': 'OBSERVES',
    'fast-event-09-M02': 'OBSERVES',
    'fast-event-09-M03': 'STARTS',
    'fast-event-10-M02': 'STARTS',
    'fast-event-10-M03': 'AMPLIFIES',
}
STABLE_ANCHOR_FAST_NODE_IDS = frozenset(STABLE_ANCHOR_ACTIONS)
STABLE_ANCHOR_MILESTONE_IDS = {
    'fast-event-01-M03': 'milestone-event-01-81cfcd5e5437',
    'fast-event-01-M04': 'milestone-event-01-1f0d9ae571b0',
    'fast-event-02-M01': 'milestone-event-02-a15f1fe4410d',
    'fast-event-02-M03': 'milestone-event-02-47ac72edd092',
    'fast-event-02-M04': 'milestone-event-02-d8017a79fdfc',
    'fast-event-03-M01': 'milestone-event-03-281443284015',
    'fast-event-03-M02': 'milestone-event-03-072bc5a52ec5',
    'fast-event-03-M03': 'milestone-event-03-3c2b0dbb65d4',
    'fast-event-03-M05': 'milestone-event-03-62fc34af53b1',
    'fast-event-04-M03': 'milestone-event-04-abc104cc4aa0',
    'fast-event-04-M04': 'milestone-event-04-5c3b3e575cb6',
    'fast-event-05-M02': 'milestone-event-05-4d0e10c71b19',
    'fast-event-05-M03': 'milestone-event-05-d12ca8adba7a',
    'fast-event-06-M02': 'milestone-event-06-072c8b1ea560',
    'fast-event-06-M03': 'milestone-event-06-8de7f47124a8',
    'fast-event-07-M01': 'milestone-event-07-5505bb622d95',
    'fast-event-07-M02': 'milestone-event-07-019c05c801b0',
    'fast-event-08-M02': 'milestone-event-08-bf7751834310',
    'fast-event-08-M04': 'milestone-event-08-3e6e93e33155',
    'fast-event-09-M01': 'milestone-event-09-10899245ebe6',
    'fast-event-09-M02': 'milestone-event-09-870a266a883b',
    'fast-event-09-M03': 'milestone-event-09-7b9407830781',
    'fast-event-10-M02': 'milestone-event-10-30c54387a6e6',
    'fast-event-10-M03': 'milestone-event-10-87a14b1556ae',
}
EXPLICIT_OVERLAY_EDGE_IDS = {
    'fast-event-03-M02': frozenset({
        'event-03-edge-shock-rate-expectations',
    }),
    'fast-event-05-M03': frozenset({
        'event-05-edge-shock-banking-stress',
        'event-05-edge-shock-rate-expectations',
        'event-05-edge-shock-safe-haven-demand',
    }),
    'fast-event-10-M03': frozenset({
        'event-10-edge-shock-global-growth',
        'event-10-edge-shock-safe-haven-demand',
        'event-10-edge-shock-trade-costs',
    }),
}
def build_anchor_catalog(
    timeline_nodes: list[dict[str, Any]],
    milestone_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Project the pinned 24-anchor contract from canonical milestone evidence."""
    milestone_by_id: dict[str, dict[str, Any]] = {}
    for milestone in milestone_records:
        milestone_by_id.setdefault(milestone['milestone_id'], milestone)
    available_fast_node_ids = {
        node['fast_node_id'] for node in timeline_nodes
    }
    anchors: list[dict[str, Any]] = []
    for fast_node_id in sorted(STABLE_ANCHOR_FAST_NODE_IDS):
        if fast_node_id not in available_fast_node_ids:
            continue
        milestone_id = STABLE_ANCHOR_MILESTONE_IDS[fast_node_id]
        milestone = milestone_by_id.get(milestone_id)
        if milestone is None:
            continue
        node_action = STABLE_ANCHOR_ACTIONS[fast_node_id]
        sequence = int(fast_node_id.rsplit('-M', 1)[1])
        activation_mode = (
            'OBSERVATION_ONLY'
            if node_action == 'OBSERVES'
            else 'CAUSAL_CANDIDATE'
        )
        source_ids = [
            source['evidence_id'] for source in milestone.get('sources', [])
        ]
        is_supplemental = any(
            source_id.startswith('supplemental-') for source_id in source_ids
        )
        anchors.append({
            'anchor_id': f'anchor-{fast_node_id}',
            'event_id': milestone['event_id'],
            'fast_node_id': fast_node_id,
            'milestone_id': milestone_id,
            'original_milestone_id': None if is_supplemental else milestone_id,
            'sequence': sequence,
            'phase': milestone['phase'],
            'node_action': node_action,
            'anchor_role': milestone['anchor_role'],
            'activation_mode': activation_mode,
            'occurred_at': milestone['occurred_at'],
            'first_public_at': milestone['first_public_at'],
            'fact': milestone['fact'],
            'source_ids': source_ids,
            'impact_tags': list(milestone.get('impact_tags') or []),
            'visibility': milestone['visibility'],
            'evidence_status': 'VERIFIED_EXISTING',
            'binding_status': 'PROPOSED',
        })
    return anchors

def _stable_binding_id(anchor: dict[str, Any], edge: dict[str, Any]) -> str:
    payload = json.dumps(
        [anchor['event_id'], anchor['fast_node_id'], edge['edge_id']],
        ensure_ascii=True,
        separators=(',', ':'),
    ).encode('utf-8')
    return f"binding-{anchor['event_id']}-{hashlib.sha256(payload).hexdigest()[:12]}"


def _explicit_overlay_edges(
    anchor: dict[str, Any],
    graph: dict[str, Any],
) -> list[dict[str, Any]]:
    allowed_edge_ids = EXPLICIT_OVERLAY_EDGE_IDS.get(anchor['fast_node_id'])
    if not allowed_edge_ids:
        return []
    selected = [
        edge for edge in graph['edges'] if edge['edge_id'] in allowed_edge_ids
    ]
    if {edge['edge_id'] for edge in selected} != set(allowed_edge_ids):
        return []
    return selected

def build_dynamic_bindings(
    anchors: list[dict[str, Any]],
    graphs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Bind causal timeline anchors to existing proposed graph edges."""
    graph_by_event = {graph['event_id']: graph for graph in graphs}
    bindings: list[dict[str, Any]] = []
    for anchor in anchors:
        if STABLE_ANCHOR_ACTIONS.get(anchor['fast_node_id']) == 'OBSERVES':
            continue
        graph = graph_by_event[anchor['event_id']]
        selected = [
            edge for edge in graph['edges']
            if edge.get('anchor_milestone_id') == anchor['milestone_id']
        ]
        edge_selection_mode = 'DIRECT_MILESTONE'
        if not selected:
            selected = _explicit_overlay_edges(anchor, graph)
            edge_selection_mode = 'EXPLICIT_ENTRY_EDGE_OVERLAY'
        if not selected:
            raise ValueError(f'CAUSAL_ANCHOR_WITHOUT_EDGE:{anchor["fast_node_id"]}')
        for edge in selected:
            counterevidence = list(edge.get('counterevidence') or [])
            bindings.append({
                'binding_id': _stable_binding_id(anchor, edge),
                'event_id': anchor['event_id'],
                'anchor_fast_node_id': anchor['fast_node_id'],
                'anchor_milestone_id': anchor['milestone_id'],
                'anchor_action': anchor['node_action'],
                'edge_selection_mode': edge_selection_mode,
                'anchor_source_ids': list(anchor['source_ids']),
                'anchor_evidence_scope': 'FACT_AND_TIME_ONLY',
                'edge_id': edge['edge_id'],
                'from_node_id': edge['from_node_id'],
                'to_node_id': edge['to_node_id'],
                'expected_path': dict(edge['expected_path']),
                'lag': dict(edge['lag']),
                'conditions': list(edge.get('conditions') or []),
                'invalidation_conditions': list(
                    edge.get('invalidation_conditions') or []
                ),
                'mechanism_evidence': list(edge.get('evidence') or []),
                'mechanism_evidence_scope': 'INHERITED_GRAPH_PROPOSAL',
                'counterevidence': counterevidence,
                'counterevidence_status': 'LINKED' if counterevidence else 'UNLINKED',
                'confidence': edge.get('confidence'),
                'binding_status': 'PROPOSED',
                'review': None,
            })
    return sorted(
        bindings,
        key=lambda row: (
            row['event_id'],
            row['anchor_fast_node_id'],
            row['edge_id'],
        ),
    )
PRODUCTION_SHA256 = {
    'event_milestones.jsonl': '2fafc57e304f810ef24c65c7248de487e711574108b179231e3f9ff869048d8a',
    'event_episodes.jsonl': '32626f4dd798c315ee1529581e31165369826c4119c5fd51fa82442623b4349b',
    'manifest.json': '3c0cd2d56aed32ac518231fb855dc69dc23c37f73e5b645ff1b84e4bdb48f4d1',
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    payload = ''.join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'
        for row in rows
    )
    path.write_text(payload, encoding='utf-8', newline='\n')


def build_projection_graphs(
    anchors: list[dict[str, Any]],
    graphs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extend graph milestone directories without changing topology or edge claims."""
    projected = copy.deepcopy(graphs)
    for graph in projected:
        event_anchors = [
            anchor for anchor in anchors if anchor['event_id'] == graph['event_id']
        ]
        graph['milestone_ids'] = [
            anchor['milestone_id']
            for anchor in sorted(event_anchors, key=lambda row: row['sequence'])
        ]
    return projected


def build_source_registry(root: Path) -> dict[str, dict[str, Any]]:
    """Resolve production and accepted supplemental source snapshots."""
    production_manifest = _read_jsonl(
        root / 'data' / 'market_event_attribution_v2_candidate' / 'source_manifest.jsonl'
    )
    supplemental_manifest = _read_jsonl(
        root / 'work' / 'timeline_fast_candidate_v2' / 'candidate_source_manifest.jsonl'
    )
    registry: dict[str, dict[str, Any]] = {}
    production_snapshot_root = root / 'evidence_snapshots' / 'macro_event_attribution_v1'
    for row in production_manifest:
        registry[row['evidence_id']] = {
            'source_id': row['evidence_id'],
            'sha256': row['sha256'],
            'snapshot_path': str(
                (production_snapshot_root / row['snapshot_path']).resolve()
            ),
            'source_tier': row['source_tier'],
            'published_at': row['published_at'],
        }
    supplemental_snapshot_root = root / 'work' / 'timeline_fast_candidate_v2'
    for row in supplemental_manifest:
        if row.get('decision') not in {'ACCEPT', 'ACCEPTED'}:
            continue
        registry[row['candidate_source_id']] = {
            'source_id': row['candidate_source_id'],
            'sha256': row['sha256'],
            'snapshot_path': str(
                (supplemental_snapshot_root / row['snapshot_path']).resolve()
            ),
            'source_tier': row['source_tier'],
            'published_at': None,
        }
    return registry


def _production_hashes(root: Path) -> dict[str, str]:
    production = root / 'data' / 'market_event_attribution_v2_candidate'
    return {
        name: _sha256(production / name)
        for name in PRODUCTION_SHA256
    }


def validate_projection(
    root: Path,
    anchors: list[dict[str, Any]],
    graphs: list[dict[str, Any]],
    bindings: list[dict[str, Any]],
    source_registry: dict[str, dict[str, Any]],
) -> list[str]:
    """Return named hard failures for anchor, graph, binding, source, or baseline drift."""
    failures: list[str] = []
    anchor_by_id = {row['fast_node_id']: row for row in anchors}
    if len(anchors) != 24 or len(anchor_by_id) != 24:
        failures.append('ANCHOR_COUNT_OR_ID_UNIQUENESS')
    if set(anchor_by_id) != set(STABLE_ANCHOR_FAST_NODE_IDS):
        failures.append('ANCHOR_STABLE_ID_SET_DRIFT')
    expected_events = {f'event-{index:02d}' for index in range(1, 11)}
    if {row['event_id'] for row in anchors} != expected_events:
        failures.append('ANCHOR_EVENT_COVERAGE')
    for anchor in anchors:
        fast_node_id = anchor['fast_node_id']
        if anchor.get('evidence_status') != 'VERIFIED_EXISTING':
            failures.append(f'PENDING_ANCHOR:{fast_node_id}')
        if not anchor.get('occurred_at') or not anchor.get('first_public_at'):
            failures.append(f'ANCHOR_TIME_UNRESOLVED:{fast_node_id}')
        if not anchor.get('source_ids'):
            failures.append(f'ANCHOR_SOURCE_REQUIRED:{fast_node_id}')
        expected_action = STABLE_ANCHOR_ACTIONS.get(fast_node_id)
        expected_milestone_id = STABLE_ANCHOR_MILESTONE_IDS.get(fast_node_id)
        expected_sequence = (
            int(fast_node_id.rsplit('-M', 1)[1]) if expected_action else None
        )
        expected_activation_mode = (
            'OBSERVATION_ONLY'
            if expected_action == 'OBSERVES'
            else 'CAUSAL_CANDIDATE'
        )
        expected_event_id = (
            '-'.join(expected_milestone_id.split('-')[1:3])
            if expected_milestone_id else None
        )
        if (
            anchor.get('anchor_id') != f'anchor-{fast_node_id}'
            or anchor.get('milestone_id') != expected_milestone_id
            or anchor.get('event_id') != expected_event_id
            or anchor.get('node_action') != expected_action
            or anchor.get('sequence') != expected_sequence
            or anchor.get('activation_mode') != expected_activation_mode
        ):
            failures.append(f'ANCHOR_CONTRACT_DRIFT:{fast_node_id}')

    graph_by_event = {row['event_id']: row for row in graphs}
    if set(graph_by_event) != expected_events:
        failures.append('GRAPH_EVENT_COVERAGE')
    known_edges: dict[str, tuple[str, dict[str, Any]]] = {}
    for graph in graphs:
        for error in validate_schema_record('transmission_graph', graph):
            failures.append(f'GRAPH_SCHEMA:{graph["event_id"]}:{error}')
        for error in transmission_graph_errors(graph):
            failures.append(f'GRAPH_RULE:{graph["event_id"]}:{error}')
        for edge in graph['edges']:
            known_edges[edge['edge_id']] = (graph['event_id'], edge)

    binding_counts = Counter(row['binding_id'] for row in bindings)
    for binding_id, count in sorted(binding_counts.items()):
        if count > 1:
            failures.append(f'DUPLICATE_BINDING_ID:{binding_id}')
    bound_causal: set[str] = set()
    used_sources: set[str] = set()
    for anchor in anchors:
        used_sources.update(anchor.get('source_ids') or [])
    for binding in bindings:
        binding_id = binding['binding_id']
        anchor_id = binding.get('anchor_fast_node_id')
        edge_id = binding.get('edge_id')
        anchor = anchor_by_id.get(anchor_id)
        if anchor is None:
            failures.append(f'UNKNOWN_BINDING_ANCHOR:{anchor_id}')
            continue
        if STABLE_ANCHOR_ACTIONS.get(anchor_id) == 'OBSERVES':
            failures.append(f'OBSERVATION_ONLY_BINDING:{anchor_id}')
        else:
            bound_causal.add(anchor_id)
        if binding.get('binding_status') != 'PROPOSED':
            failures.append(f'NON_PROPOSED_BINDING:{binding_id}')
        known_edge = known_edges.get(edge_id)
        if known_edge is None:
            failures.append(f'UNKNOWN_EDGE:{edge_id}')
        elif known_edge[0] != binding.get('event_id'):
            failures.append(f'CROSS_EVENT_BINDING:{binding_id}')
        else:
            edge = known_edge[1]
            expected_edge_payload = {
                'from_node_id': edge['from_node_id'],
                'to_node_id': edge['to_node_id'],
                'expected_path': edge['expected_path'],
                'lag': edge['lag'],
                'conditions': list(edge.get('conditions') or []),
                'invalidation_conditions': list(
                    edge.get('invalidation_conditions') or []
                ),
                'mechanism_evidence': list(edge.get('evidence') or []),
                'counterevidence': list(edge.get('counterevidence') or []),
                'counterevidence_status': (
                    'LINKED' if edge.get('counterevidence') else 'UNLINKED'
                ),
                'confidence': edge.get('confidence'),
                'edge_selection_mode': (
                    'DIRECT_MILESTONE'
                    if edge.get('anchor_milestone_id') == anchor['milestone_id']
                    else 'EXPLICIT_ENTRY_EDGE_OVERLAY'
                    if edge['edge_id'] in EXPLICIT_OVERLAY_EDGE_IDS.get(
                        anchor_id, frozenset()
                    )
                    else None
                ),
            }
            if any(
                binding.get(field) != value
                for field, value in expected_edge_payload.items()
            ):
                failures.append(f'BINDING_EDGE_PAYLOAD_DRIFT:{binding_id}')
            if binding_id != _stable_binding_id(anchor, edge):
                failures.append(f'BINDING_ID_DRIFT:{binding_id}')
        if (
            binding.get('event_id') != anchor['event_id']
            or binding.get('anchor_milestone_id') != anchor['milestone_id']
            or binding.get('anchor_action') != anchor['node_action']
            or binding.get('anchor_evidence_scope') != 'FACT_AND_TIME_ONLY'
            or binding.get('mechanism_evidence_scope') != 'INHERITED_GRAPH_PROPOSAL'
            or binding.get('review') is not None
        ):
            failures.append(f'BINDING_ANCHOR_PAYLOAD_DRIFT:{binding_id}')
        if set(binding.get('anchor_source_ids') or []) != set(anchor['source_ids']):
            failures.append(f'ANCHOR_SOURCE_DRIFT:{binding_id}')
        used_sources.update(binding.get('anchor_source_ids') or [])
        used_sources.update(
            evidence['evidence_id']
            for evidence in binding.get('mechanism_evidence') or []
        )
    for anchor in anchors:
        if (
            anchor['activation_mode'] == 'CAUSAL_CANDIDATE'
            and anchor['fast_node_id'] not in bound_causal
        ):
            failures.append(f'CAUSAL_ANCHOR_UNBOUND:{anchor["fast_node_id"]}')

    for source_id in sorted(used_sources):
        source = source_registry.get(source_id)
        if source is None:
            failures.append(f'UNKNOWN_SOURCE:{source_id}')
            continue
        snapshot = Path(source['snapshot_path'])
        if not snapshot.is_file():
            failures.append(f'SOURCE_SNAPSHOT_MISSING:{source_id}')
        elif _sha256(snapshot) != source.get('sha256'):
            failures.append(f'SOURCE_HASH_MISMATCH:{source_id}')

    if _production_hashes(root) != PRODUCTION_SHA256:
        failures.append('PRODUCTION_BASELINE_HASH_CHANGED')
    return list(dict.fromkeys(failures))


def build_artifacts(root: Path) -> dict[str, Any]:
    timeline_work = root / 'work' / 'timeline_fast_candidate_v2'
    production = root / 'data' / 'market_event_attribution_v2_candidate'
    timeline_nodes = _read_jsonl(timeline_work / 'timeline_nodes.jsonl')
    anchors = build_anchor_catalog(
        timeline_nodes,
        _read_jsonl(production / 'event_milestones.jsonl')
        + _read_jsonl(timeline_work / 'promotable_milestones.jsonl'),
    )
    graphs = build_projection_graphs(
        anchors,
        _read_jsonl(production / 'transmission_graphs.jsonl'),
    )
    bindings = build_dynamic_bindings(anchors, graphs)
    registry = build_source_registry(root)
    failures = validate_projection(root, anchors, graphs, bindings, registry)
    anchor_fast_node_ids = {row['fast_node_id'] for row in anchors}
    input_verified_label_count = sum(
        row.get('evidence_status') == 'VERIFIED_EXISTING' for row in timeline_nodes
    )
    input_pending_evidence_count = sum(
        row.get('evidence_status') == 'PENDING_EVIDENCE' for row in timeline_nodes
    )
    excluded_unresolvable_verified_count = sum(
        row.get('evidence_status') == 'VERIFIED_EXISTING'
        and row['fast_node_id'] not in anchor_fast_node_ids
        for row in timeline_nodes
    )
    excluded_pending_evidence_count = sum(
        row.get('evidence_status') == 'PENDING_EVIDENCE'
        and row['fast_node_id'] not in anchor_fast_node_ids
        for row in timeline_nodes
    )
    pinned_anchor_input_status_mismatch_count = sum(
        row['fast_node_id'] in anchor_fast_node_ids
        and row.get('evidence_status') != 'VERIFIED_EXISTING'
        for row in timeline_nodes
    )
    warnings = [
        'ALL_BINDINGS_REMAIN_PROPOSED',
        'ANCHOR_EVIDENCE_PROVES_FACT_AND_TIME_NOT_CAUSAL_MECHANISM',
        'UNLINKED_COUNTEREVIDENCE_REQUIRES_FUTURE_REVIEW',
    ]
    if excluded_unresolvable_verified_count:
        warnings.append(
            'UNRESOLVABLE_VERIFIED_LABELS_EXCLUDED:'
            f'{excluded_unresolvable_verified_count}'
        )
    if pinned_anchor_input_status_mismatch_count:
        warnings.append(
            'PINNED_ANCHOR_INPUT_STATUS_MISMATCH:'
            f'{pinned_anchor_input_status_mismatch_count}'
        )
    validation = {
        'release_tier': 'FAST_CANDIDATE',
        'formal_ready': False,
        'production_dataset_modified': False,
        'event_count': len({row['event_id'] for row in anchors}),
        'anchor_count': len(anchors),
        'input_verified_label_count': input_verified_label_count,
        'input_pending_evidence_count': input_pending_evidence_count,
        'excluded_pending_evidence_count': excluded_pending_evidence_count,
        'excluded_unresolvable_verified_count': excluded_unresolvable_verified_count,
        'pinned_anchor_input_status_mismatch_count': (
            pinned_anchor_input_status_mismatch_count
        ),
        'excluded_timeline_node_count': len(timeline_nodes) - len(anchors),
        'causal_anchor_count': sum(
            row['activation_mode'] == 'CAUSAL_CANDIDATE' for row in anchors
        ),
        'observation_anchor_count': sum(
            row['activation_mode'] == 'OBSERVATION_ONLY' for row in anchors
        ),
        'graph_count': len(graphs),
        'binding_count': len(bindings),
        'counterevidence_linked_count': sum(
            row['counterevidence_status'] == 'LINKED' for row in bindings
        ),
        'counterevidence_unlinked_count': sum(
            row['counterevidence_status'] == 'UNLINKED' for row in bindings
        ),
        'hard_failures': failures,
        'warnings': warnings,
        'production_sha256': _production_hashes(root),
    }
    return {
        'anchor_catalog': anchors,
        'transmission_graphs': graphs,
        'dynamic_edge_bindings': bindings,
        'validation_report': validation,
    }


def _readme(artifacts: dict[str, Any]) -> str:
    report = artifacts['validation_report']
    return '\n'.join([
        '# FinGoose 24-Anchor Dynamic Transmission FAST_CANDIDATE',
        '',
        'release_tier=FAST_CANDIDATE',
        'formal_ready=false',
        'production_dataset_modified=false',
        '',
        '## Counts',
        '',
        f'- Events: {report["event_count"]}',
        f'- Verified anchors: {report["anchor_count"]}',
        f'- Causal candidate anchors: {report["causal_anchor_count"]}',
        f'- Observation-only anchors: {report["observation_anchor_count"]}',
        f'- Dynamic edge bindings: {report["binding_count"]}',
        f'- Hard failures: {len(report["hard_failures"])}',
        '',
        'All bindings are PROPOSED. Anchor evidence proves the cited fact and timestamps;',
        'it does not independently confirm the inherited causal mechanism.',
        '',
        f'Timeline nodes outside the stable projection: {report["excluded_timeline_node_count"]}.',
        f'Input PENDING_EVIDENCE labels: {report["input_pending_evidence_count"]}.',
        f'Excluded PENDING_EVIDENCE nodes: {report["excluded_pending_evidence_count"]}.',
        'Unresolvable VERIFIED_EXISTING labels excluded: '
        f'{report["excluded_unresolvable_verified_count"]}.',
        'Pinned anchors restored from canonical milestone evidence despite input status drift: '
        f'{report["pinned_anchor_input_status_mismatch_count"]}.',
        'Future evidence may promote states without changing anchor, binding, or edge IDs.',
        '',
    ])


def write_artifacts(root: Path, artifacts: dict[str, Any]) -> None:
    output = root / 'work' / 'transmission_24_anchor_v2_candidate'
    output.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output / 'anchor_catalog.jsonl', artifacts['anchor_catalog'])
    _write_jsonl(output / 'transmission_graphs.jsonl', artifacts['transmission_graphs'])
    _write_jsonl(
        output / 'dynamic_edge_bindings.jsonl',
        artifacts['dynamic_edge_bindings'],
    )
    (output / 'validation_report.json').write_text(
        json.dumps(
            artifacts['validation_report'],
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + '\n',
        encoding='utf-8',
        newline='\n',
    )
    (output / 'README.md').write_text(
        _readme(artifacts),
        encoding='utf-8',
        newline='\n',
    )
    files = []
    for name in (
        'anchor_catalog.jsonl',
        'transmission_graphs.jsonl',
        'dynamic_edge_bindings.jsonl',
        'validation_report.json',
        'README.md',
    ):
        path = output / name
        record_count = (
            sum(1 for line in path.read_text(encoding='utf-8').splitlines() if line)
            if name.endswith('.jsonl')
            else 1
        )
        files.append({
            'path': name,
            'record_count': record_count,
            'sha256': _sha256(path),
        })
    manifest = {
        'dataset_version': 'fingoose-macro-event-attribution-v2.0',
        'release_tier': 'FAST_CANDIDATE',
        'formal_ready': False,
        'counts': {
            'events': artifacts['validation_report']['event_count'],
            'anchors': artifacts['validation_report']['anchor_count'],
            'graphs': artifacts['validation_report']['graph_count'],
            'bindings': artifacts['validation_report']['binding_count'],
        },
        'files': files,
    }
    (output / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
        newline='\n',
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    artifacts = build_artifacts(root)
    write_artifacts(root, artifacts)
    print(json.dumps(artifacts['validation_report'], ensure_ascii=False, indent=2))
    return 0 if not artifacts['validation_report']['hard_failures'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

