# FinGoose Ten-Event Rapid Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 event-02 的完整时间线、核心传导链、六窗口行情、混杂和行内引用模式扩展到 event-01 至 event-10，并生成十个独立页面和一个总览入口。

**Architecture:** 新建一个只读配置模块保存十事件核心路径、预选资产和重要混杂，新建一个通用生成器读取现有时间线、生产候选图、行情窗口及来源清单。生成器输出统一数据合同，再由单一 HTML 模板生成十个事件页面和总览页；全部产物位于独立工作目录，生产 v2 始终只读。

**Tech Stack:** Python 3.12、标准库 `unittest/csv/json`、现有 v2 行情计算函数、AnySearch 官方来源检索、静态 HTML/CSS/JavaScript、Microsoft Edge 无头截图。

---

## File Structure

- Modify: `tests/test_build_fingoose_event_02_rapid_candidate_v2.py`：完成 event-02 行内引用合同。
- Modify: `code/build_fingoose_event_02_rapid_candidate_v2.py`：把 A 方案引用标签加入当前模板。
- Create: `code/fingoose_ten_event_rapid_config.py`：十事件标题、核心路径、核心资产、混杂与机制来源注册表。
- Create: `code/build_fingoose_ten_event_rapid_candidate_v2.py`：通用数据组装、验证和页面生成器。
- Create: `tests/test_build_fingoose_ten_event_rapid_candidate_v2.py`：十事件覆盖、证据边界、行情、引用、页面和硬失败测试。
- Create: `work/ten_event_rapid_candidate_v2/`：十个独立事件包、总览、清单和验证报告。

当前目录不是 Git 仓库。每个任务的完成点以测试和文件检查记录，不初始化仓库、不创建提交。

### Task 1: Finish The Shared Event-02 Citation Template

**Files:**
- Modify: `tests/test_build_fingoose_event_02_rapid_candidate_v2.py`
- Modify: `code/build_fingoose_event_02_rapid_candidate_v2.py`
- Regenerate: `work/event_02_rapid_candidate_v2/index.html`

- [ ] **Step 1: Add the failing inline-citation test**

Add this method to `Event02RapidCandidateTests`:

```python
def test_timeline_and_paths_render_resolvable_inline_citations(self) -> None:
    self.build()
    timeline = json.loads((self.output / "timeline.json").read_text(encoding="utf-8"))
    paths = json.loads(
        (self.output / "core_transmission_paths.json").read_text(encoding="utf-8")
    )["paths"]
    sources = {
        row["source_id"]: row
        for row in json.loads((self.output / "sources.json").read_text(encoding="utf-8"))
    }
    page = (self.output / "index.html").read_text(encoding="utf-8")
    for node in timeline["nodes"]:
        if node["evidence_status"] == "VERIFIED_EXISTING":
            self.assertTrue(node["source_ids"])
            self.assertTrue(all(sources[source_id]["url"] for source_id in node["source_ids"]))
    self.assertEqual(timeline["nodes"][0]["source_ids"], [])
    for path in paths:
        ids = path["event_fact_evidence"] + [
            row["source_id"] for row in path["mechanism_evidence"]
        ]
        self.assertTrue(all(sources[source_id]["url"] for source_id in ids))
    for token in (
        "citationLinks", "事实来源", "事件事实依据", "机制依据",
        "事后机制验证", "暂无已验证引用", 'target="_blank"',
        'rel="noopener noreferrer"',
    ):
        self.assertIn(token, page)
```

- [ ] **Step 2: Verify the new test fails for the missing renderer**

```powershell
python -m unittest tests.test_build_fingoose_event_02_rapid_candidate_v2.Event02RapidCandidateTests.test_timeline_and_paths_render_resolvable_inline_citations -v
```

Expected: FAIL on missing `citationLinks`.

- [ ] **Step 3: Add the shared citation renderer**

In `_html()`, add wrapping styles and the following JavaScript contract:

```javascript
const sourceById = Object.fromEntries(D.sources.map(s => [s.source_id, s]));
function citationLinks(refs, role) {
  const ids = refs.map(ref => typeof ref === 'string' ? ref : ref.source_id);
  if (!ids.length) return '<span class="citation-empty">暂无已验证引用</span>';
  return ids.map(id => {
    const source = sourceById[id];
    if (!source || !source.url) return '<span class="citation-empty">UNKNOWN · ' + esc(id) + '</span>';
    const postEvent = source.visibility === 'HIDDEN_FROM_PRIMARY_PREDICTION';
    const roleLabel = postEvent ? '事后机制验证' : (role === 'mechanism' ? '机制' : '事实与时间');
    return '<a class="citation-link ' + role + '" href="' + esc(source.url)
      + '" target="_blank" rel="noopener noreferrer">↗ '
      + esc(source.publisher) + ' · ' + roleLabel + '</a>';
  }).join('');
}
```

Append fact citations to each timeline node and separate event/mechanism groups to each path.

- [ ] **Step 4: Verify event-02 and rebuild**

```powershell
python -m unittest tests.test_build_fingoose_event_02_rapid_candidate_v2 -v
python code/build_fingoose_event_02_rapid_candidate_v2.py
```

Expected: 6 tests pass and `hard_failures=[]`.

### Task 2: Define The Ten-Event Configuration Contract

**Files:**
- Create: `code/fingoose_ten_event_rapid_config.py`
- Create: `tests/test_build_fingoose_ten_event_rapid_candidate_v2.py`

- [ ] **Step 1: Write configuration coverage tests**

Create the test module with:

```python
from __future__ import annotations
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

class TenEventRapidConfigTests(unittest.TestCase):
    def test_registry_covers_ten_events_four_assets_and_about_35_paths(self):
        from fingoose_ten_event_rapid_config import EVENT_CONFIGS, CORE_PATH_SPECS
        self.assertEqual(set(EVENT_CONFIGS), {f"event-{i:02d}" for i in range(1, 11)})
        self.assertTrue(all(len(row["core_series_ids"]) == 4 for row in EVENT_CONFIGS.values()))
        counts = {
            event_id: sum(path["event_id"] == event_id for path in CORE_PATH_SPECS)
            for event_id in EVENT_CONFIGS
        }
        self.assertTrue(all(3 <= count <= 4 for count in counts.values()))
        self.assertTrue(34 <= len(CORE_PATH_SPECS) <= 36)
        self.assertEqual(len({row["path_id"] for row in CORE_PATH_SPECS}), len(CORE_PATH_SPECS))
```

- [ ] **Step 2: Run the configuration test**

```powershell
python -m unittest tests.test_build_fingoose_ten_event_rapid_candidate_v2.TenEventRapidConfigTests -v
```

Expected: ERROR because the configuration module does not exist.

- [ ] **Step 3: Create event and asset configuration**

Define `EVENT_CONFIGS` with the exact asset registry from the approved spec. Each row contains `title_zh`, `core_series_ids`, `optional_series_ids`, and `primary_anchor_strategy`. Set event-02 `optional_series_ids=["DGS10"]`; all other optional lists are empty.

- [ ] **Step 4: Create the deterministic core-path inventory**

Define these 35 stable path IDs in `CORE_PATH_SPECS`:

```text
event-01: pandemic-risk-appetite, pandemic-oil-demand, pandemic-safe-haven, pandemic-policy-response
event-02: energy-supply, inflation-rates, risk-appetite, sanctions-trade
event-03: rate-expectations, equity-duration, dollar-liquidity, growth-expectations
event-04: china-growth, commodity-demand, risk-appetite, yuan-repricing
event-05: banking-stress, rate-repricing, safe-haven
event-06: oil-supply, inflation-pass-through, global-growth
event-07: energy-supply, risk-appetite, safe-haven, shipping-disruption
event-08: yen-rate-differential, japan-rates, global-risk
event-09: china-growth, yuan-repricing, risk-assets
event-10: trade-costs, inflation-rates, global-growth-risk
```

Each path record includes `path_id`, `event_id`, `name_zh`, `anchor_phase`, `chain`, `asset_series_ids`, three directions, lag, conditions, invalidation conditions, counterevidence, and mechanism source IDs. All records use `CORE_REVIEWED / PROPOSED / AI_DESK_REVIEW_NO_HUMAN_CONFIRMATION`.

- [ ] **Step 5: Run the configuration test**

Expected: PASS with 10 events and 35 paths.

### Task 3: Build Timeline, Path, And Source Assemblers

**Files:**
- Create: `code/build_fingoose_ten_event_rapid_candidate_v2.py`
- Modify: `tests/test_build_fingoose_ten_event_rapid_candidate_v2.py`
- Read: `work/timeline_fast_candidate_v2/timeline_nodes.jsonl`
- Read: `data/market_event_attribution_v2_candidate/transmission_graphs.jsonl`
- Read: `data/market_event_attribution_v2_candidate/source_manifest.jsonl`
- Read: `work/timeline_fast_candidate_v2/candidate_source_manifest.jsonl`

- [ ] **Step 1: Add failing assembler tests**

```python
class TenEventAssemblerTests(unittest.TestCase):
    def test_timelines_keep_50_nodes_and_real_pending_boundaries(self):
        from build_fingoose_ten_event_rapid_candidate_v2 import build_timelines
        rows = build_timelines(ROOT)
        self.assertEqual(sum(len(row["nodes"]) for row in rows.values()), 50)
        self.assertEqual(sum(
            node["evidence_status"] == "PENDING_EVIDENCE"
            for event in rows.values() for node in event["nodes"]
        ), 8)
        self.assertTrue(all(sum(
            node["anchor_role"] == "PRIMARY" for node in event["nodes"]
        ) == 1 for event in rows.values()))

    def test_core_paths_resolve_fact_and_mechanism_sources(self):
        from build_fingoose_ten_event_rapid_candidate_v2 import (
            build_core_paths, build_source_registry,
        )
        sources = build_source_registry(ROOT)
        paths = build_core_paths(ROOT, sources)
        self.assertEqual(sum(len(rows) for rows in paths.values()), 35)
        for rows in paths.values():
            for path in rows:
                self.assertEqual(path["confirmation_status"], "PROPOSED")
                self.assertTrue(path["event_fact_evidence"])
                self.assertTrue(path["mechanism_evidence"])
                self.assertTrue(all(source_id in sources for source_id in path["event_fact_evidence"]))
                self.assertTrue(all(ref["source_id"] in sources for ref in path["mechanism_evidence"]))
```

- [ ] **Step 2: Run assembler tests**

Expected: ERROR because assembler functions do not exist.

- [ ] **Step 3: Implement source registry merging**

Merge production sources, only `ACCEPTED` candidate sources with non-empty URL, and mechanism sources from the configuration. Reject duplicate source IDs with different URLs. Preserve `evidence_scope` and `visibility`; mark post-anchor mechanism research `HIDDEN_FROM_PRIMARY_PREDICTION`.

- [ ] **Step 4: Implement timeline assembly**

Group the 50 work nodes by event, sort by `sequence`, retain evidence state without promotion, attach configured path IDs by phase/action, and add daily-resolution records when multiple verified nodes share a date and daily data cannot separate them.

- [ ] **Step 5: Implement core-path assembly**

Resolve each configured path to a verified primary or secondary anchor. If its configured phase only has pending nodes, keep the path `PROPOSED` but set `scoring_eligible=false` and `anchor_evidence_status=PENDING_EVIDENCE`. Never assign a pending node to a scored path.

- [ ] **Step 6: Add official mechanism sources**

Use AnySearch with official-domain queries for these ten topics: pandemic financial/energy channels; Ukraine energy/inflation channels; Federal Reserve rate transmission; China lockdown growth/commodity demand; banking stress and financial conditions; OPEC+ supply transmission; Middle East energy/shipping risk; BOJ normalization and yen differentials; China stimulus and FX; tariff costs and inflation. Save publisher, URL, publication time, locator, quote, scope and prediction visibility in the configuration. Reject search-result URLs, missing publishers and snippets without an original page.

- [ ] **Step 7: Run assembler tests**

Expected: PASS with 50 nodes, 8 pending nodes and 35 source-resolved paths.

### Task 4: Build Six-Window Market Packages

**Files:**
- Modify: `code/build_fingoose_ten_event_rapid_candidate_v2.py`
- Modify: `tests/test_build_fingoose_ten_event_rapid_candidate_v2.py`
- Read: `data/market_event_attribution_v2_candidate/market_windows.jsonl`
- Read: `evidence_snapshots/macro_event_attribution_v1/market/fred/*.csv`

- [ ] **Step 1: Add failing market tests**

```python
def test_market_packages_have_four_core_series_and_six_display_windows(self):
    from build_fingoose_ten_event_rapid_candidate_v2 import build_market_packages
    packages = build_market_packages(ROOT)
    self.assertEqual(set(packages), {f"event-{i:02d}" for i in range(1, 11)})
    for event_id, rows in packages.items():
        self.assertEqual(len([row for row in rows if row["asset_tier"] == "CORE"]), 4)
        for row in rows:
            self.assertEqual(
                list(row["display_windows"]),
                ["T-1", "T0", "D1", "D3", "D5", "D20"],
            )
            self.assertIsNotNone(row["display_windows"]["T-1"]["value"])
            self.assertTrue(row["formulas"]["raw_change"])
            self.assertEqual(row["daily_t0_rule"], "T0_CLOSE_EQUALS_D1")
```

- [ ] **Step 2: Run market tests**

Expected: ERROR because `build_market_packages` does not exist.

- [ ] **Step 3: Implement production-window projection**

For production series, project `T1` to `T-1`, duplicate `D1` as the explicitly labeled `T0` alias, and retain `D3/D5/D20`. Preserve absolute values, raw/standardized/relative changes, formulas, date, calendar, timezone and source path. Mark percentile values `DEFERRED_VALIDATION` and exclude them from validation counts.

- [ ] **Step 4: Implement event-02 natural-gas extension**

Read local `DHHNGSP.csv` and call `compute_enhanced_market_window` with `t0_session="2022-02-24"`, `metric_type="price_return_pct"`, and Brent as the preselected benchmark. Include DGS10 as `OPTIONAL_EXTENSION`; do not count it among event-02's four core assets.

- [ ] **Step 5: Run market tests**

Expected: PASS for all ten event packages.

### Task 5: Register Material Confounders And Stage Mappings

**Files:**
- Modify: `code/fingoose_ten_event_rapid_config.py`
- Modify: `code/build_fingoose_ten_event_rapid_candidate_v2.py`
- Modify: `tests/test_build_fingoose_ten_event_rapid_candidate_v2.py`

- [ ] **Step 1: Add failing confounder and mapping tests**

```python
def test_material_confounders_route_long_windows_out_of_clean_scoring(self):
    from build_fingoose_ten_event_rapid_candidate_v2 import (
        build_confounders, build_stage_mappings, build_timelines,
    )
    confounders = build_confounders()
    mappings = build_stage_mappings(build_timelines(ROOT))
    self.assertEqual(set(confounders), {f"event-{i:02d}" for i in range(1, 11)})
    self.assertTrue(all(rows["clean_attribution_decision"] in {
        "CHALLENGE_ONLY", "WINDOW_DEPENDENT", "UNRESOLVED"
    } for rows in confounders.values()))
    self.assertTrue(all(len(mappings[event_id]["node_mappings"]) == 5 for event_id in mappings))
    self.assertTrue(any(
        level == "DOMINANT"
        for row in confounders.values() for level in row["by_horizon"].values()
    ))
```

- [ ] **Step 2: Run the test**

Expected: ERROR because the two functions do not exist.

- [ ] **Step 3: Define event-specific important confounders**

For every event, register only overlapping developments assessed as `MATERIAL`, `DOMINANT` or `UNRESOLVED`. Each item includes `active_from`, `description`, `affected_path_ids`, `affected_windows`, and source IDs. D20 cannot be marked clean when it includes later policy meetings, sanctions, ongoing conflict or independent macro releases.

- [ ] **Step 4: Generate stage-to-path-to-market mappings**

For every node output its phase, action, affected core path IDs, affected core series IDs and one of `NOT_COMPUTED / PRIMARY_ANCHOR / SAME_DAY_UNRESOLVED / OUTSIDE_PRIMARY_ANCHOR_WINDOW / PENDING_EVIDENCE`. Generate mappings from config and node state rather than copying event-02 labels.

- [ ] **Step 5: Run confounder and mapping tests**

Expected: PASS for 10 confounder packages and 50 node mappings.

### Task 6: Generate Ten Event Pages And The Overview

**Files:**
- Modify: `code/build_fingoose_ten_event_rapid_candidate_v2.py`
- Modify: `tests/test_build_fingoose_ten_event_rapid_candidate_v2.py`
- Create: `work/ten_event_rapid_candidate_v2/index.html`
- Create: `work/ten_event_rapid_candidate_v2/events/event-01/` through `event-10/`

- [ ] **Step 1: Add failing output and HTML tests**

```python
def test_build_emits_ten_event_pages_and_overview(self):
    import tempfile
    from build_fingoose_ten_event_rapid_candidate_v2 import build
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "ten_event_rapid_candidate_v2"
        report = build(ROOT, output)
        self.assertEqual(report["event_count"], 10)
        self.assertEqual(report["hard_failures"], [])
        self.assertTrue((output / "index.html").exists())
        for index in range(1, 11):
            event_root = output / "events" / f"event-{index:02d}"
            self.assertTrue((event_root / "index.html").exists())
            page = (event_root / "index.html").read_text(encoding="utf-8")
            for token in (
                "事实来源", "事件事实依据", "机制依据", "绝对值与变化",
                "target=\"_blank\"", "rel=\"noopener noreferrer\"",
            ):
                self.assertIn(token, page)
```

- [ ] **Step 2: Run output tests**

Expected: FAIL because `build` and the pages do not exist.

- [ ] **Step 3: Extract the shared event-page template**

Move event-02's A-layout behavior into a pure `render_event_page(payload)` function. The function receives timeline, paths, windows, confounders, mapping and sources, and returns one standalone HTML string. It must not contain event-02-specific titles, timestamps or path IDs.

- [ ] **Step 4: Build each event package**

For each event write `timeline.json`, `core_transmission_paths.json`, `market_windows.jsonl`, `confounders.json`, `stage_edge_market_map.json`, `sources.json`, `validation_report.json` and `index.html`.

- [ ] **Step 5: Build the overview**

Render one row per event with title, verified/pending node counts, core path count, core/extension asset counts, challenge status and validation status. Link rows to `events/event-XX/index.html`. The first viewport must show event-01 through at least event-05 on desktop and event-01 through event-03 on mobile.

- [ ] **Step 6: Run output tests**

Expected: PASS with 10 event pages and one overview.

### Task 7: Validate, Rebuild, And Visually Inspect

**Files:**
- Regenerate: `work/ten_event_rapid_candidate_v2/`
- Verify: `work/ten_event_rapid_candidate_v2/validation_report.json`

- [ ] **Step 1: Implement hard-failure validation**

Return hard failures for missing event IDs, node counts other than 5, multiple/no primary anchors, unresolved sources on verified nodes or core paths, non-`PROPOSED` paths, missing direction/lag/conditions/invalidation/counterevidence, core asset counts other than 4, missing six-window keys, numeric values without dates, pending nodes marked scoring eligible, and page files missing.

- [ ] **Step 2: Build the final independent output**

```powershell
python code/build_fingoose_ten_event_rapid_candidate_v2.py
```

Expected report:

```text
release_tier=RAPID_CANDIDATE
formal_ready=false
production_dataset_modified=false
event_count=10
timeline_node_count=50
core_path_count=35
confirmed_path_count=0
hard_failures=[]
```

- [ ] **Step 3: Run focused and regression tests**

```powershell
python -m unittest tests.test_build_fingoose_event_02_rapid_candidate_v2 tests.test_build_fingoose_ten_event_rapid_candidate_v2 tests.test_build_fingoose_24_anchor_transmission_graphs tests.test_build_fingoose_macro_event_attribution_v2 -v
```

Expected: all tests pass with zero failures.

- [ ] **Step 4: Render desktop and mobile screenshots**

Use Edge headless mode at `1440x1000` and `390x844` for the overview and each event page, producing 22 PNG files under `work/ten_event_rapid_candidate_v2/qa/`.

- [ ] **Step 5: Run screenshot pixel and dimension checks**

Use Pillow to confirm every image has the requested dimensions, more than 200 unique colors, dominant-color ratio below 0.95, and content-pixel ratio above 0.05. Inspect the overview plus event-01, event-02, event-05 and event-10 screenshots for wrapping, overflow and citation placement.

- [ ] **Step 6: Verify source and JSON integrity**

Parse every JSON/JSONL file, resolve all verified/core source IDs to non-empty original URLs, confirm pending nodes have no clickable source link, and ensure validation reports contain no hard failures.

- [ ] **Step 7: Record the accurate release statement**

Update the root README to state: 10 events, 50 nodes, 35 core candidate paths, 40 core asset packages plus one event-02 extension, eight input-derived pending nodes if unchanged after rebuild, `formal_ready=false`, `confirmed_path_count=0`, long-tail edge review deferred, percentile/SHA gates deferred by user.
