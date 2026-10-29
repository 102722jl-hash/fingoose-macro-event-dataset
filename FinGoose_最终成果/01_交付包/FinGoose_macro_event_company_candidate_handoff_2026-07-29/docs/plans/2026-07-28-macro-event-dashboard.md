# FinGoose Macro Event Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only local dashboard for the formal 10-event, 40-sample macro event attribution dataset.

**Architecture:** Add one self-contained Python server module that loads and joins the persisted release artifacts through a repository class, exposes five read-only JSON endpoints, and serves an embedded responsive HTML application. Keep the implementation independent from the older candidate audit UI and from `outputs/fingoose_formal_v1_macro`.

**Tech Stack:** Python standard library, `ThreadingHTTPServer`, native HTML/CSS/JavaScript, inline SVG, `unittest`, Playwright for visual verification.

---

### Task 1: Load and summarize the formal release

**Files:**
- Create: `tests/test_fingoose_macro_event_dashboard_v1.py`
- Create: `fingoose_macro_event_dashboard_v1.py`

- [ ] **Step 1: Write failing repository tests**

Create fixtures with the required release filenames and test the public constructor and overview contract:

```python
class MacroEventDashboardRepositoryTests(unittest.TestCase):
    def test_overview_recomputes_release_counts(self):
        repository = MacroEventDashboardRepository(self.output_root)
        overview = repository.overview()
        self.assertEqual(overview['computed']['event_count'], 1)
        self.assertEqual(overview['computed']['sample_count'], 1)
        self.assertEqual(overview['computed']['market_window_count'], 1)
        self.assertEqual(overview['computed']['completed_second_reviews'], 1)
        self.assertEqual(overview['computed']['completed_adjudications'], 1)
        self.assertEqual(overview['label_distribution'], {'PRIMARY_DRIVER': 1})

    def test_missing_required_artifact_names_the_file(self):
        (self.output_root / 'market_windows.jsonl').unlink()
        with self.assertRaisesRegex(FileNotFoundError, 'market_windows.jsonl'):
            MacroEventDashboardRepository(self.output_root)
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m unittest tests.test_fingoose_macro_event_dashboard_v1 -v`

Expected: import failure because `fingoose_macro_event_dashboard_v1` does not exist.

- [ ] **Step 3: Implement the repository loader and overview**

Implement these stable members:

```python
REQUIRED_FILES = (
    'summary.json', 'event_dossiers.jsonl', 'market_windows.jsonl',
    'attribution_samples.jsonl', 'training_projection.jsonl',
    'hidden_forecast_outcomes.jsonl', 'hidden_attribution_labels.jsonl',
    'review_records.jsonl', 'source_manifest.jsonl',
)

class MacroEventDashboardRepository:
    def __init__(self, output_root: Path) -> None: ...
    def overview(self) -> dict: ...
```

The constructor must resolve only the configured output root, require every file above, decode UTF-8 JSON/JSONL, and build indexes by `event_id`, `record_id`, and `review_id`. `overview()` must return both the persisted summary and recomputed counts, label distribution, review counts, year distribution, category distribution, and required reasoning-chain sequence.

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `python -m unittest tests.test_fingoose_macro_event_dashboard_v1 -v`

Expected: repository tests pass.

### Task 2: Join event and sample audit details

**Files:**
- Modify: `tests/test_fingoose_macro_event_dashboard_v1.py`
- Modify: `fingoose_macro_event_dashboard_v1.py`

- [ ] **Step 1: Write failing query tests**

Add tests for event and sample linkage:

```python
def test_event_detail_joins_windows_samples_and_sources(self):
    detail = self.repository.event('event-01')
    self.assertEqual(detail['event']['event_id'], 'event-01')
    self.assertEqual(detail['market_windows'][0]['market_window_id'], 'event-01-sp500')
    self.assertEqual(detail['samples'][0]['record_id'], 'sample-01')
    self.assertEqual(detail['sources'][0]['source_id'], 'source-01')

def test_sample_detail_separates_public_and_internal_audit(self):
    detail = self.repository.sample('sample-01')
    self.assertNotIn('attribution', detail['public_projection'])
    self.assertEqual(detail['internal_audit']['attribution']['label'], 'PRIMARY_DRIVER')
    self.assertEqual(detail['internal_audit']['forecast_outcome']['outcome_window'], 'D20')
    self.assertEqual(detail['review']['review_id'], 'review-01')

def test_sample_filters_are_combined(self):
    rows = self.repository.samples({'event_id': 'event-01', 'label': 'PRIMARY_DRIVER'})
    self.assertEqual([row['record_id'] for row in rows], ['sample-01'])
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m unittest tests.test_fingoose_macro_event_dashboard_v1 -v`

Expected: failures because `event`, `sample`, `samples`, and `events` are not implemented.

- [ ] **Step 3: Implement query methods**

Add:

```python
def events(self, filters: Mapping[str, str] | None = None) -> list[dict]: ...
def event(self, event_id: str) -> dict | None: ...
def samples(self, filters: Mapping[str, str] | None = None) -> list[dict]: ...
def sample(self, record_id: str) -> dict | None: ...
```

Support event filters `year`, `category`, and free-text `query`. Support sample filters `event_id`, `task_type`, `label`, `confidence`, and free-text `query`. Build the internal attribution object from `hidden_attribution_labels.jsonl`, the D20 result from `hidden_forecast_outcomes.jsonl`, and public data only from `training_projection.jsonl`. Return copies so API consumers cannot mutate repository state.

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `python -m unittest tests.test_fingoose_macro_event_dashboard_v1 -v`

Expected: all repository query tests pass.

### Task 3: Expose the read-only HTTP API

**Files:**
- Modify: `tests/test_fingoose_macro_event_dashboard_v1.py`
- Modify: `fingoose_macro_event_dashboard_v1.py`

- [ ] **Step 1: Write failing handler tests**

Start an ephemeral `ThreadingHTTPServer` in the test and assert:

```python
def test_http_api_and_not_found_contract(self):
    self.assertEqual(self.get_json('/api/overview')[0], 200)
    self.assertEqual(self.get_json('/api/events')[0], 200)
    self.assertEqual(self.get_json('/api/event/event-01')[1]['event']['event_id'], 'event-01')
    self.assertEqual(self.get_json('/api/samples?label=PRIMARY_DRIVER')[0], 200)
    self.assertEqual(self.get_json('/api/sample/sample-01')[1]['record_id'], 'sample-01')
    self.assertEqual(self.get_json('/api/event/missing')[0], 404)
    self.assertEqual(self.get_json('/api/sample/missing')[0], 404)
    self.assertEqual(self.get_json('/api/unknown')[0], 404)
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m unittest tests.test_fingoose_macro_event_dashboard_v1 -v`

Expected: failures because `make_handler` and the routes do not exist.

- [ ] **Step 3: Implement handlers and CLI**

Implement `make_handler(repository)`, `_json_bytes(payload)`, and `main()`. Routes must be exactly:

```text
GET /
GET /api/overview
GET /api/events
GET /api/event/{event_id}
GET /api/samples
GET /api/sample/{record_id}
```

Use `parse_qs` for filters, UTF-8 JSON, `application/json; charset=utf-8`, and `{ "error": "NOT_FOUND" }` with HTTP 404 for unknown routes and entities. CLI defaults: output root `outputs/fingoose_macro_event_attribution_v1`, host `127.0.0.1`, port `52346`.

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `python -m unittest tests.test_fingoose_macro_event_dashboard_v1 -v`

Expected: all API tests pass.

### Task 4: Build the responsive audit dashboard

**Files:**
- Modify: `tests/test_fingoose_macro_event_dashboard_v1.py`
- Modify: `fingoose_macro_event_dashboard_v1.py`

- [ ] **Step 1: Write failing page-contract tests**

```python
def test_page_contains_required_views_and_audit_boundary(self):
    self.assertIn('data-view="overview"', INDEX_HTML)
    self.assertIn('data-view="events"', INDEX_HTML)
    self.assertIn('data-view="reviews"', INDEX_HTML)
    self.assertIn('内部审计', INDEX_HTML)
    self.assertIn('不得进入公开训练投影', INDEX_HTML)
    self.assertIn('market-chart', INDEX_HTML)
    self.assertIn('reasoning-chain', INDEX_HTML)
    self.assertIn('/api/overview', INDEX_HTML)
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m unittest tests.test_fingoose_macro_event_dashboard_v1 -v`

Expected: assertions fail because the required dashboard markup is absent.

- [ ] **Step 3: Implement `INDEX_HTML`**

Build the confirmed layout with:

- Compact dark-green header, version, ready badge, and internal-audit warning.
- Three icon-and-text tabs: overview, event analysis, and review records.
- Five fixed-height metric tiles.
- CSS conic-gradient label donut and legends.
- SVG bar/line charts generated from API data; group market windows by `change_unit`.
- Event timeline and four sample rows per event.
- Six fixed reasoning-chain steps from the sample `forecast_reasoning_chain`.
- Filterable review table plus detail pane for core dimensions and all review stages.
- HTML escaping for every value inserted into markup.
- Loading, empty, 404, and fetch-error states.
- Responsive breakpoints at 1080px and 720px, with no viewport-based font scaling.

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `python -m unittest tests.test_fingoose_macro_event_dashboard_v1 -v`

Expected: all dashboard tests pass.

### Task 5: Validate integration and visuals

**Files:**
- Create: `work/macro_event_dashboard_v1/desktop.png`
- Create: `work/macro_event_dashboard_v1/mobile.png`
- Create: `work/macro_event_dashboard_v1/visual_validation.json`

- [ ] **Step 1: Run dashboard tests against formal artifacts**

Run:

```powershell
python -m unittest tests.test_fingoose_macro_event_dashboard_v1 -v
python -B -c "from pathlib import Path; from fingoose_macro_event_dashboard_v1 import MacroEventDashboardRepository; r=MacroEventDashboardRepository(Path('outputs/fingoose_macro_event_attribution_v1')); assert r.overview()['computed']['event_count']==10; assert len(r.samples())==40"
```

Expected: tests pass and artifact assertions exit 0.

- [ ] **Step 2: Run the full test suite**

Run: `python -m unittest discover -s tests`

Expected: exit 0 with no failures.

- [ ] **Step 3: Start the dashboard**

Run: `python fingoose_macro_event_dashboard_v1.py --port 52346`

Expected: `FinGoose macro event dashboard: http://127.0.0.1:52346`.

- [ ] **Step 4: Verify desktop and mobile in Playwright**

Capture `1440x1000` and `390x844` screenshots. For each viewport assert:

```javascript
document.documentElement.scrollWidth <= document.documentElement.clientWidth
document.querySelectorAll('[data-chart-rendered="true"]').length > 0
document.querySelector('[data-view="events"]').getBoundingClientRect().height > 0
```

Exercise all three tabs, select event-10, filter `UNSUPPORTED`, and open a sample detail. Record viewport, overflow result, chart count, tab visibility, and interaction results in `visual_validation.json`.

- [ ] **Step 5: Final independent review**

Review the implementation against `docs/superpowers/specs/2026-07-28-macro-event-dashboard-design.md`, confirm no reference to `outputs/fingoose_formal_v1_macro`, and report findings before declaring completion.
