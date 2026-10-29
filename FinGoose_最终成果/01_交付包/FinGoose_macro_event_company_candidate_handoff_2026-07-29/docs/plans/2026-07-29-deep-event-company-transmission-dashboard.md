# FinGoose Deep Event-Company Transmission Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an independent read-only dashboard that preserves all six detailed market reasoning steps and continues the same event narrative into three company seven-node transmission chains.

**Architecture:** Add a focused repository/API service that composes the existing `MacroEventDashboardRepository` without modifying it, then serve a separate HTML/CSS/JavaScript client. Join the formal market root and the latest enriched company candidate root by stable IDs, keep forecast-visible and audit-only data structurally separate, and expose missing evidence as explicit unknowns.

**Tech Stack:** Python 3 standard library, `unittest`, native HTML/CSS/JavaScript, Node.js Playwright using installed Microsoft Edge.

---

## File Structure

- Create `fingoose_macro_event_company_deep_dashboard_v1.py`: independent repository, six-step/company-chain read models, read-only HTTP API, and CLI server.
- Create `fingoose_macro_event_company_deep_dashboard_v1.html`: semantic page shell only.
- Create `fingoose_macro_event_company_deep_dashboard_v1.css`: responsive workbench styling and status treatments.
- Create `fingoose_macro_event_company_deep_dashboard_v1.js`: event/sample/company selection, six-step switching, node drilldown, source drawer, and audit expansion.
- Create `tests/test_fingoose_macro_event_company_deep_dashboard_v1.py`: repository, six-step, company-chain, API, and page-contract tests.
- Create `tests/verify_fingoose_macro_event_company_deep_dashboard_v1.mjs`: browser interaction, responsive layout, and screenshot verification.
- Generate `work/macro_event_company_deep_dashboard_v1/desktop.png`, `mobile.png`, and `visual_validation.json` during verification.
- Do not modify `fingoose_macro_event_dashboard_v1.py`, `fingoose_macro_event_dashboard_v1.html`, or any file under a protected output root.

The workspace is not currently a Git repository (`git rev-parse --show-toplevel` fails). Do not initialize Git as part of this feature. Each task therefore ends with a verification checkpoint instead of a commit; if execution later occurs inside a real repository, make the listed checkpoint a commit with the stated message.

### Task 1: Independent Repository Contract

**Files:**
- Create: `tests/test_fingoose_macro_event_company_deep_dashboard_v1.py`
- Create: `fingoose_macro_event_company_deep_dashboard_v1.py`

- [ ] **Step 1: Write failing real-release repository tests**

Create the initial test module with project-local paths and the required counts:

```python
from __future__ import annotations

from pathlib import Path
import unittest

from fingoose_macro_event_company_deep_dashboard_v1 import DeepDashboardRepository

ROOT = Path(__file__).resolve().parents[1]
MARKET_ROOT = ROOT / 'outputs' / 'fingoose_macro_event_attribution_v1'
COMPANY_ROOT = ROOT / 'outputs' / 'fingoose_macro_event_company_enriched_candidate_v1'


class DeepDashboardRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository = DeepDashboardRepository(MARKET_ROOT, COMPANY_ROOT)

    def test_release_counts_and_statuses(self):
        overview = self.repository.overview()
        self.assertEqual(overview['event_count'], 10)
        self.assertEqual(overview['market_sample_count'], 40)
        self.assertEqual(overview['company_dossier_count'], 30)
        self.assertEqual(overview['company_sample_count'], 60)
        self.assertTrue(overview['market_formal_ready'])
        self.assertEqual(overview['company_release_tier'], 'CANDIDATE')
        self.assertFalse(overview['company_formal_ready'])

    def test_event_workspace_has_four_market_samples_and_three_companies(self):
        detail = self.repository.event_workspace('event-01')
        self.assertEqual(len(detail['market_samples']), 4)
        self.assertEqual(len(detail['companies']), 3)
        self.assertEqual({row['event_id'] for row in detail['companies']}, {'event-01'})

    def test_unknown_event_is_rejected(self):
        with self.assertRaisesRegex(KeyError, 'event-99'):
            self.repository.event_workspace('event-99')

    def test_missing_root_names_the_missing_artifact(self):
        with self.assertRaisesRegex(FileNotFoundError, 'summary.json'):
            DeepDashboardRepository(ROOT / 'missing-market', COMPANY_ROOT)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
New-Item -ItemType Directory -Force .test-tmp | Out-Null
$env:TEMP = (Resolve-Path .test-tmp).Path
$env:TMP = $env:TEMP
python -m unittest tests.test_fingoose_macro_event_company_deep_dashboard_v1 -v
```

Expected: import error for `fingoose_macro_event_company_deep_dashboard_v1`.

- [ ] **Step 3: Implement the independent repository wrapper**

Create `fingoose_macro_event_company_deep_dashboard_v1.py` with a wrapper that delegates artifact validation and indexing to the existing repository:

```python
from __future__ import annotations

import argparse
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from fingoose_macro_event_dashboard_v1 import MacroEventDashboardRepository

REASONING_SEQUENCE = (
    'MACRO_REPORT',
    'DATA',
    'PERIOD_DESCRIPTION',
    'FACT_TRANSMISSION_CHAIN',
    'MULTI_DATA_TREND_CONFIRMATION',
    'SHORT_TERM_PREDICTION',
)


class DeepDashboardRepository:
    def __init__(self, market_root: Path, company_root: Path) -> None:
        self.market_root = Path(market_root)
        self.company_root = Path(company_root)
        self.base = MacroEventDashboardRepository(self.market_root, self.company_root)

    def overview(self) -> dict[str, Any]:
        market = self.base.persisted_summary
        company = self.base.company_summary
        return {
            'event_count': len(self.base.event_dossiers),
            'market_sample_count': len(self.base.attribution_samples),
            'company_dossier_count': len(self.base.company_dossiers),
            'company_sample_count': (
                int(company.get('attribution_sample_count', 0))
                + int(company.get('forecast_sample_count', 0))
            ),
            'market_formal_ready': bool(market.get('formal_ready')),
            'company_release_tier': company.get('release_tier'),
            'company_formal_ready': bool(company.get('formal_ready')),
            'company_formal_blockers': deepcopy(company.get('formal_blockers', [])),
        }

    def list_events(self) -> list[dict[str, Any]]:
        return self.base.list_events()

    def event_workspace(self, event_id: str) -> dict[str, Any]:
        detail = self.base.event_detail(event_id)
        return {
            'event': detail['event'],
            'market_samples': [
                {
                    'record_id': row['record_id'],
                    'event_id': row['event_id'],
                    'task_type': row['task_type'],
                    'target_series_ids': row.get('target_series_ids', []),
                    'label': row.get('attribution', {}).get('label'),
                    'confidence': row.get('attribution', {}).get('confidence'),
                }
                for row in detail['market_samples']
            ],
            'companies': detail['company_dossiers'],
        }
```

- [ ] **Step 4: Run Task 1 tests and verify GREEN**

Run the command from Step 2. Expected: four tests pass.

- [ ] **Step 5: Record checkpoint**

Record: `Task 1 green: independent repository loads 10/40/30/60 without modifying the existing dashboard.`

Suggested commit message when Git is available: `feat: add independent deep dashboard repository`.

### Task 2: Complete Six-Step Market Read Model

**Files:**
- Modify: `tests/test_fingoose_macro_event_company_deep_dashboard_v1.py`
- Modify: `fingoose_macro_event_company_deep_dashboard_v1.py`

- [ ] **Step 1: Add failing tests for all six detailed steps**

Add these methods to `DeepDashboardRepositoryTests`:

```python
    def test_market_sample_preserves_all_six_steps_in_order(self):
        detail = self.repository.market_sample_detail(
            'macro-event-v1-event-01-single-sp500'
        )
        self.assertEqual(
            [step['step_id'] for step in detail['steps']],
            list(REASONING_SEQUENCE),
        )
        self.assertTrue(all(step['content'] for step in detail['steps']))

    def test_market_steps_retain_detailed_source_window_chain_and_prediction_data(self):
        detail = self.repository.market_sample_detail(
            'macro-event-v1-event-01-single-sp500'
        )
        steps = {step['step_id']: step['content'] for step in detail['steps']}
        self.assertTrue(steps['MACRO_REPORT']['evidence'])
        self.assertEqual(steps['DATA']['visible_window_codes'], ['D1', 'D3'])
        self.assertTrue(steps['DATA']['market_windows'])
        self.assertIn('period_description', steps['PERIOD_DESCRIPTION'])
        self.assertTrue(steps['FACT_TRANSMISSION_CHAIN']['nodes'])
        self.assertTrue(steps['FACT_TRANSMISSION_CHAIN']['edges'])
        self.assertEqual(steps['MULTI_DATA_TREND_CONFIRMATION']['series_count'], 4)
        self.assertEqual(steps['SHORT_TERM_PREDICTION']['prediction']['horizon'], 'D20')

    def test_forecast_visible_and_audit_only_market_data_are_separate(self):
        detail = self.repository.market_sample_detail(
            'macro-event-v1-event-01-single-sp500'
        )
        visible_text = json.dumps(detail['steps'], ensure_ascii=False)
        self.assertNotIn('actual_direction', visible_text)
        self.assertNotIn('verification_status', visible_text)
        self.assertEqual(detail['audit_only']['outcome']['outcome_window'], 'D20')
        self.assertTrue(detail['audit_only']['hidden_label']['hidden_from_model'])
```

Also import `json` and `REASONING_SEQUENCE` at the top of the test module.

- [ ] **Step 2: Run the focused test and verify RED**

Expected: `AttributeError` because `market_sample_detail` does not exist.

- [ ] **Step 3: Implement the complete market detail assembler**

Add `market_sample_detail` to `DeepDashboardRepository`. Build every step from archived records and keep hidden values outside `steps`:

```python
    def market_sample_detail(self, record_id: str) -> dict[str, Any]:
        if record_id not in self.base.samples_by_id:
            raise KeyError(record_id)
        sample = deepcopy(self.base.samples_by_id[record_id])
        projection = deepcopy(self.base.training_projection_by_id[record_id])
        chain = deepcopy(sample['forecast_reasoning_chain'])
        event = deepcopy(self.base.events_by_id[sample['event_id']])
        windows = [
            deepcopy(self.base.market_windows_by_id[window_id])
            for window_id in sample.get('market_window_ids', [])
        ]
        sources = [
            deepcopy(self.base.sources_by_id[source_id])
            for source_id in sample.get('visible_evidence_ids', [])
            if source_id in self.base.sources_by_id
        ]
        visible_windows = []
        for window in windows:
            visible = deepcopy(window)
            visible['windows'] = {
                code: deepcopy(window.get('windows', {}).get(code))
                for code in ('D1', 'D3')
                if window.get('windows', {}).get(code) is not None
            }
            visible_windows.append(visible)
        steps = [
            {
                'step_id': 'MACRO_REPORT',
                'content': {
                    'evidence': deepcopy(chain.get('macro_report_evidence', [])),
                    'sources': sources,
                },
            },
            {
                'step_id': 'DATA',
                'content': {
                    'forecast_as_of_at': sample.get('forecast_as_of_at'),
                    'visible_window_codes': ['D1', 'D3'],
                    'hidden_window_code': 'D20',
                    'market_windows': visible_windows,
                },
            },
            {
                'step_id': 'PERIOD_DESCRIPTION',
                'content': {
                    'event': event,
                    'period_description': deepcopy(chain.get('period_description', {})),
                    'market_windows': visible_windows,
                },
            },
            {
                'step_id': 'FACT_TRANSMISSION_CHAIN',
                'content': {
                    **deepcopy(chain.get('fact_transmission_chain', {})),
                    'channels': deepcopy(sample.get('attribution', {}).get('channels', [])),
                    'counterevidence': deepcopy(
                        sample.get('attribution', {}).get('counterevidence', [])
                    ),
                    'market_windows': visible_windows,
                },
            },
            {
                'step_id': 'MULTI_DATA_TREND_CONFIRMATION',
                'content': deepcopy(chain.get('trend_confirmation', {})),
            },
            {
                'step_id': 'SHORT_TERM_PREDICTION',
                'content': {
                    'prediction': deepcopy(chain.get('short_term_prediction', {})),
                    'forecast_as_of_at': sample.get('forecast_as_of_at'),
                    'visible_market_windows': visible_windows,
                },
            },
        ]
        review = self.base.reviews_by_id.get(sample.get('review_id'))
        return {
            'record_id': record_id,
            'event': event,
            'sample': sample,
            'public_projection': projection,
            'steps': steps,
            'audit_only': {
                'hidden_label': deepcopy(
                    self.base.hidden_labels_by_record_id.get(record_id, {})
                ),
                'outcome': deepcopy(
                    self.base.hidden_outcomes_by_record_id.get(record_id, {})
                ),
                'review': deepcopy(review or {}),
                'd20_windows': [
                    {
                        'market_window_id': window['market_window_id'],
                        'series': deepcopy(window.get('series', {})),
                        'D20': deepcopy(window.get('windows', {}).get('D20')),
                    }
                    for window in windows
                ],
            },
        }
```

- [ ] **Step 4: Run Task 2 tests and verify GREEN**

Expected: all repository and six-step tests pass, and the returned sequence is exactly the six required IDs.

- [ ] **Step 5: Record checkpoint**

Record: `Task 2 green: all six steps retain source, cutoff, period, chain, trend, and prediction content; D20 remains audit-only.`

Suggested commit message when Git is available: `feat: preserve complete six-step market reasoning`.

### Task 3: Company Seven-Node Chain and Evidence Resolution

**Files:**
- Modify: `tests/test_fingoose_macro_event_company_deep_dashboard_v1.py`
- Modify: `fingoose_macro_event_company_deep_dashboard_v1.py`

- [ ] **Step 1: Add failing tests for pending and enriched company records**

Add the canonical node sequence and these tests:

```python
COMPANY_NODE_SEQUENCE = (
    'MAJOR_EVENT',
    'INDUSTRY_MACRO_VARIABLE',
    'COMPANY_BUSINESS_EXPOSURE',
    'OPERATING_METRIC',
    'FINANCIAL_RESULT',
    'COMPETING_EXPLANATION',
    'ATTRIBUTION_OR_FORECAST',
)


    def test_company_detail_preserves_all_seven_nodes(self):
        detail = self.repository.company_chain_detail(
            'company-dossier-event-01-600009-sh'
        )
        self.assertEqual(
            [node['node_type'] for node in detail['nodes']],
            list(COMPANY_NODE_SEQUENCE),
        )
        exposure = detail['nodes'][2]
        self.assertEqual(exposure['value'], 'UNKNOWN')
        self.assertEqual(exposure['status'], 'PENDING_EVIDENCE')
        self.assertEqual(exposure['sources'], [])
        self.assertTrue(exposure['evidence_gaps'])

    def test_enriched_event_02_exposes_verified_company_sources_and_facts(self):
        detail = self.repository.company_chain_detail(
            'company-dossier-event-02-601857-sh'
        )
        by_type = {node['node_type']: node for node in detail['nodes']}
        self.assertEqual(
            by_type['COMPANY_BUSINESS_EXPOSURE']['status'],
            'VERIFIED_EVIDENCE',
        )
        self.assertTrue(by_type['COMPANY_BUSINESS_EXPOSURE']['sources'])
        self.assertGreaterEqual(
            sum(fact['status'] == 'VERIFIED_EVIDENCE' for fact in detail['metric_facts']),
            3,
        )

    def test_company_hidden_results_are_audit_only(self):
        detail = self.repository.company_chain_detail(
            'company-dossier-event-01-600009-sh'
        )
        public_text = json.dumps(
            {
                'nodes': detail['nodes'],
                'forecast': detail['forecast_sample'],
                'facts': detail['metric_facts'],
            },
            ensure_ascii=False,
        )
        self.assertNotIn('actual_validation_result', public_text)
        self.assertIn('hidden_labels', detail['audit_only'])
        self.assertIn('hidden_outcomes', detail['audit_only'])
```

- [ ] **Step 2: Run the focused test and verify RED**

Expected: `AttributeError` because `company_chain_detail` does not exist.

- [ ] **Step 3: Load company hidden artifacts without changing the base repository**

Add focused JSONL helpers and indexes in the deep repository module:

```python
def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open('r', encoding='utf-8-sig') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _group_by(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        value = row.get(key)
        if value is not None:
            grouped.setdefault(str(value), []).append(row)
    return grouped
```

Extend `DeepDashboardRepository.__init__`:

```python
        hidden_labels = _read_jsonl(
            self.company_root / 'company_candidate_hidden_labels.jsonl'
        )
        hidden_outcomes = _read_jsonl(
            self.company_root / 'company_hidden_outcomes.jsonl'
        )
        self.company_hidden_labels_by_dossier = _group_by(hidden_labels, 'dossier_id')
        self.company_hidden_outcomes_by_dossier = _group_by(hidden_outcomes, 'dossier_id')
```

- [ ] **Step 4: Implement node/source/gap resolution**

Add the company detail method. Preserve upstream values exactly and attach resolved records without inference:

```python
    def company_chain_detail(self, dossier_id: str) -> dict[str, Any]:
        raw = self.base.company_detail(dossier_id)
        dossier = raw['dossier']
        source_by_id = {
            source['source_id']: source
            for source in raw['sources']
            if source.get('source_id')
        }
        gaps_by_type = _group_by(raw['evidence_gaps'], 'node_type')
        nodes = []
        for node in dossier['transmission_chain']['nodes']:
            resolved_sources = []
            unresolved_refs = []
            for reference in node.get('evidence_refs', []):
                source_id = reference.get('source_id')
                source = source_by_id.get(str(source_id))
                if source:
                    resolved_sources.append(deepcopy(source))
                else:
                    unresolved_refs.append(deepcopy(reference))
            nodes.append({
                **deepcopy(node),
                'sources': resolved_sources,
                'unresolved_evidence_refs': unresolved_refs,
                'evidence_gaps': deepcopy(gaps_by_type.get(node['node_type'], [])),
            })
        return {
            'dossier': dossier,
            'nodes': nodes,
            'edges': deepcopy(dossier['transmission_chain'].get('edges', [])),
            'metric_facts': raw['metric_facts'],
            'stock_window': raw['stock_window'],
            'attribution_sample': raw['attribution_sample'],
            'forecast_sample': raw['forecast_sample'],
            'review': raw['review'],
            'sources': raw['sources'],
            'evidence_gaps': raw['evidence_gaps'],
            'audit_only': {
                'hidden_labels': deepcopy(
                    self.company_hidden_labels_by_dossier.get(dossier_id, [])
                ),
                'hidden_outcomes': deepcopy(
                    self.company_hidden_outcomes_by_dossier.get(dossier_id, [])
                ),
            },
        }
```

- [ ] **Step 5: Run Task 3 tests and verify GREEN**

Expected: event-01 stays explicit `UNKNOWN`, while event-02 resolves archived CNINFO evidence and at least three verified facts.

- [ ] **Step 6: Record checkpoint**

Record: `Task 3 green: seven nodes render with exact sources or explicit gaps; company hidden outcomes remain audit-only.`

Suggested commit message when Git is available: `feat: add company transmission chain detail`.
