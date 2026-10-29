from __future__ import annotations

import copy
import hashlib
import json
import math
import statistics
from datetime import date, datetime, time
from numbers import Real
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator, FormatChecker


DATASET_VERSION = 'fingoose-macro-event-attribution-v2.0'
RELEASE_TIER = 'CANDIDATE'
ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATHS = {
    'milestone': ROOT / 'schemas' / 'fingoose_macro_event_milestone_v2.schema.json',
    'episode': ROOT / 'schemas' / 'fingoose_macro_event_episode_v2.schema.json',
    'transmission_graph': ROOT / 'schemas' / 'fingoose_macro_transmission_graph_v2.schema.json',
    'market_window': ROOT / 'schemas' / 'fingoose_macro_market_window_v2.schema.json',
    'benchmark_case': ROOT / 'schemas' / 'fingoose_macro_benchmark_case_v2.schema.json',
    'benchmark_label': ROOT / 'schemas' / 'fingoose_macro_benchmark_label_v2.schema.json',
}
EXPECTATION_TYPES = {'SCHEDULED_RELEASE', 'UNSCHEDULED_SHOCK', 'EVOLVING_EVENT'}
CONFOUNDER_LEVELS = {'CLEAN', 'MINOR', 'MATERIAL', 'DOMINANT', 'UNRESOLVED'}
WINDOW_OFFSETS = {
    'T60': -60,
    'T20': -20,
    'T1': -1,
    'D1': 0,
    'D3': 2,
    'D5': 4,
    'D20': 19,
    'M3': 59,
}
LAYER_ORDER = {'shock': 0, 'channel': 1, 'intermediate': 2, 'asset': 3}
EDGE_HORIZONS = {'IMMEDIATE', 'SHORT_TERM', 'MEDIUM_TERM'}
HIDDEN_PUBLIC_KEYS = {
    'labels', 'label', 'label_id', 'benchmark_label', 'benchmark_labels',
    'direction_label', 'abstention_label', 'timeline_labels', 'graph_edge_labels',
    'hidden', 'hidden_outcome', 'hidden_label', 'verification_result',
    'verification_windows', 'actual_direction', 'actual_label',
}
LATE_WINDOWS = {'D5', 'D20', 'M3'}


def _parse_datetime(value: str | datetime) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('TIMEZONE_AWARE_DATETIME_REQUIRED')
    return parsed


def _parse_date(value: str | date) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def stable_record_id(record_type: str, event_id: str, *identity_parts: Any) -> str:
    kind = str(record_type).strip().lower().replace('_', '-')
    if not kind or any(character not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for character in kind):
        raise ValueError('INVALID_RECORD_TYPE')
    if not str(event_id).startswith('event-'):
        raise ValueError('INVALID_EVENT_ID')
    identity = json.dumps(
        [DATASET_VERSION, kind, event_id, *identity_parts],
        ensure_ascii=True,
        sort_keys=True,
        separators=(',', ':'),
        default=str,
    ).encode('utf-8')
    return f'{kind}-{event_id}-{hashlib.sha256(identity).hexdigest()[:12]}'


def normalize_expectation(
    expectation_type: str,
    *,
    consensus: Any = None,
    actual: Any = None,
    qualitative_baseline: str | None = None,
) -> dict[str, Any]:
    if expectation_type not in EXPECTATION_TYPES:
        raise ValueError('UNKNOWN_EXPECTATION_TYPE:' + str(expectation_type))
    if expectation_type == 'UNSCHEDULED_SHOCK':
        return {
            'type': expectation_type,
            'consensus': 'UNKNOWN',
            'actual': 'UNKNOWN',
            'surprise': 'UNKNOWN',
        }
    if expectation_type == 'EVOLVING_EVENT':
        return {
            'type': expectation_type,
            'qualitative_baseline': qualitative_baseline or 'UNKNOWN',
            'consensus': 'UNKNOWN',
            'actual': 'UNKNOWN',
            'surprise': 'UNKNOWN',
        }
    known_consensus = _finite_number(consensus)
    known_actual = _finite_number(actual)
    return {
        'type': expectation_type,
        'consensus': known_consensus if known_consensus is not None else 'UNKNOWN',
        'actual': known_actual if known_actual is not None else 'UNKNOWN',
        'surprise': (
            known_actual - known_consensus
            if known_actual is not None and known_consensus is not None
            else 'UNKNOWN'
        ),
    }


def align_series_t0(
    *,
    anchor_at: str | datetime,
    timezone_name: str,
    sessions: Sequence[str | date],
    observation_cutoff: str,
    calendar_id: str,
) -> dict[str, Any]:
    zone = ZoneInfo(timezone_name)
    local_anchor = _parse_datetime(anchor_at).astimezone(zone)
    cutoff = time.fromisoformat(observation_cutoff)
    if cutoff.tzinfo is not None:
        raise ValueError('LOCAL_OBSERVATION_CUTOFF_REQUIRED')
    ordered = sorted(set(_parse_date(session) for session in sessions))
    local_day = local_anchor.date()
    if local_day not in ordered:
        candidates = [session for session in ordered if session > local_day]
        reason = 'NON_TRADING_DAY'
    elif local_anchor.timetz().replace(tzinfo=None) >= cutoff:
        candidates = [session for session in ordered if session > local_day]
        reason = (
            'AT_CUTOFF'
            if local_anchor.timetz().replace(tzinfo=None) == cutoff
            else 'AFTER_CUTOFF'
        )
    else:
        candidates = [local_day]
        reason = 'IN_SESSION'
    t0 = candidates[0] if candidates else None
    prior = [session for session in ordered if t0 is not None and session < t0]
    return {
        'timezone': timezone_name,
        'calendar_id': calendar_id,
        'observation_cutoff': observation_cutoff,
        'anchor_local_at': local_anchor.isoformat(),
        'baseline_session': prior[-1].isoformat() if prior else None,
        't0_session': t0.isoformat() if t0 else None,
        'alignment_reason': reason if t0 else 'NO_FUTURE_SESSION',
    }


def _metric_change(metric_type: str, start: float, end: float) -> float:
    if metric_type in {'price_return_pct', 'fx_return_pct'}:
        if start == 0:
            raise ValueError('ZERO_BASELINE_VALUE')
        return (end - start) / abs(start) * 100.0
    if metric_type == 'yield_basis_points':
        return (end - start) * 100.0
    if metric_type == 'absolute_change':
        return end - start
    raise ValueError('UNSUPPORTED_METRIC_TYPE:' + metric_type)


def _indexed_observations(observations: Iterable[Mapping[str, Any]]) -> list[tuple[date, float]]:
    indexed: dict[date, float] = {}
    for row in observations:
        try:
            value = _finite_number(row.get('value'))
            if value is not None:
                indexed[_parse_date(str(row['date']))] = value
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(indexed.items())


def _empirical_percentile(
    ordered: Sequence[tuple[date, float]],
    end_index: int,
    horizon: int,
    actual_change: float,
    metric_type: str,
) -> float | None:
    distance = abs(horizon)
    if distance == 0:
        return None
    placebo: list[float] = []
    for index in range(distance, end_index):
        try:
            placebo.append(_metric_change(metric_type, ordered[index - distance][1], ordered[index][1]))
        except ValueError:
            continue
    if len(placebo) < 20:
        return None
    rank = sum(value <= actual_change for value in placebo)
    return rank / len(placebo)


def compute_enhanced_market_window(
    *,
    observations: Iterable[Mapping[str, Any]],
    t0_session: str,
    metric_type: str,
    benchmark_observations: Iterable[Mapping[str, Any]] | None = None,
    benchmark_metric_type: str | None = None,
) -> dict[str, Any]:
    ordered = _indexed_observations(observations)
    dates = [day for day, _ in ordered]
    t0_day = _parse_date(t0_session)
    if t0_day not in dates:
        raise ValueError('T0_SESSION_NOT_FOUND')
    t0_index = dates.index(t0_day)
    if t0_index == 0:
        raise ValueError('BASELINE_SESSION_MISSING')
    baseline_index = t0_index - 1
    baseline_day, baseline_value = ordered[baseline_index]
    daily_changes: list[float] = []
    for index in range(max(1, t0_index - 60), t0_index):
        try:
            daily_changes.append(_metric_change(metric_type, ordered[index - 1][1], ordered[index][1]))
        except ValueError:
            continue
    sigma = statistics.stdev(daily_changes) if len(daily_changes) >= 2 else None
    benchmark_index = dict(_indexed_observations(benchmark_observations or []))
    benchmark_type = benchmark_metric_type or metric_type
    benchmark_baseline = benchmark_index.get(baseline_day)

    windows: dict[str, dict[str, Any] | None] = {}
    for label, offset in WINDOW_OFFSETS.items():
        endpoint_index = t0_index + offset
        if endpoint_index < 0 or endpoint_index >= len(ordered):
            windows[label] = None
            continue
        endpoint_day, endpoint_value = ordered[endpoint_index]
        raw_change = _metric_change(metric_type, baseline_value, endpoint_value)
        session_distance = abs(endpoint_index - baseline_index)
        standardized = (
            raw_change / (sigma * math.sqrt(session_distance))
            if sigma and session_distance > 0
            else (0.0 if sigma and session_distance == 0 else None)
        )
        relative = None
        benchmark_endpoint = benchmark_index.get(endpoint_day)
        if benchmark_baseline is not None and benchmark_endpoint is not None:
            try:
                relative = raw_change - _metric_change(
                    benchmark_type, benchmark_baseline, benchmark_endpoint,
                )
            except ValueError:
                relative = None
        chronological_horizon = endpoint_index - baseline_index
        percentile = _empirical_percentile(
            ordered, t0_index, chronological_horizon, raw_change, metric_type,
        )
        windows[label] = {
            'date': endpoint_day.isoformat(),
            'value': round(endpoint_value, 10),
            'raw_change': round(raw_change, 10),
            'standardized_change': round(standardized, 10) if standardized is not None else None,
            'relative_change': round(relative, 10) if relative is not None else None,
            'empirical_percentile': round(percentile, 10) if percentile is not None else None,
        }
    return {
        'metric_type': metric_type,
        'baseline': {'date': baseline_day.isoformat(), 'value': round(baseline_value, 10)},
        't0_session': t0_day.isoformat(),
        'estimation': {
            'window': 'PREVIOUS_60_SESSIONS',
            'observation_count': len(daily_changes),
            'daily_change_stddev': round(sigma, 10) if sigma is not None else None,
        },
        'windows': windows,
    }


def classify_confounder(level: str) -> dict[str, Any]:
    if level not in CONFOUNDER_LEVELS:
        raise ValueError('UNKNOWN_CONFOUNDER_LEVEL:' + str(level))
    challenge = level in {'MATERIAL', 'DOMINANT'}
    return {
        'confounder_level': level,
        'challenge_set': challenge,
        'eligible_for_clean_attribution_score': level not in {'MATERIAL', 'DOMINANT', 'UNRESOLVED'},
    }


def _edge_has_required_details(edge: Mapping[str, Any]) -> bool:
    expected_path = edge.get('expected_path')
    lag = edge.get('lag')
    return (
        bool(edge.get('anchor_milestone_id'))
        and isinstance(expected_path, Mapping)
        and set(expected_path) == EDGE_HORIZONS
        and isinstance(lag, Mapping)
        and bool(lag.get('minimum'))
        and bool(lag.get('maximum'))
        and bool(edge.get('conditions'))
        and bool(edge.get('invalidation_conditions'))
        and bool(edge.get('evidence'))
        and isinstance(edge.get('counterevidence'), list)
        and edge.get('status') in {'PROPOSED', 'CONFIRMED', 'REJECTED'}
        and _finite_number(edge.get('confidence')) is not None
    )


def _has_cycle(node_ids: set[str], adjacency: Mapping[str, set[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in visiting:
            return True
        if node_id in visited:
            return False
        visiting.add(node_id)
        if any(visit(target) for target in adjacency.get(node_id, set())):
            return True
        visiting.remove(node_id)
        visited.add(node_id)
        return False

    return any(visit(node_id) for node_id in node_ids)


def transmission_graph_errors(graph: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    nodes = graph.get('nodes') if isinstance(graph.get('nodes'), list) else []
    edges = graph.get('edges') if isinstance(graph.get('edges'), list) else []
    node_layers = {str(node.get('node_id')): node.get('layer') for node in nodes if node.get('node_id')}
    node_ids = set(node_layers)
    if set(node_layers.values()) != set(LAYER_ORDER):
        errors.append('GRAPH_LAYERS_INCOMPLETE')
    degree = {node_id: 0 for node_id in node_ids}
    adjacency = {node_id: set() for node_id in node_ids}
    cutoff = _parse_datetime(str(graph.get('as_of_at'))) if graph.get('as_of_at') else None
    known_anchors = set(graph.get('milestone_ids') or [])
    if not known_anchors:
        errors.append('GRAPH_MILESTONE_DIRECTORY_REQUIRED')
    for edge in edges:
        edge_id = str(edge.get('edge_id') or '<unknown>')
        source = str(edge.get('from_node_id') or '')
        target = str(edge.get('to_node_id') or '')
        if source not in node_ids or target not in node_ids:
            errors.append('EDGE_NODE_UNKNOWN:' + edge_id)
            continue
        degree[source] += 1
        degree[target] += 1
        adjacency[source].add(target)
        source_layer = node_layers[source]
        target_layer = node_layers[target]
        if source_layer not in LAYER_ORDER or target_layer not in LAYER_ORDER or (
            LAYER_ORDER[target_layer] != LAYER_ORDER[source_layer] + 1
        ):
            errors.append('EDGE_LAYER_ORDER_INVALID:' + edge_id)
        if not _edge_has_required_details(edge):
            errors.append('EDGE_DETAILS_INCOMPLETE:' + edge_id)
        anchor_id = edge.get('anchor_milestone_id')
        if known_anchors and anchor_id not in known_anchors:
            errors.append('EDGE_ANCHOR_UNKNOWN:' + edge_id)
        for evidence in edge.get('evidence') or []:
            try:
                if cutoff and _parse_datetime(str(evidence.get('published_at'))) > cutoff:
                    errors.append('FUTURE_EVIDENCE:' + edge_id)
                    break
            except (TypeError, ValueError):
                errors.append('EVIDENCE_TIMESTAMP_INVALID:' + edge_id)
                break
        if edge.get('status') == 'CONFIRMED':
            review = edge.get('review')
            if not isinstance(review, Mapping) or review.get('decision') != 'CONFIRMED':
                errors.append('CONFIRMED_EDGE_REVIEW_REQUIRED:' + edge_id)
    for node_id, count in degree.items():
        if count == 0:
            errors.append('ORPHAN_NODE:' + node_id)
    if _has_cycle(node_ids, adjacency):
        errors.append('GRAPH_CYCLE')
    return list(dict.fromkeys(errors))


def assert_public_projection_safe(value: Any) -> None:
    if isinstance(value, Mapping):
        if value.get('visibility') == 'HIDDEN_VALIDATION':
            raise ValueError('PUBLIC_HIDDEN_VISIBILITY_LEAKAGE')

        forbidden = HIDDEN_PUBLIC_KEYS & set(value)
        if forbidden:
            raise ValueError('PUBLIC_HIDDEN_FIELD_LEAKAGE:' + ','.join(sorted(forbidden)))
        late = LATE_WINDOWS & set(value)
        if late:
            raise ValueError('PUBLIC_LATE_WINDOW_LEAKAGE:' + ','.join(sorted(late)))
        for key, item in value.items():
            if key in {'visible_market_windows', 'windows'} and isinstance(item, list):
                leaked = LATE_WINDOWS & set(item)
                if leaked:
                    raise ValueError('PUBLIC_LATE_WINDOW_LEAKAGE:' + ','.join(sorted(leaked)))
            assert_public_projection_safe(item)
    elif isinstance(value, list):
        for item in value:
            assert_public_projection_safe(item)


def _public_copy(value: Any, cutoff: datetime) -> Any:
    if isinstance(value, Mapping):
        if value.get('visibility') == 'HIDDEN_VALIDATION':
            return None
        published_value = value.get('published_at') or value.get('first_public_at')
        if published_value:
            try:
                if _parse_datetime(str(published_value)) > cutoff:
                    return None
            except ValueError:
                return None
        result: dict[str, Any] = {}
        for key, item in value.items():
            if key in HIDDEN_PUBLIC_KEYS or key in LATE_WINDOWS:
                continue
            if key == 'windows' and isinstance(item, Mapping):
                item = {window: point for window, point in item.items() if window not in LATE_WINDOWS}
            if key == 'visible_market_windows' and isinstance(item, list):
                item = [window for window in item if window not in LATE_WINDOWS]
            public_item = _public_copy(item, cutoff)
            if public_item is not None:
                result[key] = public_item
        return result or None
    if isinstance(value, list):
        return [item for raw in value if (item := _public_copy(raw, cutoff)) is not None]
    return copy.deepcopy(value)


def build_public_projection(record: Mapping[str, Any]) -> dict[str, Any]:
    if not record.get('forecast_cutoff_at'):
        raise ValueError('FORECAST_CUTOFF_REQUIRED')
    cutoff = _parse_datetime(str(record['forecast_cutoff_at']))
    projection = _public_copy(record, cutoff)
    if not isinstance(projection, dict):
        raise ValueError('PUBLIC_PROJECTION_EMPTY')
    assert_public_projection_safe(projection)
    return projection


def validate_schema_record(record_type: str, record: Mapping[str, Any]) -> list[str]:
    try:
        schema_path = SCHEMA_PATHS[record_type]
    except KeyError as exc:
        raise ValueError('UNKNOWN_SCHEMA_RECORD_TYPE:' + str(record_type)) from exc
    schema = json.loads(schema_path.read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        'SCHEMA_INVALID:'
        + ('.'.join(str(part) for part in error.absolute_path) or '<root>')
        + ':'
        + error.message
        for error in sorted(validator.iter_errors(dict(record)), key=lambda item: str(item.absolute_path))
    ]
