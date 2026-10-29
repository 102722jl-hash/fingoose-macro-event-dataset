# FinGoose Event Storyline and Evidence Drawer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a distinct Chinese event-development storyline for all ten macro events, with evidence drawers and bidirectional linkage to evidence nodes, proposed transmission paths, and market series.

**Architecture:** Keep `timeline.json` as the evidence-node contract and add a focused `fingoose_event_storylines.py` curation module plus one generated `event_storyline.json` per event. The builder derives evidence coverage status and rejects broken references; `fingoose_workbench_ui.py` renders the storyline before the evidence timeline and extends the existing browser-only selection state.

**Tech Stack:** Python 3 standard library, JSON/JSONL, native HTML/CSS/JavaScript, `unittest`, Node `--check`, Playwright visual checks through the existing workspace runtime.

**Repository note:** The handoff directory is not a Git repository. Every commit step is replaced by an explicit regression checkpoint; no commit will be fabricated.

---

### Task 1: Curated Storyline Contract

**Files:**
- Create: `code/fingoose_event_storylines.py`
- Modify: `tests/test_build_fingoose_ten_event_rapid_candidate_v2.py`

- [ ] **Step 1: Write failing configuration tests**

Add `TenEventStorylineTests` with assertions that the curated registry covers all ten events, each event has 5–9 unique steps, every step has a non-generic Chinese title, and `event-01` ends in `RESOLUTION`:

```python
class TenEventStorylineTests(unittest.TestCase):
    def test_storyline_specs_cover_ten_events_with_real_titles(self) -> None:
        from fingoose_event_storylines import STORYLINE_SPECS

        self.assertEqual(set(STORYLINE_SPECS), {f"event-{i:02d}" for i in range(1, 11)})
        for event_id, rows in STORYLINE_SPECS.items():
            self.assertTrue(5 <= len(rows) <= 9, event_id)
            self.assertEqual(len({row["story_step_id"] for row in rows}), len(rows))
            for row in rows:
                self.assertTrue(row["title_cn"].strip(), row["story_step_id"])
                self.assertNotIn("事件节点", row["title_cn"])
                self.assertTrue(row["narrative_cn"].strip())
                self.assertTrue(row["before_state_cn"].strip())
                self.assertTrue(row["after_state_cn"].strip())
                self.assertTrue(row["significance_cn"].strip())
        self.assertEqual(STORYLINE_SPECS["event-01"][-1]["phase"], "RESOLUTION")
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run:

```powershell
python -m unittest tests.test_build_fingoose_ten_event_rapid_candidate_v2.TenEventStorylineTests.test_storyline_specs_cover_ten_events_with_real_titles -v
```

Expected: `ModuleNotFoundError: No module named 'fingoose_event_storylines'`.

- [ ] **Step 3: Create the curated storyline module**

Create `STORYLINE_SPECS: dict[str, list[dict[str, Any]]]` with one curated step per current evidence node. Each row must contain:

```python
{
    "story_step_id": "story-event-01-01",
    "sequence": 1,
    "phase": "PRECONDITION",
    "title_cn": "国际公共卫生风险被正式确认",
    "narrative_cn": "WHO 宣布新冠疫情构成国际关注的突发公共卫生事件，事件由局部疫情进入需要跨境协调的国际风险阶段。",
    "before_state_cn": "疫情仍主要被视为局部公共卫生事件。",
    "after_state_cn": "国际机构开始按跨境公共卫生风险协调响应。",
    "significance_cn": "这是全球风险重估的前置背景，但尚不是 3 月全球大流行冲击的市场主锚点。",
    "evidence_node_ids": ["fast-event-01-M01"],
    "coverage": "DIRECT",
}
```

Use all 50 existing evidence nodes exactly once across the ten registries. Correct narrative ordering for `event-01` to M01, M02, M04, M03, M05 and for `event-10` to M01, M03, M02, M04, M05. Classify the PHEIC ending as `RESOLUTION`. For pending evidence nodes, write cautious Chinese narrative and set `coverage="PENDING"`; do not add unsupported timestamps.

- [ ] **Step 4: Run the configuration test**

Run the focused test from Step 2. Expected: `OK`.

### Task 2: Build, Derive, and Validate Storylines

**Files:**
- Modify: `code/build_fingoose_ten_event_rapid_candidate_v2.py`
- Modify: `tests/test_build_fingoose_ten_event_rapid_candidate_v2.py`

- [ ] **Step 1: Write failing assembler and hard-failure tests**

Add tests for status derivation, resolvable references, and broken-reference rejection:

```python
def test_build_storylines_derives_status_and_references(self) -> None:
    from build_fingoose_ten_event_rapid_candidate_v2 import (
        build_core_paths, build_market_packages, build_source_registry,
        build_storylines, build_timelines,
    )
    timelines = build_timelines(ROOT)
    paths = build_core_paths(ROOT, build_source_registry(ROOT))
    markets = build_market_packages(ROOT)
    rows = build_storylines(timelines, paths, markets)
    self.assertEqual(sum(len(row["steps"]) for row in rows.values()), 50)
    self.assertEqual(
        sum(step["evidence_status"] == "PENDING_EVIDENCE"
            for row in rows.values() for step in row["steps"]),
        8,
    )
    ending = rows["event-01"]["steps"][-1]
    self.assertEqual(ending["phase"], "RESOLUTION")
    self.assertEqual(ending["evidence_status"], "SUPPORTED")

def test_storyline_validation_rejects_unknown_references(self) -> None:
    from build_fingoose_ten_event_rapid_candidate_v2 import _validate_storyline
    failures = _validate_storyline(
        "event-01",
        {"event_id": "event-01", "steps": [{
            "story_step_id": "broken", "sequence": 1,
            "evidence_node_ids": ["missing-node"],
            "activated_path_ids": ["missing-path"],
            "amplified_path_ids": [], "weakened_path_ids": [],
            "market_series_ids": ["missing-series"],
            "evidence_status": "SUPPORTED",
        }]},
        {"nodes": []}, [], [],
    )
    self.assertTrue(any("UNKNOWN_EVIDENCE_NODE" in row for row in failures))
    self.assertTrue(any("UNKNOWN_PATH" in row for row in failures))
    self.assertTrue(any("UNKNOWN_MARKET_SERIES" in row for row in failures))
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run the two new tests. Expected: import failures for `build_storylines` and `_validate_storyline`.

- [ ] **Step 3: Implement deterministic storyline assembly**

Import `STORYLINE_SPECS` and implement:

```python
def build_storylines(timelines, paths_by_event, markets_by_event):
    result = {}
    for event_id, specs in STORYLINE_SPECS.items():
        nodes = {row["fast_node_id"]: row for row in timelines[event_id]["nodes"]}
        paths = {row["path_id"]: row for row in paths_by_event[event_id]}
        market_ids = {row["series_id"] for row in markets_by_event[event_id]}
        steps = []
        for spec in specs:
            refs = [nodes[node_id] for node_id in spec["evidence_node_ids"]]
            pending = any(row["evidence_status"] == "PENDING_EVIDENCE" for row in refs)
            status = "PENDING_EVIDENCE" if pending or spec["coverage"] == "PENDING" else (
                "SUPPORTED" if spec["coverage"] == "DIRECT" else "PARTIALLY_SUPPORTED"
            )
            linked = list(dict.fromkeys(path_id for row in refs for path_id in row.get("linked_path_ids", [])))
            action = refs[-1].get("node_action")
            activated = linked if action == "STARTS" else []
            amplified = linked if action == "AMPLIFIES" else []
            weakened = linked if action in {"WEAKENS", "CALMS"} else []
            series_ids = list(dict.fromkeys(
                series_id for path_id in linked for series_id in paths[path_id].get("asset_series_ids", [])
                if series_id in market_ids
            ))
            public_times = [row.get("first_public_at") for row in refs if row.get("first_public_at")]
            step = deepcopy(spec)
            step.update({
                "period_start": min(public_times) if public_times else None,
                "period_end": max(public_times) if public_times else None,
                "time_precision": "TIMESTAMP" if public_times else "UNKNOWN",
                "evidence_status": status,
                "evidence_boundary_cn": (
                    "核心事实仍待补证，当前只保留候选叙事。" if status == "PENDING_EVIDENCE"
                    else "事件事实由关联证据节点支持；前后状态和阶段意义属于研究归纳。"
                ),
                "activated_path_ids": activated,
                "amplified_path_ids": amplified,
                "weakened_path_ids": weakened,
                "market_series_ids": series_ids,
            })
            step.pop("coverage")
            steps.append(step)
        result[event_id] = {
            "event_id": event_id,
            "title": timelines[event_id]["title"],
            "ordering_basis": "CURATED_STORY_SEQUENCE",
            "steps": steps,
        }
    return result
```

- [ ] **Step 4: Implement storyline validation**

Implement `_validate_storyline(event_id, storyline, timeline, paths, windows)` to reject wrong event IDs, duplicate step IDs or sequences, fewer than 5 or more than 9 steps, unknown evidence/path/series IDs, unsupported status values, empty Chinese narrative fields, pending steps presented as supported, and sequence inversions when two adjacent steps both use supported timestamps and no curated-order exception exists.

- [ ] **Step 5: Emit the new artifact and include it in payloads**

Add `event_storyline.json` to `EVENT_OUTPUT_FILES`; call `build_storylines(...)` in `build()`, include `storyline` in every payload, write the artifact before rendering, append storyline failures to each event report, and add `storyline_step_count` plus `pending_storyline_step_count` to the root report.

- [ ] **Step 6: Run assembler, output-tree, and full Python tests**

Run:

```powershell
python -m unittest tests.test_build_fingoose_ten_event_rapid_candidate_v2 -v
```

Expected: all tests pass, including ten emitted `event_storyline.json` files and zero hard failures.

### Task 3: Storyline UI and Bidirectional Linkage

**Files:**
- Modify: `code/fingoose_workbench_ui.py`
- Modify: `tests/test_build_fingoose_ten_event_rapid_candidate_v2.py`

- [ ] **Step 1: Write failing rendering-contract tests**

Add assertions that the overview contains 50 storyline buttons, evidence drawers, the two distinct section headings in order, and linkage functions:

```python
def test_workbench_renders_storyline_before_evidence_timeline(self) -> None:
    page = self._build_overview_html()
    self.assertEqual(page.count("class='story-step"), 50)
    self.assertIn("事件发展时间线", page)
    self.assertIn("证据时间线", page)
    self.assertLess(page.index("事件发展时间线"), page.index("证据时间线"))
    for token in ("story-drawer", "selectStoryStep(", "data-story-step-id=", "data-evidence-node-ids="):
        self.assertIn(token, page)
    self.assertIn("WHO 结束 PHEIC，事件进入常态化管理", page)
```

- [ ] **Step 2: Run the rendering test and confirm failure**

Expected: failure because `story-step` and `selectStoryStep` do not exist.

- [ ] **Step 3: Add Chinese labels and storyline renderer**

Extend `COPY["status"]` with `SUPPORTED`, `PARTIALLY_SUPPORTED`, and add `RESOLUTION` to `COPY["phase"]` and `PHASES`. Implement `_storyline_html(payload)` so every step renders a stable button/header, before/after state block, significance, counts, and an inline `<div class='story-drawer'>` containing evidence-node cards and `_citation_links(...)` output. Pending steps use an amber class and the explicit boundary text.

- [ ] **Step 4: Insert the new first section and renumber the page**

Change `_event_html` to output:

```html
<section id="storyline-event-01">01 · 事件发展时间线</section>
<section id="timeline-event-01">02 · 证据时间线</section>
<section id="paths-event-01">03 · 动态传导链</section>
<section>04 · 绝对值与变化</section>
<section>05 · 证据与混杂</section>
```

Update summary statistics to distinguish “事件发展步骤” from “证据节点”.

- [ ] **Step 5: Implement bidirectional JavaScript selection**

Add `selectStoryStep(stepId)` to read `window.__FINGOOSE_DATA__`, select the story step, expand its drawer, highlight every referenced `.timeline-node`, highlight referenced `.path-card`, and highlight referenced `.market-card`. Extend `selectTimelineNode(nodeId)` to find and highlight storyline buttons whose `evidence_node_ids` contain the node. Selection only changes CSS classes and never mutates payload status.

- [ ] **Step 6: Add responsive visual styling**

Add a single-column narrative rail with stable marker dimensions, red primary selection, amber pending status, compact before/after grid, and an unframed drawer body. At widths below 760px, stack before/after states and keep all titles, status labels, and evidence links inside the viewport.

- [ ] **Step 7: Run UI contract tests and JavaScript syntax validation**

Run the full test module, extract the inline script using the existing test helper, and run `node --check`. Expected: all Python assertions and Node syntax checks pass.

### Task 4: Regenerate, Audit, and Visually Verify

**Files:**
- Regenerate: `work/ten_event_rapid_candidate_v2/index.html`
- Regenerate: `work/ten_event_rapid_candidate_v2/events/event-01` through `event-10`
- Regenerate: `work/ten_event_rapid_candidate_v2/manifest.json`
- Regenerate: `work/ten_event_rapid_candidate_v2/validation_report.json`
- Create: `work/ten_event_rapid_candidate_v2/qa/storyline_desktop.png`
- Create: `work/ten_event_rapid_candidate_v2/qa/storyline_mobile.png`

- [ ] **Step 1: Run the builder against the existing output directory**

```powershell
python code/build_fingoose_ten_event_rapid_candidate_v2.py
```

Expected: exit code 0; ten `event_storyline.json` files; `hard_failures=[]`.

- [ ] **Step 2: Recompute invariant counts**

Read `validation_report.json` and verify: event count 10, evidence nodes 50, verified evidence nodes 42, pending evidence nodes 8, storyline steps 50, pending storyline steps 8, candidate paths 35, confirmed paths 0, and `formal_ready=false`.

- [ ] **Step 3: Run the full relevant regression suite**

```powershell
python -m unittest tests.test_build_fingoose_event_02_rapid_candidate_v2 tests.test_build_fingoose_ten_event_rapid_candidate_v2 -v
python -m compileall -q code tests
```

Expected: all tests pass and compilation exits 0.

- [ ] **Step 4: Perform desktop and mobile browser verification**

Using the existing local static server, inspect 1440×1000 and 390×844 viewports. Verify event selection, story drawer expansion, story-to-evidence linkage, evidence-to-story linkage, path and market highlighting, external evidence links, and no overlap or horizontal clipping. Save the two screenshots listed above.

- [ ] **Step 5: Final boundary audit**

Confirm visible UI never calls a `PROPOSED` path confirmed, never calls any of the 8 pending evidence nodes verified, labels the event-01 PHEIC ending as resolution, and keeps SHA deferred. Report any unavailable visual tooling instead of claiming visual verification without screenshots.
