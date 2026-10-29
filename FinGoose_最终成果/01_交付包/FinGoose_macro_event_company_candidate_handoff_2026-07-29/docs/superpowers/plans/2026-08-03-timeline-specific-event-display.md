# Timeline Specific Event Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Give all 50 timeline nodes a concrete Chinese event title and summary, while retaining technical lineage in a secondary disclosure.

**Architecture:** Keep upstream evidence records immutable. A reviewed JSONL display profile keyed by `fast_node_id` is loaded during UI bundle construction, validated for exact one-to-one coverage, and merged into the public timeline projection. The renderer promotes the concrete title and Chinese summary while moving IDs and original facts into a collapsible technical section.

**Tech Stack:** Python 3, JSONL, `unittest`/pytest, generated static HTML/CSS/JavaScript.

---

### Task 1: Specify and validate the display-profile contract

**Files:**
- Modify: `tests/test_fingoose_company_impact_ui_v2.py`
- Modify: `code/fingoose_company_impact_ui_v2.py`

- [x] **Step 1: Write the failing tests**

Add tests asserting that the projected 50 nodes all contain non-empty `event_title_zh` and `event_summary_zh`, IDs are unique, titles contain Chinese characters, and no title contains `fast-event-` or equals a translated phase label. Add event-02 assertions for concrete titles describing the military operation, NATO confirmation, sanctions/energy response, and subsequent event stages.

- [x] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
python -m pytest tests/test_fingoose_company_impact_ui_v2.py -q
```

Expected: the new assertions fail because `timeline_display_profiles.jsonl` is not loaded and projected nodes lack the two display fields.

- [x] **Step 3: Add strict loader validation**

Load `configs/company_impact_high_quality_v2/timeline_display_profiles.jsonl`, index it by `fast_node_id`, reject duplicate IDs, reject missing/extra IDs against upstream timeline rows, reject empty display fields, and merge only `event_title_zh` and `event_summary_zh` into copied timeline rows.

- [x] **Step 4: Re-run the focused tests**

Expected: profile-loading tests remain RED only because the profile file has not yet been created; existing unrelated tests continue to pass.

### Task 2: Author all 50 reviewed Chinese display profiles

**Files:**
- Create: `configs/company_impact_high_quality_v2/timeline_display_profiles.jsonl`

- [x] **Step 1: Extract the exact 50-node inventory**

Read each node's `event_id`, `fast_node_id`, `phase`, `occurred_at`, `fact`, evidence quote, publisher, and source URL from `work/verifiable_evaluation_phase1_v2_candidate/timeline_nodes.jsonl`.

- [x] **Step 2: Write one profile per node**

Each JSONL row must use:

```json
{"fast_node_id":"fast-event-02-M01R1","event_id":"event-02","event_title_zh":"俄罗斯宣布对乌克兰开展‘特别军事行动’","event_summary_zh":"俄罗斯总统在官方讲话中宣布开展‘特别军事行动’，构成俄乌冲突全面升级的首次公开冲击。"}
```

Titles must name a subject and action. Summaries must stay within the cited fact and may not manufacture precision or causal certainty.

- [x] **Step 3: Run the focused tests and verify GREEN for data projection**

Run the Task 1 command. Expected: all projection assertions pass.

### Task 3: Render the concrete event first and technical metadata second

**Files:**
- Modify: `tests/test_fingoose_company_impact_ui_v2.py`
- Modify: `code/fingoose_company_impact_ui_v2.py`
- Generate: `work/company_impact_high_quality_v2_candidate/ui/index.html`
- Generate: `work/company_impact_high_quality_v2_candidate/ui/ui_data_bundle.js`

- [x] **Step 1: Write failing HTML assertions**

Assert that rendered HTML uses `node.event_title_zh` in the timeline heading, renders phase/time/precision as metadata, renders `event_summary_zh`, includes a Chinese “技术详情” disclosure with `fast_node_id` and original `fact`, and does not concatenate phase and ID in the heading.

- [x] **Step 2: Run the focused tests and verify RED**

Expected: failure against the current `${phase} · ${fast_node_id}` heading.

- [x] **Step 3: Implement the renderer and responsive styles**

Update `renderTimeline()` so the hierarchy is title, metadata, summary, chips/evidence, and `<details>` technical lineage. Add stable wrapping and mobile rules without viewport-scaled font sizes.

- [x] **Step 4: Run tests and rebuild the static UI**

Run:

```powershell
python -m pytest tests/test_fingoose_company_impact_ui_v2.py -q
python code/fingoose_company_impact_ui_v2.py --root . --output work/company_impact_high_quality_v2_candidate/ui
```

Expected: tests pass and both UI artifacts are regenerated.

### Task 4: Verify content, interaction, and publication boundaries

**Files:**
- Modify: `work/company_impact_high_quality_v2_candidate/validation_report.json` only if the existing build pipeline owns this report

- [x] **Step 1: Run the relevant regression suite**

```powershell
python -m pytest tests/test_fingoose_company_impact_ui_v2.py tests/test_fingoose_company_mechanism_chain_v2.py tests/test_build_fingoose_company_mechanism_chains_v2.py -q
```

Expected: all selected tests pass.

- [x] **Step 2: Verify release-boundary strings**

```powershell
rg -n '"formal_ready":true|"sha_gate":"ENFORCED"|"chain_status":"CONFIRMED"' work/company_impact_high_quality_v2_candidate -g '*.json' -g '*.jsonl'
```

Expected: no matches.

- [x] **Step 3: Browser-check desktop and 390px mobile**

Check all ten events, especially all five event-02 nodes. Confirm concrete Chinese titles, working official links, node-to-path filtering, collapsed technical detail, no console errors, and no horizontal overflow.

