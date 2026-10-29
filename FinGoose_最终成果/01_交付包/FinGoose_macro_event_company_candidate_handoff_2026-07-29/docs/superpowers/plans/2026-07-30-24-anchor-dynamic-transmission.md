# 24-Anchor Dynamic Transmission Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build an isolated ten-event dynamic transmission candidate that uses exactly the 24 `VERIFIED_EXISTING` timeline nodes as the stable anchor directory and excludes all 26 pending nodes from active graph bindings.

**Architecture:** Keep the production v2 graph files read-only. Reuse their validated four-layer graph topology, add an append-only anchor catalog and dynamic edge-binding overlay, and write all derived records to `work/transmission_24_anchor_v2_candidate/`. Causal bindings remain `PROPOSED`; `OBSERVES` anchors never create causal bindings.

**Tech Stack:** Python standard library, JSON/JSONL, existing FinGoose v2 graph validator and JSON Schema, SHA-256, unittest.

---

### Task 1: Lock the 24-anchor contract with failing tests

**Files:**
- Create: `tests/test_build_fingoose_24_anchor_transmission_graphs.py`
- Create: `code/build_fingoose_24_anchor_transmission_graphs.py`

- [x] **Step 1: Add a failing anchor-catalog test**

The test loads `work/timeline_fast_candidate_v2/timeline_nodes.jsonl`, calls `build_anchor_catalog()`, and asserts:

```python
self.assertEqual(len(anchors), 24)
self.assertEqual({row['evidence_status'] for row in anchors}, {'VERIFIED_EXISTING'})
self.assertEqual(sum(row['activation_mode'] == 'OBSERVATION_ONLY' for row in anchors), 10)
self.assertEqual(sum(row['activation_mode'] == 'CAUSAL_CANDIDATE' for row in anchors), 14)
self.assertFalse(set(pending_fast_node_ids) & {row['fast_node_id'] for row in anchors})
```

- [x] **Step 2: Run the test and verify RED**

Run:

```powershell
$env:PYTHONPATH = (Resolve-Path code)
python -m unittest tests/test_build_fingoose_24_anchor_transmission_graphs.py -v
```

Expected: import failure because the builder does not exist.

- [x] **Step 3: Implement stable anchor resolution**

Implement `build_anchor_catalog(timeline_nodes, promotable_milestones)` so original nodes use `original_milestone_id`, supplemental accepted nodes resolve their milestone through the supplemental evidence ID, all anchors retain both timestamps and source IDs, and pending nodes are excluded.

- [x] **Step 4: Run the focused test and verify GREEN**

Expected: the anchor-catalog test passes with 24 anchors, 10 observation-only and 14 causal candidates.

### Task 2: Build dynamic edge bindings without inventing confirmation

**Files:**
- Modify: `tests/test_build_fingoose_24_anchor_transmission_graphs.py`
- Modify: `code/build_fingoose_24_anchor_transmission_graphs.py`

- [x] **Step 1: Add failing dynamic-binding tests**

Assert that every causal anchor has at least one binding, observation-only anchors have none, every edge ID resolves in the ten production graphs, all binding states are `PROPOSED`, and no pending fast node appears.

- [x] **Step 2: Run the test and verify RED**

Expected: failure because `build_dynamic_bindings()` is missing.

- [x] **Step 3: Implement minimal binding logic**

For original anchors, bind the existing graph edges whose `anchor_milestone_id` matches. For the accepted CPI supplement `fast-event-03-M02`, bind only the event-03 shock-to-`RATE_EXPECTATIONS` entry edge. Reject any causal anchor with zero resolved bindings. Copy conditions, invalidation conditions, lag, expected path, source citations, and counterevidence status without changing edge directions.

- [x] **Step 4: Run focused tests and verify GREEN**

Expected: all dynamic-binding tests pass and every generated state is `PROPOSED`.

### Task 3: Add Data-CI validation and deterministic artifacts

**Files:**
- Modify: `tests/test_build_fingoose_24_anchor_transmission_graphs.py`
- Modify: `code/build_fingoose_24_anchor_transmission_graphs.py`
- Create: `work/transmission_24_anchor_v2_candidate/anchor_catalog.jsonl`
- Create: `work/transmission_24_anchor_v2_candidate/transmission_graphs.jsonl`
- Create: `work/transmission_24_anchor_v2_candidate/dynamic_edge_bindings.jsonl`
- Create: `work/transmission_24_anchor_v2_candidate/validation_report.json`
- Create: `work/transmission_24_anchor_v2_candidate/manifest.json`
- Create: `work/transmission_24_anchor_v2_candidate/README.md`

- [x] **Step 1: Add failing hard-gate tests**

Mutate fixtures to introduce a pending anchor, observation-only binding, unknown edge, missing source, duplicate binding ID, `CONFIRMED` state, and source hash mismatch. Assert each becomes a named hard failure.

- [x] **Step 2: Run the test and verify RED**

Expected: validation tests fail because `validate_projection()` is missing.

- [x] **Step 3: Implement validation and deterministic writes**

Validation must enforce exact counts, ten-event coverage, source resolution, timestamp presence, no pending leakage, observation-only isolation, causal anchor coverage, graph validity, all-`PROPOSED` status, unique stable IDs, and unchanged production hashes. Manifest entries contain path, record count and SHA-256.

- [x] **Step 4: Generate the isolated candidate**

Run:

```powershell
$env:PYTHONPATH = (Resolve-Path code)
python code/build_fingoose_24_anchor_transmission_graphs.py --root .
```

Expected: `hard_failures=[]`, `anchor_count=24`, `event_count=10`, `formal_ready=false`.

### Task 4: Regression and handoff

**Files:**
- Modify: `work/transmission_24_anchor_v2_candidate/README.md` through the deterministic builder only.

- [x] **Step 1: Run focused tests**

Run the new test file and expect zero failures.

- [x] **Step 2: Run existing v2 graph regression**

Run `test_fingoose_macro_event_attribution_v2.py`, `test_build_fingoose_macro_event_attribution_v2.py`, and the supplemental timeline tests.

- [x] **Step 3: Recompute production hashes**

Verify the SHA-256 values remain:

```text
event_milestones.jsonl=2fafc57e304f810ef24c65c7248de487e711574108b179231e3f9ff869048d8a
event_episodes.jsonl=32626f4dd798c315ee1529581e31165369826c4119c5fd51fa82442623b4349b
manifest.json=3c0cd2d56aed32ac518231fb855dc69dc23c37f73e5b645ff1b84e4bdb48f4d1
```

- [x] **Step 4: Report the boundary**

State explicitly that the ten-event structure is complete, anchor evidence is real, bindings are proposals, and future work promotes evidence status without changing stable IDs.
