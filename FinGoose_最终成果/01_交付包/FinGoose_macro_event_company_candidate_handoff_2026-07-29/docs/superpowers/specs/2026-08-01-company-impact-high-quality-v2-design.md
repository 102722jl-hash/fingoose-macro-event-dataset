# FinGoose 公司影响高质量数据链 v2 设计

日期：2026-08-01

## 1. 目标

在现有十事件候选包上补全以下可追溯链路：

```text
事件锚点
→ 传导渠道
→ 中间变量
→ 行业
→ 公司业务暴露
→ 方向判断
→ 价格窗口
→ 相对收益
→ 混杂与反证
```

交付范围为 23 家唯一公司的主 dossier，以及由这些 dossier 复用生成的 30 条事件-公司评估。30 条评估用于比较宏观事件及其节点如何经行业传导至公司，不代表 30 家互不重复的公司。

本轮产物仍为高质量候选集。AI 可以生成有证据支持的桌面审核判断，但不能把判断自动晋升为评分真值。人工双审、隐藏标签隔离、来源真实性、SHA 和供应商许可门禁完成前，`formal_ready=false`。

## 2. 输入、隔离与统一展示

只读上游输入来自：

- `work/verifiable_evaluation_phase1_v2_candidate/timeline_nodes.jsonl`
- `work/verifiable_evaluation_phase1_v2_candidate/dynamic_edge_bindings.jsonl`
- `work/verifiable_evaluation_phase1_v2_candidate/event_industry_impacts.jsonl`
- `work/verifiable_evaluation_phase1_v2_candidate/company_price_windows.jsonl`
- 同目录公开案例、隐藏标签和验证报告
- 现有十事件 UI 及其数据投影

新增数据写入：

```text
work/company_impact_high_quality_v2_candidate/
```

该目录不覆盖上游候选数据。物理隔离用于保留基线和回滚能力，逻辑关联通过稳定 ID 完成。构建器将上游事件数据和新增公司数据投影为一个 `ui_data_bundle.js`，并生成基于现有十事件工作台的单一整合 UI。用户选择一个事件后，可在同一页面查看时间线、传导链、行业、公司、行情、混杂和反证。

为兼容直接双击 `index.html`，UI 不依赖浏览器跨目录 `fetch` JSONL。构建时将允许公开展示的数据编译进本地 JavaScript 数据包。受供应商许可限制的原始行情不得写入可再分发页面；在许可未确认时，相关页面仅作为本机候选预览。

## 3. 数据分层与文件接口

### 3.1 公司主数据与证据

- `company_registry.jsonl`：23 家唯一公司、证券代码、交易所、历史名称和稳定 `company_id`。
- `company_evidence.jsonl`：主张级官方证据、原文引文、定位符、报告期和验证状态。
- `company_master_dossiers.jsonl`：引用证据主张后的公司业务暴露摘要，不重复保存整段原文。

主 dossier 只描述相对稳定的公司事实：主营业务、核心产品、上游原料、关键成本、下游客户、地区收入、经营区域，以及能被官方披露支持的收入、成本、产能或价格暴露。

### 3.2 事件评估

- `event_company_exposures.jsonl`：30 条事件-公司暴露关系及完整 lineage。
- `direction_assessments.jsonl`：即时、短期和中期的基本面方向候选。
- `company_confounders.jsonl`：事件级、行业级和公司级混杂及反证。

主 dossier 可以跨事件复用；事件评估必须引用具体 `claim_id`，不能只引用整个 dossier。

### 3.3 行情与相对收益

- `company_market_windows.jsonl`：原始价格、前复权价格、目标日、实际交易日、窗口收益和停复牌状态。
- `relative_return_windows.jsonl`：沪深300、申万一级行业指数或行业 ETF 代理的相对收益。
- `market_source_registry.jsonl`：行情来源、字段定义、提取时间、复权公式、许可和再分发状态。

### 3.4 构建与审计

- `upstream_lineage.jsonl`：上游文件、记录 ID 和输入版本引用。
- `ui/index.html`：基于现有十事件工作台生成的单一整合页面。
- `ui/ui_data_bundle.js`：统一 UI 投影。
- `validation_report.json`：结构、证据、计算、因果和 UI 校验结果。
- `summary.json`：计数、状态分布、缺口和发布边界。
- `manifest.json`：文件清单和记录数；SHA 字段本轮可以为 `DEFERRED`，但不得伪装为已通过。
- `README.md`：使用方法、口径和已知限制。

## 4. 稳定 ID 与完整 lineage

每条事件-公司评估必须保存并解析以下链路：

```text
event_id
→ anchor_id
→ binding_id
→ industry_impact_id
→ company_id
→ dossier_claim_id[]
→ direction_assessment_id
→ market_window_id
→ confounder_id[]
```

`event_id + company_id` 在 30 条评估中唯一。同一公司出现在不同事件时复用 `company_id` 和主 dossier，但方向、窗口和混杂记录分别创建。构建器拒绝孤立 ID、跨事件引用、重复主 dossier、行业与传导边语义错配，以及无法反向定位到事件锚点的公司记录。

## 5. 公司 dossier 证据标准

每家公司至少需要两条独立官方披露，其中至少一条为年度报告或半年度报告。第二条可以来自交易所公告、公司官网披露、投资者关系记录或招股说明书。媒体和券商研报只能作为检索线索或辅助背景，不能单独证明业务暴露。

每项事实必须以主张级记录保存：

```text
claim_id
company_id
claim
official_source_url
document_title
issuer
reporting_period
published_at
page_or_section_locator
original_quote
evidence_scope
verification_status
availability_scope
```

`availability_scope` 只能为 `PREDICTION_VISIBLE` 或 `VERIFICATION_ONLY`。公司披露的 `published_at` 不晚于对应事件的公开预测截止时，才可进入公开输入；事件截止日后的年报、公告和管理层说明只能用于隐藏验证或反证审计。后见材料不能倒灌为事件发生时已知的公司暴露证据。

证据状态为：

- `VERIFIED`：两条独立官方证据支持核心暴露；
- `PARTIALLY_VERIFIED`：只有一条官方证据，或只支持部分表述；
- `CONFLICTING_EVIDENCE`：官方披露在期间、单位或含义上冲突；
- `DATA_PENDING`：未取得足够证据；
- `REJECTED`：来源与公司、期间或主张语义不符。

缺少地区收入、成本敏感性或业务占比时保留缺失状态，不根据行业常识补造。文档只证明日期时，不能虚构时分秒。PDF 引文必须核对文字层或可见页面，扫描件需要保存页码和人工定位说明。

## 6. 方向判断

方向判断必须从事件发生时可见的事实和公司业务暴露推导，不得使用事后股价挑选公司或反向决定方向：

```text
事件锚点 → 传导渠道 → 中间变量 → 行业影响
→ 已验证公司暴露 → 基本面方向
```

三个期限分别记录：

- 即时：事件后 0 至 1 个交易日；
- 短期：D1 至 D5；
- 中期：D5 至 D20。

方向枚举为 `POSITIVE`、`NEGATIVE`、`MIXED`、`NEUTRAL` 和 `UNKNOWN`。每条判断记录收入、销量、成本、资产价值、汇率或监管等暴露类型，以及生效条件、时滞、失效条件、支持证据、反证、AI 理由和置信度。

AI 生成的记录使用 `review_origin=AI_DESK_REVIEW`、`review_status=NEEDS_HUMAN_REVIEW`，不得进入隐藏评分真值。股价表现是独立的事后验证层。方向与价格不一致时，保留原判断并检查预期差、提前定价和竞争事件，不得为了吻合行情改写方向。

## 7. 市场窗口与相对收益

每条事件-公司评估固定输出 `T-1、T0、D1、D3、D5、D20`。`T0` 根据公司所属交易所、事件首次公开时刻和交易时段逐证券确定：

- 盘前公开：当日为 `T0`；
- 盘中公开：保留当日，并标记日频无法隔离盘中影响；
- 盘后公开：下一有效交易日为 `T0`；
- 节假日或休市：顺延至下一有效交易日。

每个观察点保存目标日期、实际交易日期、原始收盘价、前复权收盘价、单位、复权因子或等价公式、数据提供方和提取时间。页面展示原始价格；收益优先使用前复权收盘价，并保存完整输入以便复算：

```text
R_company(a,b) = adjusted_close_b / adjusted_close_a - 1
AR_market(a,b) = R_company(a,b) - R_csi300(a,b)
AR_industry(a,b) = R_company(a,b) - R_industry(a,b)
```

沪深300是 30 条评估统一使用的必做大盘基准，只采集一条指数日线并复用。行业基准优先使用事件当时有效的申万一级行业指数；不可取得时，可以使用事先指定并明确标记 `benchmark_type=ETF_PROXY` 的行业 ETF。ETF 不能冒充申万指数；没有合适代理时保持 `DATA_PENDING`。

停复牌以交易所公告为主证据，可信行情交易日序列用于交叉验证。连续缺价不能自动推断停牌。发生停牌时，不跨停牌使用陈旧价格计算正常事件收益，必须保存首个实际可交易日、偏移天数和 `WINDOW_CONTAMINATED`。查不到公告时保持 `UNVERIFIED`。

## 8. 混杂与反证

混杂分为：

- 事件级：央行政策、地缘冲突、重大经济数据和系统性市场波动；
- 行业级：商品独立冲击、监管政策、供需变化和行业财报季；
- 公司级：业绩公告、并购、回购、增减持、诉讼、停复牌和重大合同。

每项混杂保存 `occurred_at`、`first_public_at`、受影响窗口、来源 URL、原文引文、可能机制、严重度和处置结论。混杂等级为 `CLEAN`、`MINOR`、`MATERIAL`、`DOMINANT` 和 `UNRESOLVED`。

`MATERIAL`、`DOMINANT` 和 `UNRESOLVED` 可以展示并进入挑战集或拒答评测，但不得进入干净归因主评分。混杂论证必须说明宏观路径、竞争解释、时间吻合度和最终处置，不得使用无来源的长篇推测填充内容。

反证单独登记，包括自然对冲、合同锁价、相关业务占比过低，或管理层明确表示影响有限。检索后没有发现反证时使用 `NO_COUNTEREVIDENCE_FOUND` 并记录检索范围，不能表述为“已证明不存在反证”。

## 9. 统一 UI

整合 UI 保持左侧十事件侧边栏。右侧按以下顺序展示：

```text
事件概览 → 事件时间线 → 动态传导链 → 行业影响
→ 公司影响 → 价格与相对收益 → 混杂与反证
```

交互规则：

- 点击时间线节点，突出对应锚点、传导边、行业和公司；
- 点击传导边，仅展示由该机制支持的行业与公司评估；
- 点击行业，显示行业下的公司及其三个期限方向；
- 点击公司，展开主 dossier、官方引文、价格折线图和竞争解释；
- 点击证据，打开官方来源并展示文档标题、页码或章节定位。

折线图同时显示公司、沪深300和行业基准的标准化走势，表格同时列出真实日期、绝对价格、窗口收益和公式。申万缺失、ETF 代理、停复牌、混杂和人工审核状态必须显式显示。缺失值显示“数据待补”，不得显示为零或静默隐藏。

## 10. 错误处理与状态门禁

上游 ID 缺失、证据语义错配、未来信息泄漏、不可复算数值和未声明的基准替换均为硬失败。单个外部网站不可达、行业指数缺失或停复牌公告未找到属于记录级缺口：保留记录并降级状态，不阻断其他公司处理。

允许的主要状态为 `VERIFIED`、`PARTIALLY_VERIFIED`、`CONFLICTING_EVIDENCE`、`NEEDS_HUMAN_REVIEW`、`DATA_PENDING`、`REJECTED` 和 `UNVERIFIED`。不同数据层独立维护状态；上游已验证不能自动晋升下游。

本轮固定：

- `release_tier=CANDIDATE`
- `formal_ready=false`
- `sha_gate=DEFERRED`
- `human_double_review_complete=false`

## 11. 测试与验收

### 11.1 结构验收

- 恰好 23 份唯一公司主 dossier；
- 恰好 30 条事件-公司评估；
- 每条评估可连接事件、锚点、传导边、行业、公司、方向、行情和混杂；
- 无孤立 ID、重复 dossier、跨事件错误引用和语义碰撞。

### 11.2 证据验收

- 每家公司至少两条独立官方披露，至少一条为年报或半年报；
- 核心主张具备原文引文和页码、章节或表格定位；
- 链接、公司、报告期与主张语义一致；
- 未达门槛的记录不会伪装成 `VERIFIED`。

### 11.3 计算验收

- 逐项复算 T-1 至 D20 的日期、绝对价格和收益；
- 逐项复算沪深300、申万或 ETF 代理相对收益；
- 覆盖盘前、盘中、盘后、休市、停复牌、缺失行情和复权因子缺失；
- 验证交易日偏移、单位、复权公式、除零和空值传播。

### 11.4 因果与泄漏验收

- 基本面方向不使用事后价格作为证据；
- 所有 AI 判断保持 `NEEDS_HUMAN_REVIEW`；
- D3 后信息不进入公开预测输入；
- `MATERIAL`、`DOMINANT` 和 `UNRESOLVED` 不进入干净归因主评分；
- 反证和竞争解释不被遗漏或改写为支持证据。

### 11.5 UI 验收

- 从事件节点可以联动到传导边、行业和公司；
- 每项结论可回溯到源 JSONL 记录和官方证据；
- 桌面、移动端和 `file://` 打开均无文本遮挡或缺失值误导；
- 图表数值与表格、公式和源记录一致。

## 12. 实施顺序与时间盒

采用“主 dossier 优先”方案：

1. 冻结并校验 23 家唯一公司注册表和 30 条事件映射；
2. 建立 23 份主 dossier 和主张级官方证据；
3. 生成 30 条事件暴露与三个期限方向候选；
4. 补齐公司、沪深300和行业基准行情，计算窗口与相对收益；
5. 登记混杂、反证和停复牌；
6. 构建统一 UI 投影并完成全量验证。

预计有效工作时间为 18 至 28 小时。其中公司官方证据检索与主张核对占主要时间。外部站点不可达、供应商字段不足或人工审核等待不以降低证据门槛解决，而是保留明确的状态和缺口。

## 13. 非目标

本轮不把 AI 判断直接写入隐藏标签，不自动宣布正式发布，不要求补齐全部分析师预期，不以事后股价替换公司候选，不为了表面完整度虚构公司业务占比、精确时间、停牌原因或行业指数。
