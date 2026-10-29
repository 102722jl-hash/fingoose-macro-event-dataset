# FinGoose Ten-Event Rapid Candidate Design

## Objective

以 event-02 已验证的展示方式为模板，为 event-01 至 event-10 生成十个独立的 `RAPID_CANDIDATE` 成果目录和一个总览入口。首轮聚焦核心闭环，不强行补齐长尾证据，不修改生产 v2，不宣称正式发布。

## Selected Approach

采用“先冻结共用 UI 契约，再完成核心数据闭环，最后批量生成页面”的两阶段方案。

1. 先完成 event-02 的时间线与传导链行内引用，使其成为共用模板。
2. 复用同一数据合同处理十个事件，不手工复制十套 HTML。
3. 8 个未闭环节点继续保持 `PENDING_EVIDENCE`，不阻塞首轮页面。
4. 每个事件选择 3 至 4 条核心候选路径，合计约 35 条，标记为 `CORE_REVIEWED + PROPOSED`。
5. 其余已有传导边继续保持 `PROPOSED`，不删除、不晋升。
6. 每个事件预先固定 4 个核心资产，计算六个主要窗口。
7. 首轮只登记 `MATERIAL / DOMINANT` 混杂；其他等级不作为验收门禁。

未采用的方案：先制作十套空页面会导致数据合同变更后返工；先补齐所有来源再做 UI 会让 8 个长尾节点阻塞核心闭环；直接把所有 111 条边都人工审核会显著超过快速版范围。

## Output Structure

```text
work/ten_event_rapid_candidate_v2/
  index.html
  manifest.json
  validation_report.json
  events/
    event-01/
      index.html
      timeline.json
      core_transmission_paths.json
      market_windows.jsonl
      confounders.json
      stage_edge_market_map.json
      sources.json
      validation_report.json
    ...
    event-10/
```

总览页显示十个事件的已验证节点数、待补证数、核心路径数、核心资产数、混杂状态和验证状态。点击事件后进入对应独立页面。

## Timeline Contract

- 每个事件沿用当前工作簿中的 5 个节点，不为满足阶段数量制造新节点。
- 保留 `occurred_at / first_public_at / phase / node_action / anchor_role / visibility`。
- 已验证节点必须能解析到可点击事实来源。
- 8 个待补证节点保持 `occurred_at`、来源和晋升状态的真实缺口，不自动复制相邻节点时间。
- 同日节点日频无法区分时标记 `SAME_DAY_UNRESOLVED`。
- 每个节点记录其启动、强化、削弱、反转或终止的核心路径。

## Core Transmission Contract

每个事件选择 3 至 4 条最能形成“冲击类型 → 统一渠道 → 事件专属中间变量 → 资产”闭环的路径。路径必须包含：

- 稳定 `path_id` 和锚点节点；
- `IMMEDIATE / SHORT_TERM / MEDIUM_TERM` 三段方向；
- 时滞、适用条件和失效条件；
- 事件事实依据与机制依据；
- 至少一条反证或竞争解释；
- `selection_status=CORE_REVIEWED`；
- `confirmation_status=PROPOSED`；
- `review_basis=AI_DESK_REVIEW_NO_HUMAN_CONFIRMATION`。

事实来源只证明事件和时间。机制来源独立引用；主锚点后发布的机制研究标记为“事后机制验证”，从预测可见区排除。

## Preselected Asset Registry

首轮核心资产在观察结果之前固定，不根据事后走势替换：

| Event | Core series |
| --- | --- |
| event-01 | `SP500 / VIXCLS / DCOILWTICO / DEXCHUS` |
| event-02 | `DCOILBRENTEU / DHHNGSP / VIXCLS / SP500` |
| event-03 | `DGS10 / SP500 / DTWEXBGS / DEXCHUS` |
| event-04 | `SP500 / DCOILWTICO / VIXCLS / DEXCHUS` |
| event-05 | `VIXCLS / DGS10 / SP500 / DEXCHUS` |
| event-06 | `DCOILBRENTEU / DCOILWTICO / SP500 / DEXCHUS` |
| event-07 | `DCOILBRENTEU / VIXCLS / SP500 / DEXCHUS` |
| event-08 | `DEXJPUS / DGS10 / SP500 / DEXCHUS` |
| event-09 | `DEXCHUS / SP500 / DGS10 / DTWEXBGS` |
| event-10 | `SP500 / DGS10 / DTWEXBGS / DEXCHUS` |

event-02 的 `DGS10` 继续作为扩展利率代理展示，但不计入四个核心资产，也不冒充纯通胀预期序列。

## Market Window Contract

每个核心序列显示：

- `T-1 / T0 / D1 / D3 / D5 / D20` 的实际日期与绝对值；
- 原始变化与标准化变化；
- 有预先指定基准时显示相对变化，否则为 `null` 并解释原因；
- 计算公式、交易日历、时区、观测截止和数据来源；
- 日频 `T0` 与 `D1` 为同一收盘观测时标记 `T0_CLOSE_EQUALS_D1`。

`T-60 / M3 / 历史安慰剂分位数` 不作为首轮验收门禁。已有且可复算的值可以保留为信息项，但必须标记 `DEFERRED_VALIDATION`，不得进入核心评分。

## Confounder Contract

首轮只强制登记会改变归因结论的 `MATERIAL / DOMINANT` 混杂：

- 混杂开始时间和描述；
- 影响的路径和窗口；
- 支持来源；
- 按窗口给出挑战集路由。

`MATERIAL / DOMINANT` 只进入挑战集，不进入干净归因主分数。无法确定等级时使用 `UNRESOLVED`，不写成 `MINOR`。

## Shared UI Contract

- event-02 页面成为唯一共用模板，由数据驱动生成十个事件页面。
- 时间线节点直接显示事实来源标签。
- 传导路径直接分组显示事件事实依据和机制依据。
- `PENDING_EVIDENCE` 节点显示“暂无已验证引用”，不得链接错位候选。
- 事后机制来源显示“事后机制验证”。
- 页面保留时间线、阶段联动、动态传导链、行情绝对值、混杂与来源视图。
- 总览页只负责导航和状态比较，不重复完整事件内容。
- 桌面和移动端均不得出现引用标签、长 ID、表格或正文溢出。

## Build Architecture

使用一个十事件生成器和事件配置注册表：

1. 读取 `timeline_nodes.jsonl`、生产候选图、行情窗口和来源注册表。
2. 用事件配置选择核心路径、资产角色和混杂规则。
3. 对所有引用执行一对一解析；未解析的已验证引用为硬失败。
4. 为每个事件生成相同结构的数据文件和页面。
5. 聚合十事件验证结果生成总览页、清单和总验证报告。

事件差异放在配置数据中，不复制 Python 函数或 HTML 模板。

## Error And Evidence Boundaries

- 缺失观测保持 `null / UNKNOWN`，禁止补 0。
- 待补证节点不激活可评分边。
- 页面不得把 `CORE_REVIEWED` 写成 `CONFIRMED`。
- 后验机制依据不得进入公开预测依据。
- 同日节点不得被日频结果强行拆分。
- 生产 v2 数据目录只读；全部输出进入独立工作目录。
- 用户已暂缓候选 SHA 门禁；页面和报告必须显示 `sha_gate=DEFERRED_BY_USER`。

## Validation And Acceptance

- 恰好覆盖 event-01 至 event-10，共 50 个时间线节点。
- 每个事件恰好一个主锚点，待补证总数按输入真实统计。
- 每个事件 3 至 4 条核心路径，合计约 35 条；全部仍为 `PROPOSED`。
- 每个事件恰好 4 个核心资产，event-02 扩展代理单独计数。
- 每个核心资产有六个窗口键、日期、绝对值和公式；缺失值有原因。
- 所有已验证节点与核心路径的行内引用可解析到 URL。
- `MATERIAL / DOMINANT / UNRESOLVED` 正确路由到挑战集或拒绝归因。
- 十个独立页面与一个总览页在桌面和移动端完成截图检查。
- event-02、24 锚点投影和现有 v2 回归测试继续通过。
- `formal_ready=false`、`production_dataset_modified=false`、`confirmed_path_count=0`。

## Delivery Tier And Timing

首轮交付为 `RAPID_CANDIDATE`，预计工作量 8 至 12 小时：

- 共用 UI 模板与引用闭环：约 1 小时；
- 核心路径筛选与机制来源：约 3 至 4 小时；
- 四资产六窗口整理：约 2 至 3 小时；
- 混杂、阶段映射、总览和验证：约 2 至 4 小时。

长尾来源补证、全部 111 条边审核、T-60、M3、安慰剂分位数和 SHA 门禁进入第二阶段，不阻塞首轮查看。
