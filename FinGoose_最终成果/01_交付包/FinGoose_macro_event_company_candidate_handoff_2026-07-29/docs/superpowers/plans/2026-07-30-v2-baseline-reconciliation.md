# FinGoose v2 Baseline Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Make v2 builds reproducible, isolate tests from production data, and generate an auditable baseline transition without overwriting production.

**Architecture:** Inject deterministic build metadata into the existing builder, redirect tests to temporary outputs, and add a read-only reconciliation module that writes only to work/baseline_reconciliation_v2. Production adoption remains a separate approval gate.

**Tech Stack:** Python standard library, unittest, JSON/JSONL, SHA-256.

---

### Task 1: Reproducible and isolated v2 builds

**Files:**
- Modify: code/build_fingoose_macro_event_attribution_v2.py
- Modify: tests/test_build_fingoose_macro_event_attribution_v2.py

- [ ] Add failing tests proving build_dataset accepts a fixed generated_at and optional release_manifest_path.
- [ ] Run the focused tests and confirm TypeError or a production-isolation assertion.
- [ ] Add generated_at and release_manifest_path parameters, using one timestamp for both manifests.
- [ ] Move test output and release manifest into TemporaryDirectory.
- [ ] Run the focused tests twice and verify production tree hashes remain unchanged.

### Task 2: Read-only baseline reconciliation

**Files:**
- Create: code/fingoose_v2_baseline_reconcile.py
- Create: tests/test_fingoose_v2_baseline_reconcile.py

- [ ] Add failing tests for valid manifest, hash mismatch, record-count mismatch, missing file, and path escape.
- [ ] Implement manifest inventory validation using resolved paths constrained to the data root.
- [ ] Implement deterministic manifest.rebuilt.json and baseline_transition.json generation.
- [ ] Verify the module writes only to the supplied work output directory.

### Task 3: Reconcile current candidate and regress

**Files:**
- Create: work/baseline_reconciliation_v2/manifest.rebuilt.json
- Create: work/baseline_reconciliation_v2/baseline_transition.json
- Create: work/baseline_reconciliation_v2/README.md
- Modify: work/timeline_fast_candidate_v2/validation_report.json (generated only)

- [ ] Run reconciliation against current v2 data and frozen hash 9d9a6f233ef0ef24c65c7248de487e711574108b179231e3f9ff869048d8a.
- [ ] Confirm every manifest entry matches the current file bytes and record count.
- [ ] Re-run supplemental source validation so manifest drift remains explicit until baseline adoption.
- [ ] Run focused and regression tests; record exact pass/fail counts.
- [ ] Stop before overwriting production manifest or changing formal_ready.