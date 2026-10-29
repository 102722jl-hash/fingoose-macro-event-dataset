from __future__ import annotations

import copy
import json
import math
import statistics
from datetime import date, datetime
from numbers import Real
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parent
DATASET_VERSION = 'fingoose-macro-event-attribution-v1.0'
SCHEMA_PATHS = {
    'event_dossier': ROOT / 'schemas' / 'fingoose_macro_event_dossier_v1.schema.json',
    'market_window': ROOT / 'schemas' / 'fingoose_macro_market_window_v1.schema.json',
    'attribution_sample': ROOT / 'schemas' / 'fingoose_macro_attribution_sample_v1.schema.json',
    'review_record': ROOT / 'schemas' / 'fingoose_macro_review_record_v1.schema.json',
    'review_decision': ROOT / 'schemas' / 'fingoose_macro_review_decision_v1.schema.json',
}
WINDOW_ENDPOINTS = {'D1': 0, 'D3': 2, 'D5': 4, 'D20': 19, 'M3': 59}
REQUIRED_CHAIN_SEQUENCE = [
    'MACRO_REPORT',
    'DATA',
    'PERIOD_DESCRIPTION',
    'FACT_TRANSMISSION_CHAIN',
    'MULTI_DATA_TREND_CONFIRMATION',
    'SHORT_TERM_PREDICTION',
]
HIDDEN_PUBLIC_KEYS = {
    'hidden_outcome', 'hidden_forecast_outcome', 'actual_direction',
    'actual_label', 'verification_result', 'attribution', 'review_id',
    'reviewer_id', 'comments', 'initial_review', 'second_review',
    'adjudication',
}
PUBLIC_ATTRIBUTION_FIELDS = (
    'record_id', 'dataset_version', 'event_id', 'task_type',
    'target_series_ids', 'as_of_at', 'forecast_as_of_at',
    'visible_evidence_ids', 'market_window_ids', 'forecast_reasoning_chain',
)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def _numeric(value: Any) -> float:
    if not isinstance(value, Real) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError('FINITE_NUMERIC_VALUE_REQUIRED')
    return float(value)


def align_event_session(
    *, anchor_at: datetime, sessions: Sequence[date], market_close_hour: int = 16,
) -> dict[str, str]:
    ordered = sorted(set(sessions))
    if len(ordered) < 2:
        raise ValueError('AT_LEAST_TWO_SESSIONS_REQUIRED')
    local_day = anchor_at.date()
    same_day_is_tradable = local_day in ordered and anchor_at.hour < market_close_hour
    candidates = [session for session in ordered if session >= local_day] if same_day_is_tradable else [
        session for session in ordered if session > local_day
    ]
    if not candidates:
        raise ValueError('NO_TRADABLE_SESSION_AFTER_EVENT')
    t0 = candidates[0]
    t0_index = ordered.index(t0)
    if t0_index == 0:
        raise ValueError('BASELINE_SESSION_MISSING')
    return {'baseline_session': ordered[t0_index - 1].isoformat(), 't0_session': t0.isoformat()}


def _change(metric_type: str, start: float, end: float) -> float:
    if metric_type in {'price_return_pct', 'fx_return_pct'}:
        if start == 0:
            raise ValueError('ZERO_BASELINE_VALUE')
        return (end - start) / abs(start) * 100.0
    if metric_type == 'yield_basis_points':
        return (end - start) * 100.0
    raise ValueError('UNSUPPORTED_METRIC_TYPE:' + metric_type)


def compute_market_windows(
    *, observations: Iterable[Mapping[str, Any]], t0_session: str, metric_type: str,
) -> dict[str, Any]:
    indexed: dict[date, float] = {}
    for row in observations:
        try:
            indexed[_parse_date(str(row['date']))] = _numeric(row['value'])
        except (KeyError, TypeError, ValueError):
            continue
    ordered = sorted(indexed.items())
    dates = [day for day, _ in ordered]
    target_day = _parse_date(t0_session)
    if target_day not in dates:
        raise ValueError('T0_SESSION_NOT_FOUND')
    t0_index = dates.index(target_day)
    if t0_index == 0:
        raise ValueError('BASELINE_SESSION_MISSING')
    baseline_date, baseline_value = ordered[t0_index - 1]

    estimation_start = max(1, t0_index - 60)
    daily_changes = [
        _change(metric_type, ordered[index - 1][1], ordered[index][1])
        for index in range(estimation_start, t0_index)
    ]
    sigma = statistics.stdev(daily_changes) if len(daily_changes) >= 2 else 0.0
    windows: dict[str, Any] = {}
    for label, offset in WINDOW_ENDPOINTS.items():
        endpoint_index = t0_index + offset
        if endpoint_index >= len(ordered):
            windows[label] = None
            continue
        endpoint_date, endpoint_value = ordered[endpoint_index]
        change = _change(metric_type, baseline_value, endpoint_value)
        session_count = offset + 1
        abnormal_score = change / (sigma * math.sqrt(session_count)) if sigma > 0 else None
        windows[label] = {
            'end_date': endpoint_date.isoformat(),
            'end_value': round(endpoint_value, 10),
            'change': round(change, 6),
            'abnormal_score': round(abnormal_score, 6) if abnormal_score is not None else None,
        }
    return {
        'metric_type': metric_type,
        'change_unit': 'basis_points' if metric_type == 'yield_basis_points' else 'percent',
        'baseline': {'date': baseline_date.isoformat(), 'value': round(baseline_value, 10)},
        't0_session': target_day.isoformat(),
        'estimation': {
            'window': 'PREVIOUS_60_SESSIONS',
            'observation_count': len(daily_changes),
            'daily_change_stddev': round(sigma, 10),
        },
        'windows': windows,
    }


def build_forecast_reasoning_chain(
    *,
    forecast_as_of_at: str,
    report_evidence: Sequence[Mapping[str, Any]],
    period_description: Mapping[str, Any],
    transmission_nodes: Sequence[Mapping[str, Any]],
    transmission_edges: Sequence[Mapping[str, Any]],
    trend_confirmations: Sequence[Mapping[str, Any]],
    short_term_prediction: Mapping[str, Any],
) -> dict[str, Any]:
    cutoff = _parse_datetime(forecast_as_of_at)
    if not report_evidence:
        raise ValueError('MACRO_REPORT_EVIDENCE_REQUIRED')
    for evidence in report_evidence:
        published_at = _parse_datetime(str(evidence.get('published_at') or ''))
        if published_at > cutoff:
            raise ValueError('FUTURE_REPORT_EVIDENCE')
        if not evidence.get('evidence_id') or not evidence.get('summary'):
            raise ValueError('MACRO_REPORT_EVIDENCE_INCOMPLETE')
    if not all(period_description.get(key) for key in ('start_date', 'end_date', 'summary')):
        raise ValueError('PERIOD_DESCRIPTION_INCOMPLETE')
    node_ids = {str(node.get('node_id') or '') for node in transmission_nodes}
    node_types = {str(node.get('node_type') or '') for node in transmission_nodes}
    if '' in node_ids or not {'event', 'mechanism', 'market'} <= node_types:
        raise ValueError('FACT_TRANSMISSION_CHAIN_INCOMPLETE')
    if not transmission_edges or any(
        edge.get('from_node_id') not in node_ids or edge.get('to_node_id') not in node_ids
        for edge in transmission_edges
    ):
        raise ValueError('FACT_TRANSMISSION_EDGE_INVALID')
    confirmed_series = {str(row.get('series_id') or '') for row in trend_confirmations}
    if '' in confirmed_series or len(confirmed_series) < 2:
        raise ValueError('MULTI_DATA_CONFIRMATION_REQUIRED')
    prediction_required = {'target_series_id', 'horizon', 'direction', 'confidence', 'invalidation_conditions'}
    if prediction_required - set(short_term_prediction):
        raise ValueError('SHORT_TERM_PREDICTION_INCOMPLETE')
    if short_term_prediction.get('horizon') != 'D20':
        raise ValueError('SHORT_TERM_HORIZON_MUST_BE_D20')
    return {
        'sequence': list(REQUIRED_CHAIN_SEQUENCE),
        'forecast_as_of_at': forecast_as_of_at,
        'macro_report_evidence': [dict(row) for row in report_evidence],
        'data_cutoff': {'visible_windows': ['D1', 'D3'], 'hidden_outcome_window': 'D20'},
        'period_description': dict(period_description),
        'fact_transmission_chain': {
            'nodes': [dict(row) for row in transmission_nodes],
            'edges': [dict(row) for row in transmission_edges],
        },
        'trend_confirmation': {
            'series_count': len(confirmed_series),
            'items': [dict(row) for row in trend_confirmations],
        },
        'short_term_prediction': dict(short_term_prediction),
    }


def second_review_trigger_reasons(review: Mapping[str, Any]) -> list[str]:
    dimensions = review.get('core_dimensions')
    dimensions = dimensions if isinstance(dimensions, Mapping) else {}
    reasons: list[str] = []
    if review.get('confidence') == 'LOW':
        reasons.append('LOW_CONFIDENCE')
    if dimensions.get('competing_explanations') == 'STRONG':
        reasons.append('STRONG_COMPETING_EXPLANATION')
    if any(value == 'UNKNOWN' for value in dimensions.values()):
        reasons.append('CORE_DIMENSION_UNKNOWN')
    if any(value == 'CONTRADICTED' for value in dimensions.values()):
        reasons.append('CORE_DIMENSION_CONTRADICTED')
    return reasons


def review_errors(review: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    initial = review.get('initial_review')
    if not isinstance(initial, Mapping) or initial.get('status') != 'APPROVED':
        errors.append('INITIAL_REVIEW_REQUIRED')
    dimensions = review.get('core_dimensions')
    if not isinstance(dimensions, Mapping) or set(dimensions) != {
        'temporal_alignment', 'abnormal_movement', 'transmission_mechanism', 'competing_explanations',
    }:
        errors.append('CORE_DIMENSIONS_INVALID')
        dimensions = {}
    requires_second = bool(second_review_trigger_reasons(review))
    second = review.get('second_review')
    if requires_second and (not isinstance(second, Mapping) or second.get('status') != 'APPROVED'):
        errors.append('SECOND_REVIEW_REQUIRED')
    return errors


PLACEHOLDER_REVIEWER_IDS = {
    'PENDING_HUMAN', 'PENDING_SECOND_HUMAN', 'PENDING_ADJUDICATOR',
}


def _verdict_payload(verdict: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'label': verdict['label'],
        'confidence': verdict['confidence'],
        'core_dimensions': copy.deepcopy(verdict['core_dimensions']),
    }


def _verdicts_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return _verdict_payload(left) == _verdict_payload(right)


def _verdict_trigger_reasons(verdict: Mapping[str, Any]) -> list[str]:
    return second_review_trigger_reasons({
        'confidence': verdict['confidence'],
        'core_dimensions': verdict['core_dimensions'],
    })


def review_decision_errors(
    decision: Mapping[str, Any], expected_event_id: str, build_at: str,
) -> list[str]:
    if validate_schema_record('review_decision', decision):
        return ['REVIEW_DECISION_SCHEMA_INVALID']
    errors: list[str] = []
    if decision['event_id'] != expected_event_id:
        errors.append('REVIEW_EVENT_MISMATCH')
    build_time = _parse_datetime(build_at)
    verdicts = [
        decision['initial_review'], decision.get('second_review'), decision.get('adjudication'),
    ]
    for verdict in (row for row in verdicts if row is not None):
        if verdict['reviewer_id'] in PLACEHOLDER_REVIEWER_IDS:
            errors.append('INITIAL_REVIEWER_PLACEHOLDER')
        if _parse_datetime(verdict['reviewed_at']) > build_time:
            errors.append('REVIEWED_AT_IN_FUTURE')

    initial = decision['initial_review']
    second = decision.get('second_review')
    adjudication = decision.get('adjudication')
    requires_second = bool(_verdict_trigger_reasons(initial))
    if requires_second and second is None:
        errors.append('SECOND_REVIEW_REQUIRED')
    if second is not None and second['reviewer_id'] == initial['reviewer_id']:
        errors.append('SECOND_REVIEWER_NOT_INDEPENDENT')
    disagrees = second is not None and not _verdicts_equal(initial, second)
    if disagrees and adjudication is None:
        errors.append('ADJUDICATION_REQUIRED')
    if not disagrees and adjudication is not None:
        errors.append('UNNECESSARY_ADJUDICATION')
    if adjudication is not None and adjudication['reviewer_id'] in {
        initial['reviewer_id'], second['reviewer_id'] if second else '',
    }:
        errors.append('ADJUDICATOR_NOT_INDEPENDENT')
    return list(dict.fromkeys(errors))


def resolve_review_decision(
    decision: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    initial = decision['initial_review']
    second = decision.get('second_review')
    adjudication = decision.get('adjudication')
    final = adjudication or second or initial
    return copy.deepcopy(_verdict_payload(final)), _verdict_trigger_reasons(initial)


def _audit_review(verdict: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'reviewer_id': verdict['reviewer_id'],
        'status': 'APPROVED',
        'reviewed_at': verdict['reviewed_at'],
        'comments': verdict['comments'],
        **_verdict_payload(verdict),
    }


def apply_review_decision(
    base_review: Mapping[str, Any], decision: Mapping[str, Any],
) -> dict[str, Any]:
    final, trigger_reasons = resolve_review_decision(decision)
    merged = copy.deepcopy(dict(base_review))
    merged['initial_review'] = _audit_review(decision['initial_review'])
    merged['second_review'] = (
        _audit_review(decision['second_review']) if decision.get('second_review') else None
    )
    merged['adjudication'] = (
        _audit_review(decision['adjudication']) if decision.get('adjudication') else None
    )
    merged['second_review_trigger_reasons'] = trigger_reasons
    merged['final_label'] = final['label']
    merged['confidence'] = final['confidence']
    merged['core_dimensions'] = final['core_dimensions']
    return merged


def assert_public_projection_safe(value: Any) -> None:
    if isinstance(value, Mapping):
        forbidden = HIDDEN_PUBLIC_KEYS & set(value)
        if forbidden:
            raise ValueError('PUBLIC_HIDDEN_FIELD_LEAKAGE:' + ','.join(sorted(forbidden)))
        for item in value.values():
            assert_public_projection_safe(item)
    elif isinstance(value, list):
        for item in value:
            assert_public_projection_safe(item)


def build_public_attribution_projection(
    sample: Mapping[str, Any],
) -> dict[str, Any]:
    projection = {
        key: copy.deepcopy(sample[key])
        for key in PUBLIC_ATTRIBUTION_FIELDS
    }
    assert_public_projection_safe(projection)
    return projection


def validate_schema_record(record_type: str, record: Mapping[str, Any]) -> list[str]:
    try:
        schema_path = SCHEMA_PATHS[record_type]
    except KeyError as exc:
        raise ValueError('UNKNOWN_SCHEMA_RECORD_TYPE:' + record_type) from exc
    schema = json.loads(schema_path.read_text(encoding='utf-8'))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        'SCHEMA_INVALID:' + ('.'.join(str(part) for part in error.absolute_path) or '<root>') + ':' + error.message
        for error in sorted(validator.iter_errors(dict(record)), key=lambda item: str(item.absolute_path))
    ]

