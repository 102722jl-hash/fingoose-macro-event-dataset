# FinGoose 十事件研究问答候选包交接

## 定位

本候选包用问答补足十个宏观事件的证据、机制、行情与行业—公司边界。宏观事件仍是一级对象，问答已并入原事件工作台，不是独立问答应用。

页面顺序固定为：

`事件概览 → 研究问答 → 事件时间线 → 动态传导链 → 行业影响 → 公司影响`

全部记录保持：

`PROPOSED / NEEDS_HUMAN_REVIEW / formal_ready=false / sha_gate=DEFERRED`

不提供买入、卖出或确定性投资建议。

## 产物

- `qa_cases.jsonl`：10 个事件 × 4 类问题，共 40 条公开问题。
- `qa_answer_candidates.jsonl`：40 条公开候选答案；每条含来源事实、研究推断、计算事实、拒答与边界四层。
- `evaluator_only/qa_labels.jsonl`：40 条隐藏标签；未进入公开 UI 数据包。
- `source_fetches.jsonl`：13 条官方来源抓取审计。
- `qa_validation_report.json`：公式、数量、连接、拒答和公开边界报告。
- `manifest.json`：产物字节数、记录数和 SHA-256。
- `ui-1440.png`、`ui-390.png`：Chrome 双视口全页截图。
- `HANDOFF.pilot-v1.md`：实施前的三事件试点交接原文备份。

原 UI 已重建到：

`work/company_impact_high_quality_v2_candidate/ui/index.html`

本地查看：`http://localhost:59144/#qa`

## 十事件合同

行业数量保持：`8 / 8 / 8 / 8 / 7 / 7 / 7 / 7 / 8 / 9`，合计 77 条。

每个事件均有：

- 综合研判
- 证据核查
- 行情验证
- 行业—公司

每条答案保留 7 步机制链、即时/短期/中期方向，以及 `T-1 / T0 / D1 / D3 / D5 / D20` 六窗口。

`event-03` 截止日已修正为 `2022-03-19T18:00:00Z`。`event-07` 配置的红海锚点首次公开于 2023-11-19，晚于 `2023-10-10T23:59:59.999999Z` 截止日，因此公开答案保留 10 月 7 日联合国冲突事实，并对红海锚点输出 `UNKNOWN + ABSTAIN + ANCHOR_POST_CUTOFF`。

## 来源状态

联网抓取后再进行无网络确定性重建，最终状态为：

- `RETRIEVED_QUOTE_VERIFIED`: 10
- `FETCH_FAILED`: 1
- `CONTENT_MISMATCH`: 1
- `POST_CUTOFF_EXCLUDED`: 1

卫健委原入口返回 HTTP 412，已追加中国政府网同文官方入口并验证成功。联合国原入口正文模板未命中登记引文，已追加 UN News 官方页面并验证成功。失败与不匹配记录保留用于审计。

## 拒答与边界

40 条答案共记录 312 个任务级强制拒答；按每事件主答案去重后为 78 个范围：30 个公司范围、47 个行业范围和 1 个截止日后事件锚点。

触发条件包括行业或公司闭环仍为 `OPEN`、交易状态未核验、重大混杂未关闭、证据发布时间不合格或事件锚点晚于截止日。缺证方向不补零、不补造确定性方向。

## 验证证据

- Python 专项与原 UI 回归：`39 passed in 2.58s`
- Python 编译检查：退出码 0
- 候选包：10 事件、40 问题、40 答案、40 隐藏标签
- 公式最大绝对误差：`0.0`
- manifest 中 5 个登记产物的 SHA-256 全部复算一致
- 公开文件扫描未发现隐藏标签、`formal_ready=true`、`sha_gate=PASSED` 或 `review_status=CONFIRMED`
- `tests/verify_qa_ui_v2.mjs`：`1440x1000` 与 `390x844` 通过
- `tests/verify_event_01_industry_ui.mjs`：通过
- `tests/verify_ten_event_industry_ui_fixed.mjs`：双视口通过

原 `tests/verify_ten_event_industry_ui.mjs` 第 1 行存在既有双单引号语法损坏；修复版保留了原脚本的数据计数、七步链、41 点行情、图表、混杂、标签和溢出断言。

## 人工审核阻断项

- 仍需人工复核每条研究推断的因果强度和措辞。
- 仍需逐项决定 `OPEN` 行业与公司是否补证或维持拒答。
- 仍需确认网页快照的再分发许可；许可未确认前不得把网页快照视为可公开发布资产。
- 当前目录的 Git 元数据无效，本次未创建提交，不得描述为已提交或正式发布。
