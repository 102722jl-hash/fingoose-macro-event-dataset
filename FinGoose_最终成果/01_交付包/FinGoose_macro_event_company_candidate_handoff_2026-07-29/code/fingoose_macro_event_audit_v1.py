from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
AUDIT_DATASET_VERSION = 'fingoose-macro-event-audit-v1.0'
PUBLIC_CLAIM_TYPES = {
    'event_fact',
    'data_observation',
    'transmission_assessment',
    'prediction',
    'counterevidence',
}
HIDDEN_TOKENS = ('hidden_outcome', 'actual_direction', 'verification_result', 'd20')
SAMPLE_KIND_LABELS = {
    'single_target': '单目标',
    'cross_asset': '跨资产',
    'channel_check': '通道核验',
    'counterfactual': '反事实',
}
CHANNEL_LABELS = {
    'RISK_APPETITE': '风险偏好',
    'ENERGY_SUPPLY': '能源供给',
    'RATE_DIFFERENTIAL': '利差',
    'YEN_FUNDING': '日元融资',
    'GLOBAL_LIQUIDITY': '全球流动性',
    'TRADE_COSTS': '贸易成本',
    'INFLATION_EXPECTATIONS': '通胀预期',
    'GLOBAL_GROWTH': '全球增长',
    'SAFE_HAVEN_DEMAND': '避险需求',
    'MONETARY_EASING': '货币宽松',
    'PROPERTY_SUPPORT': '地产支持',
}


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        dict(row) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()
        for row in [json.loads(line)] if isinstance(row, Mapping)
    ]


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        ''.join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + '\n' for row in rows),
        encoding='utf-8',
    )


def _record_parts(record_id: str) -> tuple[str, str]:
    parts = record_id.split('-')
    if len(parts) < 2 or not parts[-1].isdigit() or not parts[-2].isdigit():
        raise ValueError('RECORD_ID_FORMAT_INVALID')
    return parts[-2], parts[-1]


def build_display_id(
    *, event_id: str, record_id: str, sample_kind: str,
    target_series_ids: Sequence[str], channel: str,
) -> str:
    event_suffix = str(event_id).removeprefix('event-')
    record_event_suffix, sample_suffix = _record_parts(record_id)
    if event_suffix != record_event_suffix:
        raise ValueError('EVENT_AND_RECORD_ID_MISMATCH')
    kind = SAMPLE_KIND_LABELS.get(sample_kind, sample_kind)
    target = ' + '.join(str(value) for value in target_series_ids)
    channel_label = CHANNEL_LABELS.get(channel, channel.replace('_', ' ').title())
    return f'E{event_suffix}-S{sample_suffix} | {kind} | {target} | {channel_label}'


class _SnapshotTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = ' '.join(data.split())
        if text:
            self.parts.append(text)


def extract_source_excerpt(source: Mapping[str, Any], *, root: Path = ROOT) -> dict[str, str]:
    locator = source.get('locator') if isinstance(source.get('locator'), Mapping) else {}
    summary = str(source.get('summary') or '').strip()
    relative_path = str(source.get('local_snapshot_path') or '')
    snapshot = (Path(root) / relative_path).resolve()
    try:
        snapshot.relative_to(Path(root).resolve())
    except ValueError:
        return {'excerpt': summary, 'excerpt_origin': 'source_summary_fallback'}
    if not snapshot.is_file():
        return {'excerpt': summary, 'excerpt_origin': 'source_summary_fallback'}
    if locator.get('type') == 'html_text':
        parser = _SnapshotTextParser()
        parser.feed(snapshot.read_text(encoding='utf-8', errors='replace'))
        anchor = str(locator.get('value') or '').strip().casefold()
        matching_part = next((part for part in parser.parts if anchor and anchor in part.casefold()), '')
        if matching_part:
            return {'excerpt': matching_part, 'excerpt_origin': 'snapshot_html_locator'}
    if locator.get('type') == 'pdf_page':
        page_match = re.match(r'\s*(\d+)', str(locator.get('value') or ''))
        if page_match:
            try:
                from pypdf import PdfReader

                page_index = int(page_match.group(1)) - 1
                page_text = PdfReader(str(snapshot)).pages[page_index].extract_text() or ''
                page_text = ' '.join(page_text.split())
                if page_text:
                    return {'excerpt': page_text[:600], 'excerpt_origin': 'snapshot_pdf_page'}
            except (ImportError, IndexError, OSError, ValueError):
                pass
    return {'excerpt': summary, 'excerpt_origin': 'source_summary_fallback'}


def _source_ref(source: Mapping[str, Any], *, stance: str) -> dict[str, Any]:
    locator = source.get('locator') if isinstance(source.get('locator'), Mapping) else {}
    excerpt = extract_source_excerpt(source)
    return {
        'source_id': str(source['source_id']),
        'source_name': str(source.get('title') or source['source_id']),
        'publisher': str(source.get('publisher') or ''),
        'source_url': str(source.get('source_url') or ''),
        'published_at': str(source.get('published_at') or ''),
        'locator': dict(locator),
        'excerpt': excerpt['excerpt'],
        'excerpt_origin': excerpt['excerpt_origin'],
        'content_sha256': str(source.get('content_sha256') or ''),
        'snapshot_path': str(source.get('local_snapshot_path') or ''),
        'evidence_stance': stance,
    }


def _claim(
    claim_id: str, claim_type: str, statement: str, evidence: Sequence[Mapping[str, Any]],
    *, evidence_role: str = 'SUPPORTS',
) -> dict[str, Any]:
    return {
        'claim_id': claim_id,
        'claim_type': claim_type,
        'statement': statement,
        'evidence_refs': [_source_ref(source, stance=evidence_role) for source in evidence],
    }


def _visible_sources(
    sample: Mapping[str, Any], manifest: Mapping[str, Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    sources: list[Mapping[str, Any]] = []
    for source_id in sample.get('visible_evidence_ids') or []:
        source = manifest.get(str(source_id))
        if source is None:
            raise ValueError(f'VISIBLE_SOURCE_MISSING:{source_id}')
        sources.append(source)
    return sources


def _event_source(sources: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    return next((source for source in sources if source.get('role') == 'event_fact'), sources[0])


def _report_sources(sources: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    reports = [source for source in sources if source.get('role') != 'event_fact']
    return reports or list(sources)


def _timeline(
    sample: Mapping[str, Any], sources: Sequence[Mapping[str, Any]], event: Mapping[str, Any] | None,
) -> list[dict[str, str]]:
    period = sample['period_comparison']
    timeline: list[dict[str, str]] = []
    if event and event.get('occurred_at'):
        timeline.append({'stage': 'event_occurred', 'at': str(event['occurred_at']), 'label': '事件发生'})
    if event and event.get('first_public_at'):
        timeline.append({'stage': 'first_public_disclosure', 'at': str(event['first_public_at']), 'label': '首次公开披露'})
    for source in sources:
        timeline.append({
            'stage': 'official_source_published', 'at': str(source['published_at']),
            'label': '官方来源发布', 'source_id': str(source['source_id']),
        })
    timeline.extend([
        {'stage': 'market_d1', 'at': str(period['start_date']) + 'T23:59:59+00:00', 'label': 'D1 市场观察'},
        {'stage': 'market_d3', 'at': str(period['end_date']) + 'T23:59:59+00:00', 'label': 'D3 市场观察'},
        {'stage': 'forecast_cutoff', 'at': str(sample['forecast_as_of_at']), 'label': '预测截点'},
    ])
    return sorted(timeline, key=lambda row: (row['at'], row['stage']))


def build_audit_sample(
    sample: Mapping[str, Any], manifest: Mapping[str, Mapping[str, Any]],
    event: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    sources = _visible_sources(sample, manifest)
    report_sources = _report_sources(sources)
    chain = sample['fact_transmission_chain']
    nodes = list(chain['nodes'])
    event_node = next(node for node in nodes if node.get('node_type') == 'event')
    mechanism_node = next(node for node in nodes if node.get('node_type') == 'mechanism')
    market_node = next(node for node in nodes if node.get('node_type') == 'market')
    display_id = build_display_id(
        event_id=str(sample['event_id']), record_id=str(sample['record_id']),
        sample_kind=str(sample['sample_kind']), target_series_ids=list(sample['target_series_ids']),
        channel=str(chain['selected_channel']),
    )
    claims = [
        _claim('claim-event', 'event_fact', str(event_node['statement']), [_event_source(sources)]),
        _claim(
            'claim-data', 'data_observation',
            '; '.join(
                f"{row['series_name']}: D1 {row['d1_change']}, D3 {row['d3_change']}"
                for row in sample['supporting_observations']
            ),
            report_sources,
        ),
        _claim(
            'claim-transmission', 'transmission_assessment',
            f"{mechanism_node['statement']} {market_node['statement']}", report_sources,
        ),
        _claim(
            'claim-prediction', 'prediction',
            f"{sample['short_horizon_prediction']['target_series_id']} "
            f"{sample['short_horizon_prediction']['direction']}", sources,
        ),
        _claim(
            'claim-counterevidence', 'counterevidence',
            str(sample['counterevidence'][0]), report_sources, evidence_role='CONTEXT_FOR_ALTERNATIVE',
        ),
    ]
    return {
        'audit_dataset_version': AUDIT_DATASET_VERSION,
        'record_id': str(sample['record_id']),
        'display_id': display_id,
        'event_id': str(sample['event_id']),
        'sample_kind': str(sample['sample_kind']),
        'target_series_ids': list(sample['target_series_ids']),
        'selected_channel': str(chain['selected_channel']),
        'forecast_as_of_at': str(sample['forecast_as_of_at']),
        'period_comparison': dict(sample['period_comparison']),
        'transmission_chain': {'nodes': nodes, 'edges': list(chain['edges'])},
        'market_observations': [dict(row) for row in sample['supporting_observations']],
        'claims': claims,
        'timeline': _timeline(sample, sources, event),
        'review_status': str(sample['review_status']),
        'final_commentary': str(sample.get('final_commentary') or ''),
        'company_impact_status': 'NOT_ASSESSED',
        'formal_sample_generation_allowed': False,
    }


def validate_audit_sample(
    audited: Mapping[str, Any], manifest: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    errors: list[str] = []
    try:
        cutoff = _parse_datetime(str(audited['forecast_as_of_at']))
    except (KeyError, TypeError, ValueError):
        return ['FORECAST_CUTOFF_INVALID']
    claim_ids: set[str] = set()
    for claim in audited.get('claims') or []:
        claim_id = str(claim.get('claim_id') or '')
        if not claim_id or claim_id in claim_ids:
            errors.append('CLAIM_ID_INVALID_OR_DUPLICATE')
        claim_ids.add(claim_id)
        if claim.get('claim_type') not in PUBLIC_CLAIM_TYPES:
            errors.append('CLAIM_TYPE_INVALID')
        refs = claim.get('evidence_refs') or []
        if not refs:
            errors.append(f'CLAIM_EVIDENCE_MISSING:{claim_id}')
        for ref in refs:
            source_id = str(ref.get('source_id') or '')
            source = manifest.get(source_id)
            if source is None:
                errors.append(f'EVIDENCE_SOURCE_MISSING:{source_id}')
                continue
            for key in ('source_url', 'published_at', 'content_sha256'):
                if str(ref.get(key) or '') != str(source.get(key) or ''):
                    errors.append(f'EVIDENCE_{key.upper()}_MISMATCH:{source_id}')
            if not ref.get('excerpt') or not ref.get('locator'):
                errors.append(f'EVIDENCE_LOCATOR_OR_EXCERPT_MISSING:{source_id}')
            try:
                if _parse_datetime(str(ref['published_at'])) > cutoff:
                    errors.append(f'FUTURE_EVIDENCE:{source_id}')
            except (KeyError, TypeError, ValueError):
                errors.append(f'EVIDENCE_PUBLICATION_TIME_INVALID:{source_id}')
    if {claim.get('claim_type') for claim in audited.get('claims') or []} != PUBLIC_CLAIM_TYPES:
        errors.append('PUBLIC_CLAIM_SET_INVALID')
    public_text = '\n'.join(
        [str(audited.get('final_commentary') or '')]
        + [str(claim.get('statement') or '') for claim in audited.get('claims') or []]
    ).lower()
    if any(token in public_text for token in HIDDEN_TOKENS):
        errors.append('HIDDEN_VALIDATION_LEAK')
    return sorted(set(errors))


def build_company_impact_link(
    *, event_id: str, company_code: str, company_name: str,
    event_evidence_ids: Sequence[str], industry_evidence_ids: Sequence[str],
    company_evidence_ids: Sequence[str], counterevidence_ids: Sequence[str],
    manifest: Mapping[str, Mapping[str, Any]], period: Mapping[str, str],
    impact_metric: str, impact_direction: str, transmission_summary: str,
) -> dict[str, Any]:
    required_groups = {
        'event': list(event_evidence_ids), 'industry': list(industry_evidence_ids),
        'company': list(company_evidence_ids), 'counterevidence': list(counterevidence_ids),
    }
    missing_groups = [name for name, source_ids in required_groups.items() if not source_ids]
    unknown_ids = [
        source_id for source_ids in required_groups.values() for source_id in source_ids
        if source_id not in manifest
    ]
    status = 'VERIFIED' if not missing_groups and not unknown_ids else 'INSUFFICIENT_EVIDENCE'
    return {
        'event_id': event_id,
        'company': {'company_code': company_code, 'company_name': company_name},
        'association_status': status,
        'period': dict(period),
        'impact_metric': impact_metric,
        'impact_direction': impact_direction,
        'transmission_summary': transmission_summary,
        'evidence_groups': required_groups,
        'missing_evidence_groups': missing_groups,
        'unknown_source_ids': unknown_ids,
        'formal_sample_generation_allowed': False,
    }


def write_samples_json(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([dict(row) for row in rows], ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
def build_company_research_registry(performance_cases: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}
    for case in performance_cases:
        company = case.get('company') if isinstance(case.get('company'), Mapping) else {}
        company_code = str(company.get('company_code') or '')
        company_name = str(company.get('company_name') or '')
        if not company_code or company_code in registry:
            continue
        registry[company_code] = {
            'company_code': company_code,
            'company_name': company_name,
            'historical_event_association_status': 'NOT_ASSESSED',
            'verified_event_ids': [],
            'reason': 'No event-period company, industry, and counterevidence chain has been published.',
            'formal_sample_generation_allowed': False,
        }
    return [registry[company_code] for company_code in sorted(registry)]
def build_audit_dataset(
    *, candidates_path: Path, manifest_path: Path, config_path: Path, output_root: Path,
    performance_cases_path: Path | None = None,
) -> dict[str, Any]:
    candidates = _read_jsonl(Path(candidates_path))
    manifest_rows = _read_jsonl(Path(manifest_path))
    manifest = {str(row['source_id']): row for row in manifest_rows}
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    events = {str(row['event_id']): row for row in config.get('events', [])}
    audited: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    for sample in candidates:
        try:
            record = build_audit_sample(sample, manifest, events.get(str(sample.get('event_id'))))
            errors = validate_audit_sample(record, manifest)
            if errors:
                rejections.append({'record_id': record['record_id'], 'errors': errors})
            audited.append(record)
        except (KeyError, TypeError, ValueError) as exc:
            rejections.append({'record_id': str(sample.get('record_id') or '<unknown>'), 'errors': [str(exc)]})
    company_registry = build_company_research_registry(
        _read_jsonl(Path(performance_cases_path)) if performance_cases_path else []
    )
    event_timelines = [
        {'event_id': event_id, 'timeline': next(record['timeline'] for record in audited if record['event_id'] == event_id)}
        for event_id in sorted({record['event_id'] for record in audited})
    ]
    output_root = Path(output_root)
    _write_jsonl(output_root / 'auditable_macro_samples.jsonl', audited)
    write_samples_json(output_root / 'samples.json', audited)
    _write_jsonl(output_root / 'event_timelines.jsonl', event_timelines)
    _write_jsonl(output_root / 'company_impact_links.jsonl', [])
    _write_jsonl(output_root / 'company_research_registry.jsonl', company_registry)
    _write_jsonl(output_root / 'rejected.jsonl', rejections)
    summary = {
        'audit_dataset_version': AUDIT_DATASET_VERSION,
        'sample_count': len(audited),
        'event_count': len(event_timelines),
        'company_impact_link_count': 0,
        'company_research_registry_count': len(company_registry),
        'verified_company_impact_count': 0,
        'rejected_count': len(rejections),
        'formal_sample_generation_allowed': False,
        'status': 'ready_for_human_review' if len(audited) == 100 and not rejections else 'review_required',
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / 'summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8',
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description='Build auditable FinGoose macro event samples.')
    parser.add_argument('--candidates', type=Path, default=ROOT / 'outputs' / 'fingoose_macro_event_attribution_v1_100' / 'macro_candidates.jsonl')
    parser.add_argument('--manifest', type=Path, default=ROOT / 'outputs' / 'fingoose_macro_event_attribution_v1_100' / 'source_manifest.jsonl')
    parser.add_argument('--config', type=Path, default=ROOT / 'configs' / 'fingoose_macro_events_v1.json')
    parser.add_argument('--output-root', type=Path, default=ROOT / 'outputs' / 'fingoose_macro_event_audit_v1_100')
    parser.add_argument('--performance-cases', type=Path, default=ROOT / 'outputs' / 'fingoose_research_candidate_v0_3' / 'performance' / 'performance_cases.jsonl')
    args = parser.parse_args()
    summary = build_audit_dataset(
        candidates_path=args.candidates, manifest_path=args.manifest,
        config_path=args.config, output_root=args.output_root,
        performance_cases_path=args.performance_cases,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary['status'] == 'ready_for_human_review' else 1


if __name__ == '__main__':
    raise SystemExit(main())
