# FinGoose 事件—公司专属经营机制链实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为冻结的 30 条事件—公司映射生成一一对应的七层经营机制主链，并在 UI 中以完整路径卡片展示，同时保持候选审核和发布边界。

**Architecture:** 新增独立的机制链模型与构建器，复用时间线锚点、现有宏观绑定、公司年报证据、方向候选、行情和混杂数据。现有 JSONL 不合并，机制链通过 ID 引用各层；完成报告增加经营链硬门禁，UI 只做聚合投影。

**Tech Stack:** Python 3、JSONL、unittest/pytest、原生 HTML/CSS/JavaScript。

**Repository note:** 当前目录不是 Git 仓库。计划中的提交检查点改为运行测试并记录输出，不执行 `git commit`。

---

### Task 1: 经营机制链模型与结构门禁

**Files:**
- Create: `code/fingoose_company_mechanism_chain_v2.py`
- Create: `tests/test_fingoose_company_mechanism_chain_v2.py`
- Modify: `code/fingoose_company_candidate_completion_v2.py`

- [ ] **Step 1: 写入七层连续链失败测试**

```python
def test_chain_requires_exact_seven_layer_sequence():
    chain = build_mechanism_chain(
        mapping={"mapping_id": "m1", "event_id": "event-01", "anchor_id": "a1"},
        nodes=valid_seven_nodes(),
        edges=valid_six_edges(),
        technical_binding_ids=["binding-1"],
    )
    assert [node["node_type"] for node in chain["nodes"]] == [
        "EVENT_FACT",
        "BEHAVIOR_OR_POLICY_CHANGE",
        "OBSERVABLE_OPERATING_VARIABLE",
        "INDUSTRY_REVENUE_OR_COST_VARIABLE",
        "COMPANY_BUSINESS_EXPOSURE",
        "DIRECTION_ASSESSMENT",
        "PRICE_AND_CONFOUNDER_VERIFICATION",
    ]
    assert chain["chain_status"] == "PROPOSED_COMPANY_MECHANISM"
    assert chain["review_status"] == "NEEDS_HUMAN_REVIEW"
```

- [ ] **Step 2: 写入断链、证据混用和价格泄漏失败测试**

```python
def test_chain_rejects_disconnected_edges():
    with pytest.raises(ValueError, match="MECHANISM_CHAIN_DISCONNECTED"):
        build_mechanism_chain(mapping=MAPPING, nodes=valid_seven_nodes(), edges=[])

def test_chain_separates_event_and_company_evidence():
    with pytest.raises(ValueError, match="EVIDENCE_SCOPE_COLLISION"):
        build_mechanism_chain(
            mapping=MAPPING,
            nodes=nodes_with_same_event_and_company_evidence_id(),
            edges=valid_six_edges(),
        )

def test_chain_rejects_post_event_price_selection():
    with pytest.raises(ValueError, match="PRICE_SELECTION_LEAKAGE"):
        build_mechanism_chain(
            mapping=MAPPING,
            nodes=valid_seven_nodes(),
            edges=valid_six_edges(),
            price_selection_used=True,
        )
```

- [ ] **Step 3: 运行测试并确认因模块缺失失败**

Run:

```powershell
python -m pytest tests/test_fingoose_company_mechanism_chain_v2.py -q
```

Expected: FAIL，错误为 `ModuleNotFoundError: fingoose_company_mechanism_chain_v2`。

- [ ] **Step 4: 实现模型和结构校验**

核心接口：

```python
NODE_TYPES = (
    "EVENT_FACT",
    "BEHAVIOR_OR_POLICY_CHANGE",
    "OBSERVABLE_OPERATING_VARIABLE",
    "INDUSTRY_REVENUE_OR_COST_VARIABLE",
    "COMPANY_BUSINESS_EXPOSURE",
    "DIRECTION_ASSESSMENT",
    "PRICE_AND_CONFOUNDER_VERIFICATION",
)

def build_mechanism_chain(
    *,
    mapping: Mapping[str, Any],
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    technical_binding_ids: Sequence[str],
    rejected_binding_ids: Sequence[str],
    event_evidence_ids: Sequence[str],
    company_evidence_ids: Sequence[str],
    price_selection_used: bool = False,
) -> dict[str, Any]:
    if [row.get("node_type") for row in nodes] != list(NODE_TYPES):
        raise ValueError("MECHANISM_CHAIN_LAYER_SEQUENCE_INVALID")
    expected_pairs = [
        (nodes[index]["node_id"], nodes[index + 1]["node_id"])
        for index in range(len(nodes) - 1)
    ]
    actual_pairs = [(row.get("from_node_id"), row.get("to_node_id")) for row in edges]
    if actual_pairs != expected_pairs:
        raise ValueError("MECHANISM_CHAIN_DISCONNECTED")
    if set(event_evidence_ids) & set(company_evidence_ids):
        raise ValueError("EVIDENCE_SCOPE_COLLISION")
    if price_selection_used:
        raise ValueError("PRICE_SELECTION_LEAKAGE")
    return {
        "chain_id": "mechanism-chain-" + str(mapping["mapping_id"]),
        "mapping_id": mapping["mapping_id"],
        "event_id": mapping["event_id"],
        "anchor_id": mapping["anchor_id"],
        "nodes": [dict(row) for row in nodes],
        "edges": [dict(row) for row in edges],
        "technical_binding_ids": list(technical_binding_ids),
        "rejected_binding_ids": list(rejected_binding_ids),
        "event_evidence_ids": list(event_evidence_ids),
        "company_evidence_ids": list(company_evidence_ids),
        "price_selection_used": False,
        "chain_status": "PROPOSED_COMPANY_MECHANISM",
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }
```

- [ ] **Step 5: 扩展完成门禁**

在 `evaluate_completion` 增加 `mechanism_chain` 参数，并执行：

```python
if mechanism_chain.get("chain_status") != "PROPOSED_COMPANY_MECHANISM":
    blockers.append("MECHANISM_CHAIN_INCOMPLETE")
if len(mechanism_chain.get("nodes") or []) != 7:
    blockers.append("MECHANISM_CHAIN_INCOMPLETE")
```

- [ ] **Step 6: 运行模型和原完成门禁测试**

Run:

```powershell
python -m pytest tests/test_fingoose_company_mechanism_chain_v2.py tests/test_fingoose_company_candidate_completion_v2.py -q
```

Expected: PASS。

### Task 2: 30 条事件专属公司经营链

**Files:**
- Create: `configs/company_impact_high_quality_v2/company_mechanism_profiles.jsonl`
- Create: `code/build_fingoose_company_mechanism_chains_v2.py`
- Create: `tests/test_build_fingoose_company_mechanism_chains_v2.py`
- Generate: `work/company_impact_high_quality_v2_candidate/event_company_mechanism_chains.jsonl`

- [ ] **Step 1: 写入 30 条覆盖和 event-01 专项失败测试**

```python
def test_builder_emits_one_chain_per_frozen_mapping():
    report = build(ROOT, OUTPUT)
    rows = read_jsonl(OUTPUT / "event_company_mechanism_chains.jsonl")
    assert report["mechanism_chain_count"] == 30
    assert len(rows) == 30
    assert len({row["mapping_id"] for row in rows}) == 30

def test_event_01_daan_uses_diagnostic_demand_chain():
    row = chain("event-01", "002030.SZ")
    text = " ".join(node["title_zh"] + node["explanation_zh"] for node in row["nodes"])
    assert "核酸检测" in text
    assert "检测试剂" in text
    assert "达安基因" in text
    assert "DCOILWTICO" not in text
    assert "SP500" not in text

def test_event_01_transport_uses_passenger_variables():
    for code in ("600009.SH", "601111.SH"):
        text = chain_text("event-01", code)
        assert "客流" in text or "旅客吞吐量" in text
        assert "DCOILWTICO" not in text
```

- [ ] **Step 2: 运行测试并确认构建器缺失**

Run:

```powershell
python -m pytest tests/test_build_fingoose_company_mechanism_chains_v2.py -q
```

Expected: FAIL，错误为 `ModuleNotFoundError: build_fingoose_company_mechanism_chains_v2`。

- [ ] **Step 3: 建立 30 条配置记录**

每条配置必须包含：

```json
{
  "mapping_id": "event-company-df4365c2f77893d2",
  "behavior_change_zh": "疫情全球扩散推动公共卫生检测需求上升",
  "operating_variable_zh": "核酸检测量、试剂需求和产品准入兑现",
  "operating_metric": "核酸检测需求与获批产品兑现情况",
  "operating_unit": "检测量、试剂销量或获批范围",
  "industry_variable_zh": "体外诊断行业检测收入与试剂需求",
  "company_exposure_zh": "达安基因诊断试剂业务暴露",
  "immediate_direction": "UNKNOWN",
  "short_term_direction": "POSITIVE",
  "medium_term_direction": "MIXED",
  "conditions": ["公司产品取得准入且需求能够转化为订单"],
  "invalidation_conditions": ["产品未取得准入或检测需求未转化为公司收入"]
}
```

其余 29 条按公司业务分别使用客流、酒店入住率、油价与炼化价差、利率与净息差、融资成本、航油成本、集运运价、证券成交活跃度、房地产销售回款、光伏出口、消费电子订单等经营变量。禁止将代码型宏观资产直接写入主链。

- [ ] **Step 4: 实现构建器**

构建器读取：

```text
event_company_map.jsonl
event_company_binding_reviews.jsonl
company_mechanism_profiles.jsonl
company_evidence.jsonl
direction_assessments.jsonl
company_market_windows.jsonl
relative_return_windows.jsonl
company_confounders.jsonl
timeline_nodes.jsonl
```

为每条映射生成七个节点和六条连续边；事件事实节点引用时间线证据，公司暴露节点只引用公司证据，验证节点只引用价格和混杂记录 ID。

- [ ] **Step 5: 添加经营变量质量断言**

```python
FORBIDDEN_PRIMARY_TOKENS = {"DCOILWTICO", "DCOILBRENTEU", "SP500", "DEXCHUS", "VIXCLS"}

assert not FORBIDDEN_PRIMARY_TOKENS.intersection(
    token
    for row in chains
    for node in row["nodes"]
    for token in FORBIDDEN_PRIMARY_TOKENS
    if token in node["title_zh"] or token in node["explanation_zh"]
)
```

- [ ] **Step 6: 运行 30 条构建测试**

Run:

```powershell
python -m pytest tests/test_build_fingoose_company_mechanism_chains_v2.py -q
```

Expected: PASS，30 条映射、30 条主链、210 个节点、180 条边。

### Task 3: 接入候选完成报告和主构建

**Files:**
- Modify: `code/build_fingoose_company_candidate_completion_v2.py`
- Modify: `code/build_fingoose_company_impact_high_quality_v2.py`
- Modify: `tests/test_fingoose_company_candidate_completion_v2.py`
- Modify: `tests/test_build_fingoose_company_impact_high_quality_v2.py`

- [ ] **Step 1: 写入主构建覆盖失败测试**

```python
assert (output / "event_company_mechanism_chains.jsonl").exists()
assert report["mechanism_chain_count"] == 30
assert report["mechanism_chain_node_count"] == 210
assert report["mechanism_chain_edge_count"] == 180
```

- [ ] **Step 2: 运行主构建测试并确认失败**

Run:

```powershell
python -m pytest tests/test_build_fingoose_company_impact_high_quality_v2.py -q
```

Expected: FAIL，缺少机制链计数或输出文件。

- [ ] **Step 3: 将机制链构建器接入完成层**

在 `build_fingoose_company_candidate_completion_v2.build` 中先生成机制链，再按 `mapping_id` 传给 `evaluate_completion`：

```python
mechanism_chains = build_mechanism_chains(root, output)
chains_by_mapping = {row["mapping_id"]: row for row in mechanism_chains}
completion = [
    evaluate_completion(
        mapping_id=mapping["mapping_id"],
        mechanism_chain=chains_by_mapping[mapping["mapping_id"]],
        binding_review=bindings_by_mapping[mapping["mapping_id"]],
        dossier=dossiers_by_company[mapping["company_id"]],
        direction=directions_by_mapping[mapping["mapping_id"]],
        market_window=markets_by_mapping[mapping["mapping_id"]],
        relative_window=relatives_by_mapping[mapping["mapping_id"]],
        confounder=confounders_by_mapping[mapping["mapping_id"]],
    )
    for mapping in mappings
]
```

- [ ] **Step 4: 增加主构建硬失败检查**

检查 30 个机制链 `mapping_id` 与映射全集完全相等，所有链均为 `PROPOSED_COMPANY_MECHANISM`，并验证 `formal_ready=false`、`sha_gate=DEFERRED`、`price_selection_used=false`。

- [ ] **Step 5: 运行完成层和主构建测试**

Run:

```powershell
python -m pytest tests/test_fingoose_company_candidate_completion_v2.py tests/test_build_fingoose_company_impact_high_quality_v2.py -q
```

Expected: PASS。

### Task 4: UI 完整路径卡片和技术详情

**Files:**
- Modify: `code/fingoose_company_impact_ui_v2.py`
- Modify: `tests/test_fingoose_company_impact_ui_v2.py`
- Generate: `work/company_impact_high_quality_v2_candidate/ui/index.html`
- Generate: `work/company_impact_high_quality_v2_candidate/ui/ui_data_bundle.js`

- [ ] **Step 1: 写入 UI bundle 失败测试**

```python
event = project_event(bundle, "event-01")
daan = next(row for row in event["companies"] if row["company_code"] == "002030.SZ")
assert daan["mechanism_chain"]["chain_status"] == "PROPOSED_COMPANY_MECHANISM"
assert len(daan["mechanism_chain"]["nodes"]) == 7
assert daan["binding_review"]["primary_binding_id"]
assert daan["completion"]["completion_status"] in {"OPEN", "CANDIDATE_COMPLETE"}
```

- [ ] **Step 2: 写入页面结构失败测试**

```python
html = render_workbench(bundle)
assert "完整经营机制链" in html
assert "技术详情" in html
assert "候选闭环矩阵" in html
assert "逐边平铺" not in html
```

- [ ] **Step 3: 运行 UI 测试并确认失败**

Run:

```powershell
python -m pytest tests/test_fingoose_company_impact_ui_v2.py -q
```

Expected: FAIL，bundle 缺少 `mechanism_chain` 或页面缺少完整路径结构。

- [ ] **Step 4: 扩展 UI 数据投影**

`build_ui_bundle` 支持 `candidate_root`，读取机制链、绑定评审和完成报告。每家公司投影增加：

```python
{
    "mechanism_chain": chains.get(mapping_id),
    "binding_review": binding_reviews.get(mapping_id),
    "completion": completion.get(mapping_id),
}
```

- [ ] **Step 5: 实现主路径卡片**

卡片按 `sequence` 显示七层节点。节点标题、解释、方向、时间、单位和证据链接直接来自机制链；不在 UI 中重新推断机制。

- [ ] **Step 6: 实现技术详情折叠区**

使用原生 `<details>` 和 `<summary>`，展示 `technical_binding_ids`、主次绑定、拒绝理由、证据 ID、审核状态和 blockers。

- [ ] **Step 7: 实现候选闭环矩阵**

按事件显示三家公司六项门禁状态：

```text
经营机制链
公司 dossier
三期限方向
公司/大盘/行业窗口
混杂检索
停复牌状态
```

矩阵数据必须来自 `candidate_completion_report.jsonl` 和各底层记录，不在 JavaScript 中修改状态。

- [ ] **Step 8: 运行 UI 测试**

Run:

```powershell
python -m pytest tests/test_fingoose_company_impact_ui_v2.py -q
```

Expected: PASS。

### Task 5: 生产构建、回归与边界验证

**Files:**
- Generate/Modify: `work/company_impact_high_quality_v2_candidate/*.jsonl`
- Generate/Modify: `work/company_impact_high_quality_v2_candidate/ui/*`
- Modify: `work/company_impact_high_quality_v2_candidate/summary.json`
- Modify: `work/company_impact_high_quality_v2_candidate/validation_report.json`

- [ ] **Step 1: 运行生产构建**

Run:

```powershell
python code/build_fingoose_company_impact_high_quality_v2.py --root . --output work/company_impact_high_quality_v2_candidate
```

Expected: JSON 输出中 `event_company_count=30`、`mechanism_chain_count=30`、`formal_ready=false`、`sha_gate=DEFERRED`。

- [ ] **Step 2: 运行公司影响专项测试**

Run:

```powershell
python -m pytest tests/test_fingoose_company_mechanism_chain_v2.py tests/test_build_fingoose_company_mechanism_chains_v2.py tests/test_fingoose_company_candidate_completion_v2.py tests/test_build_fingoose_company_impact_high_quality_v2.py tests/test_fingoose_company_impact_ui_v2.py -q
```

Expected: PASS。

- [ ] **Step 3: 运行全量回归**

Run:

```powershell
python -m pytest -q
```

Expected: PASS；若存在与本任务无关的既有失败，记录测试名和错误，不修改无关模块。

- [ ] **Step 4: 校验发布边界和数据计数**

Run:

```powershell
rg -n "\"formal_ready\":true|\"sha_gate\":\"ENFORCED\"|\"chain_status\":\"CONFIRMED\"" work/company_impact_high_quality_v2_candidate -g "*.json" -g "*.jsonl"
```

Expected: 无匹配。

运行 JSONL 覆盖检查，确认：

```text
30 mechanism chains
210 chain nodes
180 chain edges
30 binding reviews
30 direction reviews
30 market windows
30 relative windows
30 confounder records
30 completion reports
```

- [ ] **Step 5: 浏览器验证**

打开 `work/company_impact_high_quality_v2_candidate/ui/index.html`，逐个检查十个事件。event-01 必须显示达安基因检测需求链、上海机场旅客吞吐量链和中国国航客流链；技术详情默认折叠；页面不得把 `OPEN` 显示为已完成。

- [ ] **Step 6: 记录检查点**

由于无 Git 仓库，在 `validation_report.json` 中保留测试命令、通过数量、生成时间、正式发布边界和未关闭 blocker 计数，作为本轮可复核检查点。

