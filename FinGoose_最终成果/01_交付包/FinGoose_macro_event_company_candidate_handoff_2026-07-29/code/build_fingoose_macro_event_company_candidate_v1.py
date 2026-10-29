from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parent
DATASET_VERSION = 'fingoose-macro-event-company-candidate-v1.0'
RELEASE_TIER = 'CANDIDATE'
ARTIFACT_NAMES = {
    'summary.json',
    'company_event_dossiers.jsonl',
    'company_metric_facts.jsonl',
    'company_stock_windows.jsonl',
    'company_attribution_samples.jsonl',
    'company_forecast_samples.jsonl',
    'company_candidate_training_projection.jsonl',
    'company_candidate_hidden_labels.jsonl',
    'company_hidden_outcomes.jsonl',
    'company_review_records.jsonl',
    'company_evidence_gaps.jsonl',
    'candidate_company_registry.jsonl',
    'source_manifest.jsonl',
    'rejected.jsonl',
    'validation_report.json',
}
NODE_TYPES = [
    'MAJOR_EVENT',
    'INDUSTRY_MACRO_VARIABLE',
    'COMPANY_BUSINESS_EXPOSURE',
    'OPERATING_METRIC',
    'FINANCIAL_RESULT',
    'COMPETING_EXPLANATION',
    'ATTRIBUTION_OR_FORECAST',
]
PENDING_GAPS = {
    'COMPANY_BUSINESS_EXPOSURE': (
        'No archived official company disclosure currently verifies the candidate business exposure.'
    ),
    'OPERATING_METRIC': (
        'No archived official company evidence currently supports a comparable operating metric.'
    ),
    'FINANCIAL_RESULT': (
        'No archived official company reports currently support standalone-quarter financial results.'
    ),
    'COMPETING_EXPLANATION': (
        'No archived company-specific evidence currently supports a competing explanation assessment.'
    ),
    'ATTRIBUTION_OR_FORECAST': (
        'Attribution and forecast labels remain unknown until company evidence and independent review exist.'
    ),
}
PUBLIC_FORBIDDEN_KEYS = {
    'actual_value', 'actual_results', 'future_source_id', 'future_source_ids',
    'D5', 'D20', 'retrospective_attribution', 'association_label', 'forecast_labels',
}


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        ''.join(
            json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + '\n'
            for row in rows
        ),
        encoding='utf-8',
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding='utf-8-sig').splitlines()
        if line.strip()
    ]


def _project_path(workspace_root: Path, configured_path: str) -> Path:
    root = workspace_root.resolve()
    candidate = (root / configured_path).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError('PATH_OUTSIDE_PROJECT_ROOT:' + configured_path)
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _load_verified_market_inputs(
    market_root: Path, workspace_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    manifest = _read_jsonl(market_root / 'source_manifest.jsonl')
    event_rows = _read_jsonl(market_root / 'event_dossiers.jsonl')
    samples = _read_jsonl(market_root / 'attribution_samples.jsonl')
    if len(manifest) != 20 or len(event_rows) != 10:
        raise ValueError('MARKET_FORMAL_INPUT_COUNTS_INVALID')
    source_ids: set[str] = set()
    for source in manifest:
        source_id = str(source.get('source_id') or '')
        if not source_id or source_id in source_ids:
            raise ValueError('MARKET_SOURCE_ID_INVALID')
        source_ids.add(source_id)
        snapshot = _project_path(workspace_root, str(source.get('local_snapshot_path') or ''))
        if not snapshot.is_file():
            raise ValueError('MARKET_SOURCE_SNAPSHOT_MISSING:' + source_id)
        if _sha256(snapshot) != source.get('content_sha256'):
            raise ValueError('MARKET_SOURCE_HASH_MISMATCH:' + source_id)
        if not source.get('source_url') or not source.get('published_at'):
            raise ValueError('MARKET_SOURCE_METADATA_INCOMPLETE:' + source_id)
    forecast_cutoffs: dict[str, str] = {}
    for sample in samples:
        event_id = str(sample.get('event_id') or '')
        cutoff = str(sample.get('forecast_as_of_at') or '')
        if event_id and cutoff:
            previous = forecast_cutoffs.setdefault(event_id, cutoff)
            if previous != cutoff:
                raise ValueError('MARKET_EVENT_CUTOFF_INCONSISTENT:' + event_id)
    return manifest, event_rows, forecast_cutoffs


def _validate_config(config: Mapping[str, Any]) -> None:
    if config.get('dataset_version') != DATASET_VERSION:
        raise ValueError('CANDIDATE_DATASET_VERSION_INVALID')
    if config.get('release_tier') != RELEASE_TIER:
        raise ValueError('CANDIDATE_RELEASE_TIER_INVALID')
    events = config.get('events')
    if not isinstance(events, list) or len(events) != 10:
        raise ValueError('TEN_EVENTS_REQUIRED')
    expected_ids = [f'event-{index:02d}' for index in range(1, 11)]
    if [event.get('event_id') for event in events] != expected_ids:
        raise ValueError('EVENT_IDS_INVALID')
    for event in events:
        companies = event.get('companies')
        if not isinstance(companies, list) or len(companies) != 3:
            raise ValueError('THREE_COMPANIES_PER_EVENT_REQUIRED:' + event['event_id'])
        codes = [company.get('company_code') for company in companies]
        if len(set(codes)) != 3 or any(
            not isinstance(code, str) or not re.fullmatch(r'[0-9]{6}\.(SH|SZ)', code)
            for code in codes
        ):
            raise ValueError('A_SHARE_COMPANY_CODES_INVALID:' + event['event_id'])
        if any(not str(company.get('company_name') or '').strip() for company in companies):
            raise ValueError('COMPANY_NAME_REQUIRED:' + event['event_id'])


def _assert_output_is_not_protected(
    output_root: Path, protected_roots: Iterable[Path], workspace_root: Path,
) -> None:
    root = workspace_root.resolve()
    output = output_root.resolve()
    if not output.is_relative_to(root):
        raise ValueError('OUTPUT_OUTSIDE_PROJECT_ROOT')
    for protected in protected_roots:
        resolved = protected.resolve()
        if output == resolved or output.is_relative_to(resolved):
            raise ValueError('PROTECTED_OUTPUT_ROOT_TARGETED:' + str(resolved))


def _evidence_ref(source: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'source_id': source['source_id'],
        'content_sha256': source['content_sha256'],
        'locator': copy.deepcopy(source['locator']),
        'published_at': source['published_at'],
        'source_tier': source['tier'],
    }


def _node(
    dossier_id: str,
    index: int,
    node_type: str,
    source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if source is not None:
        return {
            'node_id': f'{dossier_id}-n{index}',
            'node_type': node_type,
            'status': 'VERIFIED_EVIDENCE',
            'value': source['summary'],
            'evidence_refs': [_evidence_ref(source)],
            'gap_reason': None,
        }
    return {
        'node_id': f'{dossier_id}-n{index}',
        'node_type': node_type,
        'status': 'PENDING_EVIDENCE',
        'value': 'UNKNOWN',
        'evidence_refs': [],
        'gap_reason': PENDING_GAPS[node_type],
    }


def _transmission_chain(
    dossier_id: str,
    event_source: Mapping[str, Any],
    macro_source: Mapping[str, Any],
) -> dict[str, Any]:
    nodes = [
        _node(dossier_id, 1, NODE_TYPES[0], event_source),
        _node(dossier_id, 2, NODE_TYPES[1], macro_source),
    ]
    nodes.extend(
        _node(dossier_id, index, node_type)
        for index, node_type in enumerate(NODE_TYPES[2:], 3)
    )
    return {
        'nodes': nodes,
        'edges': [
            {
                'from_node_id': nodes[index]['node_id'],
                'to_node_id': nodes[index + 1]['node_id'],
                'relation': 'TRANSMITS_TO',
            }
            for index in range(6)
        ],
    }


def _public_leakage_paths(value: Any, path: tuple[str, ...] = ()) -> list[str]:
    findings: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if key_text in PUBLIC_FORBIDDEN_KEYS:
                findings.append('.'.join(path + (key_text,)))
            findings.extend(_public_leakage_paths(item, path + (key_text,)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_public_leakage_paths(item, path + (str(index),)))
    return findings


def _safe_chain(chain: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'nodes': [
            {
                'node_id': node['node_id'],
                'node_type': node['node_type'],
                'status': node['status'],
                'value': node['value'],
                'evidence_refs': copy.deepcopy(node['evidence_refs']),
                'gap_reason': node['gap_reason'],
            }
            for node in chain['nodes']
        ],
        'edges': copy.deepcopy(chain['edges']),
    }


def build_candidate_dataset(
    config_path: Path,
    output_root: Path,
    *,
    workspace_root: Path = ROOT,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    config_path = config_path.resolve()
    if not config_path.is_relative_to(workspace_root):
        raise ValueError('CONFIG_OUTSIDE_PROJECT_ROOT')
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
    _validate_config(config)
    market_root = _project_path(workspace_root, config['market_source_root'])
    protected = [
        _project_path(workspace_root, path)
        for path in config.get('protected_output_roots', [])
    ]
    _assert_output_is_not_protected(output_root, protected, workspace_root)
    source_manifest, market_events, forecast_cutoffs = _load_verified_market_inputs(
        market_root, workspace_root,
    )
    event_map = {row['event_id']: row for row in market_events}
    source_map = {row['source_id']: row for row in source_manifest}

    dossiers: list[dict[str, Any]] = []
    stock_windows: list[dict[str, Any]] = []
    attribution_samples: list[dict[str, Any]] = []
    forecast_samples: list[dict[str, Any]] = []
    public_projection: list[dict[str, Any]] = []
    hidden_labels: list[dict[str, Any]] = []
    hidden_outcomes: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    registry: list[dict[str, Any]] = []
    metric_facts: list[dict[str, Any]] = []

    for configured_event in config['events']:
        event_id = configured_event['event_id']
        market_event = event_map[event_id]
        source_rows = [source_map[source_id] for source_id in market_event['source_ids']]
        event_source = next(
            (row for row in source_rows if row.get('role') == 'event_fact'), source_rows[0],
        )
        macro_source = next(
            (row for row in source_rows if row.get('role') == 'macro_report'), source_rows[-1],
        )
        cutoff = forecast_cutoffs[event_id]
        for company in configured_event['companies']:
            company_code = company['company_code']
            slug = company_code.lower().replace('.', '-')
            dossier_id = f'company-dossier-{event_id}-{slug}'
            chain = _transmission_chain(dossier_id, event_source, macro_source)
            dossier = {
                'dossier_id': dossier_id,
                'dataset_version': DATASET_VERSION,
                'release_tier': RELEASE_TIER,
                'event_id': event_id,
                'event_title': market_event['title'],
                'company_code': company_code,
                'company_name': company['company_name'],
                'industry': 'UNKNOWN',
                'business_exposure': {'status': 'PENDING_EVIDENCE', 'value': 'UNKNOWN', 'evidence_refs': [], 'gap_reason': PENDING_GAPS['COMPANY_BUSINESS_EXPOSURE']},
                'observation_quarter': {'status': 'PENDING_EVIDENCE', 'value': 'UNKNOWN'},
                'next_validation_quarter': {'status': 'PENDING_EVIDENCE', 'value': 'UNKNOWN'},
                'competing_explanations': [{'status': 'PENDING_EVIDENCE', 'value': 'UNKNOWN', 'evidence_refs': [], 'gap_reason': PENDING_GAPS['COMPETING_EXPLANATION']}],
                'evidence_status': 'PARTIAL_EVIDENCE',
                'evidence_gaps': [PENDING_GAPS[node_type] for node_type in NODE_TYPES[2:]],
                'confidence': 'LOW',
                'review_status': 'SECOND_REVIEW_REQUIRED',
                'candidate_status': 'PENDING_EVIDENCE',
                'forecast_as_of_at': cutoff,
                'event_source_ids': list(market_event['source_ids']),
                'transmission_chain': chain,
                'formal_sample_generation_allowed': False,
            }
            dossiers.append(dossier)
            registry.append({
                'registry_id': f'candidate-{event_id}-{slug}',
                'event_id': event_id,
                'company_code': company_code,
                'company_name': company['company_name'],
                'selection_status': 'PENDING_EVIDENCE',
                'selection_basis': 'CONFIGURED_FOR_EVIDENCE_COLLECTION_ONLY',
                'verified_company_exposure': False,
                'formal_sample_generation_allowed': False,
            })
            for metric_type in ('REVENUE', 'GROSS_MARGIN', 'NET_PROFIT', 'OPERATING_CASH_FLOW'):
                metric_facts.append({
                    'metric_fact_id': f"metric-{event_id}-{slug}-{metric_type.lower()}",
                    'dossier_id': dossier_id,
                    'event_id': event_id,
                    'company_code': company_code,
                    'metric_type': metric_type,
                    'period': 'UNKNOWN',
                    'status': 'PENDING_EVIDENCE',
                    'value': 'UNKNOWN',
                    'unit': 'UNKNOWN',
                    'currency': 'UNKNOWN',
                    'evidence_refs': [],
                    'gap_reason': 'No archived official company report supports this metric for the observation quarter.',
                })
            for node in chain['nodes']:
                if node['status'] == 'PENDING_EVIDENCE':
                    gaps.append({
                        'gap_id': f"gap-{event_id}-{slug}-{node['node_type'].lower()}",
                        'dossier_id': dossier_id,
                        'event_id': event_id,
                        'company_code': company_code,
                        'node_type': node['node_type'],
                        'status': 'PENDING_EVIDENCE',
                        'gap_reason': node['gap_reason'],
                        'required_evidence': 'ARCHIVED_OFFICIAL_COMPANY_OR_REGULATORY_EVIDENCE',
                    })
            gaps.append({
                'gap_id': f'gap-{event_id}-{slug}-stock-window',
                'dossier_id': dossier_id,
                'event_id': event_id,
                'company_code': company_code,
                'node_type': 'COMPANY_STOCK_WINDOW',
                'status': 'PENDING_EVIDENCE',
                'gap_reason': (
                    'No archived auditable company and CSI 300 price series is available; returns remain unknown.'
                ),
                'required_evidence': 'ARCHIVED_COMPANY_AND_CSI300_PRICE_SERIES',
            })
            stock_windows.append({
                'stock_window_id': f'company-window-{event_id}-{slug}',
                'dossier_id': dossier_id,
                'event_id': event_id,
                'company_code': company_code,
                'status': 'PENDING_EVIDENCE',
                'baseline': None,
                'windows': {'D1': None, 'D3': None, 'D5': None, 'D20': None},
                'gap_reason': gaps[-1]['gap_reason'],
                'financial_attribution_allowed': False,
            })

            attribution_id = f'company-attribution-{event_id}-{slug}'
            forecast_id = f'company-forecast-{event_id}-{slug}'
            attribution_samples.append({
                'record_id': attribution_id,
                'dataset_version': DATASET_VERSION,
                'release_tier': RELEASE_TIER,
                'task_type': 'COMPANY_ATTRIBUTION',
                'dossier_id': dossier_id,
                'event_id': event_id,
                'company_code': company_code,
                'company_name': company['company_name'],
                'association': 'UNSUPPORTED',
                'direction': 'UNCERTAIN',
                'confidence': 'LOW',
                'label_status': 'PENDING_EVIDENCE',
                'transmission_chain': copy.deepcopy(chain),
                'formal_sample_generation_allowed': False,
            })
            forecast_samples.append({
                'record_id': forecast_id,
                'dataset_version': DATASET_VERSION,
                'release_tier': RELEASE_TIER,
                'task_type': 'COMPANY_FORECAST',
                'dossier_id': dossier_id,
                'event_id': event_id,
                'company_code': company_code,
                'company_name': company['company_name'],
                'forecast_as_of_at': cutoff,
                'visible_windows': ['D1', 'D3'],
                'forecast_labels': [
                    {'label_type': 'REVENUE_MOMENTUM', 'value': 'INCONCLUSIVE', 'status': 'PENDING_EVIDENCE'},
                    {'label_type': 'PROFIT_STATE', 'value': 'INCONCLUSIVE', 'status': 'PENDING_EVIDENCE'},
                    {'label_type': 'OPERATING_METRIC', 'value': 'INCONCLUSIVE', 'status': 'PENDING_EVIDENCE'},
                ],
                'transmission_chain': copy.deepcopy(chain),
                'formal_sample_generation_allowed': False,
            })
            common_projection = {
                'dataset_version': DATASET_VERSION,
                'release_tier': RELEASE_TIER,
                'event_id': event_id,
                'company_code': company_code,
                'company_name': company['company_name'],
                'evidence_status': 'PENDING_EVIDENCE',
                'visible_event_evidence': [_evidence_ref(event_source)],
                'visible_industry_evidence': [_evidence_ref(macro_source)],
                'visible_company_evidence': [],
                'transmission_chain': _safe_chain(chain),
                'formal_sample_generation_allowed': False,
            }
            public_projection.append({
                **copy.deepcopy(common_projection),
                'record_id': attribution_id,
                'task_type': 'COMPANY_ATTRIBUTION',
            })
            public_projection.append({
                **copy.deepcopy(common_projection),
                'record_id': forecast_id,
                'task_type': 'COMPANY_FORECAST',
                'forecast_as_of_at': cutoff,
                'visible_windows': ['D1', 'D3'],
                'projection_source': 'INDEPENDENT_CUTOFF_SNAPSHOT',
            })
            for record_id, task_type in (
                (attribution_id, 'COMPANY_ATTRIBUTION'),
                (forecast_id, 'COMPANY_FORECAST'),
            ):
                hidden_labels.append({
                    'record_id': record_id,
                    'task_type': task_type,
                    'label_status': 'PENDING_EVIDENCE',
                    'label_value': 'UNKNOWN',
                    'gap_reason': (
                        'No evidence-supported reviewed gold label is available in the candidate release.'
                    ),
                    'model_visible': False,
                })
            hidden_outcomes.append({
                'record_id': forecast_id,
                'event_id': event_id,
                'company_code': company_code,
                'outcome_status': 'PENDING_EVIDENCE',
                'outcome_value': 'UNKNOWN',
                'evidence_refs': [],
                'gap_reason': (
                    'Future company outcome evidence has not been archived and no actual value is recorded.'
                ),
                'model_visible': False,
            })
            reviews.append({
                'review_id': f'review-{event_id}-{slug}',
                'dossier_id': dossier_id,
                'event_id': event_id,
                'company_code': company_code,
                'initial_reviewer_id': 'reviewer-user-01',
                'review_status': 'SECOND_REVIEW_REQUIRED',
                'initial_review': {
                    'reviewer_id': 'reviewer-user-01',
                    'status': 'AI_INITIAL_REVIEW_COMPLETED',
                    'decision': 'PENDING_EVIDENCE',
                },
                'second_review_trigger_reasons': [
                    'LOW_CONFIDENCE',
                    'CORE_DIMENSION_UNKNOWN',
                    'EVENT_CHANNEL_NOT_EXPLICITLY_DISCLOSED',
                ],
                'second_review': None,
                'adjudication': None,
                'formal_review_complete': False,
            })

    public_leakage = _public_leakage_paths(public_projection)
    required_dossier_fields = {
        'industry', 'business_exposure', 'observation_quarter', 'next_validation_quarter',
        'competing_explanations', 'evidence_status', 'evidence_gaps', 'confidence',
        'review_status',
    }
    checks = {
        'ten_events': len({row['event_id'] for row in dossiers}) == 10,
        'three_companies_per_event': all(
            sum(row['event_id'] == event_id for row in dossiers) == 3
            for event_id in [f'event-{index:02d}' for index in range(1, 11)]
        ),
        'candidate_counts': (
            len(dossiers), len(attribution_samples), len(forecast_samples), len(public_projection)
        ) == (30, 30, 30, 60),
        'required_dossier_fields': all(required_dossier_fields <= set(row) for row in dossiers),
        'pending_metric_facts': (
            len(metric_facts) == 120
            and all(row['status'] == 'PENDING_EVIDENCE' for row in metric_facts)
            and all(row['value'] == 'UNKNOWN' for row in metric_facts)
            and all(row['gap_reason'] for row in metric_facts)
        ),
        'structured_transmission_chains': all(
            len(row['transmission_chain']['nodes']) == 7
            and len(row['transmission_chain']['edges']) == 6
            and all('evidence_refs' in node for node in row['transmission_chain']['nodes'])
            for row in dossiers
        ),
        'source_snapshots_hash_verified': len(source_manifest) == 20,
        'evidence_gaps_explicit': bool(gaps) and all(row['gap_reason'] for row in gaps),
        'initial_reviewer_fixed': (
            len(reviews) == 30
            and {row['initial_reviewer_id'] for row in reviews} == {'reviewer-user-01'}
        ),
        'second_review_triggers_explicit': (
            len(reviews) == 30
            and all(row['review_status'] == 'SECOND_REVIEW_REQUIRED' for row in reviews)
            and all(row['second_review_trigger_reasons'] for row in reviews)
        ),
        'public_projection_leakage_free': not public_leakage,
        'protected_output_roots_not_targeted': True,
    }
    errors = [name.upper() + '_FAILED' for name, passed in checks.items() if not passed]
    candidate_ready = not errors
    validation_report = {
        'dataset_version': DATASET_VERSION,
        'release_tier': RELEASE_TIER,
        'candidate_ready': candidate_ready,
        'formal_ready': False,
        'checks': checks,
        'errors': errors,
        'public_projection_leakage_paths': public_leakage,
        'formal_blockers': [
            'COMPANY_EVIDENCE_INCOMPLETE',
            'PRICE_WINDOWS_PENDING',
            'GOLD_LABELS_PENDING',
            'FORMAL_REVIEWS_INCOMPLETE',
        ],
    }
    summary = {
        'dataset_version': DATASET_VERSION,
        'release_tier': RELEASE_TIER,
        'candidate_ready': candidate_ready,
        'formal_ready': False,
        'event_count': 10,
        'company_dossier_count': len(dossiers),
        'company_metric_fact_count': len(metric_facts),
        'company_stock_window_count': len(stock_windows),
        'attribution_sample_count': len(attribution_samples),
        'forecast_sample_count': len(forecast_samples),
        'candidate_sample_count': len(public_projection),
        'hidden_label_count': len(hidden_labels),
        'hidden_outcome_count': len(hidden_outcomes),
        'review_count': len(reviews),
        'verified_dossier_count': 0,
        'partial_evidence_dossier_count': len(dossiers),
        'pending_evidence_dossier_count': len(dossiers),
        'second_review_required_count': len(reviews),
        'rejected_dossier_count': 0,
        'evidence_gap_count': len(gaps),
        'candidate_registry_count': len(registry),
        'source_count': len(source_manifest),
        'rejected_count': 0,
        'formal_blockers': validation_report['formal_blockers'],
    }

    output_root.mkdir(parents=True, exist_ok=True)
    _write_json(output_root / 'summary.json', summary)
    _write_jsonl(output_root / 'company_event_dossiers.jsonl', dossiers)
    _write_jsonl(output_root / 'company_metric_facts.jsonl', metric_facts)
    _write_jsonl(output_root / 'company_stock_windows.jsonl', stock_windows)
    _write_jsonl(output_root / 'company_attribution_samples.jsonl', attribution_samples)
    _write_jsonl(output_root / 'company_forecast_samples.jsonl', forecast_samples)
    _write_jsonl(output_root / 'company_candidate_training_projection.jsonl', public_projection)
    _write_jsonl(output_root / 'company_candidate_hidden_labels.jsonl', hidden_labels)
    _write_jsonl(output_root / 'company_hidden_outcomes.jsonl', hidden_outcomes)
    _write_jsonl(output_root / 'company_review_records.jsonl', reviews)
    _write_jsonl(output_root / 'company_evidence_gaps.jsonl', gaps)
    _write_jsonl(output_root / 'candidate_company_registry.jsonl', registry)
    _write_jsonl(output_root / 'source_manifest.jsonl', source_manifest)
    _write_jsonl(output_root / 'rejected.jsonl', [])
    _write_json(output_root / 'validation_report.json', validation_report)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description='Build the FinGoose company candidate release.')
    parser.add_argument(
        '--config', type=Path,
        default=ROOT / 'configs' / 'fingoose_macro_event_company_candidate_v1.json',
    )
    parser.add_argument(
        '--output-root', type=Path,
        default=ROOT / 'outputs' / 'fingoose_macro_event_company_candidate_v1',
    )
    args = parser.parse_args()
    summary = build_candidate_dataset(args.config, args.output_root, workspace_root=ROOT)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary['candidate_ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
