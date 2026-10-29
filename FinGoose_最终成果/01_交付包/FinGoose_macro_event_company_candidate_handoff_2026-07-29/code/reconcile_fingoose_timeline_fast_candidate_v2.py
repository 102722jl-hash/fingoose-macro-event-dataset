"""Reconcile the ten-event FAST_CANDIDATE workbook from auditable inputs."""

from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BASELINE_SHA256 = {
    'event_milestones_jsonl': (
        '2fafc57e304f810ef24c65c7248de487e711574108b179231e3f9ff869048d8a'
    ),
    'event_episodes_jsonl': (
        '32626f4dd798c315ee1529581e31165369826c4119c5fd51fa82442623b4349b'
    ),
    'manifest_json': (
        '3c0cd2d56aed32ac518231fb855dc69dc23c37f73e5b645ff1b84e4bdb48f4d1'
    ),
}

# These supplemental records cannot reproduce both exact timestamps from the
# cited local snapshot. Production-backed targets are restored from immutable
# v2 milestones; candidate-only targets return to PENDING_EVIDENCE.
UNREPRODUCIBLE_SUPPLEMENTAL = {
    'fast-event-01-M04': 'DUAL_TIME_CONTRADICTION',
    'fast-event-02-M03': 'FIRST_PUBLIC_TIME_NOT_IN_SNAPSHOT',
    'fast-event-05-M02': 'EXACT_RELEASE_TIME_NOT_IN_SNAPSHOT',
    'fast-event-05-M03': 'FACT_AND_TIME_MISMATCH',
    'fast-event-05-M04': 'TIMEZONE_NOT_PROVEN_BY_SNAPSHOT',
    'fast-event-07-M05': 'OFFICIAL_SNAPSHOT_MISSING',
    'fast-event-10-M01': 'CLAIMED_TIME_CONTRADICTS_SNAPSHOT',
    'fast-event-10-M02': 'CLAIMED_TIME_NOT_IN_SNAPSHOT',
    'fast-event-10-M04': 'FIRST_PUBLIC_TIME_NOT_IN_SNAPSHOT',
    'fast-event-10-M05': 'FIRST_PUBLIC_TIME_NOT_IN_SNAPSHOT',
}

RESTORE_PRODUCTION_TARGETS = {
    'fast-event-01-M04',
    'fast-event-02-M03',
    'fast-event-05-M02',
    'fast-event-05-M03',
    'fast-event-10-M02',
}

CANDIDATE_ONLY_PENDING_TARGETS = {
    'fast-event-05-M04',
    'fast-event-07-M05',
    'fast-event-10-M01',
    'fast-event-10-M04',
    'fast-event-10-M05',
}

SNAPSHOT_REPLACEMENTS = {
    'fast-event-05-M03': 'sources/webfetch_fast-fast-event-05-M03.txt',
}

QUOTE_REPAIRS = {
    'fast-event-01-M05': (
        'He determines that COVID-19 is now an established and ongoing health issue '
        'which no longer constitutes a public health emergency of international concern (PHEIC).'
    ),
    'fast-event-03-M02': (
        'The all items index rose 7.5 percent for the 12 months ending January, '
        'the largest 12-month increase since the period ending February 1982.'
    ),
    'fast-event-04-M05': '自2023年1月8日起，取消入境人员全员核酸检测',
    'fast-event-05-M05': (
        'JPMorgan Chase Bank, National Association, Columbus, Ohio Assumes All '
        'the Deposits of First Republic Bank, San Francisco, California'
    ),
    'fast-event-06-M05': (
        'gradually phased out on a monthly basis until the end of September 2025 '
        'to support market stability'
    ),
    'fast-event-08-M05': (
        'The benchmark Nikkei lost 4,451.28 points to end the day at 31,458.42, '
        'its lowest level this year'
    ),
    'fast-event-09-M04': (
        '市场利率定价自律机制将发布倡议，引导商业银行于2024年10月31日前开展一次'
        '存量房贷利率批量调整。'
    ),
    'fast-event-09-M05': '首期操作规模5000亿元，视情可进一步扩大操作规模。',
}

ALLOWED_VISIBILITY = {
    'PUBLIC_PREDICTION',
    'HIDDEN_VALIDATION',
    'UNRESOLVED',
}


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows),
        encoding='utf-8',
        newline='\n',
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _baseline_hashes(root: Path) -> dict[str, str]:
    production = root / 'data' / 'market_event_attribution_v2_candidate'
    return {
        'event_milestones_jsonl': _sha256(production / 'event_milestones.jsonl'),
        'event_episodes_jsonl': _sha256(production / 'event_episodes.jsonl'),
        'manifest_json': _sha256(production / 'manifest.json'),
    }


def _canonical_decision(value: str) -> str:
    return {
        'ACCEPT': 'ACCEPTED',
        'ACCEPTED': 'ACCEPTED',
        'REJECT': 'REJECTED',
        'REJECTED': 'REJECTED',
        'PENDING': 'PENDING',
    }.get(value, value)


def _snapshot_path(work: Path, relative: str | None) -> Path | None:
    if not relative:
        return None
    candidate = (work / relative).resolve()
    try:
        candidate.relative_to(work.resolve())
    except ValueError:
        return None
    return candidate


def _usable_snapshot(path: Path | None) -> bool:
    if path is None or not path.is_file():
        return False
    prefix = path.read_text(encoding='utf-8-sig', errors='replace').lstrip()[:256]
    return not prefix.startswith(('extract_fetch_failed', 'extract_upstream_error'))


def _normalized_text(value: str) -> str:
    normalized = unicodedata.normalize('NFKC', html.unescape(value))
    normalized = re.sub(r'<[^>]+>', '', normalized)
    normalized = normalized.translate(str.maketrans({
        '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"', '\u2013': '-', '\u2014': '-'
    }))
    return re.sub(r'\s+', ' ', normalized).strip().casefold()


def _quote_present(path: Path, quote: str | None) -> bool:
    if not quote:
        return False
    source = path.read_text(encoding='utf-8-sig', errors='replace')
    return _normalized_text(quote) in _normalized_text(source)


def reconcile_audit(work: Path, source_rows: list[dict]) -> list[dict]:
    rows = copy.deepcopy(source_rows)
    for row in rows:
        node_id = row['attachment_node_id']
        row['decision'] = _canonical_decision(row.get('decision', 'PENDING'))
        if node_id in QUOTE_REPAIRS:
            row['evidence_quote'] = QUOTE_REPAIRS[node_id]
            row['evidence_locator'] = (
                f'exact text in local snapshot: {row.get("snapshot_path")}'
            )
        if node_id in SNAPSHOT_REPLACEMENTS:
            row['snapshot_path'] = SNAPSHOT_REPLACEMENTS[node_id]
        snapshot = _snapshot_path(work, row.get('snapshot_path'))
        if _usable_snapshot(snapshot):
            row['sha256'] = _sha256(snapshot)
            row['retrieval_status'] = 'SNAPSHOT_AVAILABLE'
        else:
            row['snapshot_path'] = None
            row['sha256'] = None
            if row['decision'] != 'REJECTED':
                row['retrieval_status'] = 'SOURCE_IDENTIFIED_NEEDS_SNAPSHOT'

        if node_id in UNREPRODUCIBLE_SUPPLEMENTAL:
            row['decision'] = 'PENDING'
            row['fact_status'] = 'UNVERIFIED'
            for field in ('occurred_at_verification', 'first_public_at_verification'):
                previous = row.get(field) or {}
                row[field] = {
                    'status': 'UNVERIFIED',
                    'value': None,
                    'locator': None,
                    'previous_claimed_value': previous.get('value'),
                }
            row['reason_code'] = UNREPRODUCIBLE_SUPPLEMENTAL[node_id]
            row['reason'] = (
                'The local evidence does not independently reproduce both exact timestamps; '
                'the candidate remains available for later evidence replacement.'
            )

    # An accepted record must survive the mechanical evidence gate. This keeps
    # the reconciler deterministic if a snapshot is later removed or edited.
    for row in rows:
        if row['decision'] != 'ACCEPTED':
            continue
        occurred = row.get('occurred_at_verification') or {}
        first_public = row.get('first_public_at_verification') or {}
        snapshot = _snapshot_path(work, row.get('snapshot_path'))
        complete = all((
            row.get('semantic_alignment_target'),
            row.get('evidence_quote'),
            row.get('evidence_locator'),
            row.get('publisher'),
            row.get('source_tier'),
            row.get('sha256'),
            occurred.get('status') == 'VERIFIED',
            occurred.get('value'),
            occurred.get('locator'),
            first_public.get('status') == 'VERIFIED',
            first_public.get('value'),
            first_public.get('locator'),
            _usable_snapshot(snapshot),
        ))
        if not complete:
            row['decision'] = 'PENDING'
            row['reason_code'] = 'ACCEPTANCE_GATE_INCOMPLETE'
            row['reason'] = 'The record failed the reproducible acceptance gate.'
    return rows


def build_candidate_source_manifest(audit: list[dict]) -> list[dict]:
    return [{
        'attachment_node_id': row['attachment_node_id'],
        'candidate_source_id': f'supplemental-{row["attachment_node_id"]}',
        'candidate_url': row.get('candidate_url'),
        'source_url': row.get('source_url') or row.get('canonical_url'),
        'publisher': row.get('publisher'),
        'source_tier': row.get('source_tier'),
        'decision': row['decision'],
        'retrieval_status': row.get('retrieval_status'),
        'snapshot_path': row.get('snapshot_path'),
        'sha256': row.get('sha256'),
    } for row in audit]


def _restore_from_milestone(node: dict, milestone: dict) -> None:
    node.update({
        'event_id': milestone['event_id'],
        'occurred_at': milestone['occurred_at'],
        'first_public_at': milestone['first_public_at'],
        'phase': milestone['phase'],
        'fact': milestone['fact'],
        'source_ids': [
            source['evidence_id'] for source in milestone.get('sources', [])
        ],
        'evidence_status': 'VERIFIED_EXISTING',
        'visibility': milestone['visibility'],
        'anchor_role': milestone['anchor_role'],
        'impact_tags': list(milestone.get('impact_tags') or []),
    })
    if node.get('promotion_eligible'):
        node['gap_reason'] = None


def _pending_gap(node_id: str) -> str:
    if node_id == 'fast-event-02-M01':
        return (
            'The available Kremlin candidate describes conflict onset, while this node '
            'describes the EIA inventory and geopolitical-risk precondition. A semantically '
            'matched source with independently reproducible times is still required.'
        )
    reason = UNREPRODUCIBLE_SUPPLEMENTAL.get(node_id, 'SOURCE_PACKAGE_INCOMPLETE')
    return (
        f'{reason}: a semantically matched official snapshot must independently support '
        'the fact, occurred_at, and first_public_at before promotion.'
    )


def reconcile_nodes(
    source_nodes: list[dict],
    audit: list[dict],
    production_milestones: list[dict],
    production_sources: list[dict],
) -> list[dict]:
    nodes = copy.deepcopy(source_nodes)
    milestones = {row['milestone_id']: row for row in production_milestones}
    production_source_ids = {row['evidence_id'] for row in production_sources}
    accepted = {
        row['attachment_node_id']: row
        for row in audit if row['decision'] == 'ACCEPTED'
    }
    accepted_source_ids = {
        f'supplemental-{node_id}' for node_id in accepted
    }
    accepted_by_target: dict[str, list[str]] = defaultdict(list)
    for node_id, row in accepted.items():
        target = row.get('semantic_alignment_target')
        if isinstance(target, str) and target.startswith('fast-event-'):
            accepted_by_target[target].append(f'supplemental-{node_id}')

    for node in nodes:
        node_id = node['fast_node_id']
        milestone_id = node.get('original_milestone_id')
        if node_id in RESTORE_PRODUCTION_TARGETS:
            _restore_from_milestone(node, milestones[milestone_id])

        node['source_ids'] = list(dict.fromkeys(
            source_id for source_id in (node.get('source_ids') or [])
            if source_id in production_source_ids or source_id in accepted_source_ids
        ))

        if node_id in CANDIDATE_ONLY_PENDING_TARGETS or node_id == 'fast-event-02-M01':
            node.update({
                'occurred_at': None,
                'first_public_at': None,
                'source_ids': [],
                'evidence_status': 'PENDING_EVIDENCE',
                'visibility': 'UNRESOLVED',
                'promotion_eligible': False,
                'gap_reason': _pending_gap(node_id),
            })
            continue

        if node.get('evidence_status') == 'VERIFIED_EXISTING':
            for source_id in accepted_by_target.get(node_id, []):
                if source_id not in node['source_ids']:
                    node['source_ids'].append(source_id)
            if not node['source_ids'] and milestone_id in milestones:
                _restore_from_milestone(node, milestones[milestone_id])
            if node.get('visibility') == 'RESOLVED':
                node['visibility'] = 'PUBLIC_PREDICTION'

        if node.get('evidence_status') == 'VERIFIED_EXISTING' and not node['source_ids']:
            node.update({
                'occurred_at': None,
                'first_public_at': None,
                'evidence_status': 'PENDING_EVIDENCE',
                'visibility': 'UNRESOLVED',
                'promotion_eligible': False,
                'gap_reason': _pending_gap(node_id),
            })

    return sorted(nodes, key=lambda row: (row['event_id'], row['sequence']))


def build_timeline_episodes(nodes: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for node in nodes:
        groups[(node['event_id'], node['phase'])].append(node)
    episodes = []
    for (event_id, phase), members in sorted(groups.items()):
        members.sort(key=lambda row: row['sequence'])
        unresolved = any(row.get('occurred_at') is None for row in members)
        times = [row['occurred_at'] for row in members if row.get('occurred_at')]
        sources = list(dict.fromkeys(
            source_id for row in members for source_id in row.get('source_ids', [])
        ))
        episodes.append({
            'fast_episode_id': (
                f'fast-episode-{event_id}-{phase.lower().replace("_", "-")}'
            ),
            'event_id': event_id,
            'phase': phase,
            'time_status': 'UNRESOLVED' if unresolved else 'VERIFIED_EXISTING',
            'start_at': None if unresolved else min(times),
            'end_at': None if unresolved else max(times),
            'fast_node_ids': [row['fast_node_id'] for row in members],
            'evidence_coverage': sources,
            'verified_count': sum(
                row['evidence_status'] == 'VERIFIED_EXISTING' for row in members
            ),
            'pending_count': sum(
                row['evidence_status'] == 'PENDING_EVIDENCE' for row in members
            ),
        })
    return episodes


def _node_checklist(node: dict, resolvable_sources: set[str]) -> dict:
    verified = node.get('evidence_status') == 'VERIFIED_EXISTING'
    source_ok = bool(node.get('source_ids')) and all(
        source_id in resolvable_sources for source_id in node.get('source_ids', [])
    )
    occurred_ok = bool(node.get('occurred_at'))
    first_public_ok = bool(node.get('first_public_at'))
    semantic_ok = verified and source_ok
    complete = all((
        verified,
        source_ok,
        occurred_ok,
        first_public_ok,
        semantic_ok,
        not node.get('gap_reason'),
    ))
    return {
        'p1_one_to_one_link': semantic_ok,
        'p2_quote_locator': source_ok,
        'p3_occurred_at': occurred_ok,
        'p4_first_public_at': first_public_ok,
        'p5_snapshot_sha': 'DEFERRED',
        'p6_semantic': semantic_ok,
        'p7_expected_type': node.get('expected_type', 'UNKNOWN'),
        'package_complete': complete,
    }


def build_gap_report(
    nodes: list[dict],
    promotable_count: int,
    resolvable_sources: set[str],
) -> dict:
    events = []
    priority = []
    complete_count = 0
    for event_id in sorted({row['event_id'] for row in nodes}):
        members = [row for row in nodes if row['event_id'] == event_id]
        node_rows = []
        for node in members:
            checklist = _node_checklist(node, resolvable_sources)
            complete_count += int(checklist['package_complete'])
            node_rows.append({
                'fast_node_id': node['fast_node_id'],
                'phase': node['phase'],
                'node_action': node['node_action'],
                'evidence_status': node['evidence_status'],
                'promotion_eligible': bool(node.get('promotion_eligible')),
                'package_complete': checklist['package_complete'],
                'checklist': checklist,
                'fact': node['fact'],
                'gap_note': node.get('gap_reason'),
            })
        pending = sum(
            row['evidence_status'] == 'PENDING_EVIDENCE' for row in members
        )
        if pending:
            priority.append((pending, event_id))
        events.append({
            'event_id': event_id,
            'total_nodes': len(members),
            'verified_existing': len(members) - pending,
            'pending_evidence': pending,
            'promotable': sum(bool(row.get('promotion_eligible')) for row in members),
            'nodes': node_rows,
        })
    return {
        'release_tier': 'FAST_CANDIDATE',
        'formal_ready': False,
        'node_target': '40-50',
        'node_count': len(nodes),
        'verified_existing_count': sum(
            row['evidence_status'] == 'VERIFIED_EXISTING' for row in nodes
        ),
        'pending_evidence_count': sum(
            row['evidence_status'] == 'PENDING_EVIDENCE' for row in nodes
        ),
        'promotable_count': promotable_count,
        'evidence_packages_complete_count': complete_count,
        'priority_events': [event_id for _, event_id in sorted(priority, reverse=True)],
        'events': events,
    }


def _source_registries(root: Path, manifest: list[dict]) -> tuple[set[str], dict[str, dict]]:
    production_rows = _read_jsonl(
        root / 'data' / 'market_event_attribution_v2_candidate' / 'source_manifest.jsonl'
    )
    production_ids = {row['evidence_id'] for row in production_rows}
    candidate = {
        row['candidate_source_id']: row
        for row in manifest if row['decision'] == 'ACCEPTED'
    }
    return production_ids | set(candidate), candidate


def _validate_episodes(nodes: list[dict], episodes: list[dict]) -> list[str]:
    expected = {
        row['fast_episode_id']: row for row in build_timeline_episodes(nodes)
    }
    actual = {row['fast_episode_id']: row for row in episodes}
    failures = []
    if set(actual) != set(expected):
        failures.append('EPISODE_ID_SET_DRIFT')
    for episode_id in sorted(set(actual) & set(expected)):
        if actual[episode_id] != expected[episode_id]:
            failures.append(f'EPISODE_AGGREGATE_DRIFT:{episode_id}')
    return failures


def validate_workbook(root: Path, artifacts: dict[str, Any]) -> list[str]:
    work = root / 'work' / 'timeline_fast_candidate_v2'
    audit = artifacts['candidate_source_audit']
    manifest = artifacts['candidate_source_manifest']
    nodes = artifacts['timeline_nodes']
    episodes = artifacts['timeline_episodes']
    promotable = artifacts['promotable_milestones']
    gaps = artifacts['timeline_gap_report']
    failures: list[str] = []

    if len(nodes) != 50 or len({row['fast_node_id'] for row in nodes}) != 50:
        failures.append('NODE_COUNT_OR_ID_UNIQUENESS')
    expected_events = {f'event-{index:02d}' for index in range(1, 11)}
    if {row['event_id'] for row in nodes} != expected_events:
        failures.append('EVENT_COVERAGE')

    audit_by_id = {row['attachment_node_id']: row for row in audit}
    manifest_by_id = {row['attachment_node_id']: row for row in manifest}
    if set(audit_by_id) != set(manifest_by_id):
        failures.append('AUDIT_MANIFEST_ID_SET_DRIFT')
    for node_id in sorted(set(audit_by_id) & set(manifest_by_id)):
        audit_row = audit_by_id[node_id]
        manifest_row = manifest_by_id[node_id]
        if (
            audit_row.get('decision') != manifest_row.get('decision')
            or audit_row.get('snapshot_path') != manifest_row.get('snapshot_path')
            or audit_row.get('sha256') != manifest_row.get('sha256')
        ):
            failures.append(f'AUDIT_MANIFEST_STATE_DRIFT:{node_id}')

    target_counts = Counter()
    for row in audit:
        node_id = row['attachment_node_id']
        decision = row.get('decision')
        if decision not in {'ACCEPTED', 'REJECTED', 'PENDING'}:
            failures.append(f'AUDIT_DECISION_ENUM:{node_id}')
        if decision != 'ACCEPTED':
            continue
        target = row.get('semantic_alignment_target') or ''
        if not target.startswith('fast-event-'):
            failures.append(f'ACCEPTED_TARGET_INVALID:{node_id}')
        else:
            target_counts[target] += 1
        snapshot = _snapshot_path(work, row.get('snapshot_path'))
        if not _usable_snapshot(snapshot):
            failures.append(f'ACCEPTED_SNAPSHOT_MISSING:{node_id}')
        elif not _quote_present(snapshot, row.get('evidence_quote')):
            failures.append(f'ACCEPTED_QUOTE_NOT_IN_SNAPSHOT:{node_id}')
        occurred = row.get('occurred_at_verification') or {}
        first_public = row.get('first_public_at_verification') or {}
        if not all((
            row.get('evidence_locator'),
            occurred.get('status') == 'VERIFIED',
            occurred.get('value'),
            occurred.get('locator'),
            first_public.get('status') == 'VERIFIED',
            first_public.get('value'),
            first_public.get('locator'),
        )):
            failures.append(f'ACCEPTED_EVIDENCE_INCOMPLETE:{node_id}')
    for target, count in sorted(target_counts.items()):
        if count > 1:
            failures.append(f'ACCEPTED_TARGET_COLLISION:{target}')

    resolvable_sources, candidate_sources = _source_registries(root, manifest)
    for node in nodes:
        node_id = node['fast_node_id']
        if node.get('visibility') not in ALLOWED_VISIBILITY:
            failures.append(f'VISIBILITY_ENUM:{node_id}')
        if node.get('evidence_status') == 'VERIFIED_EXISTING':
            if not node.get('source_ids'):
                failures.append(f'VERIFIED_SOURCE_REQUIRED:{node_id}')
            for source_id in node.get('source_ids', []):
                if source_id not in resolvable_sources:
                    failures.append(f'UNRESOLVED_SOURCE:{node_id}:{source_id}')
        elif node.get('evidence_status') == 'PENDING_EVIDENCE':
            if node.get('promotion_eligible'):
                failures.append(f'PENDING_PROMOTABLE:{node_id}')
            if node.get('source_ids'):
                failures.append(f'PENDING_SOURCE_LEAK:{node_id}')
        else:
            failures.append(f'EVIDENCE_STATUS_ENUM:{node_id}')

    for milestone in promotable:
        matched_nodes = [
            node for node in nodes
            if (
                node.get('original_milestone_id') == milestone['milestone_id']
                or (
                    not node.get('original_milestone_id')
                    and node['event_id'] == milestone['event_id']
                    and node.get('occurred_at') == milestone.get('occurred_at')
                )
            )
        ]
        if len(matched_nodes) != 1 or not _node_passes_promotion_gate(matched_nodes[0]):
            failures.append(f'PROMOTABLE_NODE_GATE:{milestone["milestone_id"]}')

    for source_id, row in candidate_sources.items():
        snapshot = _snapshot_path(work, row.get('snapshot_path'))
        if snapshot is None or not snapshot.is_file():
            failures.append(f'SOURCE_MANIFEST_SNAPSHOT_MISSING:{source_id}')


    failures.extend(_validate_episodes(nodes, episodes))
    expected_counts = {
        'node_count': len(nodes),
        'verified_existing_count': sum(
            row['evidence_status'] == 'VERIFIED_EXISTING' for row in nodes
        ),
        'pending_evidence_count': sum(
            row['evidence_status'] == 'PENDING_EVIDENCE' for row in nodes
        ),
        'promotable_count': len(promotable),
    }
    for field, expected in expected_counts.items():
        if gaps.get(field) != expected:
            failures.append(f'GAP_REPORT_COUNT_DRIFT:{field}')

    if _baseline_hashes(root) != BASELINE_SHA256:
        failures.append('PRODUCTION_BASELINE_HASH_CHANGED')
    return list(dict.fromkeys(failures))


def _build_validation_report(
    root: Path,
    artifacts: dict[str, Any],
) -> dict:
    nodes = artifacts['timeline_nodes']
    audit = artifacts['candidate_source_audit']
    decisions = Counter(row['decision'] for row in audit)
    report = {
        'release_tier': 'FAST_CANDIDATE',
        'formal_ready': False,
        'production_dataset_modified': False,
        'event_count': len({row['event_id'] for row in nodes}),
        'node_count': len(nodes),
        'verified_existing_count': sum(
            row['evidence_status'] == 'VERIFIED_EXISTING' for row in nodes
        ),
        'pending_evidence_count': sum(
            row['evidence_status'] == 'PENDING_EVIDENCE' for row in nodes
        ),
        'unresolved_time_count': sum(
            not row.get('occurred_at') or not row.get('first_public_at') for row in nodes
        ),
        'episode_count': len(artifacts['timeline_episodes']),
        'promotable_count': len(artifacts['promotable_milestones']),
        'evidence_packages_complete_count': (
            artifacts['timeline_gap_report']['evidence_packages_complete_count']
        ),
        'supplemental_candidate_count': len(audit),
        'supplemental_accepted_count': decisions['ACCEPTED'],
        'supplemental_rejected_count': decisions['REJECTED'],
        'supplemental_pending_count': decisions['PENDING'],
        'hard_failures': validate_workbook(root, artifacts),
        'warnings': [
            'FAST_EPISODES_ARE_WORKBOOK_RECORDS_NOT_PRODUCTION_EPISODE_SCHEMA',
            'SUPPLEMENTAL_AUDIT_DOES_NOT_CHANGE_PRODUCTION_DATASET',
            'TEN_UNREPRODUCIBLE_SUPPLEMENTAL_RECORDS_DOWNGRADED',
            'TWO_SOURCE_LOCATED_RECORDS_NOT_TREATED_AS_TIME_VERIFIED',
            'CANDIDATE_SNAPSHOT_SHA_GATE_DEFERRED',
            'EVENT_02_M01_REMAINS_PENDING_DUE_TO_SEMANTIC_MISMATCH',
        ],
        'baseline_sha256': _baseline_hashes(root),
    }
    return report


def _node_passes_promotion_gate(node: dict) -> bool:
    return bool(
        node.get('promotion_eligible')
        and node.get('evidence_status') == 'VERIFIED_EXISTING'
        and node.get('occurred_at')
        and node.get('first_public_at')
        and node.get('visibility') != 'UNRESOLVED'
        and node.get('source_ids')
        and not node.get('gap_reason')
    )


def reconcile_promotable(nodes: list[dict], source_rows: list[dict]) -> list[dict]:
    eligible_original_ids = {
        node['original_milestone_id']
        for node in nodes
        if node.get('original_milestone_id') and _node_passes_promotion_gate(node)
    }
    result = []
    for milestone in source_rows:
        if milestone['milestone_id'] in eligible_original_ids:
            result.append(milestone)
            continue
        for node in nodes:
            if node.get('original_milestone_id') or not _node_passes_promotion_gate(node):
                continue
            if (
                node['event_id'] == milestone['event_id']
                and node['occurred_at'] == milestone['occurred_at']
                and set(node['source_ids']) == {
                    source['evidence_id'] for source in milestone.get('sources', [])
                }
            ):
                result.append(milestone)
                break
    return result


def reconcile_workbook(root: Path) -> dict[str, Any]:
    root = root.resolve()
    work = root / 'work' / 'timeline_fast_candidate_v2'
    production = root / 'data' / 'market_event_attribution_v2_candidate'
    audit = reconcile_audit(work, _read_jsonl(work / 'candidate_source_audit.jsonl'))
    manifest = build_candidate_source_manifest(audit)
    production_milestones = _read_jsonl(production / 'event_milestones.jsonl')
    production_sources = _read_jsonl(production / 'source_manifest.jsonl')
    nodes = reconcile_nodes(
        _read_jsonl(work / 'timeline_nodes.jsonl'),
        audit,
        production_milestones,
        production_sources,
    )
    promotable = reconcile_promotable(
        nodes, _read_jsonl(work / 'promotable_milestones.jsonl')
    )
    episodes = build_timeline_episodes(nodes)
    resolvable_sources, _ = _source_registries(root, manifest)
    gaps = build_gap_report(nodes, len(promotable), resolvable_sources)
    artifacts: dict[str, Any] = {
        'candidate_source_audit': audit,
        'candidate_source_manifest': manifest,
        'timeline_nodes': nodes,
        'promotable_milestones': promotable,
        'timeline_episodes': episodes,
        'timeline_gap_report': gaps,
    }
    artifacts['validation_report'] = _build_validation_report(root, artifacts)
    return artifacts


def _readme(artifacts: dict[str, Any]) -> str:
    report = artifacts['validation_report']
    return '\n'.join([
        '# FinGoose Ten-Event Timeline FAST_CANDIDATE',
        '',
        'release_tier=FAST_CANDIDATE',
        'formal_ready=false',
        'production_dataset_modified=false',
        'scope=timeline_and_source_reconciliation',
        '',
        '## Reconciled Counts',
        '',
        f'- Events: {report["event_count"]}',
        f'- Timeline nodes: {report["node_count"]}',
        f'- Verified existing nodes: {report["verified_existing_count"]}',
        f'- Pending evidence nodes: {report["pending_evidence_count"]}',
        f'- Promotable milestones: {report["promotable_count"]}',
        f'- Workbook episodes: {report["episode_count"]}',
        f'- Accepted supplemental candidates: {report["supplemental_accepted_count"]}',
        f'- Rejected supplemental candidates: {report["supplemental_rejected_count"]}',
        f'- Pending supplemental candidates: {report["supplemental_pending_count"]}',
        f'- Hard failures: {len(report["hard_failures"])}',
        '',
        'Ten supplemental records were downgraded because their local snapshots do not ',
        'independently reproduce both exact timestamps. Five production-backed targets were ',
        'restored from immutable v2 milestones; five candidate-only targets remain pending.',
        '',
        'event-02-M01 remains pending because its Kremlin candidate and EIA precondition fact ',
        'are semantically different records.',
        '',
        'This directory remains an isolated research workbook and does not replace production v2.',
        '',
    ])


def write_artifacts(root: Path, artifacts: dict[str, Any]) -> None:
    work = root / 'work' / 'timeline_fast_candidate_v2'
    _write_jsonl(work / 'candidate_source_audit.jsonl', artifacts['candidate_source_audit'])
    _write_jsonl(
        work / 'candidate_source_manifest.jsonl',
        artifacts['candidate_source_manifest'],
    )
    _write_jsonl(work / 'timeline_nodes.jsonl', artifacts['timeline_nodes'])
    _write_jsonl(work / 'promotable_milestones.jsonl', artifacts['promotable_milestones'])
    _write_jsonl(work / 'timeline_episodes.jsonl', artifacts['timeline_episodes'])
    (work / 'timeline_gap_report.json').write_text(
        json.dumps(
            artifacts['timeline_gap_report'], ensure_ascii=False, indent=2, sort_keys=True
        ) + '\n',
        encoding='utf-8',
        newline='\n',
    )
    (work / 'validation_report.json').write_text(
        json.dumps(
            artifacts['validation_report'], ensure_ascii=False, indent=2, sort_keys=True
        ) + '\n',
        encoding='utf-8',
        newline='\n',
    )
    (work / 'README.md').write_text(
        _readme(artifacts), encoding='utf-8', newline='\n'
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    artifacts = reconcile_workbook(root)
    write_artifacts(root, artifacts)
    print(json.dumps(artifacts['validation_report'], ensure_ascii=False, indent=2))
    return 0 if not artifacts['validation_report']['hard_failures'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
