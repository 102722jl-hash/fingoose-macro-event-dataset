"""Build the supplemental timeline-source audit and candidate-only derivatives."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from fingoose_macro_event_attribution_v2 import stable_record_id, validate_schema_record
from fingoose_supplemental_timeline_source_audit import (
    apply_audit_policy,
    parse_attachment_candidates,
    write_jsonl,
)


BASELINE_SHA256 = {
    'event_milestones_jsonl': '2fafc57e304f810ef24c65c7248de487e711574108b179231e3f9ff869048d8a',
    'event_episodes_jsonl': '32626f4dd798c315ee1529581e31165369826c4119c5fd51fa82442623b4349b',
    'manifest_json': '3c0cd2d56aed32ac518231fb855dc69dc23c37f73e5b645ff1b84e4bdb48f4d1',
}


SEMANTIC_TARGETS = {
    'fast-event-01-M01': 'fast-event-01-M01',
    'fast-event-01-M02': 'fast-event-01-M02',
    'fast-event-01-M03': 'fast-event-01-M04',
    'fast-event-01-M04': 'fast-event-01-M05',
    'fast-event-01-M05': 'NEW_NODE_CANDIDATE:event-01:PHEIC_END',
    'fast-event-02-M01': 'fast-event-02-M02',
    'fast-event-02-M02': 'NEW_NODE_CANDIDATE:event-02:OPERATION_ANNOUNCEMENT',
    'fast-event-02-M03': 'fast-event-02-M05',
    'fast-event-02-M04': 'NEW_NODE_CANDIDATE:event-02:ENERGY_IMPORT_BAN',
    'fast-event-02-M05': 'NEW_NODE_CANDIDATE:event-02:OIL_PRICE_CAP',
    'fast-event-03-M01': 'fast-event-03-M01',
    'fast-event-03-M02': 'fast-event-03-M02',
    'fast-event-03-M03': 'NEW_NODE_CANDIDATE:event-03:FIRST_HIKE',
    'fast-event-03-M04': 'fast-event-03-M03',
    'fast-event-03-M05': 'NEW_NODE_CANDIDATE:event-03:TERMINAL_RATE',
    'fast-event-04-M01': 'fast-event-04-M01',
    'fast-event-04-M02': 'fast-event-04-M02',
    'fast-event-04-M03': 'fast-event-04-M03',
    'fast-event-04-M04': 'fast-event-04-M05',
    'fast-event-04-M05': 'NEW_NODE_CANDIDATE:event-04:ENTRY_QUARANTINE_END',
    'fast-event-05-M01': 'fast-event-05-M01',
    'fast-event-05-M02': 'fast-event-05-M03',
    'fast-event-05-M03': 'NEW_NODE_CANDIDATE:event-05:CREDIT_SUISSE_LIQUIDITY',
    'fast-event-05-M04': 'fast-event-05-M04',
    'fast-event-05-M05': 'fast-event-05-M05',
    'fast-event-06-M01': 'OBSERVATION_ONLY:event-06:OIL_PRICE',
    'fast-event-06-M02': 'fast-event-06-M03',
    'fast-event-06-M03': 'fast-event-06-M05',
    'fast-event-06-M04': 'NEW_NODE_CANDIDATE:event-06:CUT_EXTENSION',
    'fast-event-06-M05': 'NEW_NODE_CANDIDATE:event-06:PHASEOUT_PLAN',
    'fast-event-07-M01': 'fast-event-07-M01',
    'fast-event-07-M02': 'NEW_NODE_CANDIDATE:event-07:WAR_STATE',
    'fast-event-07-M03': 'fast-event-07-M04',
    'fast-event-07-M04': 'fast-event-07-M05',
    'fast-event-07-M05': 'NEW_NODE_CANDIDATE:event-07:JOINT_STRIKES',
    'fast-event-08-M01': 'fast-event-08-M01',
    'fast-event-08-M02': 'fast-event-08-M03',
    'fast-event-08-M03': 'fast-event-08-M04',
    'fast-event-08-M04': 'NEW_NODE_CANDIDATE:event-08:JULY_HIKE',
    'fast-event-08-M05': 'OBSERVATION_ONLY:event-08:NIKKEI_DROP',
    'fast-event-09-M01': 'fast-event-09-M02',
    'fast-event-09-M02': 'fast-event-09-M03',
    'fast-event-09-M03': 'fast-event-09-M05',
    'fast-event-09-M04': 'NEW_NODE_CANDIDATE:event-09:MORTGAGE_ADJUSTMENT',
    'fast-event-09-M05': 'NEW_NODE_CANDIDATE:event-09:SFISF_OPERATION',
    'fast-event-10-M01': None,
    'fast-event-10-M02': None,
    'fast-event-10-M03': None,
    'fast-event-10-M04': None,
    'fast-event-10-M05': None,
}


REJECTED_REVIEWS = {
    'fast-event-02-M04': {
        'decision': 'REJECT',
        'fact_status': 'NOT_APPLICABLE',
        'occurred_at_status': 'NOT_APPLICABLE',
        'first_public_at_status': 'NOT_APPLICABLE',
        'reason_code': 'SOURCE_MISMATCH',
        'reason': (
            'Federal Register document 2022-05251 concerns migratory-bird subsistence '
            'harvest in Alaska, not Executive Order 14066 or the Russia energy import ban.'
        ),
    },
}


ACCEPTED_REVIEWS = {
    'fast-event-03-M01': {
        'semantic_alignment_target': 'fast-event-03-M01',
        'fact_status': 'VERIFIED',
        'occurred_at_status': 'VERIFIED',
        'occurred_at': '2022-01-26T19:00:00Z',
        'occurred_at_locator': 'snapshot line 66: For release at 2:00 p.m. EST',
        'first_public_at_status': 'VERIFIED',
        'first_public_at': '2022-01-26T19:00:00Z',
        'first_public_at_locator': 'snapshot line 66: For release at 2:00 p.m. EST',
        'evidence_quote': (
            'The Committee expects it will soon be appropriate to raise the target '
            'range for the federal funds rate.'
        ),
        'evidence_locator': 'snapshot line 78',
        'publisher': 'Federal Reserve Board',
        'source_tier': 'A',
        'reason_code': 'FULL_EVIDENCE_ACCEPTED',
        'reason': 'Official scheduled release proves the policy signal and exact publication time.',
    },
    'fast-event-03-M02': {
        'semantic_alignment_target': 'fast-event-03-M02',
        'fact_status': 'VERIFIED',
        'occurred_at_status': 'VERIFIED',
        'occurred_at': '2022-02-10T13:30:00Z',
        'occurred_at_locator': 'snapshot lines 25-26: embargo lifted 8:30 a.m. ET',
        'first_public_at_status': 'VERIFIED',
        'first_public_at': '2022-02-10T13:30:00Z',
        'first_public_at_locator': 'snapshot lines 25-26: embargo lifted 8:30 a.m. ET',
        'evidence_quote': 'The all items index rose 7.5 percent for the 12 months ending January.',
        'evidence_locator': 'snapshot line 51',
        'publisher': 'U.S. Bureau of Labor Statistics',
        'source_tier': 'A',
        'reason_code': 'FULL_EVIDENCE_ACCEPTED',
        'reason': 'Official release proves the reported CPI fact and exact embargo/publication time.',
    },
    'fast-event-09-M01': {
        'semantic_alignment_target': 'fast-event-09-M02',
        'fact_status': 'VERIFIED',
        'occurred_at_status': 'VERIFIED',
        'occurred_at': '2024-09-18T18:00:00Z',
        'occurred_at_locator': 'snapshot line 66: For release at 2:00 p.m. EDT',
        'first_public_at_status': 'VERIFIED',
        'first_public_at': '2024-09-18T18:00:00Z',
        'first_public_at_locator': 'snapshot line 66: For release at 2:00 p.m. EDT',
        'evidence_quote': (
            'The Committee decided to lower the target range for the federal funds '
            'rate by 1/2 percentage point to 4-3/4 to 5 percent.'
        ),
        'evidence_locator': 'snapshot line 78',
        'publisher': 'Federal Reserve Board',
        'source_tier': 'A',
        'reason_code': 'FULL_EVIDENCE_ACCEPTED',
        'reason': 'Official scheduled release proves the external policy background and exact time.',
        'node_action_constraint': 'OBSERVES',
    },
}


NODE_UPDATES = {
    'fast-event-03-M01': {
        'target': 'fast-event-03-M01',
        'fact': (
            'FOMC kept the target range at 0%-0.25%, signaled that raising it would soon '
            'be appropriate, and set asset purchases to end in early March.'
        ),
        'occurred_at': '2022-01-26T19:00:00Z',
        'first_public_at': '2022-01-26T19:00:00Z',
        'node_action': 'OBSERVES',
    },
    'fast-event-03-M02': {
        'target': 'fast-event-03-M02',
        'fact': 'BLS reported January CPI was 7.5% higher than a year earlier.',
        'occurred_at': '2022-02-10T13:30:00Z',
        'first_public_at': '2022-02-10T13:30:00Z',
        'node_action': 'AMPLIFIES',
    },
    'fast-event-09-M01': {
        'target': 'fast-event-09-M02',
        'fact': (
            'The Federal Reserve lowered its target range by 50 basis points, an external '
            'policy backdrop only; it does not prove the cause of China policy actions.'
        ),
        'occurred_at': '2024-09-18T18:00:00Z',
        'first_public_at': '2024-09-18T18:00:00Z',
        'node_action': 'OBSERVES',
    },
}


EXPECTATIONS = {
    'fast-event-03-M01': {
        'type': 'EVOLVING_EVENT',
        'qualitative_baseline': 'FOMC publicly signaled near-term policy liftoff.',
        'consensus': 'UNKNOWN', 'actual': 'UNKNOWN', 'surprise': 'UNKNOWN',
    },
    'fast-event-03-M02': {
        'type': 'SCHEDULED_RELEASE',
        'consensus': 'UNKNOWN', 'actual': 7.5, 'surprise': 'UNKNOWN',
    },
    'fast-event-09-M01': {
        'type': 'SCHEDULED_RELEASE',
        'consensus': 'UNKNOWN', 'actual': 50.0, 'surprise': 'UNKNOWN',
    },
}


PUBLISHERS = {
    'who.int': ('World Health Organization', 'A'),
    'gazzettaufficiale.it': ('Gazzetta Ufficiale', 'A'),
    'federalregister.gov': ('Federal Register', 'A'),
    'kremlin.ru': ('President of Russia', 'A'),
    'whitehouse.gov': ('The White House', 'A'),
    'treasury.gov': ('U.S. Department of the Treasury', 'A'),
    'federalreserve.gov': ('Federal Reserve Board', 'A'),
    'bls.gov': ('U.S. Bureau of Labor Statistics', 'A'),
    'nhc.gov.cn': ('National Health Commission of China', 'A'),
    'news.cn': ('Xinhua News Agency', 'B'),
    'customs.gov.cn': ('General Administration of Customs of China', 'A'),
    'sec.gov': ('U.S. Securities and Exchange Commission', 'A'),
    'finma.ch': ('Swiss Financial Market Supervisory Authority', 'A'),
    'admin.ch': ('Swiss Federal Council', 'A'),
    'fdic.gov': ('Federal Deposit Insurance Corporation', 'A'),
    'iea.org': ('International Energy Agency', 'A'),
    'spa.gov.sa': ('Saudi Press Agency', 'A'),
    'opec.org': ('OPEC', 'A'),
    'un.org': ('United Nations', 'A'),
    'gov.il': ('Government of Israel', 'A'),
    'imo.org': ('International Maritime Organization', 'A'),
    'defense.gov': ('U.S. Department of Defense', 'A'),
    'boj.or.jp': ('Bank of Japan', 'A'),
    'jtuc-rengo.org': ('JTUC-RENGO', 'A'),
    'jpx.co.jp': ('Japan Exchange Group', 'A'),
    'scio.gov.cn': ('State Council Information Office of China', 'A'),
    'pbc.gov.cn': ('People\'s Bank of China', 'A'),
    'ustr.gov': ('Office of the U.S. Trade Representative', 'A'),
    'mofcom.gov.cn': ('Ministry of Commerce of China', 'A'),
    'cbp.gov': ('U.S. Customs and Border Protection', 'A'),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _publisher(url: str | None, fallback: str) -> tuple[str, str]:
    host = (urlparse(url).hostname or '').lower() if url else ''
    for suffix, values in PUBLISHERS.items():
        if host == suffix or host.endswith('.' + suffix):
            return values
    return fallback, 'A'


def _usable_snapshot(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding='utf-8-sig', errors='replace').lstrip()
    return not text.startswith(('extract_fetch_failed', 'extract_upstream_error'))


def build_candidate_audit(candidates: list[dict], source_dir: Path) -> list[dict]:
    rows = []
    for candidate in candidates:
        node_id = candidate['attachment_node_id']
        snapshot = source_dir / f'{node_id}.md'
        usable = _usable_snapshot(snapshot)
        publisher, source_tier = _publisher(
            candidate.get('canonical_url'), candidate.get('publisher_label', 'UNKNOWN')
        )
        review = {
            'decision': 'PENDING',
            'semantic_alignment_target': SEMANTIC_TARGETS[node_id],
            'fact_status': 'UNVERIFIED',
            'occurred_at_status': 'UNVERIFIED',
            'first_public_at_status': 'UNVERIFIED',
            'publisher': publisher,
            'source_tier': source_tier,
            'snapshot_path': f'sources/{node_id}.md' if usable else None,
            'sha256': _sha256(snapshot) if usable else None,
            'reason_code': 'DUAL_TIME_UNVERIFIED' if usable else 'SOURCE_RETRIEVAL_FAILED',
            'reason': (
                'Retrieved page does not independently prove both occurred_at and first_public_at.'
                if usable else
                'AnySearch did not return usable official-page content; candidate remains unverified.'
            ),
        }
        if node_id in ACCEPTED_REVIEWS:
            review.update(ACCEPTED_REVIEWS[node_id])
            review['decision'] = 'ACCEPT'
        elif node_id in REJECTED_REVIEWS:
            review.update(REJECTED_REVIEWS[node_id])
        audited = apply_audit_policy(candidate, review)
        audited['retrieval_status'] = 'SNAPSHOT_AVAILABLE' if usable else 'RETRIEVAL_FAILED'
        audited['source_url'] = candidate.get('canonical_url')
        audited['claimed_attachment_time'] = candidate.get('claimed_at')
        rows.append(audited)
    return rows


def build_candidate_source_manifest(audit: list[dict]) -> list[dict]:
    return [{
        'candidate_source_id': f'supplemental-{row["attachment_node_id"]}',
        'attachment_node_id': row['attachment_node_id'],
        'candidate_url': row['candidate_url'],
        'source_url': row['canonical_url'],
        'publisher': row['publisher'],
        'source_tier': row['source_tier'],
        'decision': row['decision'],
        'retrieval_status': row['retrieval_status'],
        'snapshot_path': row['snapshot_path'],
        'sha256': row['sha256'],
    } for row in audit]


def upgrade_timeline_nodes(nodes: list[dict], audit: list[dict]) -> list[dict]:
    updated = copy.deepcopy(nodes)
    by_id = {row['fast_node_id']: row for row in updated}
    accepted = {row['attachment_node_id']: row for row in audit if row['decision'] == 'ACCEPT'}
    for attachment_id, specification in NODE_UPDATES.items():
        evidence = accepted[attachment_id]
        target = by_id[specification['target']]
        target.update({
            'occurred_at': specification['occurred_at'],
            'first_public_at': specification['first_public_at'],
            'fact': specification['fact'],
            'source_ids': [f'supplemental-{attachment_id}'],
            'evidence_status': 'VERIFIED_EXISTING',
            'visibility': 'PUBLIC_PREDICTION',
            'node_action': specification['node_action'],
            'promotion_eligible': True,
            'gap_reason': None,
        })
        if evidence['semantic_alignment_target'] != target['fast_node_id']:
            raise ValueError(f'Semantic mapping drift for {attachment_id}')
    return updated


def _new_milestone(node: dict, audit_row: dict) -> dict:
    attachment_id = audit_row['attachment_node_id']
    return {
        'milestone_id': stable_record_id('milestone', node['event_id'], node['occurred_at']),
        'dataset_version': 'fingoose-macro-event-attribution-v2.0',
        'release_tier': 'CANDIDATE',
        'event_id': node['event_id'],
        'occurred_at': node['occurred_at'],
        'first_public_at': node['first_public_at'],
        'phase': node['phase'],
        'fact': node['fact'],
        'sources': [{
            'evidence_id': f'supplemental-{attachment_id}',
            'source_tier': audit_row['source_tier'],
            'published_at': node['first_public_at'],
            'sha256': audit_row['sha256'],
        }],
        'visibility': node['visibility'],
        'anchor_role': node['anchor_role'],
        'impact_tags': node['impact_tags'],
        'expectation': EXPECTATIONS[attachment_id],
    }


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


def build_promotable_milestones(
    nodes: list[dict], existing_promotable: list[dict], audit: list[dict]
) -> list[dict]:
    existing_by_id = {row['milestone_id']: row for row in existing_promotable}
    audit_by_source = {
        f'supplemental-{row["attachment_node_id"]}': row
        for row in audit if row['decision'] == 'ACCEPT'
    }
    result = []
    for node in sorted(nodes, key=lambda row: (row['event_id'], row['sequence'])):
        if not _node_passes_promotion_gate(node):
            node['promotion_eligible'] = False
            continue
        original_id = node.get('original_milestone_id')
        if original_id:
            result.append(existing_by_id[original_id])
            continue
        source_id = node['source_ids'][0]
        result.append(_new_milestone(node, audit_by_source[source_id]))
    return result


def build_timeline_episodes(nodes: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for node in nodes:
        groups[(node['event_id'], node['phase'])].append(node)
    episodes = []
    for (event_id, phase), rows in sorted(groups.items()):
        rows.sort(key=lambda row: row['sequence'])
        unresolved = any(row['occurred_at'] is None for row in rows)
        times = [row['occurred_at'] for row in rows if row['occurred_at']]
        sources = list(dict.fromkeys(
            source for row in rows for source in row['source_ids']
        ))
        episodes.append({
            'fast_episode_id': f'fast-episode-{event_id}-{phase.lower().replace("_", "-")}',
            'event_id': event_id,
            'phase': phase,
            'time_status': 'UNRESOLVED' if unresolved else 'VERIFIED_EXISTING',
            'start_at': None if unresolved else min(times),
            'end_at': None if unresolved else max(times),
            'fast_node_ids': [row['fast_node_id'] for row in rows],
            'evidence_coverage': sources,
            'verified_count': sum(row['evidence_status'] == 'VERIFIED_EXISTING' for row in rows),
            'pending_count': sum(row['evidence_status'] == 'PENDING_EVIDENCE' for row in rows),
        })
    return episodes


def build_gap_report(nodes: list[dict], promotable_count: int) -> dict:
    events = []
    for event_id in sorted({row['event_id'] for row in nodes}):
        rows = [row for row in nodes if row['event_id'] == event_id]
        gaps = [{
            'fast_node_id': row['fast_node_id'],
            'evidence_status': row['evidence_status'],
            'phase': row['phase'],
            'research_task': row['fact'],
            'required_source': row['gap_reason'],
        } for row in rows if row['gap_reason']]
        events.append({
            'event_id': event_id,
            'total_nodes': len(rows),
            'verified_existing': sum(row['evidence_status'] == 'VERIFIED_EXISTING' for row in rows),
            'pending_evidence': sum(row['evidence_status'] == 'PENDING_EVIDENCE' for row in rows),
            'unresolved_time': sum(row['occurred_at'] is None for row in rows),
            'public_prediction': sum(row['visibility'] == 'PUBLIC_PREDICTION' for row in rows),
            'hidden_validation': sum(row['visibility'] == 'HIDDEN_VALIDATION' for row in rows),
            'unresolved_visibility': sum(row['visibility'] == 'UNRESOLVED' for row in rows),
            'promotable': sum(bool(row['promotion_eligible']) for row in rows),
            'gaps': gaps,
        })
    return {
        'release_tier': 'FAST_CANDIDATE',
        'formal_ready': False,
        'node_target': '40-50',
        'node_count': len(nodes),
        'promotable_count': promotable_count,
        'pending_evidence_count': sum(
            row['evidence_status'] == 'PENDING_EVIDENCE' for row in nodes
        ),
        'priority_events': ['event-04', 'event-06', 'event-07', 'event-09', 'event-10'],
        'events': events,
    }


def _baseline_hashes(root: Path) -> dict:
    production = root / 'data' / 'market_event_attribution_v2_candidate'
    return {
        'event_milestones_jsonl': _sha256(production / 'event_milestones.jsonl'),
        'event_episodes_jsonl': _sha256(production / 'event_episodes.jsonl'),
        'manifest_json': _sha256(production / 'manifest.json'),
    }


def _accepted_audit_failures(root: Path, audit: list[dict]) -> list[str]:
    failures = []
    work = (root / 'work' / 'timeline_fast_candidate_v2').resolve()
    accepted_targets = []
    for row in audit:
        if row.get('decision') != 'ACCEPT':
            continue
        node_id = row['attachment_node_id']
        occurred = row.get('occurred_at_verification') or {}
        first_public = row.get('first_public_at_verification') or {}
        required = (
            row.get('evidence_quote'),
            row.get('evidence_locator'),
            row.get('publisher'),
            row.get('source_tier'),
            row.get('snapshot_path'),
            row.get('sha256'),
            occurred.get('status') == 'VERIFIED',
            occurred.get('value'),
            occurred.get('locator'),
            first_public.get('status') == 'VERIFIED',
            first_public.get('value'),
            first_public.get('locator'),
        )
        if not all(required):
            failures.append(f'ACCEPTED_EVIDENCE_INCOMPLETE:{node_id}')

        target = row.get('semantic_alignment_target') or ''
        if target.startswith('NEW_NODE_CANDIDATE:'):
            failures.append(f'ACCEPTED_NEW_NODE_CANDIDATE:{node_id}')
        elif target.startswith('fast-event-'):
            accepted_targets.append((node_id, target))

        snapshot_relative = row.get('snapshot_path')
        if not snapshot_relative:
            continue
        snapshot = (work / snapshot_relative).resolve()
        try:
            snapshot.relative_to(work)
        except ValueError:
            failures.append(f'ACCEPTED_SNAPSHOT_PATH_ESCAPE:{node_id}')
            continue
        if not snapshot.is_file():
            failures.append(f'ACCEPTED_SNAPSHOT_MISSING:{node_id}')
        elif _sha256(snapshot) != row.get('sha256'):
            failures.append(f'ACCEPTED_SNAPSHOT_HASH_MISMATCH:{node_id}')

    counts = Counter(target for _, target in accepted_targets)
    for target, count in sorted(counts.items()):
        if count > 1:
            failures.append(f'ACCEPTED_TARGET_COLLISION:{target}')
    return failures


def build_validation_report(
    root: Path, nodes: list[dict], episodes: list[dict], promotable: list[dict], audit: list[dict]
) -> dict:
    failures = []
    if len(nodes) != 50 or len({row['fast_node_id'] for row in nodes}) != 50:
        failures.append('NODE_COUNT_OR_ID_UNIQUENESS')
    event_ids = {row['event_id'] for row in nodes}
    if event_ids != {f'event-{index:02d}' for index in range(1, 11)}:
        failures.append('EVENT_COVERAGE')
    for event_id in sorted(event_ids):
        if sum(row['anchor_role'] == 'PRIMARY' for row in nodes if row['event_id'] == event_id) != 1:
            failures.append(f'PRIMARY_ANCHOR_COUNT:{event_id}')
    for node in nodes:
        if node.get('promotion_eligible') and not _node_passes_promotion_gate(node):
            failures.append(f'PROMOTION_GATE:{node["fast_node_id"]}')
    for milestone in promotable:
        errors = validate_schema_record('milestone', milestone)
        if errors:
            failures.append(f'MILESTONE_SCHEMA:{milestone["milestone_id"]}:{errors[0]}')
    failures.extend(_accepted_audit_failures(root, audit))
    baseline = _baseline_hashes(root)
    if baseline != BASELINE_SHA256:
        failures.append('PRODUCTION_BASELINE_HASH_CHANGED')
    decisions = Counter(row['decision'] for row in audit)
    pending = sum(row['evidence_status'] == 'PENDING_EVIDENCE' for row in nodes)
    return {
        'release_tier': 'FAST_CANDIDATE',
        'formal_ready': False,
        'production_dataset_modified': False,
        'event_count': len(event_ids),
        'node_count': len(nodes),
        'verified_existing_count': sum(
            row['evidence_status'] == 'VERIFIED_EXISTING' for row in nodes
        ),
        'episode_count': len(episodes),
        'promotable_count': len(promotable),
        'pending_evidence_count': pending,
        'unresolved_time_count': sum(row['occurred_at'] is None for row in nodes),
        'supplemental_candidate_count': len(audit),
        'supplemental_accepted_count': decisions['ACCEPT'],
        'supplemental_rejected_count': decisions['REJECT'],
        'supplemental_pending_count': decisions['PENDING'],
        'hard_failures': failures,
        'warnings': [
            f'UNRESOLVED_TIME:{sum(row["occurred_at"] is None for row in nodes)}',
            'FAST_EPISODES_ARE_WORKBOOK_RECORDS_NOT_PRODUCTION_EPISODE_SCHEMA',
            'SUPPLEMENTAL_AUDIT_DOES_NOT_CHANGE_PRODUCTION_DATASET',
        ],
        'baseline_sha256': baseline,
    }


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def build_artifacts(root: Path, attachment: Path) -> dict:
    work = root / 'work' / 'timeline_fast_candidate_v2'
    candidates = parse_attachment_candidates(attachment.read_text(encoding='utf-8'))
    audit = build_candidate_audit(candidates, work / 'sources')
    manifest = build_candidate_source_manifest(audit)
    nodes = upgrade_timeline_nodes(_read_jsonl(work / 'timeline_nodes.jsonl'), audit)
    promotable = build_promotable_milestones(
        nodes, _read_jsonl(work / 'promotable_milestones.jsonl'), audit
    )
    episodes = build_timeline_episodes(nodes)
    gaps = build_gap_report(nodes, len(promotable))
    validation = build_validation_report(root, nodes, episodes, promotable, audit)
    return {
        'candidate_source_audit': audit,
        'candidate_source_manifest': manifest,
        'timeline_nodes': nodes,
        'promotable_milestones': promotable,
        'timeline_episodes': episodes,
        'timeline_gap_report': gaps,
        'validation_report': validation,
    }


def _readme(artifacts: dict) -> str:
    validation = artifacts['validation_report']
    lines = [
        '# FinGoose Ten-Event Timeline FAST_CANDIDATE', '',
        'release_tier=FAST_CANDIDATE', 'formal_ready=false',
        'production_dataset_modified=false', 'scope=timeline_nodes_only',
        'company_analysis=OUT_OF_SCOPE', 'market_recalculation=OUT_OF_SCOPE', '',
        '## Supplemental Source Audit', '',
        f'- Parsed candidates: {validation["supplemental_candidate_count"]}',
        f'- Accepted candidates: {validation["supplemental_accepted_count"]}',
        f'- Rejected candidates: {validation["supplemental_rejected_count"]}',
        f'- Pending candidates: {validation["supplemental_pending_count"]}',
        '- Event-10: all five 2024 Section 301 candidates rejected as EVENT_MISMATCH ',
        '  against the current 2025 broad reciprocal-tariff event.',
        '- Event-02-M04: Federal Register 2022-05251 rejected as SOURCE_MISMATCH; ',
        '  it is not Executive Order 14066 or evidence of the Russia energy import ban.',
        '- Market/outcome candidates are OBSERVES-only and cannot prove transmission.', '',
        '## Protected Baseline SHA-256', '',
        f'- event_milestones.jsonl: `{BASELINE_SHA256["event_milestones_jsonl"]}`',
        f'- event_episodes.jsonl: `{BASELINE_SHA256["event_episodes_jsonl"]}`',
        f'- manifest.json: `{BASELINE_SHA256["manifest_json"]}`', '',
        '## Delivery Summary', '',
        '- Events: 10',
        f'- Timeline nodes: {validation["node_count"]}',
        f'- Verified existing nodes: {validation["verified_existing_count"]}',
        f'- Promotable milestones: {validation["promotable_count"]}',
        f'- Pending evidence tasks: {validation["pending_evidence_count"]}',
        f'- Workbook episodes: {validation["episode_count"]}',
        f'- Hard failures: {len(validation["hard_failures"])}', '',
        'Only candidates with a direct official URL, semantic match, independently verified ',
        'occurred_at and first_public_at, located source text, and a hashed local snapshot ',
        'were absorbed. Page existence alone was not treated as temporal proof.', '',
        'This directory remains an isolated research workbook and does not replace production v2.',
    ]
    return '\n'.join(lines) + '\n'


def write_artifacts(root: Path, artifacts: dict) -> None:
    work = root / 'work' / 'timeline_fast_candidate_v2'
    write_jsonl(work / 'candidate_source_audit.jsonl', artifacts['candidate_source_audit'])
    write_jsonl(work / 'candidate_source_manifest.jsonl', artifacts['candidate_source_manifest'])
    write_jsonl(work / 'timeline_nodes.jsonl', artifacts['timeline_nodes'])
    write_jsonl(work / 'promotable_milestones.jsonl', artifacts['promotable_milestones'])
    write_jsonl(work / 'timeline_episodes.jsonl', artifacts['timeline_episodes'])
    (work / 'timeline_gap_report.json').write_text(
        json.dumps(artifacts['timeline_gap_report'], ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8', newline='\n',
    )
    (work / 'validation_report.json').write_text(
        json.dumps(artifacts['validation_report'], ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8', newline='\n',
    )
    (work / 'README.md').write_text(_readme(artifacts), encoding='utf-8', newline='\n')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--attachment', type=Path, required=True)
    args = parser.parse_args()
    artifacts = build_artifacts(args.root.resolve(), args.attachment.resolve())
    write_artifacts(args.root.resolve(), artifacts)
    print(json.dumps(artifacts['validation_report'], ensure_ascii=False, indent=2))
    return 0 if not artifacts['validation_report']['hard_failures'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
