# FinGoose 事件—公司影响候选数据集交接说明

交接日期：2026-07-29  
交接范围：事件型市场归因正式集、公司影响候选集、增强候选集、证据快照、构建与验证代码、统一中文 UI、审核与设计文档。  
当前结论：市场子集可以视为正式归档；公司子集仅为候选训练/评测版本，不得宣称为正式发布版。

## 1. 一句话目标

将宏观研究从“用宏观证据直接预测公司收入/利润”重构为可审计的事件链：

`重大事件 -> 市场六步推理 -> 行业/宏观变量 -> 公司业务暴露 -> 经营指标 -> 财务结果 -> 竞争解释 -> 归因或短期预测`

本数据集采用证据加权的事后归因与事前预测，不宣称严格计量因果。

## 2. 当前数据状态

### 市场事件归因集

- 版本：`fingoose-macro-event-attribution-v1.0`
- 10 个事件、40 条样本、40 个市场窗口。
- 30 条单资产题、10 条跨资产比较题。
- 20 个来源，40 条隐藏归因标签，40 条隐藏 D20 结果。
- 标签分布：`PRIMARY_DRIVER=5`、`CONTRIBUTING_FACTOR=9`、`WEAK_RELATION=8`、`UNSUPPORTED=18`。
- `formal_ready=true`，无发布门禁失败。

市场六步推理固定为：

1. `MACRO_REPORT`：宏观研报与事件证据。
2. `DATA`：预测截止日前的 D1/D3 数据。
3. `PERIOD_DESCRIPTION`：事件与观察期的时间顺序。
4. `FACT_TRANSMISSION_CHAIN`：事件、机制和市场结果。
5. `MULTI_DATA_TREND_CONFIRMATION`：多市场方向一致性。
6. `SHORT_TERM_PREDICTION`：D20 方向预测及失效条件。

D20 实际结果、隐藏标签和审核记录与模型可见数据分离。

### 公司影响增强候选集

- 版本：`fingoose-macro-event-company-enriched-candidate-v1.0`
- `release_tier=CANDIDATE`
- `candidate_ready=true`
- `formal_ready=false`
- 10 个事件、30 个公司档案。
- 30 条事后归因题、30 条事前预测题，共 60 条候选样本。
- 120 条公司指标事实、30 个个股窗口、171 条证据缺口。
- 26 个来源，3 个 event-02 公司档案得到增强，9 条指标事实已验证。
- 30 个档案均为 `PARTIAL_EVIDENCE`，30 个档案均需第二人复审。
- 关联分布：贡献关联 2、暂不支持 28。
- 方向分布：上升 1、下降 1、不确定 28。
- 置信度分布：中 2、低 28。
- 指标状态：已验证 9、待补证 111。

公司七节点固定为：重大事件、行业/宏观变量、公司业务暴露、经营指标、财务结果、竞争解释、关联判断或短期预测。每个节点保留证据引用或明确缺口，不允许伪造来源和数值。

## 3. 正式版阻断项

公司数据仍存在四个正式版阻断项：

- `COMPANY_EVIDENCE_INCOMPLETE`：公司证据不完整。
- `PRICE_WINDOWS_PENDING`：个股和沪深 300 行情窗口待归档。
- `FORMAL_REVIEWS_INCOMPLETE`：正式复审未完成。
- `TWENTY_SEVEN_COMPANIES_REQUIRE_OFFICIAL_ARCHIVES`：除 event-02 的 3 家增强公司外，27 家仍需官方材料归档。

不得因为候选版结构完整、UI 可展示或 `candidate_ready=true` 而将 `formal_ready` 改为 `true`。

## 4. 防泄漏边界

公司预测截止时间是事件后第 3 个可交易日结束时点。公开预测输入只能包含截止日前事件、行业、公司材料和 D1/D3 数据。

以下内容必须留在隐藏区：首个完整季度实际结果、次季实际结果、截止日后的来源 ID、D5/D20 行情、事后归因结论及实际预测验证结果。公开投影从独立截止日快照构建，不能从事后档案删字段生成。

## 5. 审核规则

- 初审人：`reviewer-user-01`。
- 公司低置信度、核心维度未知/矛盾、强竞争解释、季度差分、渠道未明确披露或防泄漏异常时触发第二人复审。
- 未实际完成的复审保持 `SECOND_REVIEW_REQUIRED`；不得伪造第二审核人或裁决人。
- 市场审核的四个核心维度：时点吻合、异常程度、传导机制、竞争解释。

## 6. 十个事件与公司

1. event-01，COVID-19 全球大流行：上海机场、中国国航、达安基因。
2. event-02，俄乌战争全面升级：中国石油、桐昆股份、恒力石化。
3. event-03，美联储加息 75 个基点：中国平安、招商银行、隆基绿能。
4. event-04，中国发布“新十条”：上海机场、中国国航、锦江酒店。
5. event-05，硅谷银行关闭与稳定措施：九安医疗、万孚生物、百济神州。
6. event-06，OPEC+ 额外自愿减产：中国石油、中国石化、东方盛虹。
7. event-07，中东冲突升级：中国石油、中远海控、春秋航空。
8. event-08，日本央行结束负利率：中国银行、春秋航空、国泰君安。
9. event-09，中国金融支持政策组合：保利发展、东方财富、招商银行。
10. event-10，美国广泛对等关税：立讯精密、美的集团、隆基绿能。

## 7. 目录说明

- `data/market_event_attribution_v1`：当前正式市场事件归因数据。
- `data/company_candidate_v1`：最初的 30 公司候选基线，用于对比。
- `data/company_enriched_candidate_v1`：当前默认公司候选数据。
- `data/legacy_formal_macro_v1`：旧公司宏观预测正式集，仅作历史参考，不能与新事件集混用。
- `data/commodity_market_v0_2`：商品期货派生输出与来源状态。
- `evidence_snapshots/`：宏观事件和公司官方材料快照。
- `code/`：构建器、验证逻辑、市场/公司模型和两个 Dashboard。
- `configs/`、`schemas/`、`tests/`：配置、Schema 和测试源文件。
- `docs/`：设计、实施计划和审核手册。
- `ui/screenshots/`：中文 UI 浏览器截图。
- `restricted/`：未复制的许可供应商数据清单和限制说明。
- `HANDOFF_SUMMARY.json`：机器可读的当前状态。
- `FILE_MANIFEST.csv`：全部交接文件 SHA-256 清单。

## 8. 启动中文 UI

在解压后的交接包根目录运行：

```powershell
.\START_UI.ps1
```

默认地址：`http://127.0.0.1:8778/`。

如需可信局域网访问：

```powershell
.\START_UI.ps1 -HostAddress 0.0.0.0 -Port 8778
```

局域网访问会暴露隐藏标签和审核区，只能用于可信网络。生产部署前必须增加身份认证、TLS、访问日志和隐藏审计区权限控制。

## 9. 验证交接包

```powershell
.\VERIFY_HANDOFF.ps1
```

该脚本验证关键文件、10/40/30/60 计数、候选/正式状态和 `FILE_MANIFEST.csv` 中的 SHA-256。

完整开发测试保存在 `tests/`；这些测试按原仓库路径设计，接入新仓库后应恢复原目录布局再运行。

## 10. 关键工程决定

- 原始归档数据保持不可变，中文翻译只存在于 UI 展示层。
- 市场正式集与公司候选集状态始终分开显示。
- 未知值使用 `UNKNOWN`、`INCONCLUSIVE`、`UNCERTAIN`、`WEAK_RELATION` 或 `UNSUPPORTED`，不为平衡标签制造关联。
- 原始公司候选输出与增强候选输出同时保留；增强构建不能覆盖基线。
- 许可供应商数据分类为 `LICENSED_VENDOR_DATA / VENDOR_VERIFIED / OFFICIAL_CROSSCHECK_REQUIRED`。
- 商品期货数据不能替代上交所/深交所股票交易日历。

## 11. 交接后的优先顺序

详见 `NEXT_STEPS.md`。首要工作不是继续美化 UI，而是补齐 27 家公司的官方证据、个股/沪深 300 行情、独立复审和 event-02/event-06 商品行情交叉验证。

