# FinGoose 事件—公司专属经营机制链设计

## 目标

将现有“宏观图数据库边清单”升级为投研可读、可追溯、可评测的事件—公司完整经营机制链。冻结现有 10 个事件、23 家公司和 30 条映射，不扩容公司或事件。

每条映射在主视图仅展示 1 条主经营链。次级宏观路径、原始节点 ID、边 ID、审核字段和未选绑定进入折叠的技术详情。

所有新增结论保持：

- `review_status=NEEDS_HUMAN_REVIEW`
- `formal_ready=false`
- `sha_gate=DEFERRED`
- 新增边状态为 `PROPOSED_COMPANY_MECHANISM`，不得写成 `CONFIRMED`

## 核心结构

主经营链固定为七层：

```text
具体事件事实
→ 行为或政策变化
→ 可观测经营变量
→ 行业收入或成本变量
→ 公司业务暴露
→ 即时、短期和中期方向
→ 价格验证、混杂与反证
```

事件事实必须来自时间线锚点。公司业务暴露必须来自事件前可见的官方年报或公告。价格只能用于验证，不得用于选择路径或方向。

## 数据接口

新增 `event_company_mechanism_chains.jsonl`，每个 `mapping_id` 恰好一条记录：

```text
chain_id
mapping_id
event_id
anchor_id
company_id
company_code
company_name
industry_id
industry_name
chain_status
nodes
edges
horizon_reviews
conditions
invalidation_conditions
supporting_evidence_ids
counterevidence_ids
technical_binding_ids
rejected_binding_ids
price_selection_used
review_status
formal_ready
sha_gate
```

### 节点字段

每个节点包含：

```text
node_id
node_type
sequence
title_zh
explanation_zh
occurred_at
direction
observable_metric
unit
evidence_ids
source_links
review_status
```

`node_type` 只能是：

- `EVENT_FACT`
- `BEHAVIOR_OR_POLICY_CHANGE`
- `OBSERVABLE_OPERATING_VARIABLE`
- `INDUSTRY_REVENUE_OR_COST_VARIABLE`
- `COMPANY_BUSINESS_EXPOSURE`
- `DIRECTION_ASSESSMENT`
- `PRICE_AND_CONFOUNDER_VERIFICATION`

### 边字段

每条边包含：

```text
edge_id
from_node_id
to_node_id
mechanism_zh
lag
conditions
invalidation_conditions
evidence_ids
counterevidence_ids
edge_status
review_status
```

新增事件专属公司机制边时，`edge_status=PROPOSED_COMPANY_MECHANISM`。现有宏观绑定只作为 `technical_binding_ids` 血缘引用，不自动证明公司经营机制。

## 语义规则

禁止下列替代：

- 用风险偏好渠道替代诊断检测需求。
- 用原油资产走势替代航空客流或机场吞吐量。
- 用宏观资产同名投影边替代行业经营变量。
- 用事件后股价表现选择公司方向。
- 将通用宏观边的事件事实证据冒充公司业务暴露证据。

当现有绑定无法覆盖公司经营机制时，新增事件专属候选节点和边，并保持待人工审核。

event-01 的达安基因必须采用独立链：

```text
WHO 宣布 COVID-19 构成全球大流行
→ 疫情全球扩散与公共卫生检测需求上升
→ 核酸检测量、试剂需求及准入兑现
→ 体外诊断行业检测收入变量
→ 达安基因诊断试剂业务暴露
→ 即时未知、短期候选正向、中期混合或拒答
→ 公司价格窗口、公告混杂与准入兑现反证
```

上海机场和中国国航采用旅行限制、客流和收入链，不再以 WTI 或标普 500 作为主经营链。

## UI 投影

主视图使用完整路径卡片，不逐边平铺。卡片按七层纵向展示，并在每层显示：

- 中文节点标题和机制解释；
- 时间、方向和时滞；
- 官方证据原文摘要及链接；
- 成立条件和失效条件；
- 公司年报业务暴露证据；
- 价格验证、混杂等级和反证。

技术详情折叠区展示：

- 原始 `binding_id`、`node_id` 和 `edge_id`；
- 主绑定、次级绑定和拒绝理由；
- 审核状态、证据 ID 与数据血缘；
- 未解决 blocker。

UI 增加按事件汇总的候选闭环矩阵，显示每条映射的经营链、dossier、方向、行业窗口、混杂和停复牌六项门禁状态。

## 完成门禁

单条映射只有同时满足以下条件才可标记 `CANDIDATE_COMPLETE`：

1. 七层主经营链完整且节点顺序无断裂。
2. 事件事实证据和公司业务证据来源分离并均可定位。
3. 三个期限均有方向或明确拒答。
4. 公司、沪深300和行业基准窗口可复算。
5. 公告混杂和停复牌检索完成。
6. 所有结论保持待人工审核边界。

任一条件不满足时保持 `OPEN`，并列出精确 blocker。行业指数和 ETF 均不可得时，不得强行完成。

## 数据流

```text
时间线锚点与动态宏观绑定
        +
公司年报证据与方向候选
        +
行业分类、价格窗口与混杂记录
        ↓
事件—公司经营机制链生成与规则校验
        ↓
event_company_mechanism_chains.jsonl
        ↓
candidate_completion_report.jsonl
        ↓
UI 完整路径卡片和候选闭环矩阵
```

底层现有 JSONL 保持分层，不合并为单个大文件。

## 错误处理

- 缺少时间线锚点：`ANCHOR_EVIDENCE_MISSING`
- 公司证据缺失：`COMPANY_EXPOSURE_EVIDENCE_MISSING`
- 链节点断裂：`MECHANISM_CHAIN_DISCONNECTED`
- 用事后价格选链：`PRICE_SELECTION_LEAKAGE`
- 未解释的未知方向：`UNEXPLAINED_UNKNOWN_DIRECTION`
- 行业行情不可得：`INDUSTRY_WINDOW_INCOMPLETE`
- 混杂或停复牌未关闭：保持挑战集，不进入干净归因

构建器遇到结构错误时硬失败；证据缺口作为 blocker 输出，不填零、不推测、不伪造来源。

## 测试

- 验证 30 个 `mapping_id` 一一覆盖且每条恰好一条主链。
- 验证七种节点类型和连续边完整。
- 验证 event-01 达安基因包含检测需求、试剂需求和诊断业务暴露。
- 验证上海机场和中国国航主链包含客流或吞吐量，而不是 WTI 或标普 500。
- 验证事件证据和公司证据不会混用。
- 验证所有新增边保持 `PROPOSED_COMPANY_MECHANISM`。
- 验证价格结果不进入路径选择依据。
- 验证 UI 主视图显示完整路径，原始边进入技术详情。
- 验证六项门禁矩阵与 `candidate_completion_report.jsonl` 一致。
- 保持隐藏标签隔离、`formal_ready=false` 和 `sha_gate=DEFERRED`。

