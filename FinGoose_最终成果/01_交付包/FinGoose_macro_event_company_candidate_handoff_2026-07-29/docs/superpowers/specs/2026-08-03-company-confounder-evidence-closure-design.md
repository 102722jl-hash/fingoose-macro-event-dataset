# FinGoose 公司混杂与反证证据闭环设计

## 目标

将当前 30 条事件—公司映射的混杂与反证层，从统一的 `UNRESOLVED` 占位状态推进为可追溯、可复核的高质量候选数据。页面不得通过生成性文字掩盖检索缺口；每个结论必须来自公告正文、官方交易状态或明确记录的负向检索。

本阶段覆盖现有冻结范围：10 个事件、23 家公司、30 条映射。保持 `formal_ready=false`、`sha_gate=DEFERRED` 和 `NEEDS_HUMAN_REVIEW`，不进行最终人工签署。

## 当前基线

- 30 条公司混杂记录全部为 `UNRESOLVED`。
- 15 条映射存在 47 条公告标题级高风险候选，但正文尚未审核。
- 15 条映射未筛出高风险标题候选，但负向检索链条尚不完整。
- 本地已有 30 份巨潮标题快照，共 455 条公告记录。
- 30 条停复牌状态均为 `UNVERIFIED`。
- 30 条公司级反证状态均为 `SEARCH_PENDING`。

## 证据原则

1. 公司公告优先使用巨潮资讯、上海证券交易所或深圳证券交易所的官方正文。
2. 停复牌状态优先使用交易所公告、官方交易日数据和公司公告；缺失行情不能自动解释为停牌。
3. 标题只用于候选筛选，不能单独形成 `MINOR`、`MATERIAL` 或 `DOMINANT` 结论。
4. “未发现实质混杂”必须附检索范围、日期区间、检索数量、关键词类别和审核计数。
5. 事件后披露可以用于混杂与验证，但必须保存首次公开时间，不能回填到事件前预测证据。
6. 不依据事件后股价表现选择公告、公司或竞争解释。
7. 正文无法取得、时间无法对齐或交易状态无法核验时继续标记 `UNRESOLVED`，不得填写推测性结论。

## 数据层

### `announcement_body_reviews.jsonl`

每条公告正文一条审核记录，至少包含：

```text
review_id
mapping_id
event_id
company_id
announcement_id
announcement_title
source_url
first_public_at
body_review_status
body_locator
original_quote
confounder_type
affected_windows
relevance_decision
severity_candidate
mechanism_zh
rejection_reason
review_status
```

`relevance_decision` 使用 `RELEVANT / MINOR_RELEVANCE / IRRELEVANT / UNRESOLVED`。无法获得正文时必须记录失败原因，不能把标题当作正文审核结果。

### `company_confounder_search_audits.jsonl`

每个 `mapping_id` 一条完整检索审计，至少包含：

```text
mapping_id
window_start
window_end
title_snapshot_path
title_count
candidate_count
body_reviewed_count
query_categories
source_providers
search_completed_at
search_status
negative_result_basis
unresolved_reasons
```

`search_status=COMPLETE` 仅在窗口、来源、标题记录和所有候选正文均已处理时成立。零候选不等于检索完成。

### `company_counterevidence_reviews.jsonl`

每条映射记录支持结论之外的公司级反证，包括业务缓冲、价格传导受阻、公司披露与预期方向不一致、其他经营变量占主导等。至少保存：

```text
mapping_id
counterevidence_id
claim_zh
source_url
first_public_at
locator
original_quote
affected_horizons
effect_on_thesis
review_status
```

没有找到反证时必须保存负向检索范围，不能只输出空数组。

### `trading_status_reviews.jsonl`

每条映射对齐 `T-1、T0、D1、D3、D5、D20` 的实际交易日，保存公司是否正常交易、缺失行情原因及官方依据。状态使用：

```text
VERIFIED_TRADING
VERIFIED_SUSPENDED
VERIFIED_RESUMED
UNRESOLVED
```

### `company_confounder_arguments.jsonl`

每条映射生成 250–600 个中文字符的投研论证，结构固定为：

```text
事件窗口和原假设
公司公告及独立驱动
对即时、短期、中期方向的干扰
停复牌和可交易性
公司级反证或负向检索
混杂等级与拒答边界
```

论证必须引用上述审核记录，不得新增无来源事实。

## 混杂等级规则

- `CLEAN`：检索审计完整、候选正文全部处理、停复牌为 `VERIFIED_TRADING`，且没有足以改变事件解释的独立公司因素。
- `MINOR`：存在已核对的独立因素，但影响窗口有限或不足以改变主要方向。
- `MATERIAL`：独立因素可能显著改变一个或多个核心窗口的收益或方向解释。
- `DOMINANT`：独立因素比宏观事件更可能主导观测结果。
- `UNRESOLVED`：正文、时间、停复牌、反证或检索覆盖任一关键环节未关闭。

`MATERIAL / DOMINANT / UNRESOLVED` 只能进入挑战集。任何 `CLEAN` 记录都必须通过完整性门禁，不能由“没有筛出标题候选”直接产生。

## 处理流程

1. 读取 30 份现有巨潮快照，复核 455 条标题与窗口边界。
2. 对现有 47 条高风险候选获取并审核官方 PDF 正文。
3. 对零候选和低风险标题记录形成可复算的负向检索审计。
4. 核验 30 条映射在六个市场窗口的交易状态。
5. 检索并登记每条映射的公司级反证或负向检索结果。
6. 按证据生成公司混杂论证和等级候选。
7. 重建 `company_confounders.jsonl`、完成报告、验证报告和 UI 数据包。
8. 在 UI 中以论证、证据链接、公告正文定位、窗口影响和审核边界替换当前通用占位文字。

## UI 行为

- 有相关公告时，展示正文引文、公告类型、影响机制、影响窗口、等级候选和官方链接。
- 无实质混杂时，展示检索范围、455 条快照中的公司级记录数量、候选筛选结果和 `CLEAN` 成立依据，而不是空白框。
- 未关闭时，明确列出尚缺正文、交易状态或反证中的哪一项。
- 混杂论证与传导链、价格窗口使用同一 `mapping_id` 联动。
- 技术详情保留公告 ID、审核 ID、检索参数和状态；主视图只显示投研可读内容。

## 验收门禁

- 30 个 `mapping_id` 在五张新台账和聚合记录中一一覆盖。
- 455 条本地公告标题全部可追溯到检索审计。
- 47 条既有高风险候选均有正文审核记录或明确的获取失败状态。
- 任一非 `UNRESOLVED` 等级均有正文、窗口和交易状态依据。
- 任一 `CLEAN` 记录均通过完整负向检索门禁。
- 缺失值不转换为零，空数组不冒充已完成检索。
- UI 不再把 `SEARCH_PENDING` 表述为“未发现高风险候选”。
- 十个事件的混杂论证、证据链接和窗口联动均可操作。
- 桌面和 390px 移动端无文本遮挡或页面级横向溢出。
- 继续保持隐藏标签隔离、`formal_ready=false`、`sha_gate=DEFERRED` 和人工审核边界。

## 预计工作量

自动化抓取、正文解析和初筛约 3–5 小时；47 条正文审核、30 条停复牌核验、30 条反证论证和回归验证约 7–11 小时。完整候选闭环预计 10–16 个工作小时，不包含最终人工签署和 SHA 发布门禁。
