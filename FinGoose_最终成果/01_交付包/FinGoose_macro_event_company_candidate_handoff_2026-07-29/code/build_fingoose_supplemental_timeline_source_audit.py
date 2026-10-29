"""Policy-gated entry point for the supplemental timeline source audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import fingoose_supplemental_timeline_source_audit_build_core as core
from fingoose_supplemental_timeline_source_audit import parse_attachment_candidates


# Re-export focused builders for tests and downstream audit replay.
build_candidate_audit = core.build_candidate_audit
build_candidate_source_manifest = core.build_candidate_source_manifest
build_promotable_milestones = core.build_promotable_milestones
build_timeline_episodes = core.build_timeline_episodes
build_gap_report = core.build_gap_report
build_validation_report = core.build_validation_report
write_artifacts = core.write_artifacts


def normalize_unqualified_supplemental_updates(nodes: list[dict]) -> list[dict]:
    """Reset candidate-only nodes before applying evidence that passed the full gate."""
    normalized = json.loads(json.dumps(nodes, ensure_ascii=False))
    for node in normalized:
        if node.get('original_milestone_id'):
            node['source_ids'] = [
                source_id for source_id in (node.get('source_ids') or [])
                if not source_id.startswith('supplemental-')
            ]
            node['evidence_status'] = 'VERIFIED_EXISTING'
            if node.get('promotion_eligible'):
                node['gap_reason'] = None
            continue
        node.update({
            'occurred_at': None,
            'first_public_at': None,
            'source_ids': [],
            'evidence_status': 'PENDING_EVIDENCE',
            'visibility': 'UNRESOLVED',
            'promotion_eligible': False,
            'gap_reason': (
                'Supplemental candidate has not independently verified the fact, occurred_at, '
                'first_public_at, evidence locator, and hashed snapshot as one semantic record.'
            ),
        })
    return normalized


def restore_production_baseline_nodes(
    nodes: list[dict], production_milestones: list[dict]
) -> list[dict]:
    """Restore the 21 production-backed nodes from immutable milestone records."""
    restored = normalize_unqualified_supplemental_updates(nodes)
    milestones = {row['milestone_id']: row for row in production_milestones}
    for node in restored:
        milestone_id = node.get('original_milestone_id')
        if not milestone_id:
            continue
        milestone = milestones[milestone_id]
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
            'impact_tags': milestone['impact_tags'],
        })
        if node.get('promotion_eligible'):
            node['gap_reason'] = None
    return restored


def upgrade_timeline_nodes(nodes: list[dict], audit: list[dict]) -> list[dict]:
    normalized = normalize_unqualified_supplemental_updates(nodes)
    return core.upgrade_timeline_nodes(normalized, audit)


def build_artifacts(root: Path, attachment: Path) -> dict:
    work = root / 'work' / 'timeline_fast_candidate_v2'
    candidates = parse_attachment_candidates(attachment.read_text(encoding='utf-8'))
    audit = build_candidate_audit(candidates, work / 'sources')
    manifest = build_candidate_source_manifest(audit)
    production_milestones = core._read_jsonl(
        root / 'data' / 'market_event_attribution_v2_candidate' / 'event_milestones.jsonl'
    )
    skeleton = restore_production_baseline_nodes(
        core._read_jsonl(work / 'timeline_nodes.jsonl'), production_milestones
    )
    nodes = upgrade_timeline_nodes(skeleton, audit)
    promotable = build_promotable_milestones(nodes, production_milestones, audit)
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
