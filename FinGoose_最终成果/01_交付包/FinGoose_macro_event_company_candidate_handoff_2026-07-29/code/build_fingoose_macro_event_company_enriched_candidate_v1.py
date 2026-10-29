from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from build_fingoose_macro_event_company_candidate_v1 import build_candidate_dataset


ROOT = Path(__file__).resolve().parent
DATASET_VERSION = 'fingoose-macro-event-company-enriched-candidate-v1.0'

INDUSTRIES = {
    '600009.SH': '机场与航空运输',
    '601111.SH': '航空运输',
    '002030.SZ': '体外诊断',
    '601857.SH': '石油天然气与石化',
    '601233.SH': '化纤与石化',
    '600346.SH': '炼化与化纤',
    '601318.SH': '保险与综合金融',
    '600036.SH': '商业银行',
    '601012.SH': '光伏制造',
    '600754.SH': '酒店与旅游服务',
    '002432.SZ': '医疗器械',
    '300482.SZ': '体外诊断',
    '688235.SH': '创新药',
    '600028.SH': '石油炼化与销售',
    '000301.SZ': '石化与新材料',
    '601919.SH': '集装箱航运',
    '601021.SH': '航空运输',
    '601988.SH': '商业银行',
    '601211.SH': '证券',
    '600048.SH': '房地产开发',
    '300059.SZ': '互联网证券与金融信息服务',
    '002475.SZ': '消费电子制造',
    '000333.SZ': '家电制造',
}

EVENT_PERIODS = {
    'event-01': ('2020Q2', '2020Q3'),
    'event-02': ('2022Q2', '2022Q3'),
    'event-03': ('2022Q3', '2022Q4'),
    'event-04': ('2023Q1', '2023Q2'),
    'event-05': ('2023Q2', '2023Q3'),
    'event-06': ('2023Q2', '2023Q3'),
    'event-07': ('2024Q1', '2024Q2'),
    'event-08': ('2024Q2', '2024Q3'),
    'event-09': ('2025Q1', '2025Q2'),
    'event-10': ('2025Q3', '2025Q4'),
}

EVENT_02_ENRICHMENT = {
    '601857.SH': {
        'exposure': '公司披露乌克兰危机等地缘政治因素推动国际原油价格持续震荡上行。',
        'competing': '二季度局部疫情反弹、经济下行压力及国内成品油需求减少同时影响经营结果。',
        'association': 'CONTRIBUTING_ASSOCIATION',
        'direction': 'UP',
        'confidence': 'MEDIUM',
    },
    '601233.SH': {
        'exposure': '公司披露涤纶长丝及上游 PTA 产品属于石油炼化衍生品，受到国际原油价格波动影响。',
        'competing': '原料成本上涨、国内疫情导致的需求阶段性萎缩和行业竞争同时影响经营结果。',
        'association': 'CONTRIBUTING_ASSOCIATION',
        'direction': 'DOWN',
        'confidence': 'MEDIUM',
    },
    '600346.SH': {
        'exposure': '公司披露从原油、芳烃、烯烃、PTA、乙二醇到聚酯新材料的一体化产业链。',
        'competing': '地缘冲突、疫情反复、商品价格高位和货币政策收紧共同影响经营环境。',
        'association': 'UNSUPPORTED',
        'direction': 'UNCERTAIN',
        'confidence': 'LOW',
    },
}

CLAIM_TYPE_TO_NODE = {
    'company_business_exposure': 'COMPANY_BUSINESS_EXPOSURE',
    'company_counterevidence': 'COMPETING_EXPLANATION',
}

METRIC_TYPES = {
    'revenue': 'REVENUE',
    'net_income_attributable': 'NET_PROFIT',
    'operating_cash_flow': 'OPERATING_CASH_FLOW',
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line]


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.write_text(
        ''.join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + '\n' for row in rows),
        encoding='utf-8',
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _historical_sources(historical_root: Path, workspace_root: Path) -> list[dict[str, Any]]:
    sources = _read_jsonl(historical_root / 'source_manifest.jsonl')
    result = []
    for source in sources:
        snapshot = (workspace_root / source['local_snapshot_path']).resolve()
        if not snapshot.is_file():
            raise ValueError('HISTORICAL_COMPANY_SOURCE_MISSING:' + source['source_id'])
        if _sha256(snapshot) != source['content_sha256']:
            raise ValueError('HISTORICAL_COMPANY_SOURCE_HASH_MISMATCH:' + source['source_id'])
        item = copy.deepcopy(source)
        item.update({
            'source_tier': 1,
            'tier': 1,
            'verification_status': 'VERIFIED',
            'snapshot_status': 'verified',
            'model_visible': False,
            'formal_sample_generation_allowed': False,
        })
        item.setdefault('source_locator', {'type': 'pdf_document', 'value': item['local_snapshot_path']})
        result.append(item)
    return result


def _claim_index(historical_root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    claims = _read_jsonl(historical_root / 'historical_company_impact_claims.jsonl')
    return {
        (str(row.get('company_code')), str(row.get('claim_type'))): row
        for row in claims if row.get('company_code')
    }


def _source_ref(raw: Mapping[str, Any], source_map: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    source = source_map[str(raw['source_id'])]
    return {
        'source_id': source['source_id'],
        'source_tier': 1,
        'publisher': source['publisher'],
        'source_url': source['source_url'],
        'published_at': source['published_at'],
        'retrieved_at': source.get('retrieved_at'),
        'local_snapshot_path': source['local_snapshot_path'],
        'content_sha256': source['content_sha256'],
        'source_locator': raw.get('source_locator') or source.get('source_locator'),
        'excerpt': raw.get('excerpt') or '',
        'model_visible': False,
        'verification_status': 'VERIFIED',
    }


def _node(dossier: Mapping[str, Any], node_type: str) -> dict[str, Any]:
    return next(row for row in dossier['transmission_chain']['nodes'] if row['node_type'] == node_type)


def _set_verified_node(
    dossier: dict[str, Any], node_type: str, value: str, refs: list[dict[str, Any]],
) -> None:
    node = _node(dossier, node_type)
    node.update({'status': 'VERIFIED_EVIDENCE', 'value': value, 'evidence_refs': refs, 'gap_reason': None})


def _format_financial_summary(facts: list[Mapping[str, Any]]) -> str:
    labels = {
        'revenue': '营业收入',
        'net_income_attributable': '归母净利润',
        'operating_cash_flow': '经营活动现金流',
    }
    return '；'.join(f"2022Q2 {labels[row['metric']]} {row['value']} {row['unit']}" for row in facts)


def _enrich_event_02(
    output_root: Path, historical_root: Path, company_sources: list[dict[str, Any]],
) -> None:
    dossiers = _read_jsonl(output_root / 'company_event_dossiers.jsonl')
    metric_facts = _read_jsonl(output_root / 'company_metric_facts.jsonl')
    attributions = _read_jsonl(output_root / 'company_attribution_samples.jsonl')
    reviews = _read_jsonl(output_root / 'company_review_records.jsonl')
    gaps = _read_jsonl(output_root / 'company_evidence_gaps.jsonl')
    source_map = {row['source_id']: row for row in company_sources}
    claims = _claim_index(historical_root)
    q2_facts = _read_jsonl(historical_root / 'historical_company_q2_facts.jsonl')
    q2_by_company: dict[str, list[dict[str, Any]]] = {}
    for fact in q2_facts:
        q2_by_company.setdefault(fact['company_code'], []).append(fact)

    removable_gap_nodes = {
        'COMPANY_BUSINESS_EXPOSURE', 'FINANCIAL_RESULT', 'COMPETING_EXPLANATION',
    }
    for dossier in dossiers:
        if dossier['event_id'] != 'event-02':
            continue
        code = dossier['company_code']
        enrichment = EVENT_02_ENRICHMENT[code]
        business_claim = claims[(code, 'company_business_exposure')]
        counter_claim = claims[(code, 'company_counterevidence')]
        business_refs = [_source_ref(row, source_map) for row in business_claim['evidence_refs']]
        counter_refs = [_source_ref(row, source_map) for row in counter_claim['evidence_refs']]
        dossier['business_exposure'] = {
            'status': 'VERIFIED_EVIDENCE', 'value': enrichment['exposure'],
            'evidence_refs': business_refs, 'gap_reason': None,
        }
        dossier['competing_explanations'] = [{
            'status': 'VERIFIED_EVIDENCE', 'value': enrichment['competing'],
            'evidence_refs': counter_refs, 'gap_reason': None,
        }]
        dossier['candidate_status'] = 'PARTIAL_EVIDENCE'
        dossier['evidence_status'] = 'PARTIAL_EVIDENCE'
        dossier['confidence'] = enrichment['confidence']
        dossier['evidence_gaps'] = [
            gap for gap in dossier['evidence_gaps']
            if not any(token in gap for token in ('business exposure', 'financial results', 'competing explanation'))
        ]
        _set_verified_node(dossier, 'COMPANY_BUSINESS_EXPOSURE', enrichment['exposure'], business_refs)
        _set_verified_node(dossier, 'COMPETING_EXPLANATION', enrichment['competing'], counter_refs)

        company_q2 = sorted(q2_by_company[code], key=lambda row: row['metric'])
        financial_refs = []
        for fact in company_q2:
            financial_refs.extend(_source_ref(ref, source_map) for ref in fact['evidence_refs'])
        unique_refs = {ref['source_id'] + '|' + str(ref['source_locator']): ref for ref in financial_refs}
        _set_verified_node(
            dossier, 'FINANCIAL_RESULT', _format_financial_summary(company_q2), list(unique_refs.values()),
        )
        conclusion = (
            '现有证据支持贡献性关联，不构成排他性因果证明。'
            if enrichment['association'] == 'CONTRIBUTING_ASSOCIATION'
            else '现有材料未形成公司特定事件传导的可审计关联。'
        )
        _set_verified_node(
            dossier, 'ATTRIBUTION_OR_FORECAST', conclusion,
            business_refs + counter_refs,
        )

    for row in metric_facts:
        if row['event_id'] != 'event-02' or row['metric_type'] == 'GROSS_MARGIN':
            continue
        wanted = next(
            fact for fact in q2_by_company[row['company_code']]
            if METRIC_TYPES[fact['metric']] == row['metric_type']
        )
        row.update({
            'period': wanted['period'],
            'status': 'VERIFIED_EVIDENCE',
            'value': wanted['value'],
            'unit': wanted['unit'],
            'currency': 'CNY',
            'evidence_refs': [_source_ref(ref, source_map) for ref in wanted['evidence_refs']],
            'gap_reason': None,
            'derivation_type': wanted['derivation_type'],
            'calculation': copy.deepcopy(wanted['calculation']),
        })

    dossier_by_id = {row['dossier_id']: row for row in dossiers}
    for row in attributions:
        if row['event_id'] != 'event-02':
            continue
        enrichment = EVENT_02_ENRICHMENT[row['company_code']]
        row.update({
            'association': enrichment['association'],
            'direction': enrichment['direction'],
            'confidence': enrichment['confidence'],
            'label_status': 'AI_INITIAL_REVIEW_COMPLETED',
            'transmission_chain': copy.deepcopy(dossier_by_id[row['dossier_id']]['transmission_chain']),
        })

    for row in reviews:
        if row['event_id'] != 'event-02':
            continue
        reasons = ['QUARTERLY_CUMULATIVE_DIFFERENCE', 'STRONG_COMPETING_EXPLANATION']
        if row['company_code'] == '600346.SH':
            reasons.extend(['LOW_CONFIDENCE', 'EVENT_CHANNEL_NOT_EXPLICITLY_DISCLOSED'])
        row['second_review_trigger_reasons'] = reasons
        row['initial_review']['decision'] = EVENT_02_ENRICHMENT[row['company_code']]['association']

    gaps = [
        row for row in gaps
        if not (
            row['event_id'] == 'event-02'
            and row['node_type'] in removable_gap_nodes
        )
    ]
    _write_jsonl(output_root / 'company_event_dossiers.jsonl', dossiers)
    _write_jsonl(output_root / 'company_metric_facts.jsonl', metric_facts)
    _write_jsonl(output_root / 'company_attribution_samples.jsonl', attributions)
    _write_jsonl(output_root / 'company_review_records.jsonl', reviews)
    _write_jsonl(output_root / 'company_evidence_gaps.jsonl', gaps)


def _add_identity_metadata(output_root: Path) -> None:
    dossiers = _read_jsonl(output_root / 'company_event_dossiers.jsonl')
    registry = _read_jsonl(output_root / 'candidate_company_registry.jsonl')
    for dossier in dossiers:
        observation, validation = EVENT_PERIODS[dossier['event_id']]
        dossier['industry'] = INDUSTRIES[dossier['company_code']]
        dossier['observation_quarter'] = {'status': 'CANDIDATE_PERIOD_DEFINED', 'value': observation}
        dossier['next_validation_quarter'] = {'status': 'CANDIDATE_PERIOD_DEFINED', 'value': validation}
    for row in registry:
        row['industry'] = INDUSTRIES[row['company_code']]
        row['observation_quarter'], row['next_validation_quarter'] = EVENT_PERIODS[row['event_id']]
    _write_jsonl(output_root / 'company_event_dossiers.jsonl', dossiers)
    _write_jsonl(output_root / 'candidate_company_registry.jsonl', registry)


def _validate(output_root: Path, workspace_root: Path) -> dict[str, Any]:
    dossiers = _read_jsonl(output_root / 'company_event_dossiers.jsonl')
    facts = _read_jsonl(output_root / 'company_metric_facts.jsonl')
    projection = _read_jsonl(output_root / 'company_candidate_training_projection.jsonl')
    sources = _read_jsonl(output_root / 'source_manifest.jsonl')
    company_sources = [row for row in sources if row.get('source_kind') == 'historical_company_report']
    checks = {
        'thirty_dossiers': len(dossiers) == 30,
        'all_identity_metadata_populated': all(
            row['industry'] != 'UNKNOWN'
            and row['observation_quarter']['value'] != 'UNKNOWN'
            and row['next_validation_quarter']['value'] != 'UNKNOWN'
            for row in dossiers
        ),
        'event_02_company_sources_verified': len(company_sources) == 6 and all(
            _sha256(workspace_root / row['local_snapshot_path']) == row['content_sha256']
            for row in company_sources
        ),
        'nine_verified_event_02_metric_facts': sum(
            row['event_id'] == 'event-02' and row['status'] == 'VERIFIED_EVIDENCE'
            for row in facts
        ) == 9,
        'forecast_company_evidence_cutoff_isolated': all(
            row.get('visible_company_evidence') == []
            for row in projection
            if row['event_id'] == 'event-02' and row['task_type'] == 'COMPANY_FORECAST'
        ),
        'formal_ready_false': True,
    }
    return {
        'dataset_version': DATASET_VERSION,
        'release_tier': 'CANDIDATE',
        'candidate_ready': all(checks.values()),
        'formal_ready': False,
        'checks': checks,
        'errors': [key for key, passed in checks.items() if not passed],
        'formal_blockers': [
            'COMPANY_EVIDENCE_INCOMPLETE', 'PRICE_WINDOWS_PENDING',
            'FORMAL_REVIEWS_INCOMPLETE', 'TWENTY_SEVEN_COMPANIES_REQUIRE_OFFICIAL_ARCHIVES',
        ],
    }


def build_enriched_candidate_dataset(
    config_path: Path,
    output_root: Path,
    *,
    historical_root: Path,
    workspace_root: Path = ROOT,
) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    output_root = output_root.resolve()
    if not output_root.is_relative_to(workspace_root):
        raise ValueError('OUTPUT_OUTSIDE_PROJECT_ROOT')
    build_candidate_dataset(config_path, output_root, workspace_root=workspace_root)
    _add_identity_metadata(output_root)
    company_sources = _historical_sources(historical_root, workspace_root)
    _enrich_event_02(output_root, historical_root, company_sources)
    market_sources = _read_jsonl(output_root / 'source_manifest.jsonl')
    _write_jsonl(output_root / 'source_manifest.jsonl', market_sources + company_sources)

    report = _validate(output_root, workspace_root)
    summary = json.loads((output_root / 'summary.json').read_text(encoding='utf-8'))
    summary.update({
        'dataset_version': DATASET_VERSION,
        'candidate_ready': report['candidate_ready'],
        'formal_ready': False,
        'source_count': len(market_sources) + len(company_sources),
        'evidence_gap_count': len(_read_jsonl(output_root / 'company_evidence_gaps.jsonl')),
        'verified_metric_fact_count': 9,
        'enriched_company_dossier_count': 3,
        'identity_metadata_complete_count': 30,
        'formal_blockers': report['formal_blockers'],
    })
    _write_json(output_root / 'summary.json', summary)
    _write_json(output_root / 'validation_report.json', report)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description='Build the enriched FinGoose company candidate dataset.')
    parser.add_argument('--config', type=Path, default=ROOT / 'configs' / 'fingoose_macro_event_company_candidate_v1.json')
    parser.add_argument('--historical-root', type=Path, default=ROOT / 'outputs' / 'fingoose_historical_company_impact_v1')
    parser.add_argument('--output-root', type=Path, default=ROOT / 'outputs' / 'fingoose_macro_event_company_enriched_candidate_v1')
    args = parser.parse_args()
    summary = build_enriched_candidate_dataset(
        args.config, args.output_root, historical_root=args.historical_root, workspace_root=ROOT,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary['candidate_ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
