# FinGoose 深度事件—公司传导工作台设计

## 状态

本设计于 2026-07-29 经用户确认。目标用户是需要审核和理解数据、但不熟悉数据工程细节的项目负责人。

## 目标

新建一个独立、只读的深度审计工作台，将现有市场事件归因内容和公司影响候选内容连接为一条连续推理链：

`重大事件 → 市场六步推理 → 行业变量桥梁 → 三家公司分支 → 公司七节点传导链 → 归因或短期预测 → 事后审核`

工作台必须完整保留旧市场 UI 六个步骤中的全部详细内容，不得只保留步骤名称、结论卡片或压缩摘要。

## 非目标

- 不替换现有 `fingoose_macro_event_dashboard_v1.py` 或 `fingoose_macro_event_dashboard_v1.html`。
- 不修改 `outputs/fingoose_macro_event_attribution_v1`。
- 不修改 `outputs/fingoose_macro_event_company_candidate_v1`。
- 不修改 `outputs/fingoose_macro_event_company_enriched_candidate_v1`。
- 不将公司候选数据声明为正式数据。
- 不补造公司业务暴露、经营指标、财务结果、行情或来源。
- 不在本工作台中执行审核决定、修改标签或回写 JSONL。

## 上游数据与状态边界

市场层读取：

- `outputs/fingoose_macro_event_attribution_v1/event_dossiers.jsonl`
- `outputs/fingoose_macro_event_attribution_v1/attribution_samples.jsonl`
- `outputs/fingoose_macro_event_attribution_v1/training_projection.jsonl`
- `outputs/fingoose_macro_event_attribution_v1/market_windows.jsonl`
- `outputs/fingoose_macro_event_attribution_v1/source_manifest.jsonl`
- `outputs/fingoose_macro_event_attribution_v1/hidden_attribution_labels.jsonl`
- `outputs/fingoose_macro_event_attribution_v1/hidden_forecast_outcomes.jsonl`
- `outputs/fingoose_macro_event_attribution_v1/review_records.jsonl`

公司层默认读取主任务最新增强候选根目录 `outputs/fingoose_macro_event_company_enriched_candidate_v1`。服务必须提供 `--company-output-root` 参数，允许显式切换到原候选根目录 `outputs/fingoose_macro_event_company_candidate_v1`。两者使用相同的文件契约：

- `company_event_dossiers.jsonl`
- `company_metric_facts.jsonl`
- `company_stock_windows.jsonl`
- `company_attribution_samples.jsonl`
- `company_forecast_samples.jsonl`
- `company_candidate_training_projection.jsonl`
- `company_candidate_hidden_labels.jsonl`
- `company_hidden_outcomes.jsonl`
- `company_review_records.jsonl`
- `company_evidence_gaps.jsonl`
- `source_manifest.jsonl`

两层数据只通过已有标识连接，不修改上游记录。主要连接键为 `event_id`、`record_id`、`market_window_id`、`dossier_id`、`review_id` 和 `source_id`。

市场区域始终标记为正式归档数据。公司区域始终显示 `release_tier=CANDIDATE`、`formal_ready=false` 以及实际证据和审核状态。

## 独立实现边界

计划新增：

- `fingoose_macro_event_company_deep_dashboard_v1.py`
- `fingoose_macro_event_company_deep_dashboard_v1.html`
- `tests/test_fingoose_macro_event_company_deep_dashboard_v1.py`
- `work/macro_event_company_deep_dashboard_v1/visual_validation.json`

新的 Python 服务通过组合现有 `MacroEventDashboardRepository` 读取和连接数据，但使用独立 HTML、独立路由入口和独立测试。现有统一 Dashboard 保持不变。

## 页面信息架构

页面围绕一个事件展开，主阅读顺序固定为：

1. 事件事实、发生时间、首次公开时间和来源状态。
2. 当前事件的四条市场归因题选择器。
3. 当前市场题的六步详细推理查看器。
4. 从市场背景进入公司层的行业变量桥梁。
5. 当前事件的三家公司选择器。
6. 当前公司的七节点传导链和详细内容。
7. 独立事后审核区。

页面顶部同时提供事件、市场题和公司的快速选择控件。切换事件后，市场题和公司选择重置到该事件的第一条记录，避免显示跨事件残留信息。

## 市场六步完整保留规则

六步使用点击切换，一次展开一步。所有步骤的完整内容都存在于页面数据模型中；切换只改变可见步骤，不删除或重新概括内容。

### 第一步：宏观研报

保留：

- 研报或事件来源的中文标题和摘要。
- 发布机构、发布时间、来源等级和原始编号。
- 本地快照、定位信息和 SHA-256。
- 该来源可以支持的判断。
- 该来源不能单独证明的内容和证据边界。

### 第二步：数据截止

保留：

- 预测截止时间。
- 事件前基线日期和基线值。
- 预测时可见的 D1、D3 日期、值、变化和异常分数。
- 预测时不可见的 D20 验证窗口。
- 可见数据与隐藏数据为什么必须分离的防泄漏解释。

### 第三步：期间描述

保留：

- 事件发生和首次公开的时间顺序。
- 事件可能作用于经济预期的中文说明。
- 前三个交易日内各市场实际发生的变化。
- 该阶段只描述时序和观察、尚不构成最终因果结论的提示。

### 第四步：事实传导链

保留：

- 事件事实节点、经济机制节点和市场结果节点。
- 节点之间的原始边关系。
- 候选传导渠道及其中文解释。
- D1、D3 的资产定价验证和异常程度。
- 竞争解释、反证及其对归因强度的影响。
- “分析观点”与“来源原文”的明确视觉区分。

### 第五步：多重数据趋势确认

保留：

- 每个市场的中文名称和观察窗口。
- 预期方向、实际方向、实际变化和异常分数。
- 支持、矛盾或中性的判断。
- 跨资产方向一致率、最强异常资产和竞争因素说明。
- 多市场一致性增强可信度、但不等同于严格因果证明的边界。

### 第六步：短期预测

保留：

- 目标资产、预测窗口、方向和置信度。
- 使用宏观摘要、传导渠道及 D1/D3 观察形成判断的依据。
- 证据加权分析观点。
- 竞争解释、反向信号和失效条件。
- 单独标记的 D20 事后验收结果和方向正确性。
- D20 在预测时不可见、不得倒灌为预测依据的警示。

## 市场到公司的连接规则

市场六步完成后显示明确的过渡区：

> 市场层解释发生了什么以及市场如何反应；公司层仍须用公司官方材料证明具体业务暴露。市场波动不能自动转化为公司结论。

过渡区根据公司档案中的结构化节点展示候选行业变量。只有绑定有效 `evidence_refs` 的事实才显示为有证据。没有公司官方材料支撑的渠道必须显示 `PENDING_EVIDENCE`，不得根据公司名称或常识补写。

## 公司七节点传导链

每家公司展示以下七个节点：

1. `MAJOR_EVENT`
2. `INDUSTRY_MACRO_VARIABLE`
3. `COMPANY_BUSINESS_EXPOSURE`
4. `OPERATING_METRIC`
5. `FINANCIAL_RESULT`
6. `COMPETING_EXPLANATION`
7. `ATTRIBUTION_OR_FORECAST`

点击节点后，详细区显示：

- 节点值和状态。
- 该节点的中文解释。
- `evidence_refs` 绑定的来源。
- 来源发布机构、URL、发布时间、归档时间、定位、摘录和 SHA-256。
- `model_visible` 与 `verification_status`。
- 没有来源时的具体 `gap_reason` 和所需证据类型。

公司详情同时展示指标事实、公司和沪深 300 辅助窗口、关联标签、方向、置信度、三项预测输出、竞争解释和审核状态。

任何 `UNKNOWN`、缺失行情或证据缺口保持原样显示，不能转成零值、空字符串或推测内容。

## 来源与缺口抽屉

市场六步中的来源编号和公司七节点都可打开统一的来源抽屉。抽屉有两种互斥状态：

- 有来源：展示来源元数据、定位、摘要/摘录、哈希和验证状态。
- 无来源：展示 `PENDING_EVIDENCE`、缺口原因和需要补取的材料类型。

来源抽屉只展示上游记录，不抓取网络内容、不修改验证状态。

## 事后审核区

页面底部设置独立事后审核区，容纳：

- 市场 D20 和隐藏归因标签。
- 公司未来财报、隐藏结果和预测验证。
- 初审、复审触发原因、复审和裁决信息。

该区域默认折叠，展开后持续显示“预测时不可见，仅供事后审核”。隐藏结果不得出现在市场第二步的可见数据表或公司预测输入中。

## 状态与错误处理

- 必需文件缺失或 JSON/JSONL 无法解析：服务启动失败并指出具体文件。
- 事件连接后不是四条市场题或三家公司：页面显示数据完整性错误，不静默省略。
- 单个来源缺失：节点显示待补证，不影响其他节点浏览。
- 指标或行情值为 `UNKNOWN`：原样展示并附缺口原因。
- 来源 ID 无法解析：显示未解析 ID，不生成虚构来源卡片。
- 接口请求失败：保留当前页面结构并显示中文错误和重试按钮。
- 切换事件或样本时取消旧请求，避免晚到响应覆盖当前选择。

## 响应式设计

- 桌面端使用事件主内容加来源抽屉的双栏布局。
- 窄屏端将来源抽屉移到内容下方。
- 六步和公司七节点允许组件内部横向滚动，但页面本身不能产生横向溢出。
- 所有状态文本允许换行，最长公司名称、记录 ID 和哈希不能撑破容器。

## 测试与验收

### 数据与接口测试

- 加载 10 个事件、40 条市场样本、30 个公司档案和 60 条公司样本。
- 每个事件恰好连接四条市场题和三家公司。
- 每条市场题的六个步骤均生成完整详细内容。
- 每家公司包含七个结构化节点。
- 来源抽屉能按 `source_id` 定位市场或公司来源。
- 缺口抽屉能显示具体 `gap_reason`。
- D20、未来财报和隐藏标签不进入预测可见区域。

### 页面契约测试

- 存在事件、市场题和公司选择器。
- 六个市场步骤可逐项切换，切换后内容非空。
- 三家公司可切换，七节点链随公司更新。
- 节点点击能打开来源或缺口详情。
- 事后审核区默认折叠并带防泄漏警示。
- 页面明确显示市场正式状态和公司候选状态。

### 视觉验证

- 在 1440px 桌面视口验证完整事件页、六步切换、公司切换和来源抽屉。
- 在 390px 移动视口验证无页面横向溢出、文字不重叠、节点可操作。
- 验证图表和数据表非空。
- 验证浏览器控制台无 JavaScript 错误。

### 不变性验证

在实现前后记录并比较以下受保护目录的文件清单和 SHA-256：

- `outputs/fingoose_macro_event_attribution_v1`
- `outputs/fingoose_macro_event_company_candidate_v1`
- `outputs/fingoose_macro_event_company_enriched_candidate_v1`
- `outputs/fingoose_formal_v1_macro`

验收要求三个目录均无变化，现有统一 Dashboard 文件也无变化。

## 完成标准

只有同时满足以下条件，独立深度工作台才可声明完成：

- 10 个事件均可打开。
- 40 条市场题的六步详细内容全部保留并可切换。
- 30 家公司的七节点传导链全部可查看。
- 每个来源和证据缺口都有可审计展示。
- 市场正式状态与公司候选状态清楚分离。
- 预测可见内容和事后审核内容清楚分离。
- 桌面与移动端交互验证通过。
- 受保护输出和现有 Dashboard 未被修改。
