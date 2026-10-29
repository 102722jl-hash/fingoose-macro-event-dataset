from __future__ import annotations

import argparse
import json
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from fingoose_macro_event_attribution_v2 import assert_public_projection_safe

ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = Path(__file__).with_name('fingoose_macro_event_v2_dashboard.html')
CSS_PATH = Path(__file__).with_name('fingoose_macro_event_v2_dashboard.css')
JS_PATH = Path(__file__).with_name('fingoose_macro_event_v2_dashboard.js')


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding='utf-8-sig').splitlines()
        if line.strip()
    ]


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        value = row.get(key)
        if value is not None:
            grouped.setdefault(str(value), []).append(row)
    return grouped


PUBLIC_EVENT_KEYS = (
    'event_id', 'title', 'category', 'anchor_at', 'candidate_channels',
)
PUBLIC_TARGET_KEYS = (
    'series_id', 'series_name', 'scope', 'metric_type', 'quote_convention',
    'market_timezone', 'market_close_hour',
)
PUBLIC_WINDOW_KEYS = (
    'market_window_id', 'dataset_version', 'release_tier', 'event_id',
    'series_id', 'metric_type', 'baseline', 'estimation',
    'observation_source', 'benchmark_series_id', 'timezone', 'calendar_id',
    'observation_cutoff', 't0', 'calculation_basis',
)


def _restricted_event(event: dict[str, Any]) -> dict[str, Any]:
    result = {
        key: deepcopy(event[key])
        for key in PUBLIC_EVENT_KEYS
        if key in event
    }
    result['targets'] = [
        {
            key: deepcopy(target[key])
            for key in PUBLIC_TARGET_KEYS
            if key in target
        }
        for target in event.get('targets', [])
    ]
    return result


def _restricted_window(row: dict[str, Any]) -> dict[str, Any]:
    result = {
        key: deepcopy(row[key])
        for key in PUBLIC_WINDOW_KEYS
        if key in row
    }
    result['windows'] = {
        label: deepcopy(row.get('windows', {}).get(label))
        for label in ('T60', 'T20', 'T1')
    }
    return result


def _restricted_case(case: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(case[key])
        for key in (
            'case_id', 'dataset_version', 'release_tier', 'event_id',
            'forecast_cutoff_at', 'tasks', 'visible_evidence_ids',
            'visible_market_windows',
        )
        if key in case
    } | {'split': 'HIDDEN_EVALUATION'}


class V2DashboardRepository:
    """Read-only composition of the v2 candidate data without hidden labels."""

    def __init__(self, data_root: Path, config_path: Path) -> None:
        self.data_root = Path(data_root)
        config = json.loads(Path(config_path).read_text(encoding='utf-8-sig'))
        self.events_by_id = {
            row['event_id']: row
            for row in config['events']
        }
        self.summary = json.loads(
            (self.data_root / 'summary.json').read_text(encoding='utf-8-sig')
        )
        self.validation = json.loads(
            (self.data_root / 'validation_report.json').read_text(encoding='utf-8-sig')
        )
        self.milestones = _read_jsonl(self.data_root / 'event_milestones.jsonl')
        self.episodes = _read_jsonl(self.data_root / 'event_episodes.jsonl')
        self.graphs = _read_jsonl(self.data_root / 'transmission_graphs.jsonl')
        self.windows = _read_jsonl(self.data_root / 'market_windows.jsonl')
        self.sources = _read_jsonl(self.data_root / 'source_manifest.jsonl')
        self.cases = _read_jsonl(self.data_root / 'benchmark_cases.jsonl')

        self.milestones_by_event = _group(self.milestones, 'event_id')
        self.episodes_by_event = _group(self.episodes, 'event_id')
        self.windows_by_event = _group(self.windows, 'event_id')
        self.sources_by_event = _group(self.sources, 'event_id')
        self.graphs_by_event = {row['event_id']: row for row in self.graphs}
        self.cases_by_event = {row['event_id']: row for row in self.cases}
        self.milestones_by_id = {
            row['milestone_id']: row for row in self.milestones
        }

    def overview(self) -> dict[str, Any]:
        summary = deepcopy(self.summary)
        summary.pop('challenge_event_count', None)
        summary.pop('hidden_label_count', None)
        return {
            **summary,
            'validation_valid': bool(self.validation.get('valid')),
            'scoring_tracks': deepcopy(self.validation.get('scoring_tracks', {})),
        }

    def list_events(self) -> list[dict[str, Any]]:
        events = []
        for event_id in sorted(self.events_by_id):
            event = self.events_by_id[event_id]
            case = self.cases_by_event[event_id]
            windows = self.windows_by_event.get(event_id, [])
            is_example = case['split'] == 'EXAMPLE'
            row = {
                'event_id': event_id,
                'title': event['title'],
                'category': event.get('category'),
                'anchor_at': event.get('anchor_at'),
                'split': 'EXAMPLE' if is_example else 'HIDDEN_EVALUATION',
                'milestone_count': (
                    len(self.milestones_by_event.get(event_id, []))
                    if is_example else len(case.get('visible_evidence_ids', []))
                ),
                'series_count': len(windows),
                'evaluation_restricted': not is_example,
            }
            if is_example:
                row['challenge_set'] = any(
                    window.get('challenge_set') for window in windows
                )
            events.append(row)
        return events

    def event_detail(self, event_id: str) -> dict[str, Any]:
        if event_id not in self.events_by_id:
            raise KeyError(event_id)
        case = self.cases_by_event[event_id]
        if case['split'] != 'EXAMPLE':
            visible_ids = set(case.get('visible_evidence_ids', []))
            visible_sources = [
                deepcopy(source)
                for source in self.sources_by_event.get(event_id, [])
                if source.get('evidence_id') in visible_ids
            ]
            evidence_timeline = [
                {
                    'timeline_id': 'evidence-' + source['evidence_id'],
                    'evidence_id': source['evidence_id'],
                    'first_public_at': source['published_at'],
                    'title': source.get('title') or source['evidence_id'],
                    'publisher': source.get('publisher'),
                    'source_tier': source.get('source_tier'),
                }
                for source in visible_sources
            ]
            detail = {
                'event': _restricted_event(self.events_by_id[event_id]),
                'benchmark_case': _restricted_case(case),
                'milestones': [],
                'episodes': [],
                'evidence_timeline': evidence_timeline,
                'graph': {
                    'event_id': event_id,
                    'nodes': [],
                    'edges': [],
                    'restricted': True,
                },
                'market_windows': [
                    _restricted_window(row)
                    for row in self.windows_by_event.get(event_id, [])
                ],
                'sources': visible_sources,
                'evaluation_restricted': True,
            }
            assert_public_projection_safe(detail)
            return detail
        milestones = sorted(
            self.milestones_by_event.get(event_id, []),
            key=lambda row: (row['occurred_at'], row['milestone_id']),
        )
        return {
            'event': deepcopy(self.events_by_id[event_id]),
            'benchmark_case': deepcopy(case),
            'milestones': deepcopy(milestones),
            'episodes': deepcopy(self.episodes_by_event.get(event_id, [])),
            'evidence_timeline': [],
            'graph': deepcopy(self.graphs_by_event[event_id]),
            'market_windows': deepcopy(self.windows_by_event.get(event_id, [])),
            'sources': deepcopy(self.sources_by_event.get(event_id, [])),
            'evaluation_restricted': False,
        }

    def anchor_detail(self, event_id: str, milestone_id: str) -> dict[str, Any]:
        if self.cases_by_event[event_id]['split'] != 'EXAMPLE':
            raise KeyError(milestone_id)
        detail = self.event_detail(event_id)
        milestone = self.milestones_by_id.get(milestone_id)
        if not milestone or milestone.get('event_id') != event_id:
            raise KeyError(milestone_id)
        graph = detail['graph']
        edges = [
            edge for edge in graph['edges']
            if edge.get('anchor_milestone_id') == milestone_id
        ]
        evidence_ids = {
            source['evidence_id'] for source in milestone.get('sources', [])
        }
        evidence_ids.update(
            evidence['evidence_id']
            for edge in edges
            for evidence in edge.get('evidence', [])
        )
        return {
            'event_id': event_id,
            'milestone': deepcopy(milestone),
            'edges': deepcopy(edges),
            'nodes': deepcopy(graph['nodes']),
            'market_windows': deepcopy(detail['market_windows']),
            'sources': [
                source for source in detail['sources']
                if source.get('evidence_id') in evidence_ids
            ],
        }


INDEX_HTML = INDEX_PATH.read_text(encoding='utf-8') if INDEX_PATH.exists() else ''


def make_handler(repository: V2DashboardRepository):
    class DashboardHandler(BaseHTTPRequestHandler):
        server_version = 'FinGooseV2Dashboard/1.0'

        def _send_bytes(
            self,
            payload: bytes,
            content_type: str,
            status: int = 200,
        ) -> None:
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(payload)

        def _send_json(self, value: Any, status: int = 200) -> None:
            payload = json.dumps(
                value, ensure_ascii=False, separators=(',', ':')
            ).encode('utf-8')
            self._send_bytes(payload, 'application/json; charset=utf-8', status)

        def _static(self, path: Path, content_type: str) -> None:
            if not path.exists():
                self._send_json({'error': 'NOT_FOUND'}, 404)
                return
            self._send_bytes(path.read_bytes(), content_type)

        def do_GET(self) -> None:
            route = unquote(urlparse(self.path).path)
            try:
                if route in {'/', '/index.html'}:
                    self._static(INDEX_PATH, 'text/html; charset=utf-8')
                    return
                if route == '/fingoose_macro_event_v2_dashboard.css':
                    self._static(CSS_PATH, 'text/css; charset=utf-8')
                    return
                if route == '/fingoose_macro_event_v2_dashboard.js':
                    self._static(JS_PATH, 'text/javascript; charset=utf-8')
                    return
                if route == '/api/v2/overview':
                    self._send_json(repository.overview())
                    return
                if route == '/api/v2/events':
                    self._send_json(repository.list_events())
                    return
                parts = [part for part in route.split('/') if part]
                if len(parts) == 4 and parts[:3] == ['api', 'v2', 'events']:
                    self._send_json(repository.event_detail(parts[3]))
                    return
                if (
                    len(parts) == 6
                    and parts[:3] == ['api', 'v2', 'events']
                    and parts[4] == 'anchors'
                ):
                    self._send_json(repository.anchor_detail(parts[3], parts[5]))
                    return
                self._send_json({'error': 'NOT_FOUND'}, 404)
            except KeyError as exc:
                self._send_json({'error': 'NOT_FOUND', 'id': str(exc)}, 404)
            except Exception as exc:
                self._send_json(
                    {'error': 'SERVER_ERROR', 'detail': type(exc).__name__},
                    500,
                )

        def log_message(self, format: str, *args: Any) -> None:
            return

    return DashboardHandler


def serve(
    *,
    data_root: Path,
    config_path: Path,
    host: str,
    port: int,
) -> None:
    repository = V2DashboardRepository(data_root, config_path)
    server = ThreadingHTTPServer((host, port), make_handler(repository))
    print(f'FinGoose v2 dashboard: http://{host}:{port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description='Serve the read-only FinGoose v2 dashboard')
    parser.add_argument(
        '--data-root',
        type=Path,
        default=ROOT / 'data' / 'market_event_attribution_v2_candidate',
    )
    parser.add_argument(
        '--config-path',
        type=Path,
        default=ROOT / 'configs' / 'fingoose_macro_events_v1.json',
    )
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8782)
    args = parser.parse_args()
    serve(
        data_root=args.data_root,
        config_path=args.config_path,
        host=args.host,
        port=args.port,
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
