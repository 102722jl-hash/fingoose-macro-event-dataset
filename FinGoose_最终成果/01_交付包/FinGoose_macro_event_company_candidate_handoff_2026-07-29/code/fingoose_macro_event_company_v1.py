from __future__ import annotations

import copy
import math
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from numbers import Real
from typing import Any, Iterable, Mapping


COMPANY_DATASET_VERSION = 'fingoose-macro-event-company-v1.0'
COMPANY_WINDOW_ENDPOINTS = {'D1': 1, 'D3': 3, 'D5': 5, 'D20': 20}


def _decimal_value(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError('FINITE_DECIMAL_VALUE_REQUIRED')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('FINITE_DECIMAL_VALUE_REQUIRED') from exc
    if not result.is_finite():
        raise ValueError('FINITE_DECIMAL_VALUE_REQUIRED')
    return result


def _period_quarter(period: Any) -> tuple[int, int]:
    normalized = str(period or '').strip().upper().replace('-', '').replace('_', '')
    match = re.fullmatch(r'(\d{4})(Q[1-4]|H1|S1|9M|FY|ANNUAL)(?:CUMULATIVE|YTD)?', normalized)
    if not match:
        raise ValueError('PERIOD_INVALID')
    year = int(match.group(1))
    quarter = {'Q1': 1, 'Q2': 2, 'H1': 2, 'S1': 2, 'Q3': 3, '9M': 3,
               'Q4': 4, 'FY': 4, 'ANNUAL': 4}[match.group(2)]
    return year, quarter


def _ensure_matching(
    left: Mapping[str, Any], right: Mapping[str, Any], fields: Iterable[str], prefix: str,
) -> None:
    for field in fields:
        if not left.get(field) or not right.get(field):
            raise ValueError(f'{prefix}_{field.upper()}_REQUIRED')
        if left[field] != right[field]:
            raise ValueError(f'{prefix}_{field.upper()}_MISMATCH')


def _decimal_text(value: Decimal) -> str:
    return format(value, 'f')


def _json_number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)


def derive_standalone_quarter(
    current_cumulative: Mapping[str, Any], prior_cumulative: Mapping[str, Any],
) -> dict[str, Any]:
    _ensure_matching(
        current_cumulative, prior_cumulative,
        ('company_code', 'metric', 'unit', 'currency'), 'CUMULATIVE_FACT',
    )
    current_year, current_quarter = _period_quarter(current_cumulative.get('period'))
    prior_year, prior_quarter = _period_quarter(prior_cumulative.get('period'))
    if current_year != prior_year or current_quarter != prior_quarter + 1:
        raise ValueError('CUMULATIVE_FACT_PERIOD_MISMATCH')
    current_value = _decimal_value(current_cumulative.get('value_decimal', current_cumulative.get('value')))
    prior_value = _decimal_value(prior_cumulative.get('value_decimal', prior_cumulative.get('value')))
    result = current_value - prior_value
    evidence_refs = copy.deepcopy(list(current_cumulative.get('evidence_refs') or []))
    evidence_refs.extend(copy.deepcopy(list(prior_cumulative.get('evidence_refs') or [])))
    return {
        'company_code': str(current_cumulative['company_code']),
        'metric': str(current_cumulative['metric']),
        'unit': str(current_cumulative['unit']),
        'currency': str(current_cumulative['currency']),
        'period': f'{current_year}Q{current_quarter}',
        'value': _json_number(result),
        'value_decimal': _decimal_text(result),
        'derivation_type': 'CUMULATIVE_DIFFERENCE',
        'calculation': {
            'formula': 'current_cumulative - prior_cumulative',
            'current_cumulative_value_decimal': _decimal_text(current_value),
            'prior_cumulative_value_decimal': _decimal_text(prior_value),
            'result_decimal': _decimal_text(result),
        },
        'evidence_refs': evidence_refs,
    }


def calculate_period_comparison(
    current: Mapping[str, Any], comparison: Mapping[str, Any],
) -> dict[str, Any]:
    _ensure_matching(
        current, comparison, ('company_code', 'metric', 'unit', 'currency'), 'COMPARISON_FACT',
    )
    current_year, current_quarter = _period_quarter(current.get('period'))
    comparison_year, comparison_quarter = _period_quarter(comparison.get('period'))
    if comparison_quarter == current_quarter and comparison_year == current_year - 1:
        comparison_type = 'YOY'
    elif (
        (comparison_year == current_year and comparison_quarter == current_quarter - 1)
        or (current_quarter == 1 and comparison_quarter == 4 and comparison_year == current_year - 1)
    ):
        comparison_type = 'QOQ'
    else:
        raise ValueError('COMPARISON_PERIOD_INCOMPATIBLE')
    current_value = _decimal_value(current.get('value_decimal', current.get('value')))
    comparison_value = _decimal_value(comparison.get('value_decimal', comparison.get('value')))
    base = {
        'company_code': str(current['company_code']),
        'metric': str(current['metric']),
        'unit': str(current['unit']),
        'currency': str(current['currency']),
        'current_period': str(current['period']),
        'comparison_period': str(comparison['period']),
        'comparison_type': comparison_type,
        'formula': '(current - comparison) / abs(comparison) * 100',
    }
    if comparison_value == 0:
        return {**base, 'computable': False, 'change_pct': None,
                'change_pct_decimal': None, 'reason': 'ZERO_COMPARISON_BASE'}
    change = (current_value - comparison_value) / abs(comparison_value) * Decimal('100')
    return {**base, 'computable': True, 'change_pct': float(change),
            'change_pct_decimal': _decimal_text(change), 'reason': None}


def _valid_observations(observations: Iterable[Mapping[str, Any]]) -> dict[date, float]:
    indexed: dict[date, float] = {}
    for row in observations:
        try:
            day = date.fromisoformat(str(row['date']))
            raw = row.get('value', row.get('close'))
            if isinstance(raw, bool) or not isinstance(raw, (str, Real, Decimal)):
                continue
            value = float(raw)
            if not math.isfinite(value) or value <= 0:
                continue
        except (KeyError, TypeError, ValueError):
            continue
        indexed[day] = value
    return indexed


def _return_pct(baseline: float, endpoint: float) -> float:
    return (endpoint / baseline - 1.0) * 100.0


def compute_company_stock_window(
    company_observations: Iterable[Mapping[str, Any]],
    benchmark_observations: Iterable[Mapping[str, Any]],
    t0_session: str,
) -> dict[str, Any]:
    company = _valid_observations(company_observations)
    benchmark = _valid_observations(benchmark_observations)
    t0 = date.fromisoformat(t0_session)
    common_baselines = sorted(day for day in company.keys() & benchmark.keys() if day < t0)
    if not common_baselines:
        raise ValueError('COMMON_BASELINE_SESSION_MISSING')
    baseline_day = common_baselines[-1]
    company_baseline = company[baseline_day]
    benchmark_baseline = benchmark[baseline_day]
    company_sessions = sorted(day for day in company if day >= t0)
    windows: dict[str, Any] = {}
    for label, session_count in COMPANY_WINDOW_ENDPOINTS.items():
        if len(company_sessions) < session_count:
            windows[label] = None
            continue
        endpoint_day = company_sessions[session_count - 1]
        benchmark_endpoint = benchmark.get(endpoint_day)
        if benchmark_endpoint is None:
            windows[label] = None
            continue
        company_return = _return_pct(company_baseline, company[endpoint_day])
        benchmark_return = _return_pct(benchmark_baseline, benchmark_endpoint)
        windows[label] = {
            'end_date': endpoint_day.isoformat(),
            'company_close': company[endpoint_day],
            'benchmark_close': benchmark_endpoint,
            'company_return_pct': company_return,
            'benchmark_return_pct': benchmark_return,
            'csi300_return_pct': benchmark_return,
            'relative_abnormal_return_pct': company_return - benchmark_return,
            'company_trading_session_count': session_count,
        }
    return {
        't0_session': t0.isoformat(),
        'baseline': {
            'date': baseline_day.isoformat(),
            'company_close': company_baseline,
            'benchmark_close': benchmark_baseline,
            'csi300_close': benchmark_baseline,
        },
        'benchmark': 'CSI300',
        'window_basis': 'COMPANY_TRADING_SESSIONS',
        'windows': windows,
    }

COMPANY_SCHEMA_FILES = {
    'event_dossier': 'fingoose_company_event_dossier_v1.schema.json',
    'metric_fact': 'fingoose_company_metric_fact_v1.schema.json',
    'stock_window': 'fingoose_company_stock_window_v1.schema.json',
    'attribution_sample': 'fingoose_company_attribution_sample_v1.schema.json',
    'forecast_sample': 'fingoose_company_forecast_sample_v1.schema.json',
    'review_record': 'fingoose_company_review_record_v1.schema.json',
}


def validate_schema_record(record_type: str, record: Mapping[str, Any]) -> list[str]:
    import json
    from pathlib import Path
    from jsonschema import Draft202012Validator, FormatChecker

    try:
        filename = COMPANY_SCHEMA_FILES[record_type]
    except KeyError as exc:
        raise ValueError('UNKNOWN_COMPANY_SCHEMA_RECORD_TYPE:' + str(record_type)) from exc
    path = Path(__file__).resolve().parent / 'schemas' / filename
    schema = json.loads(path.read_text(encoding='utf-8'))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        'SCHEMA_INVALID:' + ('.'.join(str(part) for part in error.absolute_path) or '<root>') + ':' + error.message
        for error in sorted(validator.iter_errors(dict(record)), key=lambda item: str(item.absolute_path))
    ]


def company_second_review_trigger_reasons(review: Mapping[str, Any]) -> list[str]:
    dimensions = review.get('core_dimensions')
    dimensions = dimensions if isinstance(dimensions, Mapping) else {}
    reasons: list[str] = []
    if review.get('confidence') == 'LOW':
        reasons.append('LOW_CONFIDENCE')
    if any(value == 'UNKNOWN' for value in dimensions.values()):
        reasons.append('CORE_DIMENSION_UNKNOWN')
    if any(value == 'CONTRADICTED' for value in dimensions.values()):
        reasons.append('CORE_DIMENSION_CONTRADICTED')
    if dimensions.get('competing_explanations') == 'STRONG' or review.get('competing_explanation_strength') == 'STRONG':
        reasons.append('STRONG_COMPETING_EXPLANATION')
    if any(review.get(key) is True for key in ('quarter_differencing_used', 'standalone_quarter_derived', 'quarter_difference_used')):
        reasons.append('QUARTER_DIFFERENCING')
    if review.get('event_channel_explicitly_disclosed') is not True:
        reasons.append('EVENT_CHANNEL_NOT_EXPLICITLY_DISCLOSED')
    leakage = review.get('leakage_anomalies', review.get('leakage_findings', []))
    if leakage or review.get('leakage_anomaly') is True:
        reasons.append('LEAKAGE_ANOMALY')
    return reasons


def _company_verdict_payload(verdict: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'label': verdict.get('label'),
        'confidence': verdict.get('confidence'),
        'core_dimensions': copy.deepcopy(verdict.get('core_dimensions')),
    }


def _company_verdicts_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return _company_verdict_payload(left) == _company_verdict_payload(right)


def company_review_errors(review: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    initial = review.get('initial_review')
    if not isinstance(initial, Mapping) or initial.get('status') != 'APPROVED':
        errors.append('INITIAL_REVIEW_REQUIRED')
        initial = {}
    elif not str(initial.get('reviewer_id') or '').strip():
        errors.append('INITIAL_REVIEWER_REQUIRED')

    second = review.get('second_review')
    requires_second = bool(company_second_review_trigger_reasons(review))
    if requires_second and (not isinstance(second, Mapping) or second.get('status') != 'APPROVED'):
        errors.append('SECOND_REVIEW_REQUIRED')
    if isinstance(second, Mapping):
        if second.get('status') != 'APPROVED':
            errors.append('SECOND_REVIEW_INCOMPLETE')
        if second.get('reviewer_id') == initial.get('reviewer_id'):
            errors.append('SECOND_REVIEWER_NOT_INDEPENDENT')

    disagrees = isinstance(second, Mapping) and bool(initial) and not _company_verdicts_equal(initial, second)
    adjudication = review.get('adjudication')
    if disagrees and (not isinstance(adjudication, Mapping) or adjudication.get('status') != 'APPROVED'):
        errors.append('ADJUDICATION_REQUIRED')
    if isinstance(adjudication, Mapping):
        if adjudication.get('status') != 'APPROVED':
            errors.append('ADJUDICATION_INCOMPLETE')
        reviewer_id = adjudication.get('reviewer_id')
        if reviewer_id in {initial.get('reviewer_id'), second.get('reviewer_id') if isinstance(second, Mapping) else None}:
            errors.append('ADJUDICATOR_NOT_INDEPENDENT')
        if not disagrees:
            errors.append('UNNECESSARY_ADJUDICATION')
    return list(dict.fromkeys(errors))


def resolve_company_review(review: Mapping[str, Any]) -> dict[str, Any]:
    errors = company_review_errors(review)
    if errors:
        raise ValueError('COMPANY_REVIEW_INVALID:' + ','.join(errors))
    final = review.get('adjudication') or review.get('second_review') or review['initial_review']
    return _company_verdict_payload(final)


def resolve_company_review_decision(review: Mapping[str, Any]) -> dict[str, Any]:
    return resolve_company_review(review)
_CUTOFF_SNAPSHOT_KINDS = {
    'INDEPENDENT_CUTOFF_SNAPSHOT', 'independent_cutoff_snapshot', 'CUTOFF_SNAPSHOT',
}
_FORECAST_FORBIDDEN_KEYS = {
    'actual', 'actual_value', 'actual_values', 'actual_direction', 'actual_label',
    'hidden_outcome', 'hidden_outcomes', 'outcome', 'outcome_evidence', 'verification_result',
    'attribution', 'retrospective_attribution', 'association', 'association_label',
    'future_source_id', 'future_source_ids', 'future_report', 'future_reports',
    'next_quarter', 'next_quarter_result', 'next_quarter_results',
    'post_event_dossier', 'review', 'review_id', 'review_record',
}
_FORECAST_PUBLIC_FIELDS = {
    'record_id', 'dataset_version', 'event_id', 'company_code', 'company_name',
    'forecast_as_of_at', 'event_materials', 'industry_materials', 'company_materials',
    'stock_windows', 'visible_windows', 'forecast_labels', 'transmission_chain',
    'instruction', 'counterevidence', 'reasoning_summary', 'observation_quarter',
}


def _parse_projection_datetime(value: Any):
    from datetime import datetime, timezone

    text = str(value or '').strip()
    if not text:
        raise ValueError('FORECAST_DATETIME_REQUIRED')
    try:
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('FORECAST_DATETIME_INVALID') from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _assert_cutoff_tree_safe(value: Any, cutoff: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key)
            normalized = key.strip().lower().replace('-', '_')
            if (normalized in _FORECAST_FORBIDDEN_KEYS or normalized in {'d5', 'd20'}
                    or normalized.startswith(('actual_', 'future_', 'retrospective_', 'post_event_'))
                    or 'next_quarter' in normalized):
                raise ValueError('COMPANY_FORECAST_LEAKAGE:' + '.'.join(path + (key,)))
            if normalized in {'published_at', 'announcement_at', 'available_at', 'retrieved_at'}:
                if _parse_projection_datetime(item) > cutoff:
                    raise ValueError('FUTURE_COMPANY_FORECAST_EVIDENCE:' + '.'.join(path + (key,)))
            if normalized == 'source_id':
                source_id = str(item).lower().replace('_', '-')
                if 'future' in source_id or 'next-quarter' in source_id:
                    raise ValueError('FUTURE_SOURCE_ID_LEAKAGE:' + str(item))
            if normalized == 'report_type':
                report_type = str(item).lower().replace('-', '_')
                if 'future' in report_type or 'next_quarter' in report_type:
                    raise ValueError('FUTURE_REPORT_LEAKAGE:' + str(item))
            _assert_cutoff_tree_safe(item, cutoff, path + (key,))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_cutoff_tree_safe(item, cutoff, path + (str(index),))
    elif isinstance(value, str) and value.upper() in {'D5', 'D20'}:
        raise ValueError('COMPANY_FORECAST_LEAKAGE:' + '.'.join(path))


def _material_errors(snapshot: Mapping[str, Any], cutoff: Any) -> list[str]:
    errors: list[str] = []
    for field in ('event_materials', 'industry_materials', 'company_materials'):
        materials = snapshot.get(field)
        if not isinstance(materials, (list, tuple)) or not materials:
            errors.append(field.upper() + '_REQUIRED')
            continue
        for material in materials:
            if not isinstance(material, Mapping) or not material.get('source_id') or not material.get('published_at'):
                errors.append(field.upper() + '_INCOMPLETE')
                continue
            if _parse_projection_datetime(material['published_at']) > cutoff:
                errors.append('FUTURE_' + field.upper())
    return errors


def build_company_forecast_projection(cutoff_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(cutoff_snapshot, Mapping):
        raise ValueError('INDEPENDENT_CUTOFF_SNAPSHOT_REQUIRED')
    independent = cutoff_snapshot.get('independent_cutoff_snapshot') is True
    kind = cutoff_snapshot.get('snapshot_kind', cutoff_snapshot.get('snapshot_type'))
    if not independent and kind not in _CUTOFF_SNAPSHOT_KINDS:
        raise ValueError('INDEPENDENT_CUTOFF_SNAPSHOT_REQUIRED')
    cutoff = _parse_projection_datetime(cutoff_snapshot.get('forecast_as_of_at'))
    _assert_cutoff_tree_safe(cutoff_snapshot, cutoff)
    material_errors = _material_errors(cutoff_snapshot, cutoff)
    if material_errors:
        raise ValueError('CUTOFF_SNAPSHOT_INVALID:' + ','.join(material_errors))
    visible_windows = cutoff_snapshot.get('visible_windows')
    stock_windows = cutoff_snapshot.get('stock_windows')
    if visible_windows != ['D1', 'D3']:
        raise ValueError('VISIBLE_WINDOWS_MUST_BE_D1_D3')
    if not isinstance(stock_windows, Mapping) or set(stock_windows) != {'D1', 'D3'}:
        raise ValueError('STOCK_WINDOWS_MUST_BE_D1_D3')
    projection = {
        key: copy.deepcopy(cutoff_snapshot[key])
        for key in _FORECAST_PUBLIC_FIELDS if key in cutoff_snapshot
    }
    projection['projection_source'] = 'INDEPENDENT_CUTOFF_SNAPSHOT'
    return projection


def _release_collection(records: Mapping[str, Any], *names: str) -> list[Any]:
    for name in names:
        value = records.get(name)
        if value is not None:
            return list(value) if isinstance(value, (list, tuple)) else []
    return []


def _public_release_leakage(value: Any, path: tuple[str, ...] = ()) -> list[str]:
    findings: list[str] = []
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            key = str(raw_key)
            normalized = key.strip().lower().replace('-', '_')
            if (normalized in _FORECAST_FORBIDDEN_KEYS or normalized in {'d5', 'd20'}
                    or normalized.startswith(('actual_', 'future_', 'retrospective_', 'post_event_'))
                    or 'next_quarter' in normalized):
                findings.append('PUBLIC_LEAKAGE:' + '.'.join(path + (key,)))
            findings.extend(_public_release_leakage(item, path + (key,)))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            findings.extend(_public_release_leakage(item, path + (str(index),)))
    elif isinstance(value, str) and value.upper() in {'D5', 'D20'}:
        findings.append('PUBLIC_LEAKAGE:' + '.'.join(path))
    return findings


def _expected_release_counts(
    pilot_mode: bool, expected_counts: Mapping[str, Any] | None,
) -> dict[str, int]:
    defaults = {'dossiers': 9, 'attribution_samples': 9, 'forecast_samples': 9, 'samples': 18} if pilot_mode else {
        'dossiers': 30, 'attribution_samples': 30, 'forecast_samples': 30, 'samples': 60,
    }
    if not expected_counts:
        return defaults
    aliases = {
        'dossiers': ('dossiers', 'dossier_count'),
        'attribution_samples': ('attribution_samples', 'attribution_sample_count'),
        'forecast_samples': ('forecast_samples', 'forecast_sample_count'),
        'samples': ('samples', 'sample_count', 'public_sample_count'),
    }
    result = dict(defaults)
    for target, names in aliases.items():
        for name in names:
            if name in expected_counts:
                result[target] = int(expected_counts[name])
                break
    return result


def validate_company_release(
    records: Mapping[str, Any], pilot_mode: bool | None = None,
    expected_counts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(records, Mapping):
        raise ValueError('COMPANY_RELEASE_RECORDS_MAPPING_REQUIRED')
    dossiers = _release_collection(records, 'dossiers', 'company_event_dossiers')
    attribution = _release_collection(records, 'attribution_samples', 'company_attribution_samples')
    forecasts = _release_collection(records, 'forecast_samples', 'company_forecast_samples')
    reviews = _release_collection(records, 'review_records', 'company_review_records')
    projection = _release_collection(records, 'training_projection', 'company_training_projection')
    configured_counts = expected_counts or (records.get('expected_counts') if isinstance(records.get('expected_counts'), Mapping) else None)
    if pilot_mode is None:
        pilot_mode = bool(records.get('pilot_mode', (configured_counts or {}).get('dossiers', len(dossiers)) == 9))
    expected = _expected_release_counts(bool(pilot_mode), configured_counts)

    sample_count = len(attribution) + len(forecasts)
    count_ok = (
        len(dossiers) == expected['dossiers']
        and len(attribution) == expected['attribution_samples']
        and len(forecasts) == expected['forecast_samples']
        and sample_count == expected['samples']
        and len(projection) == expected['samples']
    )
    review_error_map = {
        str(review.get('review_id', index)): company_review_errors(review)
        for index, review in enumerate(reviews)
        if isinstance(review, Mapping) and company_review_errors(review)
    }
    reviews_ok = len(reviews) == expected['dossiers'] and not review_error_map
    explicit_leakage = list(records.get('leakage_findings') or [])
    detected_leakage = _public_release_leakage(projection)
    leakage_ok = not explicit_leakage and not detected_leakage
    rejected = list(records.get('rejected') or records.get('rejections') or [])
    rejection_ok = not rejected

    association_counts: dict[str, int] = {}
    direction_counts: dict[str, int] = {}
    for sample in attribution:
        if not isinstance(sample, Mapping):
            continue
        association = str(sample.get('association') or sample.get('association_label') or '')
        direction = str(sample.get('direction') or '')
        association_counts[association] = association_counts.get(association, 0) + 1
        direction_counts[direction] = direction_counts.get(direction, 0) + 1
    known_associations = {'VERIFIED_ASSOCIATION', 'CONTRIBUTING_ASSOCIATION', 'WEAK_RELATION', 'UNSUPPORTED'}
    known_directions = {'UP', 'DOWN', 'MIXED', 'UNCERTAIN'}
    labels_known = set(association_counts) <= known_associations and '' not in association_counts
    directions_known = set(direction_counts) <= known_directions and '' not in direction_counts
    if pilot_mode:
        distribution_ok = labels_known and directions_known
    else:
        total = len(attribution) or 1
        weak_share = (association_counts.get('WEAK_RELATION', 0) + association_counts.get('UNSUPPORTED', 0)) / total
        up_share = direction_counts.get('UP', 0) / total
        down_share = direction_counts.get('DOWN', 0) / total
        max_association_share = max(association_counts.values(), default=0) / total
        distribution_ok = (
            labels_known and directions_known and weak_share >= 0.25
            and up_share >= 0.15 and down_share >= 0.15 and max_association_share <= 0.60
        )

    gates = {
        'counts': count_ok,
        'reviews_complete': reviews_ok,
        'leakage_free': leakage_ok,
        'no_rejections': rejection_ok,
        'label_distribution': distribution_ok,
    }
    failures = [name.upper() + '_GATE_FAILED' for name, passed in gates.items() if not passed]
    return {
        'pilot_mode': bool(pilot_mode),
        'expected_counts': expected,
        'dossier_count': len(dossiers),
        'attribution_sample_count': len(attribution),
        'forecast_sample_count': len(forecasts),
        'sample_count': sample_count,
        'review_count': len(reviews),
        'incomplete_review_count': max(0, expected['dossiers'] - len(reviews)) + len(review_error_map),
        'public_hidden_field_count': len(explicit_leakage) + len(detected_leakage),
        'association_distribution': dict(sorted(association_counts.items())),
        'direction_distribution': dict(sorted(direction_counts.items())),
        'review_errors': review_error_map,
        'leakage_findings': explicit_leakage + detected_leakage,
        'gates': gates,
        'gate_failures': failures,
        'formal_ready': all(gates.values()),
    }