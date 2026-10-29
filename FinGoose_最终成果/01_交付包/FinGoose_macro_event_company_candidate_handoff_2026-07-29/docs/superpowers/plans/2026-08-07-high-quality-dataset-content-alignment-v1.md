# High-Quality Dataset Content Alignment v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 UI 中已经具备的事件、行业、公司、问答、证据链和三阶段研究内容规范化为统一内容契约，先完成 `event-01` 金标准样本，再扩展到全部 10 个事件和 157 条 SFT 样本。

**Architecture:** 不解析 UI DOM，也不把展示 HTML 当事实来源。严格读取 `ui_data_bundle.js` 中的 JSON 数据段，将其规范化为 `research_content_v1`；统一主数据保存完整内容契约，推理链编译器消费契约生成可审计 DAG，SFT 投影器按任务渲染中文答案，验证器检查 UI、metadata、assistant 三层一致性。现有候选包、审核状态、截止日门禁和推理链 metadata 继续保留。

**Tech Stack:** Python 3.12、标准库 `json`/`hashlib`/`pathlib`/`typing`、现有 JSONL 构建脚本、pytest、静态 HTML/JavaScript UI bundle。

---

## 成功标准

- `event-01-event-analysis` 不再包含空对象、`待补充陈述`、英文裸事实或被截断的 JSON。
- 四类 assistant 都有直接结论、证据事实、具体机制、即时/短期/中期、行情验证及证据边界。
- UI、统一主数据、reasoning-chain metadata 和 assistant 引用相同的事件、行业、公司、证据 ID 和方向。
- `EVIDENCE_MISSING`、`INFERENCE_ONLY`、`NEEDS_HUMAN_REVIEW`、`formal_ready=false` 和 `causal_attribution_allowed=false` 不得被改写为确定性结论。
- 10 个事件、157 条样本及 10/77/30/40 任务分布不变；事件不跨 split。
- 新增内容门禁为 `0 errors / 0 warnings`，连续两次重建 SHA-256 一致。
- 不执行人工审核，不把 `ready=true` 解释为已完成人工审核或真实 GPU 训练。

## 文件边界

- Create: `training/fingoose_training/ui_reference.py`：严格解析 UI bundle JSON，校验版本、事件唯一性和 SHA。
- Create: `training/fingoose_training/research_content.py`：将 UI 事件规范化为 `research_content_v1`。
- Create: `training/fingoose_training/answer_renderer.py`：按四类任务渲染中文 assistant，不承担数据加载或推理状态判断。
- Create: `training/fingoose_training/unified_builder_impl_003.py`：把内容契约接入统一主数据并调用新版链编译器。
- Modify: `training/fingoose_training/unified_builder.py`：公开加载器指向 `unified_builder_impl_003.py`。
- Create: `training/fingoose_training/reasoning_chain_impl_009.py`：使用规范陈述、前提和主路径覆盖事件链。
- Modify: `training/fingoose_training/reasoning_chain.py`：公开加载器指向 `reasoning_chain_impl_009.py`。
- Create: `training/fingoose_training/sft_projector_impl_004.py`：用任务渲染器替换旧的 JSON 压缩答案。
- Modify: `training/fingoose_training/sft_projector.py`：公开加载器指向 `sft_projector_impl_004.py`。
- Create: `training/fingoose_training/validation_impl_004.py`：增加内容完整性和三层一致性门禁。
- Modify: `training/fingoose_training/validation.py`：公开加载器指向 `validation_impl_004.py`。
- Modify: `training/fingoose_training/loaders.py`：支持配置中的受控 UI reference bundle。
- Modify: `training/fingoose_training/artifacts.py`：把 UI bundle 纳入来源 SHA。
- Modify: `training/scripts/build_unified_dataset.py`：加载 UI reference 并传给 unified builder。
- Modify: `training/configs/dataset.json`：声明 UI bundle 路径和内容契约版本。
- Create: `training/tests/test_ui_reference.py`。
- Create: `training/tests/test_research_content.py`。
- Create: `training/tests/test_high_quality_answers.py`。
- Create: `training/tests/test_content_alignment_validation.py`。
- Modify: `training/tests/test_unified_builder.py`。
- Modify: `training/tests/test_sft_real_dataset.py`。
- Modify: `training/README.md`。
- Generated: `training/data/unified_events.jsonl`、`training/data/sft_dataset.jsonl`、`training/data/manifest.json`、`training/data/validation_report.json`、`training/data/split_manifest.json`。

项目目录不是有效 Git 仓库，因此下述每个任务以测试输出和产物 SHA 作为检查点，不执行虚假 commit。

---

### Task 1: 固定 event-01 金标准和失败测试

**Files:**
- Create: `training/tests/test_ui_reference.py`
- Create: `training/tests/test_research_content.py`
- Create: `training/tests/test_high_quality_answers.py`
- Create: `training/tests/test_content_alignment_validation.py`

- [ ] **Step 1: 写 UI bundle 严格读取失败测试**

```python
def test_load_ui_reference_reads_exact_json_wrapper(project_root):
    bundle = load_ui_reference(
        project_root / "work/company_impact_high_quality_v2_candidate/ui/ui_data_bundle.js"
    )
    assert bundle["dataset_version"] == "fingoose-company-impact-high-quality-v2-candidate"
    assert [row["event_id"] for row in bundle["events"]] == [f"event-{i:02d}" for i in range(1, 11)]


def test_load_ui_reference_rejects_arbitrary_javascript(tmp_path):
    path = tmp_path / "bundle.js"
    path.write_text("alert(1)", encoding="utf-8")
    with pytest.raises(UIReferenceError, match="exact JSON wrapper"):
        load_ui_reference(path)
```

- [ ] **Step 2: 写 event-01 内容契约失败测试**

```python
def test_event_01_research_content_has_complete_three_horizons(ui_bundle):
    ui_event = next(row for row in ui_bundle["events"] if row["event_id"] == "event-01")
    content = build_event_research_content(ui_event)
    assert content["schema_version"] == "research-content-v1"
    assert content["event_id"] == "event-01"
    assert set(content["horizon_analysis"]) == {"IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM"}
    for horizon in content["horizon_analysis"].values():
        assert horizon["summary_zh"].strip()
        assert horizon["mechanism_node_ids"]
        assert horizon["evidence_ids"]
    assert content["main_path_node_ids"][-1] != content["precondition_node_ids"][0]
```

- [ ] **Step 3: 写高质量 assistant 失败测试**

```python
def test_event_01_answer_is_concrete_chinese_research_answer(event_01_sample):
    answer = event_01_sample["messages"][2]["content"]
    for heading in ("结论", "来源事实", "即时影响", "短期影响", "中期影响", "行情验证", "证据边界"):
        assert heading in answer
    for forbidden in ("待补充陈述", '"nodes": [{}, {}', "[嵌套内容省略]", "omitted_count"):
        assert forbidden not in answer
    assert "event01-who-pandemic" in answer
    assert "NEEDS_HUMAN_REVIEW" in answer or "待人工审核" in answer
```

- [ ] **Step 4: 写三层一致性失败测试**

```python
def test_ui_metadata_and_answer_share_horizons_and_evidence(event_01_sample):
    metadata = event_01_sample["metadata"]
    content = metadata["research_content"]
    answer = event_01_sample["messages"][2]["content"]
    registry_ids = {row["evidence_id"] for row in metadata["evidence_registry"]}
    assert set(content["horizon_analysis"]) == {"IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM"}
    assert set(content["answer_evidence_ids"]) <= registry_ids
    assert all(evidence_id in answer for evidence_id in content["primary_answer_evidence_ids"])
```

- [ ] **Step 5: 运行 RED 测试**

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests/test_ui_reference.py training/tests/test_research_content.py training/tests/test_high_quality_answers.py training/tests/test_content_alignment_validation.py -q
```

Expected: FAIL，原因是 `ui_reference.py`、`research_content.py` 和 `answer_renderer.py` 尚不存在。

---

### Task 2: 建立受控 UI reference 读取层

**Files:**
- Create: `training/fingoose_training/ui_reference.py`
- Modify: `training/fingoose_training/loaders.py`
- Modify: `training/fingoose_training/artifacts.py`
- Modify: `training/configs/dataset.json`
- Test: `training/tests/test_ui_reference.py`

- [ ] **Step 1: 定义严格解析接口**

```python
UI_PREFIX = "window.FINGOOSE_COMPANY_IMPACT_V2="
UI_SUFFIX = ";"


class UIReferenceError(ValueError):
    pass


def load_ui_reference(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text.startswith(UI_PREFIX) or not text.endswith(UI_SUFFIX):
        raise UIReferenceError(f"{path}: expected exact JSON wrapper")
    payload = json.loads(text[len(UI_PREFIX):-len(UI_SUFFIX)])
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise UIReferenceError(f"{path}: expected object with events")
    ids = [row.get("event_id") for row in payload["events"] if isinstance(row, dict)]
    if len(ids) != 10 or len(set(ids)) != 10:
        raise UIReferenceError(f"{path}: expected 10 unique events")
    return payload
```

该实现只剥离固定赋值包装，实际内容仍由 `json.loads` 解析；禁止 `eval`、正则抽取和执行 JavaScript。

- [ ] **Step 2: 在配置中声明 reference，而不是伪装成 JSONL 来源**

```json
"content_alignment": {
  "schema_version": "research-content-v1",
  "ui_reference_path": "work/company_impact_high_quality_v2_candidate/ui/ui_data_bundle.js",
  "ui_dataset_version": "fingoose-company-impact-high-quality-v2-candidate",
  "gold_event_ids": ["event-01"]
}
```

- [ ] **Step 3: 增加路径解析函数**

```python
def resolve_ui_reference_path(project_root: Path, config: Mapping[str, Any]) -> Path:
    relative = config["content_alignment"]["ui_reference_path"]
    path = (project_root / relative).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"ui reference missing: {path}")
    return path
```

- [ ] **Step 4: 将 UI bundle 纳入 manifest SHA**

在 `resolve_source_paths()` 返回值中追加：

```python
alignment = config.get("content_alignment") or {}
if alignment.get("ui_reference_path"):
    paths["ui_reference_bundle"] = (
        project_root / alignment["ui_reference_path"]
    ).resolve()
```

- [ ] **Step 5: 运行读取层测试**

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests/test_ui_reference.py -q
```

Expected: PASS。

---

### Task 3: 定义 research_content_v1 规范层

**Files:**
- Create: `training/fingoose_training/research_content.py`
- Test: `training/tests/test_research_content.py`

- [ ] **Step 1: 固定公开 schema**

每个事件的 `research_content` 必须有：

```python
REQUIRED_CONTENT_FIELDS = {
    "schema_version",
    "event_id",
    "title_zh",
    "source_facts",
    "macro_mechanism",
    "horizon_analysis",
    "market_validation",
    "industry_impacts",
    "company_impacts",
    "qa_sections",
    "evidence_registry",
    "main_path_node_ids",
    "precondition_node_ids",
    "boundaries",
    "review_state",
}
```

- [ ] **Step 2: 规范来源事实，不把展示文案当原文**

```python
def _source_fact(node: Mapping[str, Any]) -> dict[str, Any]:
    evidence = [row for row in node.get("evidence", []) if isinstance(row, Mapping)]
    return {
        "node_id": str(node["fast_node_id"]),
        "statement_zh": str(node.get("event_summary_zh") or node.get("event_title_zh") or "").strip(),
        "occurred_at": node.get("occurred_at"),
        "first_public_at": node.get("first_public_at"),
        "evidence_ids": sorted({str(row["source_id"]) for row in evidence if row.get("source_id")}),
        "evidence_status": node.get("evidence_status") or "PENDING_EVIDENCE",
    }
```

原始引文只从 evidence registry 的 `original_quote` 读取；`event_summary_zh` 只能作为中文陈述。

- [ ] **Step 3: 规范即时、短期和中期**

```python
HORIZONS = ("IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM")


def _horizon_block(impacts: Sequence[Mapping[str, Any]], horizon: str) -> dict[str, Any]:
    rows = []
    for impact in impacts:
        detail = (impact.get("horizon_details") or {}).get(horizon) or {}
        if detail.get("detail_zh"):
            rows.append({
                "scope_id": impact.get("event_industry_mapping_id"),
                "scope_name_zh": impact.get("industry_name_zh"),
                "direction": detail.get("direction") or "UNKNOWN",
                "detail_zh": detail["detail_zh"].strip(),
                "condition_zh": impact.get("condition_zh"),
                "invalidation_condition_zh": impact.get("invalidation_condition_zh"),
                "evidence_ids": sorted(set(impact.get("research_evidence_ids") or [])),
            })
    if not rows:
        raise ContentAlignmentError(f"missing {horizon} content")
    return {
        "summary_zh": _summarize_horizon(rows, horizon),
        "impact_rows": rows,
        "mechanism_node_ids": sorted({row["scope_id"] for row in rows if row["scope_id"]}),
        "evidence_ids": sorted({eid for row in rows for eid in row["evidence_ids"]}),
    }
```

`_summarize_horizon()` 只从 `detail_zh` 归纳，不生成 UI 中不存在的数字或事实；相同文本不得复制到三个阶段。

- [ ] **Step 4: 规范行业与公司层**

行业记录必须保留：`impact_tier`、`observable_driver_zh`、`industry_operating_variable_zh`、`industry_financial_variable_zh`、`horizon_details`、`condition_zh`、`invalidation_condition_zh`、`counterevidence_zh` 和 `research_evidence_ids`。

公司记录必须保留：

```python
{
    "mapping_id": company["mapping_id"],
    "company_code": company["company_code"],
    "company_name": company["company_name"],
    "business_exposure_zh": business_exposure,
    "mechanism_zh": direction.get("mechanism"),
    "horizon_directions": direction.get("horizons") or {},
    "conditions": direction.get("conditions") or [],
    "invalidation_conditions": direction.get("invalidation_conditions") or [],
    "counterevidence": counter.get("findings") or [],
    "confounder_argument_zh": argument.get("argument_zh"),
    "review_status": direction.get("review_status") or "NEEDS_HUMAN_REVIEW",
    "formal_ready": bool(direction.get("formal_ready", False)),
    "causal_attribution_allowed": bool(confounders.get("causal_attribution_allowed", False)),
    "evidence_ids": sorted(set(binding.get("evidence_ids") or [])),
}
```

- [ ] **Step 5: 规范行情与边界**

```python
boundaries = {
    "causal_claim_allowed": False,
    "market_is_validation_only": True,
    "review_status": _worst_review_status(ui_event),
    "limitations_zh": _collect_limitations(ui_event),
}
```

行情记录必须带 `asset_id`、`window`、`actual_date`、`raw_change` 或 `relative_change`、`verdict` 和 `linked_node_ids`；缺数据保留 `DATA_PENDING`，不得写成 0。

- [ ] **Step 6: 构建 event-01 契约并运行测试**

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests/test_research_content.py -q
```

Expected: PASS，且 event-01 的三个阶段文本不同，所有 evidence ID 非空且可追溯。

---

### Task 4: 将规范内容写入统一主数据

**Files:**
- Create: `training/fingoose_training/unified_builder_impl_003.py`
- Modify: `training/fingoose_training/unified_builder.py`
- Modify: `training/scripts/build_unified_dataset.py`
- Modify: `training/tests/test_unified_builder.py`

- [ ] **Step 1: 扩展 builder 接口**

```python
def build_unified_events(
    source: dict[str, list[dict[str, Any]]],
    dataset_version: str,
    *,
    ui_reference: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    records = _build_v2(source, dataset_version)
    if ui_reference is None:
        raise BuildError("content alignment requires ui_reference")
    ui_by_event = index_unique(ui_reference["events"], "event_id", "ui_reference.events")
    for record in records:
        ui_event = ui_by_event.get(record["event_id"])
        if ui_event is None:
            raise BuildError(f"ui reference missing event_id={record['event_id']}")
        record["research_content"] = build_event_research_content(ui_event)
        _attach_content_to_scopes(record)
        _recompile_reasoning_chains(record)
    return records
```

- [ ] **Step 2: 把内容按作用域写入四层对象**

```python
def _attach_content_to_scopes(record: dict[str, Any]) -> None:
    content = record["research_content"]
    record["event"]["research_content"] = deepcopy(content["macro_mechanism"])
    industry_by_id = {row["event_industry_mapping_id"]: row for row in content["industry_impacts"]}
    for industry in record["industries"]:
        industry["research_content"] = deepcopy(industry_by_id[industry["event_industry_mapping_id"]])
    company_by_id = {row["mapping_id"]: row for row in content["company_impacts"]}
    for company in record["companies"]:
        company["research_content"] = deepcopy(company_by_id[company["mapping_id"]])
    qa_by_id = {str(row["case_id"]): row for row in content["qa_sections"]}
    for qa in record["qa"]:
        qa["research_content"] = deepcopy(qa_by_id[str(qa["case_id"])])
```

任何 UI mapping_id 在统一数据中找不到，或统一数据 mapping_id 在 UI 中缺失，都应抛出 `BuildError`，禁止静默跳过。

- [ ] **Step 3: 在构建脚本加载 reference**

```python
ui_path = resolve_ui_reference_path(project_root, config)
ui_reference = load_ui_reference(ui_path)
records = build_unified_events(
    source,
    config["dataset_version"],
    ui_reference=ui_reference,
)
```

- [ ] **Step 4: 更新公开加载器**

`unified_builder.py` 只重导出 `unified_builder_impl_003` 的公开符号，不复制实现。

- [ ] **Step 5: 运行 builder 测试**

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests/test_unified_builder.py training/tests/test_research_content.py -q
```

Expected: PASS；10 个统一事件都有 `research_content.schema_version=research-content-v1`。

---

### Task 5: 用规范内容修正推理链陈述和主路径

**Files:**
- Create: `training/fingoose_training/reasoning_chain_impl_009.py`
- Modify: `training/fingoose_training/reasoning_chain.py`
- Modify: `training/tests/test_reasoning_chain_v1.py`
- Modify: `training/tests/test_sft_reasoning_chain_v1.py`

- [ ] **Step 1: 在编译前覆盖空陈述**

```python
PLACEHOLDER_STATEMENTS = {"", "待补充陈述。", "待补充陈述", "UNKNOWN"}


def _apply_content_statements(nodes: list[dict[str, Any]], content: Mapping[str, Any]) -> None:
    statement_by_id = content.get("statement_by_node_id") or {}
    for node in nodes:
        current = str(node.get("statement_zh") or "").strip()
        replacement = statement_by_id.get(node.get("node_id"))
        if current in PLACEHOLDER_STATEMENTS and replacement:
            node["statement_zh"] = replacement
        if str(node.get("statement_zh") or "").strip() in PLACEHOLDER_STATEMENTS:
            raise ValueError(f"unresolved reasoning statement: {node.get('node_id')}")
```

- [ ] **Step 2: 补齐 `premise_node_ids`**

对每条 edge 执行：

```python
premises: dict[str, set[str]] = defaultdict(set)
for edge in edges:
    premises[str(edge["to_node_id"])].add(str(edge["from_node_id"]))
for node in nodes:
    node["premise_node_ids"] = sorted(premises.get(str(node["node_id"]), set()))
```

状态传播必须基于这些真实前提，而不是仅依赖节点排列顺序。

- [ ] **Step 3: 使用内容契约指定 event 主路径**

```python
preferred = list(content.get("main_path_node_ids") or [])
if preferred:
    unknown = set(preferred) - {str(node["node_id"]) for node in nodes}
    if unknown:
        raise ValueError(f"content main path references unknown nodes: {sorted(unknown)}")
    graph["main_path_node_ids"] = preferred
    graph["final_node_id"] = preferred[-1]
```

event 主路径至少包含 `EVENT_FACT → shock/channel → intermediate/asset → MARKET_VALIDATION` 中的三层；最终节点不得是 `PRECONDITION` 里程碑。

- [ ] **Step 4: 保持证据状态诚实**

- 有 URL 但无原文/locator：仍可为 `EVIDENCE_MISSING`。
- 研究推断即使文案完整，没有直接来源时仍为 `INFERENCE_ONLY`。
- 行情节点固定为 `CALCULATED_ONLY`。
- UI 的 `NEEDS_HUMAN_REVIEW` 不改变节点事实状态，只进入 review metadata 和答案边界。

- [ ] **Step 5: 运行推理链测试**

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests/test_reasoning_chain_v1.py training/tests/test_sft_reasoning_chain_v1.py -q
```

Expected: PASS；event-01 主路径不再只包含第一个缺证里程碑。

---

### Task 6: 按四类任务生成高质量中文 assistant

**Files:**
- Create: `training/fingoose_training/answer_renderer.py`
- Create: `training/fingoose_training/sft_projector_impl_004.py`
- Modify: `training/fingoose_training/sft_projector.py`
- Test: `training/tests/test_high_quality_answers.py`
- Modify: `training/tests/test_sft_projector.py`

- [ ] **Step 1: 定义统一 section renderer**

```python
def render_sections(sections: Sequence[tuple[str, Sequence[str]]], max_chars: int) -> str:
    blocks: list[str] = []
    for heading, lines in sections:
        clean = [line.strip() for line in lines if isinstance(line, str) and line.strip()]
        if not clean:
            raise AnswerRenderError(f"empty required section: {heading}")
        block = heading + "：\n" + "\n".join(f"- {line}" for line in clean)
        if len("\n".join([*blocks, block])) > max_chars:
            break
        blocks.append(block)
    answer = "\n".join(blocks)
    if not answer.endswith("。"):
        answer += "。"
    return answer
```

禁止字符串中部硬截断；预算不足时减少次要行业/公司条目，但必须保留七个必需 section。

- [ ] **Step 2: 实现 EVENT_ANALYSIS 渲染**

固定顺序：

```python
sections = [
    ("结论", [render_event_conclusion(content)]),
    ("来源事实", render_source_facts(content, limit=2)),
    ("即时影响", [render_horizon(content, "IMMEDIATE")]),
    ("短期影响", [render_horizon(content, "SHORT_TERM")]),
    ("中期影响", [render_horizon(content, "MEDIUM_TERM")]),
    ("行情验证", render_market_validation(content, limit=2)),
    ("证据边界", [render_boundaries(content)]),
]
```

结论必须包含主要方向、关键机制和候选状态；来源事实中文化后保留证据 ID。

- [ ] **Step 3: 实现 INDUSTRY_IMPACT 渲染**

答案必须按具体行业输出：直接结论、事件事实、七步机制的可读摘要、即时/短期/中期、经营变量、财务变量、行情和失效条件。不得用整个 event 的行业平均替代当前行业。

```python
industry = select_industry_content(sample, event)
assert industry["event_industry_mapping_id"] in sample["metadata"]["related_industry_ids"]
```

- [ ] **Step 4: 实现 COMPANY_IMPACT 渲染**

答案必须包含：公司业务暴露、事件到公司的经营路径、即时/短期/中期方向、公司行情、混杂因素、反证、审核状态和因果边界。

```python
if not company["causal_attribution_allowed"]:
    boundary = "当前材料不允许将公司行情确定性归因于该宏观事件。"
if not company["formal_ready"]:
    boundary += "该记录仍为候选数据，状态为待人工审核。"
```

- [ ] **Step 5: 实现 EVENT_QA 渲染**

QA 首句必须直接回答问题，随后只引用当前问题相关的事件、行业、公司或行情节点。四类 QA 映射：

- `main-reasoning`：事件事实、机制和三阶段。
- `evidence-audit`：证据是否齐全、缺口与可核验位置。
- `market-validation`：具体资产窗口、支持/削弱/无法区分。
- `industry-company`：行业变量到公司业务暴露和公司边界。

- [ ] **Step 6: 在 projector 中替换旧 assistant，不再追加压缩 JSON**

```python
answer = render_answer(sample["task_type"], event=event, sample=sample, chain=chain)
messages[2]["content"] = answer
metadata["research_content_version"] = "research-content-v1"
metadata["research_content"] = select_task_content(event, sample)
```

保留现有完整 reasoning metadata；`messages` 不复制原文大段。

- [ ] **Step 7: 运行投影测试**

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests/test_high_quality_answers.py training/tests/test_sft_projector.py -q
```

Expected: PASS；四类 assistant 都没有空对象、占位语和 JSON 截断标记。

---

### Task 7: 增加语义质量和三层一致性门禁

**Files:**
- Create: `training/fingoose_training/validation_impl_004.py`
- Modify: `training/fingoose_training/validation.py`
- Test: `training/tests/test_content_alignment_validation.py`
- Modify: `training/tests/test_validation.py`

- [ ] **Step 1: 定义稳定错误码**

```python
CONTENT_ERROR_CODES = {
    "CONTENT_SCHEMA_MISSING",
    "CONTENT_REQUIRED_FIELD_MISSING",
    "CONTENT_PLACEHOLDER",
    "CONTENT_HORIZON_MISSING",
    "CONTENT_HORIZON_DUPLICATE",
    "CONTENT_EVIDENCE_UNKNOWN",
    "CONTENT_SCOPE_MISMATCH",
    "CONTENT_MARKET_NODE_MISMATCH",
    "CONTENT_UI_PARITY_MISMATCH",
    "ANSWER_REQUIRED_SECTION_MISSING",
    "ANSWER_PLACEHOLDER",
    "ANSWER_EVIDENCE_UNKNOWN",
    "ANSWER_REVIEW_BOUNDARY_MISSING",
    "REASONING_MAIN_PATH_TOO_SHALLOW",
    "REASONING_PRECONDITION_IS_FINAL",
}
```

- [ ] **Step 2: 检查占位语和空结构**

```python
PLACEHOLDER_TOKENS = (
    "待补充陈述",
    '"nodes": [{}, {}',
    "omitted_count",
    "[嵌套内容省略]",
)

if any(token in assistant for token in PLACEHOLDER_TOKENS):
    codes.append("ANSWER_PLACEHOLDER")
```

- [ ] **Step 3: 检查三个阶段不是机械重复**

```python
horizons = content.get("horizon_analysis") or {}
texts = [str((horizons.get(name) or {}).get("summary_zh") or "").strip() for name in HORIZONS]
if any(not text for text in texts):
    codes.append("CONTENT_HORIZON_MISSING")
elif len(set(texts)) != len(texts):
    codes.append("CONTENT_HORIZON_DUPLICATE")
```

- [ ] **Step 4: 检查证据和作用域**

- assistant 引用的 evidence ID 必须存在于 metadata registry。
- industry 样本只能引用当前 `related_industry_ids` 对应内容。
- company 样本只能引用当前 `related_company_codes` 对应内容。
- QA 样本引用上游链必须存在于 `parent_chain_refs`。
- market validation 的资产 ID 必须连接到 graph 中对应资产或行情节点。

- [ ] **Step 5: 检查审核边界**

当 task content 中存在 `formal_ready=false`、`NEEDS_HUMAN_REVIEW` 或 `causal_attribution_allowed=false` 时，assistant 必须出现“候选”“待人工审核”或“不允许确定性归因”等对应中文边界。

- [ ] **Step 6: 把质量统计写入 validation_report**

```python
report["content_quality_stats"] = {
    "content_contract_count": len(samples),
    "complete_horizon_count": complete_horizon_count,
    "placeholder_sample_count": placeholder_sample_count,
    "ui_parity_pass_count": ui_parity_pass_count,
    "answer_section_coverage": dict(sorted(section_coverage.items())),
    "review_boundary_count": review_boundary_count,
}
```

- [ ] **Step 7: 运行验证失败场景测试**

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests/test_content_alignment_validation.py training/tests/test_validation.py -q
```

Expected: PASS；每个构造的坏样本返回唯一稳定错误码。

---

### Task 8: event-01 金标准验收后扩展全部事件

**Files:**
- Modify: `training/tests/test_sft_real_dataset.py`
- Generated: `training/data/unified_events.jsonl`
- Generated: `training/data/sft_dataset.jsonl`

- [ ] **Step 1: 只构建 event-01 检查样本**

增加测试辅助函数按 `event_id=event-01` 过滤，但不改变正式 split。检查 16 条 event-01 样本：1 条事件、8 条行业、3 条公司、4 条 QA。

- [ ] **Step 2: 对 event-01 做逐层断言**

```python
event_samples = [row for row in samples if row["event_id"] == "event-01"]
assert Counter(row["task_type"] for row in event_samples) == {
    "EVENT_ANALYSIS": 1,
    "INDUSTRY_IMPACT": 8,
    "COMPANY_IMPACT": 3,
    "EVENT_QA": 4,
}
assert all(row["metadata"]["research_content_version"] == "research-content-v1" for row in event_samples)
assert all(not any(token in row["messages"][2]["content"] for token in PLACEHOLDER_TOKENS) for row in event_samples)
```

- [ ] **Step 3: 检查 event-01 关键语义**

- 宏观答案包含 WHO 大流行定性、风险偏好/全球需求/避险需求及行情边界。
- 石油石化答案包含原油需求、炼厂开工、库存、即时负向、短期负向、中期分化和减产失效条件。
- 医药生物答案包含检测需求、产品准入、短期正向和中期分化。
- 中国国航/上海机场/达安基因公司答案包含各自业务暴露，而不是共享同一公司模板。
- 四条 QA 分别直接回答证据查询、行情验证、行业到公司和主推理链。

- [ ] **Step 4: 扩展 10 个事件**

取消 gold-event 构建过滤，仅保留 `gold_event_ids` 作为回归样本标记。所有事件都必须通过同一 schema 和门禁，禁止为 event-02 至 event-10 写特殊分支。

- [ ] **Step 5: 运行真实数据测试**

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests/test_sft_real_dataset.py training/tests/test_high_quality_answers.py -q
```

Expected: PASS；四类任务仍为 10/77/30/40。

---

### Task 9: 文档、全量重建和确定性验收

**Files:**
- Modify: `training/README.md`
- Generated: `training/data/unified_events.jsonl`
- Generated: `training/data/sft_dataset.jsonl`
- Generated: `training/data/manifest.json`
- Generated: `training/data/split_manifest.json`
- Generated: `training/data/validation_report.json`
- Create: `docs/superpowers/plans/2026-08-07-high-quality-dataset-content-alignment-v1-execution-report.md`

- [ ] **Step 1: 更新 README**

记录：UI reference 只是受控结构化参考；`research_content_v1` 的字段；UI/metadata/messages 分工；四类答案模板；内容门禁；候选和人工审核边界。

- [ ] **Step 2: 重建统一主数据和 SFT**

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
$env:PYTHONUTF8='1'
python training/scripts/build_unified_dataset.py --config training/configs/dataset.json
python training/scripts/build_sft_dataset.py --config training/configs/dataset.json
```

Expected: `wrote 10 unified events`、`wrote 157 SFT samples`。

- [ ] **Step 3: 运行完整验证**

```powershell
python -m pytest training/tests -q
python -m compileall -q training/fingoose_training training/scripts
python training/scripts/validate_dataset.py --config training/configs/dataset.json
python training/scripts/train_sft.py --config training/configs/sft_qlora_3b.json --dry-run
```

Expected: 全部测试通过；`validation passed: 0 errors, 0 warnings`；dry-run `ready=true` 且 `model_loaded=false`。

- [ ] **Step 4: 做内容级抽样输出**

执行只读脚本输出以下 8 条 assistant：event-01 的事件分析、石油石化、医药生物、三家公司及四类 QA 中至少两类。逐条确认无 JSON 碎片、无占位语、三阶段具体、证据 ID 可追溯、审核边界存在。

- [ ] **Step 5: 连续重建并比较 SHA**

连续执行两次 Step 2 和 Step 3，比较：

```powershell
Get-FileHash -Algorithm SHA256 training/data/unified_events.jsonl
Get-FileHash -Algorithm SHA256 training/data/sft_dataset.jsonl
Get-FileHash -Algorithm SHA256 training/data/split_manifest.json
Get-FileHash -Algorithm SHA256 training/data/validation_report.json
```

任何差异都作为失败处理。

- [ ] **Step 6: 写执行报告**

报告必须包含：测试数量、任务分布、split 分布、内容契约数量、三阶段覆盖、占位样本数、UI parity 结果、证据缺口数、开放闭环数、四个 SHA 和 dry-run 状态。报告必须明确“未执行人工审核和真实 GPU 训练”。

---

## 实施顺序和停止条件

1. Task 1-7 只以 event-01 为金标准完成结构和内容门禁。
2. event-01 的事件、行业、公司、QA 四层全部通过后，才执行 Task 8 的全量扩展。
3. 若 UI bundle 与候选 JSONL 的 mapping/evidence ID 不一致，立即停止并报告具体 ID，不做猜测性映射。
4. 若 assistant 预算无法容纳七个必需 section，先压缩次要条目数量，不允许删除证据边界或三个时间阶段。
5. 若来源只有 URL、没有原文和 locator，继续标记 `EVIDENCE_MISSING`，不得因 UI 可点击链接而升级为 `VERIFIED_SOURCE`。
6. 若全量扩展造成现有 157 条数量或 split 变化，作为回归失败处理。

