# Complete Transmission Path UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat 111-edge transmission list with default company operating paths and a secondary complete macro-market path view.

**Architecture:** Preserve upstream edges and mechanism chains. Add a reviewed display registry for 19 channels and 8 market series, project root-to-asset macro paths with deterministic graph traversal, and expose unresolved edge coverage explicitly. Render operating and macro paths behind a segmented control while keeping raw IDs in technical disclosures.

**Tech Stack:** Python 3, JSONL, static HTML/CSS/JavaScript, unittest/pytest, Playwright with installed Chrome.

---

### Task 1: Define the graph-projection contract with failing tests

**Files:**
- Modify: `tests/test_fingoose_company_impact_ui_v2.py`
- Modify: `code/fingoose_company_impact_ui_v2.py`

- [ ] Add tests asserting each event exposes exactly three `operating_transmission_paths`, non-empty `macro_transmission_paths`, and `unresolved_macro_edges`.
- [ ] Add coverage assertions proving every one of the 111 raw `edge_id` values appears in either a macro path's `edge_ids` or the unresolved list exactly once at set level.
- [ ] Add event-01 assertions for the diagnostic-testing, airport-throughput, and airline-traffic operating paths.
- [ ] Add macro assertions that each path starts with a concrete Chinese timeline title and ends with a registered series containing Chinese name, code, unit, economic meaning, and direction interpretation.
- [ ] Run `python -m pytest tests/test_fingoose_company_impact_ui_v2.py -q` and verify RED because the projection fields do not exist.

### Task 2: Add reviewed channel and market-series display metadata

**Files:**
- Create: `configs/company_impact_high_quality_v2/transmission_node_display_registry.jsonl`
- Modify: `code/fingoose_company_impact_ui_v2.py`

- [ ] Register all 19 observed channels with `channel_id`, `name_zh`, `up_label_zh`, `down_label_zh`, and `economic_meaning_zh`.
- [ ] Register the eight observed series `DCOILBRENTEU`, `DCOILWTICO`, `DEXCHUS`, `DEXJPUS`, `DGS10`, `DTWEXBGS`, `SP500`, and `VIXCLS` with Chinese name, unit, economic meaning, and up/down interpretation.
- [ ] Load the registry during bundle construction and fail on duplicate records, missing observed IDs, empty Chinese fields, or unknown record types.
- [ ] Re-run the focused tests; registry validation should pass while path-projection tests remain RED.

### Task 3: Build complete operating and macro path projections

**Files:**
- Modify: `code/fingoose_company_impact_ui_v2.py`
- Modify: `tests/test_fingoose_company_impact_ui_v2.py`

- [ ] Project the three existing company mechanism chains per event as `operating_transmission_paths`, merging the concrete timeline display title into the `EVENT_FACT` node without modifying source JSONL.
- [ ] Build a directed adjacency map for each event's raw macro edges, detect cycles, and enumerate deterministic root-to-asset paths.
- [ ] Merge an intermediate node and its same-code asset leaf into one registered market indicator display node while preserving all underlying `edge_ids`.
- [ ] Aggregate edge directions, lag, conditions, invalidation conditions, event evidence, mechanism evidence, counterevidence, confidence, and review status into each macro path.
- [ ] Put every raw edge not reached by a root-to-asset path into `unresolved_macro_edges` with a reason; never silently drop an edge.
- [ ] Run the focused tests and verify all projection and coverage assertions pass.

### Task 4: Replace the flat list with two path views

**Files:**
- Modify: `code/fingoose_company_impact_ui_v2.py`
- Modify: `tests/test_fingoose_company_impact_ui_v2.py`
- Generate: `work/company_impact_high_quality_v2_candidate/ui/index.html`
- Generate: `work/company_impact_high_quality_v2_candidate/ui/ui_data_bundle.js`

- [ ] Add failing HTML assertions for a segmented control, default operating cards, macro cards, Chinese series metadata, and collapsed raw-edge details.
- [ ] Add `transmissionMode` to UI state and render “经营影响链” by default and “宏观市场链” on demand.
- [ ] Render each operating path as one seven-step continuous card with evidence links, directions, metrics, conditions, invalidation conditions, and company-detail linkage.
- [ ] Render each macro path as one complete event-channel-indicator card; remove `SP500 → SP500` and equivalent duplicate visual nodes.
- [ ] Preserve raw edge IDs, node IDs, confidence, evidence scope, and review rationale inside collapsed technical details.
- [ ] Keep time-node filtering active in both views and show an explicit fallback message if a selected node has no bound path.
- [ ] Run focused tests and rebuild the two static UI artifacts with `write_ui()`.

### Task 5: Verify regressions, graph coverage, and responsive interaction

**Files:**
- No production file changes expected.

- [ ] Run the five company-impact and mechanism-chain test modules; expected result is zero failures.
- [ ] Verify 10 events, 30 operating paths, 111 raw-edge coverage, registered market fields, `formal_ready=false`, and `sha_gate=DEFERRED` with a standalone projection audit.
- [ ] Use installed Chrome to test both tabs, time-node filtering, company linkage, technical disclosures, official links, and console errors.
- [ ] Verify 1440px desktop and 390px mobile have no document-level horizontal overflow or incoherent text overlap.
- [ ] Confirm release-boundary search returns no `formal_ready=true`, `sha_gate=ENFORCED`, or `chain_status=CONFIRMED` records.

