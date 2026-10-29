# FinGoose Ten-Event Industry Impact Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a separate, evidence-auditable 77-record event-to-industry candidate layer and integrate it into the existing Chinese research workbench.

**Architecture:** Keep existing company and legacy industry candidates unchanged. Build six normalized JSONL outputs under a new candidate directory, then join them into the company-impact UI by stable `event_industry_mapping_id` values.

**Tech Stack:** Python 3, JSON/JSONL, `unittest`/`pytest`, static HTML/CSS/JavaScript.

---

## Confirmed Decisions

- Freeze 77 mappings across ten events with mutually exclusive `CORE_DIRECT`, `SECOND_ORDER`, and `CONDITIONAL` tiers.
- Use the event-date Shenwan L1 code as the data key and a normalized Chinese alias plus segment labels for display.
- Store one seven-step mechanism chain per mapping: event fact, behavior/policy change, observable driver, industry operating variable, revenue/cost variable, three-horizon direction, and price/confounder verification.
- Keep source facts separate from research inferences. Missing evidence or market data remains explicit and blocks candidate completion.
- Compare the industry benchmark with CSI 300 on a continuous T-20 to D20 chart normalized at the common T-1 date. Keep M3 in the fixed-window table.
- Add an optional per-mapping primary driver, with at most one secondary driver. Driver series never determine selection or direction.
- Keep `PROPOSED`, `NEEDS_HUMAN_REVIEW`, `formal_ready=false`, and `sha_gate=DEFERRED` throughout this delivery.

## Deliverables

- `event_industry_mappings.jsonl`
- `industry_mechanism_chains.jsonl`
- `industry_evidence.jsonl`
- `industry_driver_registry.jsonl`
- `industry_market_windows.jsonl`
- `industry_completion_report.jsonl`
- Chinese UI tabs for direct, second-order, and conditional industries.
- A third transmission view named `行业板块链` and a detailed industry research panel.

## Execution Order

1. Add failing schema and coverage tests.
2. Implement stable profile loading, validation, and six-file candidate generation.
3. Validate event-01, event-05, and event-10 as vertical mechanism/UI examples.
4. Expand the same schema to the remaining seven events.
5. Add market-window ingestion and deterministic normalization without zero imputation.
6. Join the industry layer into the existing company UI without overwriting company records.
7. Run targeted, full-suite, desktop, and mobile verification.

## Release Gates

A mapping is `CANDIDATE_COMPLETE` only when the verified anchor, seven-step chain, evidence/inference boundary, three-horizon direction or explicit abstention, recomputable market windows, and confounder review are all complete. Otherwise it remains `OPEN` with blockers. Market outcomes may validate but never select an industry or set its direction.
