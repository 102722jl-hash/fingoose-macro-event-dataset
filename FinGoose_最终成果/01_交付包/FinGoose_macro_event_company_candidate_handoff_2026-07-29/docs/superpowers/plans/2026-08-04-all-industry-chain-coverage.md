# FinGoose 全行业板块链覆盖 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让十个事件的全部 77 条行业分支始终可见，并在每条行业卡片上展示机制证据、驱动数据、行情窗口和公司样本四项可复核门禁。

**Architecture:** 在行业候选构建器中计算门禁字段并写入 `industry_completion_report.jsonl`，UI bundle 继续通过 `event_industry_mapping_id` 聚合这些字段。前端把行业层级从单选过滤改成三个同时展开的分组，把选中状态仅用于高亮、详情和公司联动，不再影响行业分支集合。

**Tech Stack:** Python 3.12、`unittest`/`pytest`、内嵌 HTML/CSS/JavaScript、JSONL。

---

### Task 1: 锁定完成门禁数据契约

**Files:**
- Modify: `tests/test_fingoose_industry_impact_v2.py`
- Modify: `code/fingoose_industry_impact_v2.py`

- [ ] **Step 1: 写入失败测试**

在 `test_candidate_builder_emits_six_joinable_layers` 中对每条完成报告增加以下断言：

```python
self.assertEqual(
    set(completion["gate_statuses"]),
    {"mechanism_evidence", "driver_data", "market_window", "company_sample"},
)
self.assertEqual(
    set(completion["evidence_coverage"]),
    {"required_node_count", "evidenced_node_count", "missing_node_ids"},
)
self.assertEqual(completion["evidence_coverage"]["required_node_count"], 7)
self.assertEqual(
    completion["evidence_coverage"]["evidenced_node_count"]
    + len(completion["evidence_coverage"]["missing_node_ids"]),
    7,
)
```

- [ ] **Step 2: 运行测试并确认 RED**

Run: `python -m pytest tests/test_fingoose_industry_impact_v2.py -q`

Expected: 因 `gate_statuses` 或 `evidence_coverage` 不存在而失败。

- [ ] **Step 3: 实现最小门禁计算**

在 `build_industry_candidate_bundle()` 中根据当前链、驱动、窗口和公司链接生成：

```python
missing_node_ids = [
    node["node_id"]
    for node in chain["nodes"]
    if not node.get("evidence_ids")
]
evidence_coverage = {
    "required_node_count": len(chain["nodes"]),
    "evidenced_node_count": len(chain["nodes"]) - len(missing_node_ids),
    "missing_node_ids": missing_node_ids,
}
gate_statuses = {
    "mechanism_evidence": "AVAILABLE" if not missing_node_ids else "DATA_PENDING",
    "driver_data": driver["primary_driver"]["source_status"],
    "market_window": window["window_status"],
    "company_sample": "AVAILABLE" if company_links else "DATA_PENDING",
}
```

将两个对象写入对应 `completion`，保留 `completion_status="OPEN"`、`formal_ready=false` 和 `sha_gate="DEFERRED"`。

- [ ] **Step 4: 运行测试并确认 GREEN**

Run: `python -m pytest tests/test_fingoose_industry_impact_v2.py -q`

Expected: PASS。

### Task 2: 锁定全部行业始终可见的 UI 行为

**Files:**
- Modify: `tests/test_fingoose_industry_ui_v2.py`
- Modify: `code/fingoose_company_impact_ui_v2.py`

- [ ] **Step 1: 写入失败测试**

增加 HTML 契约测试，要求事件行业链不再按选中行业或层级过滤，并要求三个分组和四项门禁存在：

```python
def test_all_industry_branches_remain_visible_after_selection(self) -> None:
    self.assertNotIn(
        "if(state.industryMappingId)rows=rows.filter",
        self.html,
    )
    self.assertNotIn(
        "else rows=rows.filter(function(row){return row.impact_tier===state.industryTier})",
        self.html,
    )
    self.assertIn("industry-tier-group", self.html)
    self.assertIn("机制证据", self.html)
    self.assertIn("驱动数据", self.html)
    self.assertIn("行情窗口", self.html)
    self.assertIn("公司样本", self.html)
```

再增加冻结分支计数的 bundle 断言，覆盖十事件 `8/8/8/8/7/7/7/7/8/9`。

- [ ] **Step 2: 运行测试并确认 RED**

Run: `python -m pytest tests/test_fingoose_industry_ui_v2.py -q`

Expected: 当前 HTML 含选中行业过滤逻辑，测试失败。

- [ ] **Step 3: 实现全量行业链**

修改 `renderIndustryPaths(event)`：仅按事件读取 `event.industry_impacts`，不按 `state.industryMappingId`、`state.industryTier` 或时间线锚点删减分支；按 `CORE_DIRECT / SECOND_ORDER / CONDITIONAL` 分组输出。选中行业只增加 `active` 类名，并由 `data-industry-detail` 更新详情。

- [ ] **Step 4: 实现三组行业卡片**

修改 `renderIndustries(event)`：三个层级同时输出 `.industry-tier-group`，层级按钮只负责聚焦对应组；每张卡使用 `impact.completion.gate_statuses` 和 `evidence_coverage` 展示：

```javascript
const gate=impact.completion.gate_statuses||{};
const coverage=impact.completion.evidence_coverage||{};
const gateHtml='<div class="industry-gates">'
  +'<span>机制证据 '+esc(coverage.evidenced_node_count||0)+'/'+esc(coverage.required_node_count||7)+'</span>'
  +'<span>驱动数据 '+esc(status(gate.driver_data||'DATA_PENDING'))+'</span>'
  +'<span>行情窗口 '+esc(status(gate.market_window||'DATA_PENDING'))+'</span>'
  +'<span>公司样本 '+esc(impact.company_count||0)+' 家</span>'
  +'</div>';
```

- [ ] **Step 5: 增加响应式样式**

为 `.industry-tier-group`、`.industry-tier-group-head`、`.industry-gates` 和选中行业链卡片增加稳定网格、状态颜色和 390px 单列规则，禁止横向溢出。

- [ ] **Step 6: 运行测试并确认 GREEN**

Run: `python -m pytest tests/test_fingoose_industry_ui_v2.py -q`

Expected: PASS。

### Task 3: 重新生成候选数据和 UI

**Files:**
- Generated: `work/industry_impact_high_quality_v2_candidate/industry_completion_report.jsonl`
- Generated: `work/company_impact_high_quality_v2_candidate/ui/index.html`

- [ ] **Step 1: 运行行业构建器**

Run: `python code/fingoose_industry_impact_v2.py`

Expected: 输出 77 条映射，所有记录仍为 `OPEN`。

- [ ] **Step 2: 运行 UI 构建器**

Run: `python code/fingoose_company_impact_ui_v2.py`

Expected: 更新 `work/company_impact_high_quality_v2_candidate/ui/index.html`。

- [ ] **Step 3: 验证生成数据**

Run: `python -m pytest tests/test_fingoose_industry_impact_v2.py tests/test_fingoose_industry_ui_v2.py -q`

Expected: 两个测试文件全部 PASS，77 条完成报告均含四项门禁和证据覆盖字段。

### Task 4: 完整回归与浏览器验收

**Files:**
- Verify: `work/company_impact_high_quality_v2_candidate/ui/index.html`

- [ ] **Step 1: 运行相关完整测试集**

Run: `python -m pytest tests/test_fingoose_company_impact_ui_v2.py tests/test_fingoose_industry_impact_v2.py tests/test_fingoose_industry_ui_v2.py tests/test_build_fingoose_company_impact_high_quality_v2.py -q`

Expected: 全部 PASS，且无警告或控制台错误。

- [ ] **Step 2: 桌面端验收**

在 1440×900 下检查 event-01 同时显示 8 条行业分支，点击任一行业后仍为 8 条；event-10 显示 9 条。确认行业详情、公司筛选和折线图空状态联动正常。

- [ ] **Step 3: 移动端验收**

在 390×844 下检查三个层级均可见、卡片单列、门禁文字不溢出、行业链横向滚动区域不遮挡页面正文。

- [ ] **Step 4: 校验状态边界**

确认页面仍包含 `PROPOSED`、`NEEDS_HUMAN_REVIEW`、`formal_ready=false`、`sha_gate=DEFERRED`，缺行情时不绘制虚假折线、不补零。

## 自审结论

- 规格覆盖：全行业可见、三层同时展开、四项门禁、选中仅联动详情、缺失数据边界和十事件计数均有对应任务。
- 占位扫描：没有 `TBD`、`TODO` 或未定义实现步骤。
- 类型一致性：数据层统一使用 `gate_statuses` 与 `evidence_coverage`；UI 仅消费这两个字段，不临时推测完成状态。
- 仓库边界：当前目录不是 Git 仓库，因此计划不包含提交步骤。
