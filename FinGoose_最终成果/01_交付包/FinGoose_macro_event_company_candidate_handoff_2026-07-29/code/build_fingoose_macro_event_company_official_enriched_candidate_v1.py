from __future__ import annotations

import argparse
import copy
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping

from build_fingoose_macro_event_company_enriched_candidate_v1 import (
    ROOT,
    build_enriched_candidate_dataset,
)


DATASET_VERSION = 'fingoose-macro-event-company-official-enriched-candidate-v1.0'

QUARTER_REPORTS = {
    1: ('q1',),
    2: ('q1', 'h1'),
    3: ('h1', 'q3'),
    4: ('q3', 'annual'),
}

METRIC_TYPE_MAP = {
    'REVENUE': 'revenue',
    'NET_PROFIT': 'net_profit',
    'OPERATING_CASH_FLOW': 'operating_cash_flow',
}

BUSINESS_PATTERNS = (
    '\u62a5\u544a\u671f\u5185\u516c\u53f8\u4ece\u4e8b\u7684\u4e3b\u8981\u4e1a\u52a1',
    '\u4e3b\u8981\u4e1a\u52a1', '\u4e3b\u8425\u4e1a\u52a1', '\u4e1a\u52a1\u677f\u5757',
    '\u975e\u5229\u606f\u51c0\u6536\u5165', '\u8d37\u6b3e\u548c\u57ab\u6b3e',
)

RISK_PATTERNS = (
    '\u53ef\u80fd\u9762\u5bf9\u7684\u98ce\u9669', '\u884c\u4e1a\u7ade\u4e89\u52a0\u5267',
    '\u539f\u6750\u6599\u4ef7\u683c\u6ce2\u52a8', '\u5e02\u573a\u9700\u6c42\u4e0d\u8db3',
    '\u5b8f\u89c2\u7ecf\u6d4e\u4e0b\u884c', '\u98ce\u9669\u7ba1\u7406',
)
RISK_EXCLUSIONS = (
    '\u4f1a\u8ba1\u653f\u7b56', '\u4e3b\u8981\u98ce\u9669\u548c\u62a5\u916c', '\u6536\u5165\u786e\u8ba4',
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding='utf-8-sig').splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        ''.join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + '\n' for row in rows),
        encoding='utf-8',
    )


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )


def derive_standalone_quarter(
    period: str,
    cumulative_facts: Iterable[Mapping[str, Any]],
    metric: str,
) -> dict[str, Any] | None:
    match = re.fullmatch(r'(20\d{2})Q([1-4])', period)
    if match is None:
        raise ValueError('INVALID_OBSERVATION_QUARTER')
    year, quarter_text = match.groups()
    kinds = QUARTER_REPORTS[int(quarter_text)]
    by_report = {
        str(row.get('report_type')): row
        for row in cumulative_facts
        if row.get('metric') == metric
    }
    reports = [kind + '_' + year for kind in kinds]
    if any(report not in by_report for report in reports):
        return None
    selected = [by_report[report] for report in reports]
    units = {str(row.get('unit')) for row in selected}
    if len(units) != 1 or 'UNKNOWN' in units:
        return None
    values = [Decimal(str(row['value_decimal'])) for row in selected]
    result = values[0] if len(values) == 1 else values[1] - values[0]
    value: int | float = (
        int(result) if result == result.to_integral_value() else float(result)
    )
    evidence_refs = [
        {
            'source_id': str(row['source_id']),
            'source_locator': str(row['source_locator']),
            'text_sha256': str(row['text_sha256']),
        }
        for row in selected
    ]
    return {
        'company_code': str(selected[0]['company_code']),
        'metric': metric,
        'period': period,
        'value': value,
        'value_decimal': format(result, 'f'),
        'unit': next(iter(units)),
        'currency': 'CNY',
        'derivation_type': 'direct_cumulative' if len(values) == 1 else 'cumulative_difference',
        'calculation': {
            'report_types': reports,
            'input_values': [format(value, 'f') for value in values],
            'formula': 'direct_q1' if len(values) == 1 else 'later_cumulative - earlier_cumulative',
            'result_decimal': format(result, 'f'),
        },
        'evidence_refs': evidence_refs,
        'formal_sample_generation_allowed': False,
    }


def _select_page(
    pages: Iterable[Mapping[str, Any]], patterns: tuple[str, ...],
) -> tuple[dict[str, Any], str] | None:
    matches: list[tuple[int, int, dict[str, Any], str]] = []
    for raw in pages:
        statement = re.sub(r'\s+', ' ', str(raw.get('statement') or '')).strip()
        for priority, pattern in enumerate(patterns):
            index = statement.find(pattern)
            if index >= 0:
                matches.append((priority, -len(statement), dict(raw), pattern))
                break
    if not matches:
        return None
    _, _, page, pattern = sorted(matches, key=lambda row: (row[0], row[1]))[0]
    return page, pattern

def _select_risk_page(
    pages: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Any], str] | None:
    eligible = [
        row for row in pages
        if int(row.get('page_number') or 0) <= 50
        and not any(
            exclusion in str(row.get('statement') or '')
            for exclusion in RISK_EXCLUSIONS
        )
    ]
    return _select_page(eligible, RISK_PATTERNS)


def _excerpt(statement: str, marker: str, limit: int = 700) -> str:
    text = re.sub(r'\s+', ' ', statement).strip()
    index = max(0, text.find(marker))
    start = max(0, index - 100)
    return text[start:start + limit]


def _source_ref(
    page: Mapping[str, Any], marker: str, manifest: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        'source_id': page['source_id'],
        'source_tier': 1,
        'publisher': 'CNINFO',
        'source_url': page['source_url'],
        'published_at': page['published_at'],
        'retrieved_at': manifest.get('retrieved_at'),
        'local_snapshot_path': manifest['local_snapshot_path'],
        'content_sha256': page['content_sha256'],
        'source_locator': page['source_locator'],
        'text_sha256': page['text_sha256'],
        'excerpt': _excerpt(str(page['statement']), marker),
        'model_visible': False,
        'verification_status': 'VERIFIED',
    }


def _node(dossier: Mapping[str, Any], node_type: str) -> dict[str, Any]:
    return next(
        row for row in dossier['transmission_chain']['nodes']
        if row['node_type'] == node_type
    )


def _set_node(
    dossier: dict[str, Any], node_type: str, value: str, refs: list[dict[str, Any]],
) -> None:
    _node(dossier, node_type).update({
        'status': 'VERIFIED_EVIDENCE',
        'value': value,
        'evidence_refs': refs,
        'gap_reason': None,
    })


def _fact_refs(
    derived: Mapping[str, Any],
    pages_by_key: Mapping[tuple[str, str], Mapping[str, Any]],
    manifest_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    refs = []
    for raw in derived['evidence_refs']:
        page = pages_by_key[(raw['source_id'], raw['source_locator'])]
        refs.append(_source_ref(page, '', manifest_by_id[raw['source_id']]))
    return refs


def _enrich_output(
    output_root: Path,
    manifests: list[dict[str, Any]],
    pages: list[dict[str, Any]],
    cumulative_facts: list[dict[str, Any]],
) -> dict[str, int]:
    dossiers = _read_jsonl(output_root / 'company_event_dossiers.jsonl')
    metric_facts = _read_jsonl(output_root / 'company_metric_facts.jsonl')
    attributions = _read_jsonl(output_root / 'company_attribution_samples.jsonl')
    gap_rows = _read_jsonl(output_root / 'company_evidence_gaps.jsonl')

    manifest_by_id = {row['source_id']: row for row in manifests}
    pages_by_company: dict[str, list[dict[str, Any]]] = {}
    pages_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for page in pages:
        pages_by_company.setdefault(page['company_code'], []).append(page)
        pages_by_key[(page['source_id'], page['source_locator'])] = page
    facts_by_company: dict[str, list[dict[str, Any]]] = {}
    for fact in cumulative_facts:
        facts_by_company.setdefault(fact['company_code'], []).append(fact)

    dossier_by_id: dict[str, dict[str, Any]] = {}
    filled_nodes: set[tuple[str, str]] = set()
    derived_by_dossier: dict[str, dict[str, dict[str, Any]]] = {}
    exposure_count = 0
    risk_count = 0
    standalone_count = 0

    for dossier in dossiers:
        dossier_by_id[dossier['dossier_id']] = dossier
        code = dossier['company_code']
        company_pages = pages_by_company.get(code, [])
        if dossier['event_id'] != 'event-02':
            selected = _select_page(company_pages, BUSINESS_PATTERNS)
            if selected:
                page, marker = selected
                ref = _source_ref(page, marker, manifest_by_id[page['source_id']])
                value = ref['excerpt']
                dossier['business_exposure'] = {
                    'status': 'VERIFIED_EVIDENCE', 'value': value,
                    'evidence_refs': [ref], 'gap_reason': None,
                }
                _set_node(dossier, 'COMPANY_BUSINESS_EXPOSURE', value, [ref])
                filled_nodes.add((dossier['dossier_id'], 'COMPANY_BUSINESS_EXPOSURE'))
                exposure_count += 1

            selected_risk = _select_risk_page(company_pages)
            if selected_risk:
                page, marker = selected_risk
                ref = _source_ref(page, marker, manifest_by_id[page['source_id']])
                value = ref['excerpt']
                dossier['competing_explanations'] = [{
                    'status': 'VERIFIED_EVIDENCE', 'value': value,
                    'evidence_refs': [ref], 'gap_reason': None,
                }]
                _set_node(dossier, 'COMPETING_EXPLANATION', value, [ref])
                filled_nodes.add((dossier['dossier_id'], 'COMPETING_EXPLANATION'))
                risk_count += 1

        observation = dossier['observation_quarter']['value']
        company_facts = facts_by_company.get(code, [])
        derived_metrics: dict[str, dict[str, Any]] = {}
        for metric_type, metric in METRIC_TYPE_MAP.items():
            derived = derive_standalone_quarter(observation, company_facts, metric)
            if derived is not None:
                derived['evidence_refs'] = _fact_refs(
                    derived, pages_by_key, manifest_by_id,
                )
                derived_metrics[metric_type] = derived
                standalone_count += 1
        derived_by_dossier[dossier['dossier_id']] = derived_metrics
        if derived_metrics:
            refs = []
            summaries = []
            for metric_type, fact in derived_metrics.items():
                refs.extend(fact['evidence_refs'])
                summaries.append(
                    metric_type + ' ' + fact['value_decimal'] + ' ' + fact['unit']
                )
            unique_refs = {
                ref['source_id'] + '|' + ref['source_locator']: ref for ref in refs
            }
            _set_node(
                dossier, 'FINANCIAL_RESULT', '; '.join(summaries),
                list(unique_refs.values()),
            )
            filled_nodes.add((dossier['dossier_id'], 'FINANCIAL_RESULT'))

        dossier['candidate_status'] = 'PARTIAL_EVIDENCE'
        dossier['evidence_status'] = 'PARTIAL_EVIDENCE'
        dossier['evidence_gaps'] = [
            node['gap_reason']
            for node in dossier['transmission_chain']['nodes']
            if node.get('gap_reason')
        ]

    for row in metric_facts:
        derived = derived_by_dossier.get(row['dossier_id'], {}).get(row['metric_type'])
        if derived is None:
            continue
        row.update({
            'period': derived['period'],
            'status': 'VERIFIED_EVIDENCE',
            'value': derived['value'],
            'value_decimal': derived['value_decimal'],
            'unit': derived['unit'],
            'currency': derived['currency'],
            'evidence_refs': derived['evidence_refs'],
            'gap_reason': None,
            'derivation_type': derived['derivation_type'],
            'calculation': derived['calculation'],
        })

    for row in attributions:
        row['transmission_chain'] = copy.deepcopy(
            dossier_by_id[row['dossier_id']]['transmission_chain']
        )

    gap_rows = [
        row for row in gap_rows
        if (row['dossier_id'], row['node_type']) not in filled_nodes
    ]
    _write_jsonl(output_root / 'company_event_dossiers.jsonl', dossiers)
    _write_jsonl(output_root / 'company_metric_facts.jsonl', metric_facts)
    _write_jsonl(output_root / 'company_attribution_samples.jsonl', attributions)
    _write_jsonl(output_root / 'company_evidence_gaps.jsonl', gap_rows)

    existing_sources = _read_jsonl(output_root / 'source_manifest.jsonl')
    source_ids = {row['source_id'] for row in existing_sources}
    official_sources = []
    for raw in manifests:
        if raw['source_id'] in source_ids:
            continue
        row = copy.deepcopy(raw)
        row.update({
            'source_kind': 'official_company_report_intake',
            'source_tier': 1,
            'tier': 1,
            'verification_status': 'VERIFIED',
            'model_visible': False,
            'formal_sample_generation_allowed': False,
        })
        official_sources.append(row)
    _write_jsonl(
        output_root / 'source_manifest.jsonl',
        existing_sources + official_sources,
    )
    _write_jsonl(
        output_root / 'official_cumulative_financial_facts.jsonl',
        cumulative_facts,
    )
    return {
        'official_report_count': len(manifests),
        'official_page_evidence_count': len(pages),
        'official_cumulative_fact_count': len(cumulative_facts),
        'official_exposure_dossier_count': exposure_count,
        'official_competing_explanation_dossier_count': risk_count,
        'official_standalone_metric_fact_count': standalone_count,
        'remaining_evidence_gap_count': len(gap_rows),
    }


def build_official_enriched_candidate(
    config_path: Path,
    output_root: Path,
    *,
    historical_root: Path,
    intake_root: Path,
    workspace_root: Path = ROOT,
) -> dict[str, Any]:
    build_enriched_candidate_dataset(
        config_path,
        output_root,
        historical_root=historical_root,
        workspace_root=workspace_root,
    )
    manifests = _read_jsonl(intake_root / 'evidence' / 'source_manifest.jsonl')
    pages = _read_jsonl(
        intake_root / 'evidence' / 'company_report_page_evidence.jsonl'
    )
    cumulative_facts = _read_jsonl(
        intake_root / 'financial_facts' / 'official_cumulative_financial_facts.jsonl'
    )
    counts = _enrich_output(output_root, manifests, pages, cumulative_facts)

    dossiers = _read_jsonl(output_root / 'company_event_dossiers.jsonl')
    attributions = _read_jsonl(output_root / 'company_attribution_samples.jsonl')
    forecasts = _read_jsonl(output_root / 'company_forecast_samples.jsonl')
    projection = _read_jsonl(
        output_root / 'company_candidate_training_projection.jsonl'
    )
    official_ids = {row['source_id'] for row in manifests}
    checks = {
        'thirty_dossiers': len(dossiers) == 30,
        'thirty_attribution_samples': len(attributions) == 30,
        'thirty_forecast_samples': len(forecasts) == 30,
        'official_sources_isolated_from_forecast_projection': all(
            source_id not in json.dumps(row, ensure_ascii=False)
            for row in projection
            if row['task_type'] == 'COMPANY_FORECAST'
            for source_id in official_ids
        ),
        'formal_ready_false': True,
    }
    report = {
        'dataset_version': DATASET_VERSION,
        'release_tier': 'CANDIDATE',
        'candidate_ready': all(checks.values()),
        'formal_ready': False,
        'checks': checks,
        'errors': [key for key, passed in checks.items() if not passed],
        'formal_blockers': [
            'OFFICIAL_REPORT_COVERAGE_INCOMPLETE',
            'EVENT_CHANNEL_REVIEW_INCOMPLETE',
            'PRICE_WINDOWS_PENDING',
            'SECOND_REVIEWS_INCOMPLETE',
        ],
    }
    summary = json.loads(
        (output_root / 'summary.json').read_text(encoding='utf-8')
    )
    summary.update(counts)
    summary.update({
        'dataset_version': DATASET_VERSION,
        'candidate_ready': report['candidate_ready'],
        'formal_ready': False,
        'source_count': len(_read_jsonl(output_root / 'source_manifest.jsonl')),
        'verified_metric_fact_count': sum(
            row['status'] == 'VERIFIED_EVIDENCE'
            for row in _read_jsonl(output_root / 'company_metric_facts.jsonl')
        ),
        'evidence_gap_count': counts['remaining_evidence_gap_count'],
        'formal_blockers': report['formal_blockers'],
    })
    _write_json(output_root / 'summary.json', summary)
    _write_json(output_root / 'validation_report.json', report)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description='Build the official-evidence enriched company candidate dataset.')
    parser.add_argument(
        '--config', type=Path,
        default=ROOT / 'configs' / 'fingoose_macro_event_company_candidate_v1.json',
    )
    parser.add_argument(
        '--historical-root', type=Path,
        default=ROOT / 'outputs' / 'fingoose_historical_company_impact_v1',
    )
    parser.add_argument(
        '--intake-root', type=Path,
        default=ROOT / 'outputs' / 'fingoose_macro_event_company_official_intake_v1',
    )
    parser.add_argument(
        '--output-root', type=Path,
        default=ROOT / 'outputs' / 'fingoose_macro_event_company_official_enriched_candidate_v1',
    )
    args = parser.parse_args()
    summary = build_official_enriched_candidate(
        args.config,
        args.output_root,
        historical_root=args.historical_root,
        intake_root=args.intake_root,
        workspace_root=ROOT,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary['candidate_ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

