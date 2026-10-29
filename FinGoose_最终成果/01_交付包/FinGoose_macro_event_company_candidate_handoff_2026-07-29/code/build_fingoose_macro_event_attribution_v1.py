from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from fingoose_macro_event_attribution_v1 import (
    DATASET_VERSION,
    align_event_session,
    apply_review_decision,
    assert_public_projection_safe,
    build_forecast_reasoning_chain,
    build_public_attribution_projection,
    compute_market_windows,
    review_decision_errors,
    review_errors,
    second_review_trigger_reasons,
    validate_schema_record,
)


ROOT = Path(__file__).resolve().parent

REVIEW_CHECKLIST = [
    'Confirm the event fact and first-public timestamp.',
    'Confirm the baseline is the last valid close before the first tradable session.',
    'Recalculate visible D1 and D3 windows from the archived market series.',
    'Assess whether timing supports the proposed attribution.',
    'Assess abnormal movement against the prior 60-session baseline.',
    'Assess whether the transmission mechanism is explicit and coherent.',
    'Compare material concurrent explanations.',
    'Confirm that multiple market series support or contradict the chain.',
    'Assess the short-term prediction horizon, direction and confidence.',
    'Confirm concrete prediction invalidation conditions.',
]


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        ''.join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + '\n' for row in rows),
        encoding='utf-8',
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _rooted_path(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ValueError('PATH_OUTSIDE_PROJECT_ROOT')
    return candidate


def _read_review_decisions(
    path: Path | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if path is None or not path.is_file():
        return [], []
    rows: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        path.read_text(encoding='utf-8-sig').splitlines(), 1,
    ):
        if not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            rejections.append({
                'record_id': f'<review-line-{line_number}>',
                'code': 'REVIEW_DECISION_JSON_INVALID',
                'line_number': line_number,
            })
            continue
        if not isinstance(parsed, dict):
            rejections.append({
                'record_id': f'<review-line-{line_number}>',
                'code': 'REVIEW_DECISION_SCHEMA_INVALID',
                'line_number': line_number,
            })
            continue
        parsed['_line_number'] = line_number
        rows.append(parsed)
    return rows, rejections


def _read_observations(path: Path) -> list[dict[str, Any]]:
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        date_key = 'date' if 'date' in fieldnames else 'observation_date'
        value_key = 'value' if 'value' in fieldnames else next(
            (name for name in fieldnames if name != date_key), ''
        )
        rows = []
        for row in reader:
            day = str(row.get(date_key) or '')
            raw_value = row.get(value_key)
            if not day or raw_value in {None, '', '.'}:
                continue
            rows.append({'date': day, 'value': float(raw_value)})
        return rows


def _source_errors(root: Path, event: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    sources = [row for row in event.get('sources', []) if isinstance(row, Mapping)]
    if not any(row.get('role') == 'event_fact' and row.get('tier') in {1, 2} for row in sources):
        errors.append('EVENT_REQUIRES_TIER_1_OR_2_SOURCE')
    if not any(row.get('role') == 'macro_report' and row.get('tier') in {1, 2} for row in sources):
        errors.append('MACRO_REPORT_REQUIRES_TIER_1_OR_2_SOURCE')
    for source in sources:
        source_id = str(source.get('source_id') or '<unknown>')
        try:
            snapshot = _rooted_path(root, str(source['local_snapshot_path']))
        except (KeyError, ValueError):
            errors.append('SOURCE_PATH_INVALID:' + source_id)
            continue
        if not snapshot.is_file():
            errors.append('SOURCE_SNAPSHOT_MISSING:' + source_id)
        elif _sha256(snapshot) != source.get('content_sha256'):
            errors.append('SOURCE_HASH_MISMATCH:' + source_id)
    return errors


def _event_dossier(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'event_id': event['event_id'],
        'dataset_version': DATASET_VERSION,
        'title': event['title'],
        'category': event['category'],
        'anchor_at': event['anchor_at'],
        'occurred_at': event.get('occurred_at', event['anchor_at']),
        'first_public_at': event.get('first_public_at', event['anchor_at']),
        'phase': event['phase'],
        'candidate_channels': list(event['candidate_channels']),
        'source_ids': [row['source_id'] for row in event['sources']],
        'target_series_ids': [row['series_id'] for row in event['targets']],
    }


def _market_window(root: Path, event: Mapping[str, Any], target: Mapping[str, Any]) -> dict[str, Any]:
    observation_path = _rooted_path(root, str(target['observation_path']))
    observations = _read_observations(observation_path)
    sessions = [datetime.fromisoformat(str(row['date'])).date() for row in observations if row.get('date')]
    anchor = datetime.fromisoformat(str(event['anchor_at']).replace('Z', '+00:00'))
    anchor = anchor.astimezone(ZoneInfo(str(target.get('market_timezone') or 'UTC')))
    alignment = align_event_session(
        anchor_at=anchor,
        sessions=sessions,
        market_close_hour=int(target.get('market_close_hour', 16)),
    )
    calculation = compute_market_windows(
        observations=observations,
        t0_session=alignment['t0_session'],
        metric_type=str(target['metric_type']),
    )
    return {
        'market_window_id': f"{event['event_id']}-{str(target['series_id']).lower()}",
        'dataset_version': DATASET_VERSION,
        'event_id': event['event_id'],
        'series': {
            'series_id': target['series_id'],
            'series_name': target['series_name'],
            'scope': target['scope'],
            'metric_type': target['metric_type'],
            **({'quote_convention': target['quote_convention']}
               if target['metric_type'] == 'fx_return_pct'
               else {}),
        },
        'observation_source': {
            'path': str(target['observation_path']),
            'sha256': _sha256(observation_path),
        },
        'alignment': alignment,
        **calculation,
    }


def _window_direction(window: Mapping[str, Any] | None) -> str:
    if not window:
        return 'UNKNOWN'
    score = window.get('abnormal_score')
    if score is not None and abs(float(score)) < 0.5:
        return 'FLAT'
    change = float(window['change'])
    return 'UP' if change > 0 else 'DOWN' if change < 0 else 'FLAT'


def _iso_end_of_day(day: str) -> str:
    return day + 'T23:59:59+00:00'

def _trend_items(targets: list[Mapping[str, Any]], windows: Mapping[str, Mapping[str, Any]]) -> list[dict[str, str]]:
    items = []
    for target in targets:
        series_id = str(target['series_id'])
        observed = _window_direction(windows[series_id]['windows']['D3'])
        expected = str(target['expected_d3_direction'])
        items.append({
            'series_id': series_id,
            'window': 'D3',
            'observed_direction': observed,
            'expected_direction': expected,
            'alignment': 'SUPPORTS' if observed == expected else 'CONTRADICTS',
        })
    return items


def _review_record(event_id: str, sample_suffix: str, attribution: Mapping[str, Any], review: Mapping[str, Any]) -> dict[str, Any]:
    record = {
        'review_id': f'review-{event_id}-{sample_suffix}',
        'dataset_version': DATASET_VERSION,
        'event_id': event_id,
        'initial_review': copy.deepcopy(review.get('initial_review')),
        'second_review': copy.deepcopy(review.get('second_review')),
        'adjudication': None,
        'final_label': attribution['label'],
        'confidence': attribution['confidence'],
        'core_dimensions': copy.deepcopy(review.get('core_dimensions')),
    }
    record['second_review_trigger_reasons'] = second_review_trigger_reasons(record)
    return record


def _reasoning_chain(
    event: Mapping[str, Any], targets: list[Mapping[str, Any]], windows: Mapping[str, Mapping[str, Any]],
    prediction_target: Mapping[str, Any], prediction: Mapping[str, Any],
) -> dict[str, Any]:
    d3_dates = [windows[str(target['series_id'])]['windows']['D3']['end_date'] for target in targets]
    forecast_as_of_at = _iso_end_of_day(max(d3_dates))
    report_evidence = [
        {
            'evidence_id': source['source_id'],
            'published_at': source['published_at'],
            'summary': source['summary'],
        }
        for source in event['sources'] if source['role'] == 'macro_report'
    ]
    target_id = str(prediction_target['series_id'])
    target_window = windows[target_id]
    return build_forecast_reasoning_chain(
        forecast_as_of_at=forecast_as_of_at,
        report_evidence=report_evidence,
        period_description={
            'start_date': target_window['t0_session'],
            'end_date': target_window['windows']['D3']['end_date'],
            'summary': event['period_summary'],
        },
        transmission_nodes=event['transmission_nodes'],
        transmission_edges=event['transmission_edges'],
        trend_confirmations=_trend_items(targets, windows),
        short_term_prediction={
            'target_series_id': target_id,
            'horizon': 'D20',
            'direction': prediction['direction'],
            'confidence': prediction['confidence'],
            'invalidation_conditions': list(prediction['invalidation_conditions']),
        },
    )


def _sample_record(
    event: Mapping[str, Any], sample_suffix: str, task_type: str,
    sample_targets: list[Mapping[str, Any]], all_targets: list[Mapping[str, Any]],
    windows: Mapping[str, Mapping[str, Any]], attribution: Mapping[str, Any],
    prediction_target: Mapping[str, Any], prediction: Mapping[str, Any], review_id: str,
) -> dict[str, Any]:
    d20_dates = [windows[str(target['series_id'])]['windows']['D20']['end_date'] for target in sample_targets]
    chain = _reasoning_chain(event, all_targets, windows, prediction_target, prediction)
    return {
        'record_id': f"macro-event-v1-{event['event_id']}-{sample_suffix}",
        'dataset_version': DATASET_VERSION,
        'event_id': event['event_id'],
        'task_type': task_type,
        'target_series_ids': [target['series_id'] for target in sample_targets],
        'as_of_at': _iso_end_of_day(max(d20_dates)),
        'forecast_as_of_at': chain['forecast_as_of_at'],
        'visible_evidence_ids': [source['source_id'] for source in event['sources']],
        'market_window_ids': [windows[str(target['series_id'])]['market_window_id'] for target in all_targets],
        'attribution': {
            'label': attribution['label'],
            'confidence': attribution['confidence'],
            'channels': list(attribution['channels']),
            'counterevidence': list(attribution['counterevidence']),
        },
        'forecast_reasoning_chain': chain,
        'review_id': review_id,
    }


def _hidden_attribution_label(
    sample: Mapping[str, Any], review: Mapping[str, Any],
) -> dict[str, Any]:
    release_errors = review_errors(review)
    return {
        'record_id': sample['record_id'],
        'review_id': review['review_id'],
        'hidden_from_model': True,
        'label_status': 'FINAL' if not release_errors else 'PROVISIONAL',
        'label': review['final_label'],
        'confidence': review['confidence'],
        'core_dimensions': copy.deepcopy(review['core_dimensions']),
    }


def _hidden_outcome(sample: Mapping[str, Any], windows: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    prediction = sample['forecast_reasoning_chain']['short_term_prediction']
    target_id = str(prediction['target_series_id'])
    actual = _window_direction(windows[target_id]['windows']['D20'])
    predicted = str(prediction['direction'])
    status = 'INCONCLUSIVE' if actual == 'UNKNOWN' else ('CORRECT' if predicted == actual else 'INCORRECT')
    return {
        'outcome_id': 'outcome-' + str(sample['record_id']).removeprefix('macro-event-v1-'),
        'source_sample_id': sample['record_id'],
        'hidden_from_model': True,
        'target_series_id': target_id,
        'outcome_window': 'D20',
        'predicted_direction': predicted,
        'actual_direction': actual,
        'verification_status': status,
        'calculation': copy.deepcopy(windows[target_id]['windows']['D20']),
    }


def _review_batch_id(event_id: str) -> str:
    event_number = int(event_id.rsplit('-', 1)[-1])
    if event_number <= 2:
        return 'review-batch-01-pilot'
    if event_number <= 5:
        return 'review-batch-02'
    if event_number <= 8:
        return 'review-batch-03'
    return 'review-batch-04'


def build_review_work_queue(
    samples: Sequence[Mapping[str, Any]],
    reviews: Sequence[Mapping[str, Any]],
    dossiers: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    review_index = {str(row['review_id']): row for row in reviews}
    dossier_index = {str(row['event_id']): row for row in dossiers}
    queue: list[dict[str, Any]] = []
    for sample in samples:
        review = review_index[str(sample['review_id'])]
        event_id = str(sample['event_id'])
        initial = review.get('initial_review') or {}
        second = review.get('second_review') or {}
        trigger_reasons = list(review.get('second_review_trigger_reasons') or [])
        second_required = bool(trigger_reasons)
        initial_status = str(initial.get('status') or 'PENDING')
        second_status = str(second.get('status') or 'PENDING') if second_required else 'NOT_REQUIRED'
        if initial_status != 'APPROVED':
            review_state = 'PENDING_HUMAN'
        elif second_required and second_status != 'APPROVED':
            review_state = 'PENDING_SECOND_HUMAN'
        else:
            review_state = 'COMPLETE'
        queue.append({
            'task_id': 'task-' + str(review['review_id']).removeprefix('review-'),
            'review_id': review['review_id'],
            'record_id': sample['record_id'],
            'event_id': event_id,
            'event_title': dossier_index[event_id]['title'],
            'batch_id': _review_batch_id(event_id),
            'task_type': sample['task_type'],
            'target_series_ids': list(sample['target_series_ids']),
            'proposed_label': review['final_label'],
            'proposed_confidence': review['confidence'],
            'initial_reviewer_id': initial.get('reviewer_id', 'PENDING_HUMAN'),
            'initial_review_status': initial_status,
            'second_review_required': second_required,
            'second_review_trigger_reasons': trigger_reasons,
            'second_reviewer_id': second.get('reviewer_id') if second_required else None,
            'second_review_status': second_status,
            'review_state': review_state,
            'visible_evidence_ids': list(sample['visible_evidence_ids']),
            'market_window_ids': list(sample['market_window_ids']),
            'review_checklist': list(REVIEW_CHECKLIST),
        })
    return queue


def _review_visible_market_window(
    market_window: Mapping[str, Any],
) -> dict[str, Any]:
    visible = copy.deepcopy(dict(market_window))
    visible['windows'] = {
        key: copy.deepcopy(market_window['windows'][key])
        for key in ('D1', 'D3')
    }
    return visible


def build_pilot_review_packet(
    work_queue: Sequence[Mapping[str, Any]],
    samples: Sequence[Mapping[str, Any]],
    dossiers: Sequence[Mapping[str, Any]],
    market_rows: Sequence[Mapping[str, Any]],
    sources: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    sample_index = {str(row['record_id']): row for row in samples}
    dossier_index = {str(row['event_id']): row for row in dossiers}
    market_index = {str(row['market_window_id']): row for row in market_rows}
    source_index = {str(row['source_id']): row for row in sources}
    packet: list[dict[str, Any]] = []
    for task in work_queue:
        if task['batch_id'] != 'review-batch-01-pilot':
            continue
        sample = sample_index[str(task['record_id'])]
        item = dict(task)
        item['event_dossier'] = copy.deepcopy(dossier_index[str(task['event_id'])])
        item['attribution_sample'] = build_public_attribution_projection(sample)
        item['market_windows'] = [
            _review_visible_market_window(market_index[str(window_id)])
            for window_id in sample['market_window_ids']
        ]
        item['visible_sources'] = [
            copy.deepcopy(source_index[str(source_id)]) for source_id in sample['visible_evidence_ids']
        ]
        packet.append(item)
    return packet


def _review_decision_template(task: Mapping[str, Any]) -> dict[str, Any]:
    empty_verdict = {
        'reviewer_id': '',
        'reviewed_at': '',
        'comments': '',
        'label': None,
        'confidence': None,
        'core_dimensions': {
            'temporal_alignment': None,
            'abnormal_movement': None,
            'transmission_mechanism': None,
            'competing_explanations': None,
        },
    }
    return {
        'review_id': task['review_id'],
        'event_id': task['event_id'],
        'initial_review': copy.deepcopy(empty_verdict),
        'second_review': None,
        'adjudication': None,
    }


def build_second_review_packet(
    work_queue: Sequence[Mapping[str, Any]],
    samples: Sequence[Mapping[str, Any]],
    dossiers: Sequence[Mapping[str, Any]],
    market_rows: Sequence[Mapping[str, Any]],
    sources: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    sample_index = {str(row['record_id']): row for row in samples}
    dossier_index = {str(row['event_id']): row for row in dossiers}
    market_index = {str(row['market_window_id']): row for row in market_rows}
    source_index = {str(row['source_id']): row for row in sources}
    packet: list[dict[str, Any]] = []
    for task in work_queue:
        if not task['second_review_required']:
            continue
        if task['second_review_status'] == 'APPROVED':
            continue
        sample = sample_index[str(task['record_id'])]
        dossier = {
            key: copy.deepcopy(value)
            for key, value in dossier_index[str(task['event_id'])].items()
            if key != 'dataset_version'
        }
        visible_sample = {
            key: copy.deepcopy(sample[key])
            for key in (
                'record_id', 'event_id', 'target_series_ids', 'as_of_at',
                'forecast_as_of_at', 'visible_evidence_ids',
                'market_window_ids', 'forecast_reasoning_chain',
            )
        }
        visible_markets = []
        for window_id in sample['market_window_ids']:
            window = _review_visible_market_window(
                market_index[str(window_id)],
            )
            window.pop('dataset_version', None)
            window.pop('observation_source', None)
            visible_markets.append(window)
        visible_sources = []
        for source_id in sample['visible_evidence_ids']:
            source = {
                key: copy.deepcopy(value)
                for key, value in source_index[str(source_id)].items()
                if key != 'local_snapshot_path'
            }
            visible_sources.append(source)
        packet.append({
            'task_id': task['task_id'],
            'review_id': task['review_id'],
            'record_id': task['record_id'],
            'event_id': task['event_id'],
            'event_title': task['event_title'],
            'batch_id': task['batch_id'],
            'target_series_ids': copy.deepcopy(task['target_series_ids']),
            'second_review_trigger_reasons': copy.deepcopy(
                task['second_review_trigger_reasons'],
            ),
            'event_dossier': dossier,
            'sample': visible_sample,
            'market_windows': visible_markets,
            'visible_sources': visible_sources,
        })
    return packet


def build_event_attribution_dataset(
    root: Path,
    config_path: Path,
    output_root: Path,
    review_decisions_path: Path | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    output_root = Path(output_root)
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    events = [event for event in config.get('events', []) if isinstance(event, Mapping)]
    dossiers: list[dict[str, Any]] = []
    market_rows: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    hidden: list[dict[str, Any]] = []
    source_manifest: dict[str, dict[str, Any]] = {}
    rejections: list[dict[str, Any]] = []

    for event in events:
        event_id = str(event.get('event_id') or '<unknown>')
        rejections.extend({'record_id': event_id, 'code': code} for code in _source_errors(root, event))
        targets = [row for row in event.get('targets', []) if isinstance(row, Mapping)]
        if len(targets) != 4:
            rejections.append({'record_id': event_id, 'code': 'EVENT_REQUIRES_FOUR_TARGETS'})
            continue
        scopes = {str(target.get('scope')) for target in targets}
        if not {'global', 'china'} <= scopes:
            rejections.append({'record_id': event_id, 'code': 'GLOBAL_AND_CHINA_TARGETS_REQUIRED'})
        for source in event.get('sources', []):
            source_manifest[str(source['source_id'])] = copy.deepcopy(dict(source))
        dossier = _event_dossier(event)
        dossiers.append(dossier)
        for code in validate_schema_record('event_dossier', dossier):
            rejections.append({'record_id': event_id, 'code': code})

        event_windows: dict[str, dict[str, Any]] = {}
        for target in targets:
            series_id = str(target['series_id'])
            try:
                window = _market_window(root, event, target)
            except (KeyError, TypeError, ValueError) as exc:
                rejections.append({'record_id': f'{event_id}-{series_id}', 'code': 'MARKET_WINDOW_INVALID:' + str(exc)})
                continue
            event_windows[series_id] = window
            market_rows.append(window)
            for code in validate_schema_record('market_window', window):
                rejections.append({'record_id': window['market_window_id'], 'code': code})
            if window['windows']['D20'] is None:
                rejections.append({'record_id': window['market_window_id'], 'code': 'D20_WINDOW_REQUIRED'})
        if len(event_windows) != 4 or any(row['windows']['D20'] is None for row in event_windows.values()):
            continue

        event_samples: list[dict[str, Any]] = []
        event_reviews: list[dict[str, Any]] = []
        for target in targets[:3]:
            series_id = str(target['series_id'])
            suffix = 'single-' + series_id.lower()
            attribution = target['attribution']
            review = _review_record(event_id, suffix, attribution, target['review'])
            sample = _sample_record(
                event, suffix, 'single_asset_attribution_forecast', [target], targets,
                event_windows, attribution, target, target['short_term_prediction'], review['review_id'],
            )
            event_samples.append(sample)
            event_reviews.append(review)

        cross = event['cross_asset_attribution']
        target_index = {str(target['series_id']): target for target in targets}
        forecast_target = target_index[str(cross['forecast_target_series_id'])]
        suffix = 'cross-asset'
        cross_review = _review_record(event_id, suffix, cross, cross['review'])
        cross_sample = _sample_record(
            event, suffix, 'cross_asset_attribution_forecast', targets, targets,
            event_windows, cross, forecast_target, cross['short_term_prediction'], cross_review['review_id'],
        )
        event_samples.append(cross_sample)
        event_reviews.append(cross_review)

        reviews.extend(event_reviews)
        for sample in event_samples:
            samples.append(sample)
            for code in validate_schema_record('attribution_sample', sample):
                rejections.append({'record_id': sample['record_id'], 'code': code})
            hidden.append(_hidden_outcome(sample, event_windows))

    decision_rows, decision_rejections = _read_review_decisions(review_decisions_path)
    rejections.extend(decision_rejections)
    review_by_id = {str(row['review_id']): row for row in reviews}
    seen_review_ids: set[str] = set()
    build_at = datetime.now().astimezone().isoformat()
    for input_row in decision_rows:
        decision = dict(input_row)
        line_number = int(decision.pop('_line_number'))
        review_id = str(decision.get('review_id') or f'<review-line-{line_number}>')
        if review_id in seen_review_ids:
            rejections.append({
                'record_id': review_id,
                'code': 'REVIEW_DECISION_DUPLICATE',
                'line_number': line_number,
            })
            continue
        seen_review_ids.add(review_id)
        base_review = review_by_id.get(review_id)
        if base_review is None:
            rejections.append({
                'record_id': review_id,
                'code': 'REVIEW_DECISION_UNKNOWN',
                'line_number': line_number,
            })
            continue
        decision_errors = review_decision_errors(
            decision, str(base_review['event_id']), build_at,
        )
        if decision_errors:
            rejections.extend({
                'record_id': review_id,
                'code': code,
                'line_number': line_number,
            } for code in decision_errors)
            continue
        merged = apply_review_decision(base_review, decision)
        review_by_id[review_id] = merged

    reviews = [review_by_id[str(row['review_id'])] for row in reviews]
    for review in reviews:
        for code in validate_schema_record('review_record', review) + review_errors(review):
            rejections.append({'record_id': review['review_id'], 'code': code})

    for sample in samples:
        review = review_by_id[str(sample['review_id'])]
        sample['attribution']['label'] = review['final_label']
        sample['attribution']['confidence'] = review['confidence']

    expected_events = int(config.get('expected_event_count', 10))
    expected_samples = int(config.get('expected_sample_count', 40))
    task_counts = Counter(str(row.get('task_type')) for row in samples)
    label_counts = Counter(str(row.get('attribution', {}).get('label')) for row in samples)
    if len(dossiers) != expected_events:
        rejections.append({'record_id': '<release>', 'code': 'EVENT_COUNT_INVALID'})
    if len(samples) != expected_samples:
        rejections.append({'record_id': '<release>', 'code': 'SAMPLE_COUNT_INVALID'})
    if task_counts != Counter({
        'single_asset_attribution_forecast': expected_events * 3,
        'cross_asset_attribution_forecast': expected_events,
    }):
        rejections.append({'record_id': '<release>', 'code': 'TASK_DISTRIBUTION_INVALID'})
    weak_count = label_counts['WEAK_RELATION'] + label_counts['UNSUPPORTED']
    if samples and weak_count / len(samples) < 0.20:
        rejections.append({'record_id': '<release>', 'code': 'NEGATIVE_ATTRIBUTION_SHARE_TOO_LOW'})
    if samples and max(label_counts.values(), default=0) / len(samples) > 0.60:
        rejections.append({'record_id': '<release>', 'code': 'ATTRIBUTION_LABEL_TOO_CONCENTRATED'})
    if any(row['verification_status'] == 'INCONCLUSIVE' for row in hidden):
        rejections.append({'record_id': '<release>', 'code': 'FORECAST_OUTCOME_INCONCLUSIVE'})

    public_projection = [
        build_public_attribution_projection(sample) for sample in samples
    ]
    hidden_attribution_labels = [
        _hidden_attribution_label(
            sample, review_by_id[str(sample['review_id'])],
        )
        for sample in samples
    ]
    final_attribution_label_count = sum(
        row['label_status'] == 'FINAL' for row in hidden_attribution_labels
    )
    source_rows = list(source_manifest.values())
    review_work_queue = build_review_work_queue(samples, reviews, dossiers)
    pilot_review_packet = build_pilot_review_packet(
        review_work_queue, samples, dossiers, market_rows, source_rows,
    )
    review_decision_template = [
        _review_decision_template(task) for task in review_work_queue
    ]
    second_review_packet = build_second_review_packet(
        review_work_queue, samples, dossiers, market_rows, source_rows,
    )
    initial_review_pending_count = sum(
        row['initial_review_status'] != 'APPROVED' for row in review_work_queue
    )
    second_review_required_count = sum(row['second_review_required'] for row in review_work_queue)
    second_review_pending_count = sum(
        row['second_review_required'] and row['second_review_status'] != 'APPROVED'
        for row in review_work_queue
    )
    review_preparation_ready = (
        len(review_work_queue) == expected_samples
        and len({row['review_id'] for row in review_work_queue}) == expected_samples
        and len(pilot_review_packet) == expected_events // 5 * 4
    )
    formal_ready = (
        not rejections
        and len(dossiers) == expected_events
        and len(samples) == expected_samples
        and len(hidden) == expected_samples
        and len(hidden_attribution_labels) == expected_samples
        and final_attribution_label_count == expected_samples
    )
    output_root.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_root / 'event_dossiers.jsonl', dossiers)
    _write_jsonl(output_root / 'market_windows.jsonl', market_rows)
    _write_jsonl(output_root / 'attribution_samples.jsonl', samples)
    _write_jsonl(output_root / 'training_projection.jsonl', public_projection)
    _write_jsonl(output_root / 'hidden_forecast_outcomes.jsonl', hidden)
    _write_jsonl(
        output_root / 'hidden_attribution_labels.jsonl',
        hidden_attribution_labels,
    )
    _write_jsonl(output_root / 'review_records.jsonl', reviews)
    _write_jsonl(output_root / 'source_manifest.jsonl', source_rows)
    _write_jsonl(output_root / 'audit_rejections.jsonl', rejections)
    _write_jsonl(output_root / 'review_work_queue.jsonl', review_work_queue)
    _write_jsonl(
        output_root / 'review_decision_template.jsonl',
        review_decision_template,
    )
    _write_jsonl(output_root / 'pilot_review_packet.jsonl', pilot_review_packet)
    _write_jsonl(output_root / 'second_review_packet.jsonl', second_review_packet)
    summary = {
        'dataset_version': DATASET_VERSION,
        'formal_ready': formal_ready,
        'event_count': len(dossiers),
        'market_window_count': len(market_rows),
        'sample_count': len(samples),
        'single_asset_count': task_counts['single_asset_attribution_forecast'],
        'cross_asset_count': task_counts['cross_asset_attribution_forecast'],
        'hidden_outcome_count': len(hidden),
        'hidden_attribution_label_count': len(hidden_attribution_labels),
        'final_attribution_label_count': final_attribution_label_count,
        'review_count': len(reviews),
        'initial_review_pending_count': initial_review_pending_count,
        'second_review_required_count': second_review_required_count,
        'second_review_pending_count': second_review_pending_count,
        'pilot_review_task_count': len(pilot_review_packet),
        'review_decision_template_count': len(review_decision_template),
        'second_review_packet_count': len(second_review_packet),
        'review_preparation_ready': review_preparation_ready,
        'source_count': len(source_manifest),
        'rejected_count': len(rejections),
        'label_distribution': dict(sorted(label_counts.items())),
        'gate_failures': sorted({row['code'] for row in rejections}),
        'forecast_reasoning_chain': [
            'MACRO_REPORT', 'DATA', 'PERIOD_DESCRIPTION', 'FACT_TRANSMISSION_CHAIN',
            'MULTI_DATA_TREND_CONFIRMATION', 'SHORT_TERM_PREDICTION',
        ],
    }
    (output_root / 'summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8',
    )
    review_readiness = {
        'dataset_version': DATASET_VERSION,
        'status': (
            'FORMAL_READY' if formal_ready else
            'READY_FOR_HUMAN_REVIEW' if review_preparation_ready else
            'REVIEW_PREPARATION_INCOMPLETE'
        ),
        'review_handbook_path': 'docs/fingoose_macro_event_review_handbook_v1.md',
        'formal_ready': formal_ready,
        'blocking_gates': summary['gate_failures'],
        'human_work_remaining': {
            'initial_reviews': initial_review_pending_count,
            'second_reviews': second_review_pending_count,
        },
        'review_batches': {
            'review-batch-01-pilot': 8,
            'review-batch-02': 12,
            'review-batch-03': 12,
            'review-batch-04': 8,
        },
    }
    (output_root / 'review_readiness.json').write_text(
        json.dumps(review_readiness, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description='Build FinGoose macro event attribution and short-term forecast data.')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--config', type=Path, default=ROOT / 'configs' / 'fingoose_macro_events_v1.json')
    parser.add_argument('--output-root', type=Path, default=ROOT / 'outputs' / 'fingoose_macro_event_attribution_v1')
    parser.add_argument(
        '--review-decisions',
        type=Path,
        default=ROOT / 'configs' / 'fingoose_macro_review_decisions_v1.jsonl',
    )
    args = parser.parse_args()
    summary = build_event_attribution_dataset(
        args.root,
        args.config,
        args.output_root,
        review_decisions_path=args.review_decisions,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary['formal_ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
