# FinGoose 研究工作台界面重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with review checkpoints.

**Goal:** 将十事件快速候选版改造成左侧事件导航、右侧联动长页面的中文投研工作台，补充证据摘录、动态传导可视化、行情折线图和丰富的混杂解释。

**Architecture:** 保留现有 JSON/JSONL 数据合同和 RAPID_CANDIDATE 边界，扩展 Python 生成器生成一个内嵌全部事件 payload 的单页应用；页面状态只在浏览器内切换，不修改数据。中文 UI 文案、阶段/状态映射、受控混杂论证由生成器提供，原始英文事实和引文只在折叠证据块中保留。

**Tech Stack:** Python 3 标准库、现有 HTML/CSS/原生 JavaScript、原生 SVG、unittest、Node `--check`。

---

### Task 1: 先建立页面合同测试

**Files:**
- Modify: `handoff/FinGoose_macro_event_company_candidate_handoff_2026-07-29/tests/test_build_fingoose_ten_event_rapid_candidate_v2.py`

- [ ] **Step 1: 写失败测试**

在 `TenEventOutputTests` 增加以下测试，调用现有 `build(ROOT, output)` 后读取 `index.html`：

```python
def test_overview_is_linked_research_workbench(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        html = (Path(tmp) / "ten_event_rapid_candidate_v2" / "index.html")
        build(ROOT, html.parent)
        page = html.read_text(encoding="utf-8")
    self.assertIn('class="event-sidebar"', page)
    self.assertIn('data-event-id="event-02"', page)
    self.assertIn('id="research-main"', page)
    self.assertIn('data-node-id=', page)
    self.assertIn('<svg', page)
    self.assertIn('混杂与竞争解释', page)
    self.assertNotIn('RAPID_CANDIDATE', page)
    self.assertNotIn('PENDING_EVIDENCE', page)
```

增加状态联动合同测试：

```python
def test_workbench_contains_cross_section_linkage_contract(self) -> None:
    page = self._build_overview_html()
    for token in ('selectEvent(', 'selectTimelineNode(', 'data-path-id=', 'scrollIntoView', 'windowPoints'):
        self.assertIn(token, page)
```

- [ ] **Step 2: 运行测试确认按预期失败**

运行：
`python -m unittest tests.test_build_fingoose_ten_event_rapid_candidate_v2.TenEventOutputTests.test_overview_is_linked_research_workbench -v`

预期：FAIL，因为当前总览仍是事件卡片页，没有 `event-sidebar` 和内嵌 SVG。

### Task 2: 增加受控中文派生文案和数据聚合

**Files:**
- Modify: `handoff/FinGoose_macro_event_company_candidate_handoff_2026-07-29/code/build_fingoose_ten_event_rapid_candidate_v2.py`
- Test: `handoff/FinGoose_macro_event_company_candidate_handoff_2026-07-29/tests/test_build_fingoose_ten_event_rapid_candidate_v2.py`

- [ ] **Step 1: 写派生文案测试**

```python
def test_ui_copy_maps_status_phase_and_market_labels_to_chinese(self) -> None:
    from build_fingoose_ten_event_rapid_candidate_v2 import ui_copy
    copy = ui_copy()
    self.assertEqual(copy["status"]["PENDING_EVIDENCE"], "待补证")
    self.assertEqual(copy["phase"]["INITIAL_SHOCK"], "首次冲击")
    self.assertEqual(copy["window"]["T-1"], "前一交易日")
```

- [ ] **Step 2: 运行测试确认失败**

运行同名测试，预期 `ImportError` 或 `AttributeError`，因为 `ui_copy()` 尚不存在。

- [ ] **Step 3: 实现最小派生层**

新增 `ui_copy()` 返回状态、阶段、窗口、资产角色、方向和证据范围的中文映射；新增 `build_confounder_argument(event_id, timeline, paths, confounder)`，只使用事件标题、混杂描述、受影响窗口、路径名称和已有证据 ID 组装 180-350 字中文论证，并对无事实的字段明确写“当前数据未证明”。新增 `build_workbench_payloads(...)` 将十个事件 payload 以事件 ID 建索引，保留 `formal_ready=false`、pending 节点和 PROPOSED 状态。

- [ ] **Step 4: 运行派生层测试确认通过**

运行上述测试，预期 PASS。

### Task 3: 重构总览页为单页工作台骨架

**Files:**
- Modify: `handoff/FinGoose_macro_event_company_candidate_handoff_2026-07-29/code/build_fingoose_ten_event_rapid_candidate_v2.py`

- [ ] **Step 1: 写页面骨架测试**

增加断言：十个 `data-event-id`、`event-sidebar`、`research-main`、移动端菜单按钮和版本状态中文文案均存在。

- [ ] **Step 2: 实现 `render_workbench(payloads, initial_event_id)`**

使用稳定结构：

```html
<aside class="event-sidebar" aria-label="事件导航">...</aside>
<main id="research-main">...</main>
```

CSS 使用 248px 左栏和 `minmax(0,1fr)` 主区；移动端将左栏转为横向事件选择器。页面内嵌 `window.__FINGOOSE_DATA__`，不再为每次点击跳转文件。

- [ ] **Step 3: 让 `render_overview` 调用工作台渲染器**

保留总览统计和入口文件名，改为 `render_workbench(all_payloads, "event-01")`；事件页继续生成，但复用同一渲染器并传入单一初始事件，确保直接打开任一事件页时仍具备左侧导航。

- [ ] **Step 4: 运行页面骨架测试确认通过**

运行 `python -m unittest tests.test_build_fingoose_ten_event_rapid_candidate_v2.TenEventOutputTests -v`，预期新旧页面合同均通过。

### Task 4: 实现联动时间线和动态传导链

**Files:**
- Modify: `handoff/FinGoose_macro_event_company_candidate_handoff_2026-07-29/code/build_fingoose_ten_event_rapid_candidate_v2.py`

- [ ] **Step 1: 写联动测试**

断言每个节点具有 `data-node-id`，每条路径具有 `data-path-id`，脚本包含 `selectTimelineNode`、`activatePath` 和 `scrollIntoView`，且 PENDING 节点没有评分标记。

- [ ] **Step 2: 实现时间线渲染**

按 `phase` 分组，渲染阶段标题、时间、事实摘要、中文影响标签、证据状态、quote 摘录和来源链接；节点按钮使用 `data-node-id`，点击调用 `selectTimelineNode(nodeId)`。

- [ ] **Step 3: 实现传导链渲染**

将 `chain` 映射为四个节点，分别标注“冲击类型、统一渠道、事件中间变量、资产”；为路径显示方向、时滞、条件、失效条件、反证、事实证据和机制证据；路径使用 `data-path-id` 和 `data-anchor-node-id`。

- [ ] **Step 4: 实现前端联动**

`selectTimelineNode` 根据 `anchor_fast_node_ids` 找到路径，切换 `.is-selected`，更新上下文条并滚动至首条路径；点击路径反向高亮时间线节点。禁止变更 payload 的证据状态和评分字段。

- [ ] **Step 5: 运行联动测试确认通过**

运行对应测试和 Node `--check`，预期 PASS。

### Task 5: 增加行情 SVG 折线图和证据/混杂详情

**Files:**
- Modify: `handoff/FinGoose_macro_event_company_candidate_handoff_2026-07-29/code/build_fingoose_ten_event_rapid_candidate_v2.py`

- [ ] **Step 1: 写图表与证据测试**

断言页面包含 `windowPoints`、`polyline`、T-1/T0/D1/D3/D5/D20 中文标签、公式字段、`target="_blank"`、`事后机制验证` 和每个事件的混杂论证容器。

- [ ] **Step 2: 实现 `render_market_chart(series)`**

从已有 `display_windows` 读取日期和值，过滤 `None` 后按窗口顺序归一化到 SVG viewBox；保留断点，不插值；生成折线、T0/D1 标记、混杂区间色带和 hover 文本。

- [ ] **Step 3: 实现证据摘录与中文摘要**

事实来源显示来源机构、中文摘要、原文 quote、locator 和外链；机制来源显示“事后机制验证，不用于事前预测”；无 URL 显示“来源链接待补”。

- [ ] **Step 4: 实现混杂长文**

将 `build_confounder_argument` 输出放入混杂区，并单独列出影响窗口、竞争路径、反证和证据链接；用 `CHALLENGE_ONLY` 中文状态防止清洁归因过度表述。

- [ ] **Step 5: 运行图表与证据测试确认通过**

运行页面合同测试和已有全量回归。

### Task 6: 视觉回归与交付

**Files:**
- Modify: `handoff/FinGoose_macro_event_company_candidate_handoff_2026-07-29/tests/test_build_fingoose_ten_event_rapid_candidate_v2.py`

- [ ] **Step 1: 运行完整 Python 回归**

`python -m unittest tests.test_build_fingoose_event_02_rapid_candidate_v2 tests.test_build_fingoose_ten_event_rapid_candidate_v2 -v`

预期 25 项或新增测试全部通过。

- [ ] **Step 2: 编译并检查生成脚本**

`python -m compileall -q code tests`

对总览页和十个事件页执行 `node --check`，确认内联脚本无语法错误。

- [ ] **Step 3: 浏览器验证桌面和移动端**

启动静态页面，验证 1440px 和 390px：左侧导航、联动滚动、折线图非空、表格不遮挡、证据链接可点击；保存至少 2 张截图用于 QA。

- [ ] **Step 4: 读取最终报告并交付**

确认 `hard_failures=[]`、`formal_ready=false`、`pending_evidence_count=8`、`confirmed_path_count=0`，交付入口 `work/ten_event_rapid_candidate_v2/index.html`。

