# FinGoose Evidence, Market, and Causal Closure v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 94 条由证据传递与别名解析造成的开放推理链，补齐 77 条行业行情和 30 条公司可复核相对收益，并以 `NOT_IDENTIFIED + ABSTAIN` 严格限制未识别的因果归因。

**Architecture:** 在现有 versioned implementation 模式上新增三个独立模块：`evidence_closure.py` 负责证据合并与里程碑别名，`market_enrichment.py` 负责同日期同基期的行业/市场基准对齐和公司相对收益，`causal_identification.py` 负责四级因果门控。`research_content_impl_004.py` 和 `unified_builder_impl_008.py` 只负责编排，答案与验证分别通过新版本实现文件消费统一主数据，不直接修改生成 JSONL。

**Tech Stack:** Python 3.12、标准库 `copy`/`decimal`/`json`/`pathlib`/`typing`、pytest、现有 JSONL 构建与验证脚本、静态 UI JSON bundle。

**Repository note:** 当前项目目录不是 Git 仓库。以下每个任务以定向测试和文件 SHA 作为检查点，不执行虚假 `git commit`；若执行时发现目录已初始化为 Git 仓库，再按任务边界分别提交。

---

## 文件结构

- Create `training/fingoose_training/evidence_closure.py`：严格合并证据，解析 original/fast/supplemental 里程碑证据别名。
- Create `training/fingoose_training/market_enrichment.py`：连接行业窗口，按公司实际日期和共同基期计算相对收益。
- Create `training/fingoose_training/causal_identification.py`：计算四级因果识别状态和 `ABSTAIN` 门控。
- Create `training/fingoose_training/research_content_impl_004.py`：把行情与因果结构接入 `research-content-v1`。
- Create `training/fingoose_training/unified_builder_impl_008.py`：使用事件完整证据编译事件、行业和公司链。
- Create `training/fingoose_training/answer_renderer_impl_007.py`：展示绝对/相对行情、计算边界和因果弃答。
- Modify `training/fingoose_training/sft_projector_impl_013.py`：将新 renderer 接入现有四类投影流程。
- Create `training/fingoose_training/validation_impl_006.py`：验证证据闭环原因、行情回算和因果门控。
- Modify `training/fingoose_training/research_content/__init__.py`：公开 `research_content_impl_004`。
- Modify `training/fingoose_training/unified_builder/__init__.py`：公开 `unified_builder_impl_008`。
- Modify `training/fingoose_training/validation/__init__.py`：公开 `validation_impl_006`。
- Create `training/tests/test_evidence_closure.py`。
- Create `training/tests/test_market_enrichment.py`。
- Create `training/tests/test_causal_identification.py`。
- Create `training/tests/test_evidence_market_causal_projection.py`。
- Modify `training/tests/test_sft_real_reasoning_dataset_v1.py`。
- Modify `training/tests/test_content_alignment_validation.py`。
- Modify `training/README.md`。
- Generated `training/data/unified_events.jsonl`、`training/data/sft_dataset.jsonl`、`training/data/manifest.json`、`training/data/split_manifest.json`、`training/data/validation_report.json`。
- Create `docs/superpowers/plans/2026-08-11-evidence-market-causal-closure-v1-execution-report.md`。

---

### Task 1: 严格证据合并与里程碑别名

**Files:**
- Create: `training/fingoose_training/evidence_closure.py`
- Create: `training/tests/test_evidence_closure.py`

- [ ] **Step 1: 写证据继承失败测试**

```python
from fingoose_training.evidence_closure import merge_evidence_records


def test_child_sparse_reference_inherits_complete_event_evidence():
    event = [{
        "evidence_id": "event-official-1",
        "original_quote": "Official text",
        "locator": "section 2",
        "source_url": "https://example.test/official",
    }]
    child = [{"evidence_id": "event-official-1"}]

    merged = merge_evidence_records(event, child)

    assert merged == [{
        "evidence_id": "event-official-1",
        "original_quote": "Official text",
        "locator": "section 2",
        "source_url": "https://example.test/official",
        "missing": False,
    }]
```

- [ ] **Step 2: 写冲突和别名失败测试**

```python
import pytest

from fingoose_training.evidence_closure import (
    EvidenceClosureError,
    bind_milestone_evidence_aliases,
    merge_evidence_records,
)


def test_conflicting_complete_source_urls_fail_closed():
    with pytest.raises(EvidenceClosureError, match="source_url conflict"):
        merge_evidence_records(
            [{"evidence_id": "e1", "source_url": "https://a.test"}],
            [{"evidence_id": "e1", "source_url": "https://b.test"}],
        )


def test_fast_evidence_is_bound_to_canonical_milestone():
    milestones = [{
        "milestone_id": "milestone-event-03-main",
        "sources": [{"evidence_id": "old-incomplete"}],
    }]
    aliases = {
        "milestone-event-03-main": ["supplemental-fast-event-03-M04"]
    }
    bound = bind_milestone_evidence_aliases(milestones, aliases)
    assert {row["evidence_id"] for row in bound[0]["sources"]} == {
        "old-incomplete", "supplemental-fast-event-03-M04"
    }
```

- [ ] **Step 3: 运行 RED 测试**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests/test_evidence_closure.py -q
```

Expected: FAIL，原因是 `fingoose_training.evidence_closure` 尚不存在。

- [ ] **Step 4: 实现严格合并与缺失判定**

```python
from copy import deepcopy
from typing import Mapping


CRITICAL_FIELDS = ("original_quote", "locator", "source_url")


class EvidenceClosureError(ValueError):
    pass


def _normalized_record(record):
    return {
        "evidence_id": str(record.get("evidence_id") or record.get("source_id")),
        "original_quote": record.get("original_quote") or record.get("quote"),
        "locator": record.get("locator") or record.get("locator_zh")
        or record.get("page_or_section_locator"),
        "source_url": record.get("source_url") or record.get("url"),
        **{
            key: deepcopy(value)
            for key, value in record.items()
            if key not in {"source_id", "quote", "locator_zh", "url", "missing"}
        },
    }


def merge_evidence_records(*groups):
    merged = {}
    for record in (row for group in groups for row in group if isinstance(row, Mapping)):
        clean = _normalized_record(record)
        evidence_id = clean["evidence_id"]
        if not evidence_id:
            continue
        current = merged.setdefault(evidence_id, {"evidence_id": evidence_id})
        for field, value in clean.items():
            if value in (None, "", []):
                continue
            if field in CRITICAL_FIELDS and current.get(field) not in (None, "", value):
                raise EvidenceClosureError(
                    f"evidence_id={evidence_id}: {field} conflict"
                )
            if field == "supports_node_ids":
                current[field] = sorted(set(current.get(field) or []) | set(value))
            elif current.get(field) in (None, "", []):
                current[field] = deepcopy(value)
    for current in merged.values():
        current["missing"] = not all(current.get(field) for field in CRITICAL_FIELDS)
    return [merged[key] for key in sorted(merged)]


def build_milestone_evidence_aliases(timeline):
    aliases = {}
    for row in timeline:
        if not isinstance(row, Mapping):
            continue
        canonical = str(row.get("original_milestone_id") or "")
        if not canonical:
            continue
        evidence_ids = {
            str(evidence.get("evidence_id") or evidence.get("source_id"))
            for evidence in row.get("evidence") or []
            if isinstance(evidence, Mapping)
            and (evidence.get("evidence_id") or evidence.get("source_id"))
        }
        if evidence_ids:
            aliases.setdefault(canonical, set()).update(evidence_ids)
    return {key: sorted(value) for key, value in sorted(aliases.items())}


def bind_milestone_evidence_aliases(milestones, aliases):
    result = deepcopy(list(milestones))
    by_id = {str(row.get("milestone_id")): row for row in result}
    unknown = set(aliases) - set(by_id)
    if unknown:
        raise EvidenceClosureError(f"canonical milestone missing: {sorted(unknown)}")
    for milestone_id, evidence_ids in aliases.items():
        sources = by_id[milestone_id].setdefault("sources", [])
        existing = {
            str(row.get("evidence_id") or row.get("source_id"))
            for row in sources if isinstance(row, Mapping)
        }
        sources.extend(
            {"evidence_id": evidence_id}
            for evidence_id in evidence_ids
            if evidence_id not in existing
        )
    return result
```

别名只读取同一事件 timeline 行内显式给出的 `original_milestone_id` 与证据，不进行跨事件或文本相似度猜测。

- [ ] **Step 5: 运行 GREEN 测试并保存检查点**

Run:

```powershell
python -m pytest training/tests/test_evidence_closure.py -q
Get-FileHash -Algorithm SHA256 training/fingoose_training/evidence_closure.py
```

Expected: 全部 PASS；记录文件 SHA 到执行报告草稿。

---

### Task 2: 行业窗口连接与公司可比收益

**Files:**
- Create: `training/fingoose_training/market_enrichment.py`
- Create: `training/tests/test_market_enrichment.py`

- [ ] **Step 1: 写行业窗口唯一映射测试**

```python
import pytest

from fingoose_training.market_enrichment import MarketEnrichmentError, index_industry_windows


def test_industry_windows_are_indexed_by_mapping_id():
    windows = [{"event_industry_mapping_id": "industry-1", "fixed_windows": {}}]
    assert index_industry_windows(windows)["industry-1"] == windows[0]


def test_duplicate_industry_window_mapping_fails():
    rows = [
        {"event_industry_mapping_id": "industry-1"},
        {"event_industry_mapping_id": "industry-1"},
    ]
    with pytest.raises(MarketEnrichmentError, match="duplicate"):
        index_industry_windows(rows)
```

- [ ] **Step 2: 写共同日期与共同基期回算测试**

```python
from fingoose_training.market_enrichment import calculate_company_relative_windows


def test_company_relative_returns_use_company_dates_and_common_base():
    company = {
        "observations": {
            "T_MINUS_1": {"actual_date": "2020-01-01", "absolute_return": 0.0},
            "D1": {"actual_date": "2020-01-02", "absolute_return": 0.10},
        }
    }
    industry = {
        "continuous_window": [
            {"actual_date": "2020-01-01", "industry_value": 2000.0, "market_value": 4000.0},
            {"actual_date": "2020-01-02", "industry_value": 2060.0, "market_value": 4040.0},
        ]
    }

    result = calculate_company_relative_windows(company, industry)
    d1 = result["D1"]
    assert d1["formula_inputs"] == {
        "company_absolute_return": 0.10,
        "industry_base_value": 2000.0,
        "industry_value": 2060.0,
        "market_base_value": 4000.0,
        "market_value": 4040.0,
    }
    assert d1["market_relative_return"] == pytest.approx(0.09)
    assert d1["industry_relative_return"] == pytest.approx(0.07)
```

- [ ] **Step 3: 写缺失传播和日期错配测试**

```python
def test_missing_benchmark_date_stays_missing_not_zero():
    result = calculate_company_relative_windows(
        {"observations": {
            "T_MINUS_1": {"actual_date": "2020-01-01", "absolute_return": 0.0},
            "D1": {"actual_date": "2020-01-03", "absolute_return": 0.10},
        }},
        {"continuous_window": [
            {"actual_date": "2020-01-01", "industry_value": 2000.0, "market_value": 4000.0},
        ]},
    )
    assert result["D1"] == {
        "status": "DATA_MISSING",
        "missing_reason": "BENCHMARK_ACTUAL_DATE_NOT_FOUND:2020-01-03",
    }
```

- [ ] **Step 4: 运行 RED 测试**

Run: `python -m pytest training/tests/test_market_enrichment.py -q`

Expected: FAIL，原因是模块和函数尚不存在。

- [ ] **Step 5: 实现行情连接和公司收益计算**

实现以下公开接口：

```python
from copy import deepcopy


WINDOW_KEYS = ("T0", "D1", "D3", "D5", "D20")


class MarketEnrichmentError(ValueError):
    pass


def index_industry_windows(rows) -> dict[str, dict]:
    result = {}
    for row in rows:
        mapping_id = str(row.get("event_industry_mapping_id") or "")
        if not mapping_id:
            raise MarketEnrichmentError("industry window missing mapping_id")
        if mapping_id in result:
            raise MarketEnrichmentError(f"duplicate industry window: {mapping_id}")
        result[mapping_id] = deepcopy(dict(row))
    return result


def attach_industry_market_windows(industry_impacts, industry_market_windows) -> list[dict]:
    windows = index_industry_windows(industry_market_windows)
    result = []
    for impact in industry_impacts:
        clean = deepcopy(dict(impact))
        mapping_id = str(clean.get("event_industry_mapping_id") or "")
        if mapping_id not in windows:
            raise MarketEnrichmentError(f"industry market window missing: {mapping_id}")
        clean["market_window"] = deepcopy(windows[mapping_id])
        result.append(clean)
    return result


def build_industry_window_sw1_index(rows) -> dict[str, dict]:
    result = {}
    for row in rows:
        benchmark = row.get("benchmark") or {}
        benchmark_id = str(benchmark.get("benchmark_id") or "")
        sw1_id = str(row.get("sw1_id") or row.get("industry_id") or "")
        if not sw1_id and benchmark_id.startswith("SW1-"):
            sw1_id = benchmark_id.split("-", 1)[1]
        if sw1_id:
            if sw1_id in result:
                raise MarketEnrichmentError(f"duplicate industry sw1 window: {sw1_id}")
            result[sw1_id] = deepcopy(dict(row))
    return result


def resolve_company_industry_window(company, windows_by_mapping, windows_by_sw1) -> dict | None:
    binding = company.get("binding_review") or {}
    mapping_id = str(
        binding.get("industry_impact_id")
        or company.get("industry_impact_id")
        or ""
    )
    if mapping_id and mapping_id in windows_by_mapping:
        return deepcopy(windows_by_mapping[mapping_id])
    market = company.get("market_window") or {}
    sw1_id = str(market.get("industry_id") or "")
    return deepcopy(windows_by_sw1.get(sw1_id)) if sw1_id in windows_by_sw1 else None


def calculate_company_relative_windows(company_window, industry_window) -> dict[str, dict]:
    observations = company_window.get("observations") or {}
    base = observations.get("T_MINUS_1") or {}
    base_date = base.get("actual_date")
    by_date = {
        str(row.get("actual_date")): row
        for row in industry_window.get("continuous_window") or []
        if row.get("actual_date")
    }
    result = {}
    for name in WINDOW_KEYS:
        observation = observations.get(name) or {}
        actual_date = observation.get("actual_date")
        if not actual_date:
            result[name] = {"status": "DATA_MISSING", "missing_reason": f"COMPANY_WINDOW_MISSING:{name}"}
            continue
        if not base_date or base_date not in by_date:
            result[name] = {"status": "DATA_MISSING", "missing_reason": f"BENCHMARK_BASE_DATE_NOT_FOUND:{base_date}"}
            continue
        if actual_date not in by_date:
            result[name] = {"status": "DATA_MISSING", "missing_reason": f"BENCHMARK_ACTUAL_DATE_NOT_FOUND:{actual_date}"}
            continue
        company_return = observation.get("absolute_return")
        base_row, target_row = by_date[base_date], by_date[actual_date]
        required = (
            company_return, base_row.get("industry_value"), target_row.get("industry_value"),
            base_row.get("market_value"), target_row.get("market_value"),
        )
        if any(value is None for value in required):
            result[name] = {"status": "DATA_MISSING", "missing_reason": f"FORMULA_INPUT_MISSING:{name}"}
            continue
        industry_return = target_row["industry_value"] / base_row["industry_value"] - 1
        market_return = target_row["market_value"] / base_row["market_value"] - 1
        result[name] = {
            "status": "CALCULATED", "actual_date": actual_date,
            "formula_version": "company-relative-v1",
            "formula_inputs": {
                "company_absolute_return": company_return,
                "industry_base_value": base_row["industry_value"],
                "industry_value": target_row["industry_value"],
                "market_base_value": base_row["market_value"],
                "market_value": target_row["market_value"],
            },
            "industry_return": industry_return,
            "market_return": market_return,
            "industry_relative_return": company_return - industry_return,
            "market_relative_return": company_return - market_return,
        }
    return result
```

`calculate_company_relative_windows()` 必须使用公司 `T_MINUS_1.actual_date` 作为共同基期，并从行业 `continuous_window` 中按实际日期取行业值和沪深300值。每个窗口保存 `actual_date`、`formula_version="company-relative-v1"`、`formula_inputs`、`market_return`、`industry_return`、`market_relative_return`、`industry_relative_return` 和 `status`。数值计算使用 Python `float` 并保留原始精度，展示时才格式化；任何输入缺失返回 `DATA_MISSING` 和稳定原因码。

- [ ] **Step 6: 运行 GREEN 测试并保存检查点**

Run:

```powershell
python -m pytest training/tests/test_market_enrichment.py -q
Get-FileHash -Algorithm SHA256 training/fingoose_training/market_enrichment.py
```

Expected: 全部 PASS。

---

### Task 3: 四级因果识别与弃答门控

**Files:**
- Create: `training/fingoose_training/causal_identification.py`
- Create: `training/tests/test_causal_identification.py`

- [ ] **Step 1: 写四级状态失败测试**

```python
from fingoose_training.causal_identification import classify_causal_identification


DESCRIPTIVE_GATES = {
    "market_windows_complete": True,
    "market_benchmark_complete": True,
    "industry_benchmark_complete": True,
    "continuous_trading_verified": True,
}


def test_incomplete_market_is_not_identified_and_abstains():
    result = classify_causal_identification({})
    assert result["status"] == "NOT_IDENTIFIED"
    assert result["causal_attribution_allowed"] is False
    assert result["causal_conclusion"] == "ABSTAIN"


def test_complete_descriptive_event_study_still_abstains():
    result = classify_causal_identification(DESCRIPTIVE_GATES)
    assert result["status"] == "DESCRIPTIVE_EVENT_STUDY"
    assert result["causal_conclusion"] == "ABSTAIN"


def test_quasi_candidate_still_abstains():
    result = classify_causal_identification({
        **DESCRIPTIVE_GATES,
        "comparison_group_defined": True,
        "pretrend_passed": True,
        "confounders_controlled": True,
    })
    assert result["status"] == "QUASI_EXPERIMENTAL_CANDIDATE"
    assert result["causal_attribution_allowed"] is False


def test_only_all_identification_gates_allow_attribution():
    result = classify_causal_identification({
        **DESCRIPTIVE_GATES,
        "comparison_group_defined": True,
        "pretrend_passed": True,
        "confounders_controlled": True,
        "robustness_passed": True,
        "counterevidence_passed": True,
    })
    assert result["status"] == "IDENTIFIED"
    assert result["causal_attribution_allowed"] is True
    assert result["causal_conclusion"] != "ABSTAIN"
```

- [ ] **Step 2: 运行 RED 测试**

Run: `python -m pytest training/tests/test_causal_identification.py -q`

Expected: FAIL，原因是模块尚不存在。

- [ ] **Step 3: 实现确定性门控**

```python
DESCRIPTIVE_GATES = (
    "market_windows_complete",
    "market_benchmark_complete",
    "industry_benchmark_complete",
    "continuous_trading_verified",
)
QUASI_GATES = (
    *DESCRIPTIVE_GATES,
    "comparison_group_defined",
    "pretrend_passed",
    "confounders_controlled",
)
IDENTIFIED_GATES = (
    *QUASI_GATES,
    "robustness_passed",
    "counterevidence_passed",
)


def classify_causal_identification(gates, *, method=None, confounders=(), counterevidence=()):
    gate_results = {name: bool(gates.get(name, False)) for name in IDENTIFIED_GATES}
    if all(gate_results[name] for name in IDENTIFIED_GATES):
        status = "IDENTIFIED"
    elif all(gate_results[name] for name in QUASI_GATES):
        status = "QUASI_EXPERIMENTAL_CANDIDATE"
    elif all(gate_results[name] for name in DESCRIPTIVE_GATES):
        status = "DESCRIPTIVE_EVENT_STUDY"
    else:
        status = "NOT_IDENTIFIED"
    allowed = status == "IDENTIFIED"
    return {
        "status": status,
        "causal_attribution_allowed": allowed,
        "causal_conclusion": "IDENTIFIED_EFFECT" if allowed else "ABSTAIN",
        "method": method,
        "gate_results": gate_results,
        "unmet_conditions": [name for name in IDENTIFIED_GATES if not gate_results[name]],
        "confounders": list(confounders),
        "counterevidence": list(counterevidence),
        "boundary_zh": (
            "已满足预设因果识别门禁。" if allowed
            else "行情仅描述窗口表现和机制一致性；因果条件未满足，因此拒绝归因。"
        ),
    }
```

- [ ] **Step 4: 运行 GREEN 测试并保存检查点**

Run:

```powershell
python -m pytest training/tests/test_causal_identification.py -q
Get-FileHash -Algorithm SHA256 training/fingoose_training/causal_identification.py
```

Expected: 全部 PASS。

---

### Task 4: 接入 research-content-v1

**Files:**
- Create: `training/fingoose_training/research_content_impl_004.py`
- Modify: `training/fingoose_training/research_content/__init__.py`
- Create: `training/tests/test_evidence_market_causal_projection.py`

- [ ] **Step 1: 写 77 条行业和 30 条公司内容投影失败测试**

```python
from pathlib import Path

from fingoose_training.research_content import build_event_research_content
from fingoose_training.ui_reference import load_ui_reference


PROJECT = Path(__file__).resolve().parents[2]
UI = PROJECT / "work/company_impact_high_quality_v2_candidate/ui/ui_data_bundle.js"


def _all_content():
    return [build_event_research_content(event) for event in load_ui_reference(UI)["events"]]


def test_all_industries_receive_fixed_market_windows():
    industries = [row for content in _all_content() for row in content["industry_impacts"]]
    assert len(industries) == 77
    assert all(set((row["market_window"].get("fixed_windows") or {})) >= {
        "T0", "D1", "D3", "D5", "D20"
    } for row in industries)


def test_all_companies_receive_relative_windows_or_explicit_missing_reasons():
    companies = [row for content in _all_content() for row in content["company_impacts"]]
    assert len(companies) == 30
    for company in companies:
        assert set(company["relative_market_windows"]) == {"T0", "D1", "D3", "D5", "D20"}
        for window in company["relative_market_windows"].values():
            assert window["status"] in {"CALCULATED", "DATA_MISSING"}
            assert window.get("formula_inputs") or window.get("missing_reason")
```

- [ ] **Step 2: 写当前公司不得自动升级因果的失败测试**

```python
def test_current_company_records_do_not_claim_identified_causality():
    companies = [row for content in _all_content() for row in content["company_impacts"]]
    assert all(company["causal_identification"]["status"] in {
        "NOT_IDENTIFIED", "DESCRIPTIVE_EVENT_STUDY"
    } for company in companies)
    assert all(company["causal_identification"]["causal_conclusion"] == "ABSTAIN" for company in companies)
    assert all(company["causal_attribution_allowed"] is False for company in companies)
```

- [ ] **Step 3: 运行 RED 测试**

Run: `python -m pytest training/tests/test_evidence_market_causal_projection.py -q`

Expected: FAIL，行业内容缺少 `market_window`，公司缺少 `relative_market_windows` 和 `causal_identification`。

- [ ] **Step 4: 实现内容编排器**

`research_content_impl_004.py` 调用 `research_content_impl_003.build_event_research_content()`，然后：

```python
from copy import deepcopy

from .causal_identification import classify_causal_identification
from .evidence_closure import build_milestone_evidence_aliases
from .market_enrichment import (
    attach_industry_market_windows,
    build_industry_window_sw1_index,
    calculate_company_relative_windows,
    index_industry_windows,
    resolve_company_industry_window,
)
from .research_content import select_task_content
from .research_content_impl_003 import build_event_research_content as _build


def _records(value):
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    return [value] if isinstance(value, dict) else []


def collect_confounders(company):
    rows = _records(company.get("confounders"))
    return [
        row.get("claim_zh") or row.get("argument_zh") or row.get("display_state")
        for record in rows
        for row in _records(record.get("registered_confounders")) or [record]
        if row.get("claim_zh") or row.get("argument_zh") or row.get("display_state")
    ]


def collect_counterevidence(company):
    review = company.get("counterevidence_review") or {}
    confounders = company.get("confounders") or {}
    rows = [
        *_records(review.get("findings")),
        *_records(confounders.get("counterevidence") if isinstance(confounders, dict) else None),
    ]
    return [row.get("claim_zh") for row in rows if row.get("claim_zh")]


def causal_gates_from_company(ui_company, company_content):
    relative = company_content.get("relative_market_windows") or {}
    calculated = [relative.get(name, {}).get("status") == "CALCULATED" for name in ("T0", "D1", "D3", "D5", "D20")]
    reviews = [
        *_records(ui_company.get("trading_status_review")),
        *_records(ui_company.get("trading_status_reviews")),
    ]
    continuous_verified = any(
        str(row.get("status") or row.get("suspension_status") or "").upper() == "VERIFIED_TRADING"
        and bool(row.get("evidence_ids") or row.get("source_ids") or row.get("trading_review_id"))
        for row in reviews
    )
    design = ui_company.get("causal_design") or {}
    return {
        "market_windows_complete": all(calculated),
        "market_benchmark_complete": all(calculated),
        "industry_benchmark_complete": all(calculated),
        "continuous_trading_verified": continuous_verified,
        "comparison_group_defined": bool(design.get("comparison_group_defined")),
        "pretrend_passed": bool(design.get("pretrend_passed")),
        "confounders_controlled": bool(design.get("confounders_controlled")),
        "robustness_passed": bool(design.get("robustness_passed")),
        "counterevidence_passed": bool(design.get("counterevidence_passed")),
    }


def build_event_research_content(ui_event):
    content = _build(ui_event)
    windows = index_industry_windows(ui_event.get("industry_market_windows") or [])
    content["industry_impacts"] = attach_industry_market_windows(
        content["industry_impacts"], ui_event.get("industry_market_windows") or []
    )
    industry_by_sw1 = build_industry_window_sw1_index(windows.values())
    ui_company_by_mapping = {
        str(row["mapping_id"]): row
        for row in ui_event.get("companies") or []
        if row.get("mapping_id")
    }
    for company in content["company_impacts"]:
        ui_company = ui_company_by_mapping[str(company["mapping_id"])]
        industry_window = resolve_company_industry_window(
            ui_company, windows, industry_by_sw1
        )
        company["market_window"] = deepcopy(ui_company.get("market_window") or {})
        company["relative_market_windows"] = calculate_company_relative_windows(
            company["market_window"], industry_window or {}
        )
        gates = causal_gates_from_company(ui_company, company)
        company["causal_identification"] = classify_causal_identification(
            gates,
            confounders=collect_confounders(ui_company),
            counterevidence=collect_counterevidence(ui_company),
        )
        company["causal_attribution_allowed"] = company[
            "causal_identification"
        ]["causal_attribution_allowed"]
    content["milestone_evidence_aliases"] = build_milestone_evidence_aliases(
        ui_event.get("timeline") or []
    )
    return content
```

`causal_gates_from_company()` 只能从明确字段得出 `True`。端点价格存在不能设置 `continuous_trading_verified`；需要经过来源记录覆盖的 `trading_status_review`。缺少对照组、前趋势或稳健性字段时保持 `False`。

保留 `research_content/__init__.py` 当前动态加载基础 `research_content.py` 的兼容结构，在定义 `CONTENT_SCHEMA_VERSION`、`ContentAlignmentError`、`HORIZONS` 和 `select_task_content` 后，将原有本地 wrapper 替换为：

```python
from ..research_content_impl_004 import build_event_research_content

__all__ = [
    "CONTENT_SCHEMA_VERSION", "ContentAlignmentError", "HORIZONS",
    "build_event_research_content", "select_task_content",
]
```

- [ ] **Step 5: 运行 GREEN 和现有内容回归测试**

Run:

```powershell
python -m pytest training/tests/test_evidence_market_causal_projection.py training/tests/test_research_content.py training/tests/test_qa_content_projection.py -q
```

Expected: 全部 PASS；行业 77、公司 30，QA 仍关联原十个事件。

---

### Task 5: 修复事件、行业和公司链的证据注册表

**Files:**
- Create: `training/fingoose_training/unified_builder_impl_008.py`
- Modify: `training/fingoose_training/unified_builder/__init__.py`
- Modify: `training/tests/test_evidence_market_causal_projection.py`

- [ ] **Step 1: 写子链继承与真实全量闭环失败测试**

```python
from collections import Counter

from fingoose_training.artifacts import resolve_project_root
from fingoose_training.loaders import load_source_bundle, load_ui_reference_bundle, read_json
from fingoose_training.unified_builder import build_unified_events


def _events():
    config_path = PROJECT / "training/configs/dataset.json"
    config = read_json(config_path)
    root = resolve_project_root(config_path, config)
    source, _ = load_source_bundle(root, config)
    ui, _ = load_ui_reference_bundle(root, config)
    return build_unified_events(source, config["dataset_version"], ui_reference=ui)


def test_child_event_fact_evidence_is_complete_after_inheritance():
    events = _events()
    child_chains = [
        scope["reasoning_chain"]
        for event in events
        for scope in [*event["industries"], *event["companies"]]
    ]
    for chain in child_chains:
        registry = {row["evidence_id"]: row for row in chain["evidence_registry"]}
        for node in chain["reasoning_chain"]["nodes"]:
            if node["node_type"] == "EVENT_FACT":
                assert node["evidence_ids"]
                assert all(registry[evidence_id]["missing"] is False for evidence_id in node["evidence_ids"])


def test_known_94_open_chains_close_after_recompile():
    statuses = Counter(
        scope["reasoning_chain"]["reasoning_chain"]["closure_gate"]["status"]
        for event in _events()
        for scope in [event["event"], *event["industries"], *event["companies"]]
    )
    assert statuses["OPEN"] == 0
```

- [ ] **Step 2: 运行 RED 测试**

Run: `python -m pytest training/tests/test_evidence_market_causal_projection.py -q`

Expected: FAIL；当前行业/公司链未合并事件完整 registry，且 event-02/event-03 别名未绑定证据。

- [ ] **Step 3: 实现新 builder 编排**

`unified_builder_impl_008.py` 复用 `unified_builder_impl_003` 的 `_attach_content_to_scopes`、`_attach_qa_chains` 和公共索引函数，但重新实现三个链构建函数：

```python
from copy import deepcopy
from typing import Mapping

from .evidence_closure import bind_milestone_evidence_aliases, merge_evidence_records
from .reasoning_chain_impl_009 import compile_reasoning_chain
from .research_content_impl_004 import build_event_research_content
from .unified_builder_impl_001 import (
    BuildError, build_unified_events as _build_v1, group_by, index_unique,
)
from .unified_builder_impl_003 import (
    _attach_content_to_scopes, _attach_qa_chains, _company_parent_refs,
    _evidence_records,
)


def _attach_event_chain(record, content):
    event = deepcopy(record["event"])
    event["milestones"] = bind_milestone_evidence_aliases(
        event.get("milestones") or [],
        content.get("milestone_evidence_aliases") or {},
    )
    event_evidence = merge_evidence_records(
        _evidence_records(event.get("sources"), event.get("milestones")),
        content.get("evidence_registry") or [],
    )
    record["event"]["reasoning_chain"] = compile_reasoning_chain(
        "EVENT_ANALYSIS",
        scope={"event_id": record["event_id"], **event, "research_content": content},
        evidence_registry=event_evidence,
    )


def _attach_industry_chains(record, content):
    event_registry = record["event"]["reasoning_chain"]["evidence_registry"]
    event_chain_ref = record["event"]["reasoning_chain"]["reasoning_chain"]["scope_id"]
    content_by_industry_id = {
        str(row["event_industry_mapping_id"]): row
        for row in content.get("industry_impacts") or []
    }
    for industry in record["industries"]:
        industry_content = content_by_industry_id[industry["event_industry_mapping_id"]]
        evidence = merge_evidence_records(
            event_registry,
            _evidence_records(industry.get("evidence"), industry.get("mechanism_chain"), industry_content),
        )
        mapping = industry.get("mapping") or {}
        scope = {
            **deepcopy(mapping),
            "event_id": record["event_id"],
            "event_industry_mapping_id": industry["event_industry_mapping_id"],
            "mechanism_chain": deepcopy(industry.get("mechanism_chain")),
            "market_window": deepcopy(industry.get("market_window")),
            "research_content": industry_content,
        }
        industry["reasoning_chain"] = compile_reasoning_chain(
            "INDUSTRY_IMPACT", scope=scope,
            evidence_registry=evidence, parent_chain_refs=[event_chain_ref],
        )


def _attach_company_chains(record, content):
    event_registry = record["event"]["reasoning_chain"]["evidence_registry"]
    content_by_company_id = {
        str(row["mapping_id"]): row
        for row in content.get("company_impacts") or []
    }
    for company in record["companies"]:
        company_content = content_by_company_id[company["mapping_id"]]
        evidence = merge_evidence_records(
            event_registry,
            _evidence_records(
                company.get("evidence"), company.get("mechanism_chain"),
                company.get("counterevidence_reviews"), company_content,
            ),
        )
        mapping = company.get("mapping") or {}
        scope = {
            **deepcopy(mapping),
            "event_id": record["event_id"],
            "mapping_id": company["mapping_id"],
            "company_code": company.get("company_code"),
            "mechanism_chain": deepcopy(company.get("mechanism_chain")),
            "direction_assessment": deepcopy(company.get("direction_assessment")),
            "market_windows": deepcopy(company.get("market_windows")),
            "trading_status_reviews": deepcopy(company.get("trading_status_reviews")),
            "confounders": deepcopy(company.get("confounders")),
            "counterevidence_reviews": deepcopy(company.get("counterevidence_reviews")),
            "research_content": company_content,
        }
        company["reasoning_chain"] = compile_reasoning_chain(
            "COMPANY_IMPACT", scope=scope,
            evidence_registry=evidence, parent_chain_refs=_company_parent_refs(record, company),
        )


def build_unified_events(source, dataset_version, *, ui_reference=None):
    records = _build_v1(source, dataset_version)
    if ui_reference is None:
        if len(records) > 1:
            raise BuildError("content alignment requires ui_reference")
        return records
    ui_by_id = {
        str(row.get("event_id")): row
        for row in ui_reference.get("events") or []
        if isinstance(row, Mapping)
    }
    for record in records:
        ui_event = ui_by_id.get(str(record["event_id"]))
        if ui_event is None:
            raise BuildError(f"ui reference missing event_id={record['event_id']}")
        content = build_event_research_content(ui_event)
        _attach_content_to_scopes(record, content)
        _attach_event_chain(record, content)
        _attach_industry_chains(record, content)
        _attach_company_chains(record, content)
        _attach_qa_chains(record, content)
    return records


__all__ = ["BuildError", "build_unified_events", "group_by", "index_unique"]
```

公开入口保持原兼容规则：单事件且无 UI 时调用 legacy builder，多事件无 UI 时抛出 `BuildError`。将 `unified_builder/__init__.py` 改为从 `unified_builder_impl_008` 重导出。

- [ ] **Step 4: 运行 GREEN、图结构和 builder 回归测试**

Run:

```powershell
python -m pytest training/tests/test_evidence_market_causal_projection.py training/tests/test_unified_builder.py training/tests/test_unified_builder_reasoning_chain_v1.py training/tests/test_reasoning_chain_v1.py -q
```

Expected: 全部 PASS；119 条非 QA 事件/行业/公司链中 `OPEN=0`，图结构无错误。若仍有 `OPEN`，输出 `sample_id + blocker + evidence_id` 并确认是否属于真实 `SOURCE_EVIDENCE_INCOMPLETE`；不得修改门禁绕过测试。

---

### Task 6: 答案渲染、因果门禁和验证统计

**Files:**
- Create: `training/fingoose_training/answer_renderer_impl_007.py`
- Modify: `training/fingoose_training/sft_projector_impl_013.py`
- Create: `training/fingoose_training/validation_impl_006.py`
- Modify: `training/fingoose_training/validation/__init__.py`
- Modify: `training/tests/test_content_alignment_validation.py`
- Modify: `training/tests/test_evidence_market_causal_projection.py`

- [ ] **Step 1: 写公司答案必须展示相对收益与弃答的失败测试**

```python
from fingoose_training.sft_projector import project_sft_samples


def test_company_answer_separates_market_observation_from_causal_abstention():
    samples = project_sft_samples(_events())
    company = next(row for row in samples if row["task_type"] == "COMPANY_IMPACT")
    answer = company["messages"][2]["content"]
    assert "绝对收益" in answer
    assert "相对沪深300" in answer
    assert "相对行业" in answer
    assert "因果识别" in answer
    assert "ABSTAIN" in answer
    assert "不能把同期波动直接归因" in answer
```

- [ ] **Step 2: 写验证器拒绝伪因果和不可回算数字的失败测试**

```python
from copy import deepcopy

from fingoose_training.validation_impl_006 import _check


def test_validation_rejects_nonidentified_causal_attribution(company_sample):
    broken = deepcopy(company_sample)
    content = broken["metadata"]["research_content"]
    content["causal_identification"]["status"] = "NOT_IDENTIFIED"
    content["causal_identification"]["causal_attribution_allowed"] = True
    assert "CAUSAL_GATE_CONTRADICTION" in {row["code"] for row in _check(broken)}


def test_validation_rejects_unreproducible_relative_return(company_sample):
    broken = deepcopy(company_sample)
    d1 = broken["metadata"]["research_content"]["relative_market_windows"]["D1"]
    d1["market_relative_return"] += 0.01
    assert "MARKET_CALCULATION_MISMATCH" in {row["code"] for row in _check(broken)}
```

- [ ] **Step 3: 运行 RED 测试**

Run:

```powershell
python -m pytest training/tests/test_evidence_market_causal_projection.py training/tests/test_content_alignment_validation.py -q
```

Expected: FAIL；答案尚未展示新字段，验证器尚无两个错误码。

- [ ] **Step 4: 实现新答案 renderer 与 projector**

`answer_renderer_impl_007.py` 基于 `answer_renderer_impl_006`，为行业和公司覆盖 market renderer：

```python
def _pct(value):
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "缺失"


def _relative_window_lines(content, limit=2):
    lines = []
    for name in ("T0", "D1", "D3", "D5", "D20")[:limit]:
        row = (content.get("relative_market_windows") or {}).get(name) or {}
        if row.get("status") == "CALCULATED":
            lines.append(
                f"{name}：绝对收益 {_pct(row['formula_inputs']['company_absolute_return'])}，"
                f"相对沪深300 {_pct(row['market_relative_return'])}，"
                f"相对行业 {_pct(row['industry_relative_return'])}；"
                f"实际日期 {row['actual_date']}，公式 {row['formula_version']}"
            )
        else:
            lines.append(f"{name}：数据缺失（{row.get('missing_reason', 'UNKNOWN')}）")
    return lines


def _causal_boundary(content):
    causal = content.get("causal_identification") or {}
    status = causal.get("status") or "NOT_IDENTIFIED"
    unmet = "、".join(causal.get("unmet_conditions") or [])
    return (
        f"因果识别：{status}；结论：{causal.get('causal_conclusion', 'ABSTAIN')}；"
        f"未满足条件：{unmet or '无'}。不能把同期波动直接归因于宏观事件。"
    )
```

公司答案保留业务暴露、经营路径、三阶段、混杂因素与反证，并增加上述两段。行业行情展示 `industry_return`、`market_return` 和 `market_relative_return`，明确“机制一致性不等于因果”。EVENT_QA 的行情验证只读取统一 research content，不创建新的独立 QA 行情结论。

在 `sft_projector_impl_013.py` 只修改 renderer 导入，不改变投影逻辑、2000 字符门禁或四类 metadata 关联：

```python
from .answer_renderer_impl_007 import render_answer
```

- [ ] **Step 5: 实现验证错误码和统计**

`validation_impl_006.py` 包装 `validation_impl_005.validate_datasets`，并新增：

```python
from collections import Counter
from typing import Mapping

from .validation_impl_005 import (
    _check as _check_v5,
    _error,
    validate_datasets as _validate_v5,
    validate_reasoning_chain,
)


CAUSAL_STATUSES = {
    "NOT_IDENTIFIED", "DESCRIPTIVE_EVENT_STUDY",
    "QUASI_EXPERIMENTAL_CANDIDATE", "IDENTIFIED",
}


def _check_causal(content, sample_id):
    causal = content.get("causal_identification")
    if not isinstance(causal, Mapping):
        return []
    status = str(causal.get("status") or "")
    allowed = causal.get("causal_attribution_allowed") is True
    conclusion = causal.get("causal_conclusion")
    gates = causal.get("gate_results") or {}
    contradiction = (
        status not in CAUSAL_STATUSES
        or (status != "IDENTIFIED" and (allowed or conclusion != "ABSTAIN"))
        or (status == "IDENTIFIED" and (not allowed or not all(gates.values())))
    )
    return [_error("CAUSAL_GATE_CONTRADICTION", sample_id, status)] if contradiction else []


def _check_market_calculations(content, sample_id, tolerance=1e-12):
    errors = []
    for name, row in (content.get("relative_market_windows") or {}).items():
        if row.get("status") == "DATA_MISSING":
            if not row.get("missing_reason"):
                errors.append(_error("MARKET_MISSING_REASON_REQUIRED", sample_id, name))
            continue
        inputs = row.get("formula_inputs") or {}
        try:
            industry_return = inputs["industry_value"] / inputs["industry_base_value"] - 1
            market_return = inputs["market_value"] / inputs["market_base_value"] - 1
            expected_industry = inputs["company_absolute_return"] - industry_return
            expected_market = inputs["company_absolute_return"] - market_return
        except (KeyError, TypeError, ZeroDivisionError):
            errors.append(_error("MARKET_CALCULATION_MISMATCH", sample_id, name))
            continue
        if (
            abs(row.get("industry_relative_return", float("inf")) - expected_industry) > tolerance
            or abs(row.get("market_relative_return", float("inf")) - expected_market) > tolerance
        ):
            errors.append(_error("MARKET_CALCULATION_MISMATCH", sample_id, name))
    return errors


def _closure_reason_stats(sft_samples):
    stats = Counter()
    for sample in sft_samples:
        gate = ((sample.get("metadata") or {}).get("reasoning_chain") or {}).get("closure_gate") or {}
        if gate.get("status") == "CLOSED":
            stats["CLOSED"] += 1
        else:
            for blocker in gate.get("blockers") or ["UNKNOWN_OPEN_REASON"]:
                reason = str(blocker).split(":", 1)[0]
                stats["SOURCE_EVIDENCE_INCOMPLETE" if reason == "EVIDENCE_MISSING" else reason] += 1
    return dict(sorted(stats.items()))


def _market_completeness_stats(sft_samples):
    industries = [row for row in sft_samples if row.get("task_type") == "INDUSTRY_IMPACT"]
    companies = [row for row in sft_samples if row.get("task_type") == "COMPANY_IMPACT"]
    calculated = sum(
        window.get("status") == "CALCULATED"
        for sample in companies
        for window in ((sample.get("metadata") or {}).get("research_content") or {}).get("relative_market_windows", {}).values()
    )
    return {"industry_total": len(industries), "company_total": len(companies), "company_calculated_window_count": calculated}


def _causal_status_stats(sft_samples):
    stats = Counter({status: 0 for status in CAUSAL_STATUSES})
    for sample in sft_samples:
        if sample.get("task_type") != "COMPANY_IMPACT":
            continue
        content = (sample.get("metadata") or {}).get("research_content") or {}
        stats[str((content.get("causal_identification") or {}).get("status") or "NOT_IDENTIFIED")] += 1
    return dict(sorted(stats.items()))


def _check(sample):
    errors = list(_check_v5(sample))
    metadata = sample.get("metadata") or {}
    content = metadata.get("research_content") or {}
    errors.extend(_check_causal(content, sample.get("sample_id")))
    errors.extend(_check_market_calculations(content, sample.get("sample_id")))
    graph = metadata.get("reasoning_chain") or {}
    registry = {
        str(row.get("evidence_id")): row
        for row in metadata.get("evidence_registry") or []
        if row.get("evidence_id")
    }
    for node in graph.get("nodes") or []:
        if node.get("node_type") != "EVENT_FACT":
            continue
        for evidence_id in node.get("evidence_ids") or []:
            if evidence_id not in registry:
                errors.append(_error("REGISTRY_NOT_INHERITED", sample.get("sample_id"), evidence_id))
    aliases = content.get("milestone_evidence_aliases") or {}
    node_by_id = {str(row.get("node_id")): row for row in graph.get("nodes") or []}
    for node_id, evidence_ids in aliases.items():
        if node_id in node_by_id and not set(evidence_ids) <= set(node_by_id[node_id].get("evidence_ids") or []):
            errors.append(_error("ALIAS_UNRESOLVED", sample.get("sample_id"), node_id))
    return errors


def validate_datasets(unified_events, sft_samples, expected_events, expected_task_types=None):
    report = _validate_v5(unified_events, sft_samples, expected_events, expected_task_types)
    extra = [error for sample in sft_samples for error in _check(sample) if error not in report.get("errors", [])]
    report["errors"] = list(report.get("errors") or []) + extra
    report["valid"] = not report["errors"]
    report["closure_reason_stats"] = _closure_reason_stats(sft_samples)
    report["market_completeness_stats"] = _market_completeness_stats(sft_samples)
    report["causal_identification_stats"] = _causal_status_stats(sft_samples)
    return report
```

规则：非 `IDENTIFIED` 出现 `causal_attribution_allowed=true` 或非 `ABSTAIN`，返回 `CAUSAL_GATE_CONTRADICTION`；`IDENTIFIED` 未通过所有 gate 也返回同一错误。回算公司相对收益时使用保存的 `formula_inputs`，偏差超过 `1e-12` 返回 `MARKET_CALCULATION_MISMATCH`。`DATA_MISSING` 没有原因返回 `MARKET_MISSING_REASON_REQUIRED`。验证报告新增 `closure_reason_stats`、`market_completeness_stats` 和 `causal_identification_stats`。

将 `validation/__init__.py` 改为从 `validation_impl_006` 导出 `validate_datasets`、`validate_reasoning_chain`；保留测试直接调用的 `_check`。

- [ ] **Step 6: 运行 GREEN 和全量答案回归测试**

Run:

```powershell
python -m pytest training/tests/test_evidence_market_causal_projection.py training/tests/test_content_alignment_validation.py training/tests/test_high_quality_answers.py training/tests/test_qa_content_projection.py training/tests/test_sft_projector.py -q
```

Expected: 全部 PASS；四类答案不超过 2000 字符，QA 仍与十个事件关联。

---

### Task 7: 全量重建、确定性验证和执行报告

**Files:**
- Modify: `training/tests/test_sft_real_reasoning_dataset_v1.py`
- Modify: `training/README.md`
- Generated: `training/data/unified_events.jsonl`
- Generated: `training/data/sft_dataset.jsonl`
- Generated: `training/data/manifest.json`
- Generated: `training/data/split_manifest.json`
- Generated: `training/data/validation_report.json`
- Create: `docs/superpowers/plans/2026-08-11-evidence-market-causal-closure-v1-execution-report.md`

- [ ] **Step 1: 固定真实数据验收断言**

在 `test_sft_real_reasoning_dataset_v1.py` 增加：

```python
def test_real_dataset_closes_known_build_defects_and_keeps_causal_abstention():
    samples = _jsonl("sft_dataset.jsonl")
    non_qa = [row for row in samples if row["task_type"] != "EVENT_QA"]
    assert all(
        row["metadata"]["reasoning_chain"]["closure_gate"]["status"] == "CLOSED"
        for row in non_qa
    )
    industries = [row for row in samples if row["task_type"] == "INDUSTRY_IMPACT"]
    companies = [row for row in samples if row["task_type"] == "COMPANY_IMPACT"]
    assert len(industries) == 77
    assert len(companies) == 30
    assert all((row["metadata"]["research_content"].get("market_window") or {}).get("fixed_windows") for row in industries)
    assert all(row["metadata"]["research_content"]["causal_identification"]["causal_conclusion"] == "ABSTAIN" for row in companies)


def test_validation_report_exposes_market_and_causal_stats():
    report = json.loads((TRAINING_ROOT / "data/validation_report.json").read_text(encoding="utf-8"))
    assert report["reasoning_chain_stats"]["totals"]["open_closure_count"] == 0
    assert report["market_completeness_stats"]["industry_total"] == 77
    assert report["market_completeness_stats"]["company_total"] == 30
    assert report["causal_identification_stats"]["IDENTIFIED"] == 0
    assert sum(report["causal_identification_stats"].values()) == 30
```

- [ ] **Step 2: 运行预重建 RED 测试**

Run: `python -m pytest training/tests/test_sft_real_reasoning_dataset_v1.py -q`

Expected: FAIL，因为生成数据仍是旧版本，报告仍显示 94 条 `OPEN`。

- [ ] **Step 3: 更新 README 数据语义**

明确记录：

- 证据继承不改变“原文 + 定位 + URL”门禁；
- 行业窗口使用 `T0/D1/D3/D5/D20`；
- 公司相对收益使用公司实际日期和共同 `T_MINUS_1` 基期；
- `NOT_IDENTIFIED`、`DESCRIPTIVE_EVENT_STUDY`、`QUASI_EXPERIMENTAL_CANDIDATE` 均必须 `ABSTAIN`；
- `NEEDS_HUMAN_REVIEW`、未执行人工审核和未执行真实 GPU 训练的边界。

- [ ] **Step 4: 全量重建统一主数据和 SFT**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
$env:PYTHONUTF8='1'
python training/scripts/build_unified_dataset.py --config training/configs/dataset.json
python training/scripts/build_sft_dataset.py --config training/configs/dataset.json
```

Expected:

```text
wrote 10 unified events
wrote 157 SFT samples
```

- [ ] **Step 5: 运行完整验证**

Run:

```powershell
python -m pytest training/tests -q
python -m compileall -q training/fingoose_training training/scripts
python training/scripts/validate_dataset.py --config training/configs/dataset.json
python training/scripts/train_sft.py --config training/configs/sft_qlora_3b.json --dry-run
```

Expected: 所有测试通过；`compileall` 无输出；验证 `0 errors / 0 warnings`；dry-run 显示 `ready=true`、`model_loaded=false`。

- [ ] **Step 6: 执行只读语义审计**

使用 PowerShell/标准 JSON 解析输出并核对：

```text
事件数=10
SFT数=157
任务分布=10/77/30/40
OPEN=0
行业行情=77
公司行情=30
IDENTIFIED=0
非IDENTIFIED且非ABSTAIN=0
乱码样本=0
```

若 `OPEN` 非零，只允许 `SOURCE_EVIDENCE_INCOMPLETE`；执行报告必须列出具体事件、节点和缺失字段，不能改写为已闭环。

- [ ] **Step 7: 连续重建并比较 SHA**

连续再次执行 Step 4 和 Step 5，然后运行：

```powershell
Get-FileHash -Algorithm SHA256 training/data/unified_events.jsonl
Get-FileHash -Algorithm SHA256 training/data/sft_dataset.jsonl
Get-FileHash -Algorithm SHA256 training/data/split_manifest.json
Get-FileHash -Algorithm SHA256 training/data/validation_report.json
```

Expected: 两轮四个 SHA 完全一致。

- [ ] **Step 8: 写执行报告**

`2026-08-11-evidence-market-causal-closure-v1-execution-report.md` 必须记录：变更文件、测试数、任务分布、证据闭环前后统计、行业/公司行情完整性、公式缺失原因分布、四级因果状态分布、验证错误/警告、四个 SHA 和 dry-run 状态。结尾明确：

```text
本轮未执行人工审核，所有记录继续保留候选审核边界；未执行真实 GPU 训练。
行情结果用于描述事件窗口和检验机制一致性，不能自动证明宏观事件因果。
```

---

## 实施顺序与停止条件

1. Task 1-3 必须先以纯函数单元测试通过，再接入真实数据。
2. Task 4 的 77/30 内容投影通过后，才能改 builder 证据链。
3. 任一相同 `evidence_id` 出现完整关键字段冲突时立即停止并报告，不静默选择较长文本。
4. 公司窗口无法建立共同实际日期和共同基期时保持 `DATA_MISSING`，不执行标签对标签的直接相减。
5. 只要任何因果门禁未通过，就必须 `ABSTAIN`；不得为减少缺口升级状态。
6. 10 个事件、157 条样本、10/77/30/40 分布或 split 发生变化时，视为回归失败。
7. 只有全量测试、编译、验证、dry-run 和两轮 SHA 全部通过后，才能声明本实施计划完成。
