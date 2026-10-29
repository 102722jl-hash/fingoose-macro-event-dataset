from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from fingoose_macro_event_attribution_v2 import (
    DATASET_VERSION,
    RELEASE_TIER,
    classify_confounder,
    compute_enhanced_market_window,
    normalize_expectation,
    stable_record_id,
    transmission_graph_errors,
    validate_schema_record,
)

WINDOW_LABELS = ('T60', 'T20', 'T1', 'D1', 'D3', 'D5', 'D20', 'M3')
EXAMPLE_EVENTS = {'event-02', 'event-03', 'event-04'}
TIER_MAP = {1: 'A', 2: 'B', 3: 'C', 4: 'D'}
EXPECTATION_TYPE = {
    'event-01': 'EVOLVING_EVENT',
    'event-02': 'UNSCHEDULED_SHOCK',
    'event-03': 'SCHEDULED_RELEASE',
    'event-04': 'EVOLVING_EVENT',
    'event-05': 'UNSCHEDULED_SHOCK',
    'event-06': 'UNSCHEDULED_SHOCK',
    'event-07': 'UNSCHEDULED_SHOCK',
    'event-08': 'SCHEDULED_RELEASE',
    'event-09': 'SCHEDULED_RELEASE',
    'event-10': 'SCHEDULED_RELEASE',
}
CONFOUNDER_BY_EVENT = {
    'event-01': 'DOMINANT',
    'event-02': 'MINOR',
    'event-03': 'MATERIAL',
    'event-04': 'MINOR',
    'event-05': 'MATERIAL',
    'event-06': 'MINOR',
    'event-07': 'MATERIAL',
    'event-08': 'UNRESOLVED',
    'event-09': 'MINOR',
    'event-10': 'DOMINANT',
}
EVENT_TITLE_ZH = {
    'event-01': '世卫组织将新冠疫情定性为全球大流行',
    'event-02': '俄罗斯对乌克兰发动全面进攻',
    'event-03': '美联储加息 75 个基点',
    'event-04': '中国发布优化疫情防控十条措施',
    'event-05': '硅谷银行关闭及监管部门稳定金融系统',
    'event-06': 'OPEC+ 成员宣布额外自愿减产',
    'event-07': '2023 年 10 月 7 日中东冲突升级',
    'event-08': '日本银行结束负利率政策',
    'event-09': '中国宣布一揽子金融支持政策',
    'event-10': '美国宣布广泛对等关税措施',
}
PILOT_FACTS = {
    ('event-02', 'event02-eia-steo'): 'EIA 在冲击前记录低库存与地缘紧张背景，供应中断风险的敏感度已较高。',
    ('event-02', 'event02-nato-statement'): 'NATO 首次公开确认俄罗斯对乌克兰发动大规模进攻；现有快照不支持把 03:00Z 作为已确认事实时刻。',
    ('event-03', 'event03-fomc'): 'FOMC 将联邦基金利率目标区间提高至 1.5%–1.75%，并表示将继续加息和缩表。',
    ('event-03', 'event03-mpr'): '6 月 17 日货币政策报告补充通胀和金融条件背景，只能作为主锚点后的验证证据。',
    ('event-04', 'event04-govcn'): '官方页面确认 2022-12-07 发布十条优化措施，但精确时刻未被现有快照证明；配置时间仅保留为 provisional。',
    ('event-04', 'event04-gz-briefing'): '次日发布的官方简报追述出行与活动变化，属于验证或次级节点。',
}
PILOT_DERIVED_MILESTONES = {
    'event-02': [{
        'source_id': 'event02-nato-statement',
        'phase': 'POLICY_RESPONSE',
        'fact': (
            'NATO \u540c\u4e00\u58f0\u660e\u8bb0\u5f55\u6210\u5458\u56fd\u5df2\u4f9d\u636e\u300a\u534e\u76db\u987f\u6761\u7ea6\u300b\u7b2c\u56db\u6761\u5b8c\u6210\u78cb\u5546\uff0c'
            '\u5e76\u51b3\u5b9a\u52a0\u5f3a\u8054\u76df\u5a01\u6151\u4e0e\u9632\u5fa1\u90e8\u7f72\u3002'
        ),
        'anchor_role': 'SECONDARY',
    }],
}
PHASE_ORDER = {
    'PRECONDITION': 0, 'INITIAL_SHOCK': 1, 'ESCALATION': 2,
    'POLICY_RESPONSE': 3, 'EASING': 4, 'SECONDARY_SHOCK': 5,
}
SECONDARY_ANCHOR_SERIES = {
    'event-02': {'VIXCLS', 'SP500'},
    'event-03': {'DGS10', 'DTWEXBGS'},
    'event-04': {'DCOILWTICO', 'DEXCHUS'},
}
BENCHMARK_SERIES = {
    'DCOILBRENTEU': 'DCOILWTICO',
    'DCOILWTICO': 'DCOILBRENTEU',
    'DEXCHUS': 'DTWEXBGS',
    'DEXJPUS': 'DTWEXBGS',
}



def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )


def _write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    rows = list(values)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows),
        encoding='utf-8',
    )


def _parse_at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _slug(value: str) -> str:
    result = re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')
    return result or 'unknown'


def _source_tier(source: dict[str, Any]) -> str:
    return TIER_MAP.get(int(source.get('tier', 4)), 'D')


def _source_ref(source: dict[str, Any]) -> dict[str, Any]:
    return {
        'evidence_id': source['source_id'],
        'source_tier': _source_tier(source),
        'published_at': source['published_at'],
        'sha256': source['content_sha256'],
    }


def _expectation(event_id: str) -> dict[str, Any]:
    event_type = EXPECTATION_TYPE[event_id]
    if event_type == 'EVOLVING_EVENT':
        baseline = {
            'event-01': '全球病例与传播范围在公告前持续扩大',
            'event-04': '防控措施已逐步优化，但开放速度和执行范围不确定',
        }[event_id]
        return normalize_expectation(event_type, qualitative_baseline=baseline)
    if event_id == 'event-03':
        return normalize_expectation(event_type, actual=75)
    return normalize_expectation(event_type)


def _event_cutoff(event_id: str, windows: list[dict[str, Any]], anchor_at: str) -> str:
    d3_dates = [
        row['windows']['D3']['end_date']
        for row in windows
        if row['event_id'] == event_id and row.get('windows', {}).get('D3')
    ]
    if not d3_dates:
        return _utc_iso(_parse_at(anchor_at))
    return datetime.fromisoformat(max(d3_dates) + 'T23:59:59+00:00').isoformat()


def _primary_source(event: dict[str, Any]) -> dict[str, Any]:
    event_fact = [source for source in event['sources'] if source.get('role') == 'event_fact']
    return (event_fact or event['sources'])[0]


def _milestone_phase(source_at: datetime, anchor_at: datetime, is_primary: bool, source: dict[str, Any]) -> str:
    if source_at < anchor_at and not is_primary:
        return 'PRECONDITION'
    if is_primary:
        return 'INITIAL_SHOCK'
    if source.get('role') in {'policy_response', 'official_response'}:
        return 'POLICY_RESPONSE'
    return 'ESCALATION'


def _build_milestones(
    events: list[dict[str, Any]],
    v1_windows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    milestones: list[dict[str, Any]] = []
    cutoffs: dict[str, str] = {}
    for event in events:
        event_id = event['event_id']
        anchor = _parse_at(event['anchor_at'])
        cutoff = _event_cutoff(event_id, v1_windows, event['anchor_at'])
        cutoffs[event_id] = cutoff
        primary = _primary_source(event)
        ordered_sources = sorted(event['sources'], key=lambda source: source['published_at'])
        for source in ordered_sources:
            is_primary = source['source_id'] == primary['source_id']
            source_at = _parse_at(source['published_at'])
            occurred_at = event['anchor_at'] if is_primary else source['published_at']
            if event_id == 'event-02' and is_primary:
                occurred_at = '2022-02-24T05:00:00+00:00'
            fact = PILOT_FACTS.get(
                (event_id, source['source_id']),
                source.get('summary') or EVENT_TITLE_ZH[event_id],
            )
            hidden = source_at > _parse_at(cutoff) or (
                event_id == 'event-03' and source['source_id'] == 'event03-mpr'
            )
            phase = _milestone_phase(source_at, anchor, is_primary, source)
            milestone_id = stable_record_id(
                'milestone', event_id, source['source_id'], occurred_at, phase,
            )
            milestones.append({
                'milestone_id': milestone_id,
                'dataset_version': DATASET_VERSION,
                'release_tier': RELEASE_TIER,
                'event_id': event_id,
                'occurred_at': occurred_at,
                'first_public_at': source['published_at'],
                'phase': phase,
                'fact': fact,
                'sources': [_source_ref(source)],
                'visibility': 'HIDDEN_VALIDATION' if hidden else 'PUBLIC_PREDICTION',
                'anchor_role': 'PRIMARY' if is_primary else (
                    'SECONDARY' if source_at >= anchor else 'NONE'
                ),
                'impact_tags': list(dict.fromkeys(event['candidate_channels'])),
                'expectation': _expectation(event_id),
            })
        source_by_id = {source['source_id']: source for source in event['sources']}
        for derived in PILOT_DERIVED_MILESTONES.get(event_id, []):
            source = source_by_id[derived['source_id']]
            occurred_at = source['published_at']
            phase = derived['phase']
            milestone_id = stable_record_id(
                'milestone', event_id, source['source_id'], occurred_at, phase,
            )
            milestones.append({
                'milestone_id': milestone_id,
                'dataset_version': DATASET_VERSION,
                'release_tier': RELEASE_TIER,
                'event_id': event_id,
                'occurred_at': occurred_at,
                'first_public_at': source['published_at'],
                'phase': phase,
                'fact': derived['fact'],
                'sources': [_source_ref(source)],
                'visibility': 'PUBLIC_PREDICTION',
                'anchor_role': derived['anchor_role'],
                'impact_tags': list(dict.fromkeys(event['candidate_channels'])),
                'expectation': _expectation(event_id),
            })
    milestones.sort(key=lambda row: (row['event_id'], row['occurred_at'], row['milestone_id']))
    return milestones, cutoffs


def _build_episodes(milestones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in milestones:
        grouped.setdefault((row['event_id'], row['phase']), []).append(row)

    episodes: list[dict[str, Any]] = []
    for (event_id, phase), phase_rows in sorted(
        grouped.items(),
        key=lambda item: (item[0][0], PHASE_ORDER[item[0][1]]),
    ):
        ordered = sorted(
            phase_rows, key=lambda row: (row['occurred_at'], row['milestone_id'])
        )
        milestone_ids = [row['milestone_id'] for row in ordered]
        evidence_coverage = list(dict.fromkeys(
            source['evidence_id']
            for row in ordered
            for source in row['sources']
        ))
        episodes.append({
            'episode_id': stable_record_id(
                'episode', event_id, phase, *milestone_ids,
            ),
            'dataset_version': DATASET_VERSION,
            'release_tier': RELEASE_TIER,
            'event_id': event_id,
            'phase': phase,
            'start_at': ordered[0]['occurred_at'],
            'end_at': ordered[-1]['occurred_at'],
            'milestone_ids': milestone_ids,
            'evidence_coverage': evidence_coverage,
        })
    return episodes


def _edge(
    *,
    edge_id: str,
    source_node: str,
    target_node: str,
    anchor_id: str,
    direction: str,
    evidence: dict[str, Any],
    invalidation: list[str],
    counterevidence: list[str],
    maximum_lag: str,
    confidence: float,
) -> dict[str, Any]:
    return {
        'edge_id': edge_id,
        'from_node_id': source_node,
        'to_node_id': target_node,
        'anchor_milestone_id': anchor_id,
        'expected_path': {
            'IMMEDIATE': direction,
            'SHORT_TERM': direction,
            'MEDIUM_TERM': 'UNKNOWN',
        },
        'lag': {'minimum': 'P0D', 'maximum': maximum_lag},
        'conditions': ['锚点事实未被官方更正，且该渠道在观测窗口内仍有效。'],
        'invalidation_conditions': invalidation or ['出现足以覆盖本渠道的反向政策或供需冲击。'],
        'evidence': [{
            'evidence_id': evidence['source_id'],
            'published_at': evidence['published_at'],
            'source_tier': _source_tier(evidence),
        }],
        'counterevidence': counterevidence,
        'status': 'PROPOSED',
        'confidence': confidence,
        'review': None,
    }


def _build_graphs(
    events: list[dict[str, Any]],
    milestones: list[dict[str, Any]],
    cutoffs: dict[str, str],
) -> list[dict[str, Any]]:
    by_event = {
        event_id: [row for row in milestones if row['event_id'] == event_id]
        for event_id in {row['event_id'] for row in milestones}
    }
    graphs = []
    for event in events:
        event_id = event['event_id']
        primary_milestone = next(
            row for row in by_event[event_id] if row['anchor_role'] == 'PRIMARY'
        )
        primary_source = _primary_source(event)
        secondary_milestone = next(
            (
                row for row in by_event[event_id]
                if row['anchor_role'] == 'SECONDARY'
            ),
            None,
        )
        source_by_id = {source['source_id']: source for source in event['sources']}
        shock_id = f'{event_id}-shock'
        nodes = [{'node_id': shock_id, 'layer': 'shock', 'label': EVENT_TITLE_ZH[event_id]}]
        edges: list[dict[str, Any]] = []
        channel_nodes: set[str] = set()
        for target in event['targets']:
            direction = target.get('expected_d3_direction', 'UNKNOWN')
            channel = (target.get('attribution', {}).get('channels') or event['candidate_channels'])[0]
            channel_id = f'{event_id}-channel-{_slug(channel)}'
            intermediate_id = f'{event_id}-intermediate-{_slug(target["series_id"])}'
            asset_id = f'{event_id}-asset-{_slug(target["series_id"])}'
            if channel_id not in channel_nodes:
                channel_nodes.add(channel_id)
                nodes.append({'node_id': channel_id, 'layer': 'channel', 'label': channel})
                edges.append(_edge(
                    edge_id=f'{event_id}-edge-shock-{_slug(channel)}',
                    source_node=shock_id,
                    target_node=channel_id,
                    anchor_id=primary_milestone['milestone_id'],
                    direction='MIXED',
                    evidence=primary_source,
                    invalidation=['官方来源撤回或实质修正锚点事实。'],
                    counterevidence=[],
                    maximum_lag='P1D',
                    confidence=0.6,
                ))
            nodes.extend([
                {
                    'node_id': intermediate_id,
                    'layer': 'intermediate',
                    'label': f'{target["series_name"]} 的事件专属定价变量',
                },
                {
                    'node_id': asset_id,
                    'layer': 'asset',
                    'label': target['series_name'],
                },
            ])
            invalidation = target.get('short_term_prediction', {}).get(
                'invalidation_conditions', []
            )
            counter = target.get('attribution', {}).get('counterevidence', [])
            branch_milestone = primary_milestone
            branch_source = primary_source
            if (
                secondary_milestone is not None
                and target['series_id'] in SECONDARY_ANCHOR_SERIES.get(event_id, set())
            ):
                branch_milestone = secondary_milestone
                evidence_id = secondary_milestone['sources'][0]['evidence_id']
                branch_source = source_by_id[evidence_id]
            edges.append(_edge(
                edge_id=f'{event_id}-edge-{_slug(channel)}-{_slug(target["series_id"])}',
                source_node=channel_id,
                target_node=intermediate_id,
                anchor_id=branch_milestone['milestone_id'],
                direction=direction,
                evidence=branch_source,
                invalidation=invalidation,
                counterevidence=counter,
                maximum_lag='P5D',
                confidence=0.5,
            ))
            confidence = {'HIGH': 0.7, 'MEDIUM': 0.55, 'LOW': 0.4}.get(
                target.get('short_term_prediction', {}).get('confidence'), 0.4,
            )
            edges.append(_edge(
                edge_id=f'{event_id}-edge-{_slug(target["series_id"])}-asset',
                source_node=intermediate_id,
                target_node=asset_id,
                anchor_id=branch_milestone['milestone_id'],
                direction=direction,
                evidence=branch_source,
                invalidation=invalidation,
                counterevidence=counter,
                maximum_lag='P20D',
                confidence=confidence,
            ))
        graphs.append({
            'graph_id': stable_record_id('graph', event_id, 'dynamic-transmission-v2'),
            'dataset_version': DATASET_VERSION,
            'release_tier': RELEASE_TIER,
            'event_id': event_id,
            'as_of_at': cutoffs[event_id],
            'milestone_ids': [row['milestone_id'] for row in by_event[event_id]],
            'nodes': nodes,
            'edges': edges,
        })
    return graphs


def _window_point(v1_point: dict[str, Any]) -> dict[str, Any]:
    return {
        'date': v1_point['end_date'],
        'value': v1_point['end_value'],
        'raw_change': v1_point.get('change'),
        'standardized_change': v1_point.get('abnormal_score'),
        'relative_change': None,
        'empirical_percentile': None,
    }


def _read_market_csv(path: Path, series_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if 'observation_date' not in (reader.fieldnames or []):
            raise ValueError('MARKET_DATE_COLUMN_MISSING:' + series_id)
        if series_id not in (reader.fieldnames or []):
            raise ValueError('MARKET_SERIES_COLUMN_MISSING:' + series_id)
        for row in reader:
            try:
                value = float(row[series_id])
            except (TypeError, ValueError):
                continue
            rows.append({'date': row['observation_date'], 'value': value})
    return rows


def _alignment_reason(event: dict[str, Any], t0_date: str) -> str:
    anchor = _parse_at(event['anchor_at']).astimezone(
        ZoneInfo(event['targets'][0].get('market_timezone') or 'UTC')
    )
    t0 = datetime.fromisoformat(t0_date).date()
    if t0 == anchor.date():
        cutoff = time(hour=int(event['targets'][0].get('market_close_hour', 23)))
        if anchor.timetz().replace(tzinfo=None) == cutoff:
            return 'AT_CUTOFF'
        return 'IN_SESSION' if anchor.timetz().replace(tzinfo=None) < cutoff else 'AFTER_CUTOFF'
    if anchor.weekday() >= 5:
        return 'NON_TRADING_DAY'
    return 'AFTER_CUTOFF'


def _build_windows(
    events: list[dict[str, Any]],
    v1_windows: list[dict[str, Any]],
    market_root: Path,
) -> list[dict[str, Any]]:
    event_map = {event['event_id']: event for event in events}
    metric_by_series = {
        target['series_id']: target['metric_type']
        for event in events
        for target in event['targets']
    }
    observations_by_series: dict[str, list[dict[str, Any]]] = {}
    source_by_series: dict[str, dict[str, Any]] = {}
    for source_row in v1_windows:
        series_id = source_row['series']['series_id']
        if series_id in observations_by_series:
            continue
        source_path = market_root / (series_id + '.csv')
        if not source_path.exists():
            raise ValueError('MARKET_SOURCE_MISSING:' + series_id)
        actual_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
        expected_sha256 = source_row['observation_source']['sha256']
        if actual_sha256 != expected_sha256:
            raise ValueError('MARKET_SOURCE_HASH_MISMATCH:' + series_id)
        observations_by_series[series_id] = _read_market_csv(source_path, series_id)
        source_by_series[series_id] = {
            'path': 'market/fred/' + source_path.name,
            'sha256': actual_sha256,
            'hash_verified': True,
        }
    output = []
    for row in v1_windows:
        event = event_map[row['event_id']]
        target = next(
            item for item in event['targets']
            if item['series_id'] == row['series']['series_id']
        )
        confounder = classify_confounder(CONFOUNDER_BY_EVENT[row['event_id']])
        series_id = target['series_id']
        benchmark_series_id = BENCHMARK_SERIES.get(series_id)
        computed = compute_enhanced_market_window(
            observations=observations_by_series[series_id],
            t0_session=row['t0_session'],
            metric_type=target['metric_type'],
            benchmark_observations=(
                observations_by_series.get(benchmark_series_id)
                if benchmark_series_id else None
            ),
            benchmark_metric_type=(
                metric_by_series.get(benchmark_series_id)
                if benchmark_series_id else None
            ),
        )
        baseline = computed['baseline']
        windows = computed['windows']
        digest = stable_record_id(
            'window', row['event_id'], target['series_id']
        ).rsplit('-', 1)[-1]
        output.append({
            'market_window_id': (
                f'window-{row["event_id"]}-{_slug(target["series_id"])}-{digest}'
            ),
            'dataset_version': DATASET_VERSION,
            'release_tier': RELEASE_TIER,
            'event_id': row['event_id'],
            'series_id': target['series_id'],
            'metric_type': target['metric_type'],
            'baseline': computed['baseline'],
            'estimation': computed['estimation'],
            'observation_source': source_by_series[series_id],
            'benchmark_series_id': benchmark_series_id,
            'timezone': target.get('market_timezone') or 'UTC',
            'calendar_id': f'FRED-{target["series_id"]}',
            'observation_cutoff': f'{int(target.get("market_close_hour", 23)):02d}:00:00',
            't0': {
                'date': row.get('t0_session'),
                'alignment_reason': _alignment_reason(event, row['t0_session']),
            },
            'windows': windows,
            'confounder_level': confounder['confounder_level'],
            'challenge_set': confounder['challenge_set'],
            'calculation_basis': (
                f'T-1={baseline["date"]} 的绝对值 {baseline["value"]}；'
                f'原始变化按 {target["metric_type"]} 从 T-1 到各端点复算；'
                '标准化变化=原始变化/(前 60 个交易日日变化标准差*sqrt(会话距离))；'
                '历史分位数使用事件前同长度安慰剂窗口。'
                f'原始快照 {source_by_series[series_id]["path"]}'
                f'（SHA-256 {source_by_series[series_id]["sha256"]}，已核验）。'
                + (
                    f'相对变化基准为预先指定的 {benchmark_series_id}。'
                    if benchmark_series_id
                    else '未指定可比基准，相对变化保持 null。'
                )
            ),
        })
    return output


def _build_benchmarks(
    events: list[dict[str, Any]],
    milestones: list[dict[str, Any]],
    graphs: list[dict[str, Any]],
    windows: list[dict[str, Any]],
    cutoffs: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases = []
    labels = []
    graph_map = {row['event_id']: row for row in graphs}
    for event in events:
        event_id = event['event_id']
        event_milestones = [row for row in milestones if row['event_id'] == event_id]
        visible_evidence_ids = list(dict.fromkeys(
            source['evidence_id']
            for row in event_milestones
            if row['visibility'] == 'PUBLIC_PREDICTION'
            and _parse_at(row['first_public_at']) <= _parse_at(cutoffs[event_id])
            for source in row['sources']
        ))
        event_windows = [row for row in windows if row['event_id'] == event_id]
        challenge = any(row['challenge_set'] for row in event_windows)
        unresolved = any(
            row['confounder_level'] == 'UNRESOLVED' for row in event_windows
        )
        score_eligible = not challenge and not unresolved
        case_id = stable_record_id('case', event_id, 'three-track-benchmark')
        split = (
            'EXAMPLE'
            if event_id in EXAMPLE_EVENTS
            else ('CHALLENGE' if challenge else 'HIDDEN_EVALUATION')
        )
        cases.append({
            'case_id': case_id,
            'dataset_version': DATASET_VERSION,
            'release_tier': RELEASE_TIER,
            'event_id': event_id,
            'forecast_cutoff_at': cutoffs[event_id],
            'tasks': [
                'TIMELINE_RECONSTRUCTION',
                'GRAPH_CONSTRUCTION',
                'DIRECTION',
                'ABSTENTION',
            ],
            'visible_evidence_ids': visible_evidence_ids,
            'visible_market_windows': (
                ['T60', 'T20', 'T1', 'D1', 'D3']
                if split == 'EXAMPLE' else ['T60', 'T20', 'T1']
            ),
            'split': split,
            'challenge_set': challenge,
            'score_eligible': score_eligible,
        })
        d3_changes = [
            row['windows']['D3']['raw_change']
            for row in event_windows
            if row['windows']['D3'] and row['windows']['D3']['raw_change'] is not None
        ]
        direction = 'UNKNOWN'
        if d3_changes:
            positive = sum(value > 0 for value in d3_changes)
            negative = sum(value < 0 for value in d3_changes)
            direction = 'UP' if positive and not negative else (
                'DOWN' if negative and not positive else 'MIXED'
            )
        challenge = any(row['challenge_set'] for row in event_windows)
        unresolved = any(row['confounder_level'] == 'UNRESOLVED' for row in event_windows)
        labels.append({
            'label_id': stable_record_id('label', event_id, case_id),
            'dataset_version': DATASET_VERSION,
            'release_tier': RELEASE_TIER,
            'case_id': case_id,
            'event_id': event_id,
            'hidden': True,
            'timeline_labels': [row['milestone_id'] for row in event_milestones],
            'graph_edge_labels': [edge['edge_id'] for edge in graph_map[event_id]['edges']],
            'direction_label': direction,
            'abstention_label': challenge or unresolved,
            'verification_windows': ['D5', 'D20', 'M3'],
        })
    return cases, labels


def _source_manifest(
    events: list[dict[str, Any]],
    evidence_root: Path,
) -> list[dict[str, Any]]:
    hash_paths: dict[str, str] = {}
    source_root = evidence_root / 'sources'
    if source_root.exists():
        for path in source_root.iterdir():
            if path.is_file():
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                hash_paths[digest] = path.relative_to(evidence_root).as_posix()
    rows = []
    for event in events:
        for source in event['sources']:
            digest = source['content_sha256']
            rows.append({
                'event_id': event['event_id'],
                'evidence_id': source['source_id'],
                'source_tier': _source_tier(source),
                'publisher': source.get('publisher'),
                'title': source.get('title'),
                'published_at': source['published_at'],
                'source_url': source.get('source_url'),
                'sha256': digest,
                'snapshot_path': hash_paths.get(digest),
                'snapshot_status': 'VERIFIED' if digest in hash_paths else 'NOT_PACKAGED',
            })
    return rows


def _cross_record_errors(
    milestones: list[dict[str, Any]],
    episodes: list[dict[str, Any]],
    graphs: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    milestone_event: dict[str, str] = {}
    for row in milestones:
        milestone_id = row['milestone_id']
        if milestone_id in milestone_event:
            errors.append('DUPLICATE_MILESTONE_ID:' + milestone_id)
        milestone_event[milestone_id] = row['event_id']
    for episode in episodes:
        for milestone_id in episode['milestone_ids']:
            owner = milestone_event.get(milestone_id)
            if owner is None:
                errors.append(
                    'EPISODE_MILESTONE_UNKNOWN:' + episode['episode_id']
                    + ':' + milestone_id
                )
            elif owner != episode['event_id']:
                errors.append(
                    'EPISODE_MILESTONE_EVENT_MISMATCH:' + episode['episode_id']
                    + ':' + milestone_id
                )
    for graph in graphs:
        directory = set(graph.get('milestone_ids', []))
        for milestone_id in directory:
            owner = milestone_event.get(milestone_id)
            if owner is None:
                errors.append('GRAPH_MILESTONE_UNKNOWN:' + graph['graph_id'])
            elif owner != graph['event_id']:
                errors.append('GRAPH_MILESTONE_EVENT_MISMATCH:' + graph['graph_id'])
        for edge in graph.get('edges', []):
            if edge.get('anchor_milestone_id') not in directory:
                errors.append('GRAPH_EDGE_ANCHOR_OUTSIDE_DIRECTORY:' + edge['edge_id'])
    return errors


def _public_projection_errors(
    cases: list[dict[str, Any]],
    milestones: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    for case in cases:
        event_id = case['event_id']
        cutoff = _parse_at(case['forecast_cutoff_at'])
        if 'visible_milestone_ids' in case:
            errors.append('VISIBLE_GOLD_MILESTONE_IDS:' + event_id)
        if case['split'] != 'EXAMPLE':
            leaked_windows = {'D1', 'D3', 'D5', 'D20', 'M3'} & set(
                case.get('visible_market_windows', [])
            )
            if leaked_windows:
                errors.append(
                    'POST_EVENT_WINDOWS:' + event_id + ':'
                    + ','.join(sorted(leaked_windows))
                )
        known_evidence = {
            source['evidence_id']
            for row in milestones
            if row['event_id'] == event_id
            and row['visibility'] == 'PUBLIC_PREDICTION'
            and _parse_at(row['first_public_at']) <= cutoff
            for source in row['sources']
        }
        unknown = set(case.get('visible_evidence_ids', [])) - known_evidence
        if unknown:
            errors.append(
                'NONPUBLIC_EVIDENCE:' + event_id + ':'
                + ','.join(sorted(unknown))
            )
    return errors


def _record_count(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding='utf-8').splitlines() if line.strip())


def build_dataset(
    *,
    config_path: Path,
    v1_market_root: Path,
    evidence_root: Path,
    output_root: Path,
    generated_at: str | None = None,
    release_manifest_path: Path | None = None,
) -> dict[str, Any]:
    build_timestamp = generated_at or datetime.now(timezone.utc).isoformat()
    config = json.loads(config_path.read_text(encoding='utf-8'))
    events = config['events']
    v1_windows = _read_jsonl(v1_market_root / 'market_windows.jsonl')

    milestones, cutoffs = _build_milestones(events, v1_windows)
    episodes = _build_episodes(milestones)
    graphs = _build_graphs(events, milestones, cutoffs)
    market_windows = _build_windows(
        events, v1_windows, evidence_root / 'market' / 'fred',
    )
    cases, labels = _build_benchmarks(
        events, milestones, graphs, market_windows, cutoffs,
    )
    sources = _source_manifest(events, evidence_root)

    outputs = {
        'event_milestones.jsonl': milestones,
        'event_episodes.jsonl': episodes,
        'transmission_graphs.jsonl': graphs,
        'market_windows.jsonl': market_windows,
        'benchmark_cases.jsonl': cases,
        'hidden/benchmark_labels.jsonl': labels,
        'source_manifest.jsonl': sources,
    }
    for relative, records in outputs.items():
        _write_jsonl(output_root / relative, records)

    schema_mapping = {
        'milestone': milestones,
        'episode': episodes,
        'transmission_graph': graphs,
        'market_window': market_windows,
        'benchmark_case': cases,
        'benchmark_label': labels,
    }
    schema_errors = {
        record_type: [
            {'id': next(iter(record.values())), 'errors': errors}
            for record in records
            if (errors := validate_schema_record(record_type, record))
        ]
        for record_type, records in schema_mapping.items()
    }
    graph_errors = {
        graph['event_id']: errors
        for graph in graphs
        if (errors := transmission_graph_errors(graph))
    }
    cross_record_errors = _cross_record_errors(milestones, episodes, graphs)
    public_projection_errors = _public_projection_errors(cases, milestones)
    non_recomputable_window = any(
        not row['observation_source']['hash_verified']
        or row['estimation']['observation_count'] < 2
        for row in market_windows
    )
    hard_failures = {
        'schema_invalid': any(schema_errors.values()),
        'cross_record_invalid': bool(cross_record_errors),
        'graph_invalid': bool(graph_errors),
        'public_hidden_leakage': bool(public_projection_errors),
        'fabricated_source': any(
            row['snapshot_status'] == 'NOT_PACKAGED' for row in sources
        ),
        'non_recomputable_window': non_recomputable_window,
    }
    validation_report = {
        'dataset_version': DATASET_VERSION,
        'release_tier': RELEASE_TIER,
        'valid': not any(hard_failures.values()),
        'hard_failures': hard_failures,
        'schema_errors': schema_errors,
        'graph_errors': graph_errors,
        'cross_record_errors': cross_record_errors,
        'public_projection_errors': public_projection_errors,
        'scoring_tracks': {
            'timeline_reconstruction': {'aggregate_score': None, 'status': 'READY'},
            'transmission_graph': {'aggregate_score': None, 'status': 'READY'},
            'direction_and_abstention': {'aggregate_score': None, 'status': 'READY'},
        },
        'notes': [
            '三个赛道独立记录，不生成综合总分。',
            '原始 FRED 快照已按 SHA-256 核验，并用于重算八窗口、标准化变化和历史分位数。',
            '所有传导边均为 AI 生成的 PROPOSED 候选，尚未完成人工确认。',
        ],
    }
    _write_json(output_root / 'validation_report.json', validation_report)

    summary = {
        'dataset_version': DATASET_VERSION,
        'release_tier': RELEASE_TIER,
        'candidate_ready': validation_report['valid'],
        'formal_ready': False,
        'event_count': len(events),
        'example_event_count': len(EXAMPLE_EVENTS),
        'hidden_evaluation_event_count': sum(
            case['split'] == 'HIDDEN_EVALUATION' for case in cases
        ),
        'challenge_case_count': sum(case['split'] == 'CHALLENGE' for case in cases),
        'milestone_count': len(milestones),
        'episode_count': len(episodes),
        'transmission_graph_count': len(graphs),
        'market_window_count': len(market_windows),
        'benchmark_case_count': len(cases),
        'hidden_label_count': len(labels),
        'challenge_event_count': len({
            row['event_id'] for row in market_windows if row['challenge_set']
        }),
        'release_decision': 'CANDIDATE_REVIEW_REQUIRED',
    }
    _write_json(output_root / 'summary.json', summary)

    manifest_files = []
    for path in sorted(output_root.rglob('*')):
        if path.is_file() and path.name != 'manifest.json':
            manifest_files.append({
                'path': path.relative_to(output_root).as_posix(),
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'record_count': _record_count(path),
            })
    manifest = {
        'dataset_version': DATASET_VERSION,
        'release_tier': RELEASE_TIER,
        'schema_version': '2020-12',
        'generated_at': build_timestamp,
        'files': manifest_files,
        'counts': {
            'events': len(events),
            'milestones': len(milestones),
            'episodes': len(episodes),
            'graphs': len(graphs),
            'windows': len(market_windows),
            'cases': len(cases),
            'labels': len(labels),
        },
    }
    _write_json(output_root / 'manifest.json', manifest)
    package_root = config_path.parent.parent
    release_paths = [
        'README_V2.md',
        'START_UI_V2.ps1',
        'code/fingoose_macro_event_attribution_v2.py',
        'code/build_fingoose_macro_event_attribution_v2.py',
        'code/fingoose_macro_event_v2_dashboard.py',
        'code/fingoose_macro_event_v2_dashboard.html',
        'code/fingoose_macro_event_v2_dashboard.css',
        'code/fingoose_macro_event_v2_dashboard.js',
        'schemas/fingoose_macro_event_milestone_v2.schema.json',
        'schemas/fingoose_macro_event_episode_v2.schema.json',
        'schemas/fingoose_macro_transmission_graph_v2.schema.json',
        'schemas/fingoose_macro_market_window_v2.schema.json',
        'schemas/fingoose_macro_benchmark_case_v2.schema.json',
        'schemas/fingoose_macro_benchmark_label_v2.schema.json',
        'tests/test_fingoose_macro_event_attribution_v2.py',
        'tests/test_build_fingoose_macro_event_attribution_v2.py',
        'tests/test_fingoose_macro_event_v2_dashboard.py',
        'data/market_event_attribution_v2_candidate/manifest.json',
    ]
    release_files = []
    for relative in release_paths:
        path = package_root / relative
        if not path.is_file():
            raise ValueError('V2_RELEASE_ASSET_MISSING:' + relative)
        release_files.append({
            'path': relative,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'size_bytes': path.stat().st_size,
        })
    _write_json(release_manifest_path or package_root / 'V2_RELEASE_MANIFEST.json', {
        'dataset_version': DATASET_VERSION,
        'release_tier': RELEASE_TIER,
        'formal_ready': False,
        'generated_at': build_timestamp,
        'files': release_files,
    })
    return summary


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description='Build FinGoose macro attribution v2 candidate')
    parser.add_argument(
        '--config-path',
        type=Path,
        default=root / 'configs' / 'fingoose_macro_events_v1.json',
    )
    parser.add_argument(
        '--v1-market-root',
        type=Path,
        default=root / 'data' / 'market_event_attribution_v1',
    )
    parser.add_argument(
        '--evidence-root',
        type=Path,
        default=root / 'evidence_snapshots' / 'macro_event_attribution_v1',
    )
    parser.add_argument(
        '--output-root',
        type=Path,
        default=root / 'data' / 'market_event_attribution_v2_candidate',
    )
    parser.add_argument('--generated-at')
    parser.add_argument('--release-manifest-path', type=Path)
    args = parser.parse_args()
    summary = build_dataset(
        config_path=args.config_path,
        v1_market_root=args.v1_market_root,
        evidence_root=args.evidence_root,
        output_root=args.output_root,
        generated_at=args.generated_at,
        release_manifest_path=args.release_manifest_path,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
