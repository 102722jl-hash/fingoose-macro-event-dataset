# FinGoose · 项目完全剖析

> 本文档面向**技术面试**场景，对 FinGoose（金融宏观事件传导链高质量数据集 / SFT 训练框架）做一次"完全解剖"：
> 从项目定位、技术栈、四层传导链领域模型、推理链设计、数据防泄漏体系、Schema 驱动、
> 工程门禁与质量保证、人工审查制度、前端交付形态，到版本演进与工程踩坑，逐层展开。
>
> 阅读方式建议：面试前通读第 1、3、5、7 章建立全局观；被追问细节时按第 4、6、8~11 章逐层下钻；
> 第 13、14 章是"踩坑 + 加分点"，是拉开差距的地方。
>
> —— 所有事件数、样本数、字段枚举、哈希、门禁项均以交付包内文件实测为准；关键处标注文件与字段。
> 凡两处文件记录冲突者，均显式标注"版本差异"。

---

## 目录

1. 项目一句话与定位
2. 技术栈与运行环境
3. 架构总览：四层传导链与"研究区段"
4. 目录结构与代码规模
5. 领域模型：宏观事件 → 行业 → 公司
6. 推理链设计：市场六步链 + 行业/公司七节点链
7. 数据防泄漏与可审计体系（核心）
8. Schema 驱动、数据集规模与切分
9. 工程门禁与质量保证
10. 人工审查制度（Review Handbook）
11. 前端 Dashboard 与交付形态
12. 版本演进：Canonical v0.1 → v2
13. 工程踩坑与解决总览
14. 面试加分点提炼
15. 已知局限与后续规划
16. 附录：关键数字速查表 & 高频追问题库

---

## 1. 项目一句话与定位

**一句话**：FinGoose 是一个**金融宏观事件驱动的、可审计、可复现的多任务高质量数据集与 SFT 训练框架**——围绕"宏观事件 → 传导机制（时间线）→ 行业影响 → 公司影响 / 事件研究问答"四层主线，把"证据 / 来源 / 时点 / 因果口径"全部结构化落盘，**答不出出处的样本一律 ABSTAIN，绝不编造因果**。

**与"普通用大模型生成财经问答"的本质区别**（面试第一句话就该点出的钩子）：

| 维度 | 普通 LLM 生成数据 | 本项目 |
|---|---|---|
| 数字/来源 | 模型"记得"、可能编造 | 每条结论挂 `source_ref` + 快照 SHA-256 + 原文定位符 |
| 因果归因 | 顺口就给因果 | 四级因果识别，非 `IDENTIFIED` **必须 ABSTAIN** |
| 事后诸葛 | 隐含未来信息 | 预测截止 = 事件后第 3 个可交易日；D20 结果进 hidden 层，公开仅见 D1/D3 |
| 缺失值 | 补 0 / 猜一个 | `KEEP_NULL_NEVER_ZERO_IMPUTE`、`KEEP_PENDING_NEVER_INFER_AVAILABLE`（fail-closed） |
| 数据契约 | 靠约定 | **21 个 JSON Schema** 硬约束 + 16 项验证门禁 |
| 交付质量 | 人肉抽查 | `VERIFY_HANDOFF.ps1` 遍历 **201 个文件**逐一 SHA-256 核验，输出 `HANDOFF VERIFIED` |

**解决问题的业务背景**：

1. 财经视频/内容生产需要"事件 → 影响"的**可追溯推理链**，而通用大模型输出的因果归因往往不可核查、易编造；
2. 需要一套**防数据泄漏、防 look-ahead bias（事后诸葛）**的数据工程规范；
3. 需要把不稳定的"AI 生成结论"**门禁化**：只有满足证据闭环（strict claim closure）的样本才能进训练集，否则 ABSTAIN。

**目标用户**：金融内容/研究团队（财经视频脚本）、数据集交付方与审核方（初审人 / 复审人 / 仲裁人 / 发布负责人四角色）、下游 SFT 训练工程师。

**交付主线（四层）**：宏观事件 → 时间线与传导机制 → 行业影响 → 公司影响 → 事件研究问答。

---

## 2. 技术栈与运行环境

### 2.1 运行时依赖

| 层 | 技术 | 备注 |
|---|---|---|
| 数据工程 / 后端 | **Python**（stdlib + dataclasses + hashlib） | 120+ 个 `.py`，`code/` 与 `training/` 为主 |
| 前端 | 原生 **HTML / CSS / JavaScript**（非框架 SPA） | 单页 Dashboard，含不可变版本链 |
| 抓取脚本 | **Node.js `.mjs`**（如 `fetch_cninfo_company_reports_v2.mjs`） | 配合 Python 抓公告正文 |
| 启动 / 校验 | **PowerShell**（`START_UI.ps1` / `START_UI_V2.ps1` / `VERIFY_HANDOFF.ps1`） | 一键启动与一键核验 |
| 数据格式 | **JSONL / JSON / CSV**（+ PDF / HTML 快照） | 无数据库，纯文件系统 |
| 训练栈 | `torch>=2.4,<3`、`transformers>=4.48,<6`、`datasets>=3,<5`、`trl>=0.15,<1`、`peft>=0.14,<1`、`accelerate>=1,<2`、`bitsandbytes>=0.45,<1`、`pytest>=7,<9` | 见 `training/requirements.txt` |
| UI 验收 | **Playwright**（系统 Chrome，双视口 1440×1000 / 390×844） | 桌面 + 移动端截图验收 |

### 2.2 硬件基线（统一 SFT 设计文档给定）

Windows 11 / Ryzen 9 7940H / 16GB RAM / **RTX 4060 Laptop 8GB**；默认 **1.5B–3B 4-bit QLoRA**，序列长度 2048、batch 1、grad_accum 16；7B 仅作实验配置（`sft_qlora_7b_experimental.json`）。

> 面试点：**数据工程与"能不能真训"无关**——项目刻意选择"本地 8GB 显存可跑"的模型档位，把交付重心放在数据集本身的质量与可审计性上。

### 2.3 运行方式与端口

- `START_UI.ps1`：端口默认 **8778**，`PYTHONPATH=code`，调用 `code\fingoose_macro_event_company_deep_dashboard_v1.py`（该脚本代码默认端口 **8776**）。
- `START_UI_V2.ps1`：端口默认 **8782**，调用 `code\fingoose_macro_event_v2_dashboard.py`（代码默认端口 **8782**，一致）。
- 更早版本 `code\fingoose_macro_event_dashboard_v1.py` 代码默认端口 **8765**；归档旧计划文档中出现默认端口 **52346**。
- 局域网查看：`python -m http.server 8000 --bind 0.0.0.0`（示例 `http://192.168.1.227:8000/#qa`）。

> 说明：`8776`（deep dashboard 代码默认）与 `8778`（ps1 覆盖）、`8765`（旧 dashboard）、`52346`（归档）并存，属**多版本共存**；端口选择原因交付包内无显式说明（标注"未确认"）。

---

## 3. 架构总览：四层传导链与"研究区段"

### 3.1 四层传导链

```
┌─────────────────────────────────────────────────────────────────────┐
│ ① 宏观事件层  10 个全球宏观事件（WHO 疫情定性 / 俄乌冲突 / 美联储加息  │
│               / 中国防疫转向 / 硅谷银行 / OPEC+ 减产 / 红海危机 /      │
│               日本结束负利率 / 中国一揽子金融政策 / 美国对等关税）      │
├─────────────────────────────────────────────────────────────────────┤
│ ② 传导机制层  时间线 + 里程碑（episode / milestone，事件级 21 条）      │
│               事件锚点 anchor_node_id、dynamic transmission graph     │
├─────────────────────────────────────────────────────────────────────┤
│ ③ 行业影响层  申万一级（SW1）行业映射，77 条；每行业含 driver /        │
│               operating / financial / directions / condition /        │
│               invalidation；事件级 behavior_change_zh / counterevidence│
├─────────────────────────────────────────────────────────────────────┤
│ ④ 公司 + 问答层  每事件固定 3 家公司 → 30 条事件-公司映射；             │
│               公司档案 dossier / 归因样本 / 行情窗口 / 事件研究 QA      │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 主 UI "研究区段"（6 段）

`work/company_impact_high_quality_v2_candidate/ui/index.html` 将研究过程拆成 6 段线性叙事：
**事件概览 → 研究问答 → 事件时间线 → 动态传导链 → 行业影响 → 公司影响**。

> 面试点：这套"区段顺序"不是随便排的，它**就是数据集的任务类型顺序**（EVENT_ANALYSIS → EVENT_QA → INDUSTRY_IMPACT → COMPANY_IMPACT），前端即数据集的"可视化说明书"。

### 3.3 数据流向

宏观事件配置 → 四层构建器（`build_*`）逐层产出候选 → Schema 校验 + 门禁 → 人工审查 → 发布（formal_ready / candidate_ready）→ SFT 投影（`sft_projector`）→ 统一多任务数据集 → QLoRA 训练。

---

## 4. 目录结构与代码规模

### 4.1 核心目录（交付包 `FinGoose_macro_event_company_candidate_handoff_2026-07-29/`）

```
├── code/                      # 130 文件：四层构建器 + dashboard（含 _base/_impl_NNN 级联实现）
├── training/                  # 185 文件：统一多任务 SFT 训练区（fingoose_training 包 + scripts + tests）
├── skills/                    #  23 文件：Skill 封装（SKILL.md + 7 references + 3 scripts + 9 tests）
├── data/                      #  74 文件：6 个数据集版本目录
├── docs/                      #  72 文件：specs / plans / superpowers / guides
├── schemas/                   #  21 文件：21 个 JSON Schema（数据契约核心）
├── configs/                   #  27 文件：事件 / 行业 / 公司 / 问答配置
├── tests/                     # 109 文件：顶层测试（对应 46 passed 验收口径）
├── evidence_snapshots/        #  40 文件（29.5MB）：证据原始快照
├── restricted/                #   2 文件：受限数据清单 / 声明
├── ui/                        #   5 文件：截图
├── work/                      # 790 文件（423.6MB）：各阶段候选工作产物（含主 UI）
├── FILE_MANIFEST.csv          # 201 个文件逐一 sha256
├── VERIFY_HANDOFF.ps1         # 一键核验（遍历 manifest 校验 hash + 断言关键计数）
├── START_UI.ps1 / START_UI_V2.ps1
└── HANDOFF_CURRENT_2026-08-06.md / README_HANDOFF.md / README_V2.md / NEXT_STEPS.md
```

### 4.2 规模体量（面试可说的"量级"）

- **交付包由 12.1GB / 6701 文件精简为约 503MB / 1489 文件**（历史路线与临时产物拆到 `02_归档_历史路线` / `03_归档_临时产物`）；
- `FILE_MANIFEST.csv` 共 **201 个受控文件**，字段 `relative_path, size_bytes, sha256, category`；
- `code/` 130 文件，`training/` 185 文件，`schemas/` 21 个，`configs/` 27 个，`tests/` 109 文件；
- 申报口径：**120 个 `.py` / 约 34,449 行**、10 个前端文件 / 约 3,558 行（以实测统计为准）；前端最大单文件约 1309 行；
- 主 UI 含**不可变版本链**：`versions/fingoose-ui-20260813-r000/`、`r001/`（各含 `index.html` + `release_manifest.json` + `ui_data_bundle.js`）。

> 交付包根路径在 `HANDOFF_CURRENT_2026-08-06.md` 中记为 `D:\桌面\workspace\codex1\handoff\...`，与当前实际路径（`高质量数据集\FinGoose_最终成果\01_交付包\...`）不同，属**路径迁移/复制**，需在文档中注明。

---

## 5. 领域模型：宏观事件 → 行业 → 公司

### 5.1 宏观事件层：10 个事件（`configs/fingoose_macro_events_v1.json`，63,371B）

| # | 事件 | 时间 | 锚点 anchor |
|---|---|---|---|
| 01 | WHO 将新冠疫情定性为全球大流行 | 2020-03-11 | `fast-event-01-M04` |
| 02 | 俄乌冲突全面升级 | — | `fast-event-02-M03` |
| 03 | 美联储开启加息周期 | — | `fast-event-03-M03` |
| 04 | 中国防疫政策转向 | — | `fast-event-04-M03` |
| 05 | 硅谷银行倒闭与银行业冲击 | — | `fast-event-05-M02` |
| 06 | OPEC+ 意外减产 | — | `fast-event-06-M03` |
| 07 | 红海航运危机升级 | — | `fast-event-07-M03` |
| 08 | 日本央行结束负利率 | — | `fast-event-08-M04` |
| 09 | 中国一揽子金融支持政策 | — | `fast-event-09-M03` |
| 10 | 美国对等关税政策公布 | 2025-04-02 | `fast-event-10-M02` |

- 事件目标资产序列：`SP500 / VIXCLS / DCOILWTICO / DCOILBRENTEU / DEXCHUS / DGS10 / DTWEXBGS / DEXJPUS`（覆盖股指、波动率、油价、汇率、美债收益率、美元指数）。

### 5.2 行业层：77 条申万映射

- 行业基线映射：`event-01` 8 条 + `event-02~10` 69 条 = **77 条**（`multi_event_closure_contract.json`：`expected_union_mapping_count=77`、`expected_mapping_count=69`）。
- v2 行业影响候选集 `work/industry_impact_high_quality_v2_candidate`：`validation_report.json` 的 `industry_total=77`。
- 每行业字段（`configs/industry_impact_v2/event_industry_profiles.json`）：
  `sw1_id`、`name`、`name_at_event`（事件日历史名称，如 801020"采掘"）、`tier`（如 `CORE_DIRECT`）、`segments`、`driver`、`unit`、`operating`、`financial`、`directions`（含 `POSITIVE/NEGATIVE/MIXED`）、`condition`、`invalidation`；
  事件级含 `behavior_change_zh`、`counterevidence_zh`、`anchor_node_id`、`classification_edition`（`SW2014` / `SW2021`）。

> 面试点：**用"事件日的历史行业名称"而非今日名称**（`name_at_event`）——这是防"后视偏差"的一个细节：2020 年时申万还没有"电力设备"这一级名称，若用现代分类名会产生时代错位。

### 5.3 公司层：23 家公司 / 30 条事件-公司映射

- 公司构成：**每个事件固定 3 家公司** → 10 事件 × 3 = **30 条事件-公司映射**（`configs/company_impact_high_quality_v2/event_company_map.jsonl`，30 条）。
- 公司注册表 `company_registry.jsonl` 为 **23 家**（去重后），全部 `dossier_status=DATA_PENDING`、`formal_ready=false`。
- 样例映射：event-01→达安基因/上海机场/中国国航；event-02→恒力石化/桐昆股份/中国石油；event-03→招商银行/隆基绿能/中国平安；event-05→九安医疗/万孚生物/百济神州；event-07→春秋航空/中国石油/中远海控；event-10→美的集团/立讯精密/隆基绿能。
- 映射内嵌申万分类血缘：`classification_edition`（SW2014/SW2021）、`classification_status=OFFICIAL_HISTORY_ASOF_MATCHED`、`source_snapshot_path=sources/industry_classification/StockClassifyUse_stock_2026-08-02.xls`、**源哈希 `source_snapshot_sha256=d0f92b795b3364da303d72c5a0464a79d7e4710c4b53f26f7fb510e8106c8843`**、`member_valid_from / member_valid_to_exclusive`。
- 映射状态：`binding_selection_status=PENDING_COMPANY_MECHANISM_REVIEW`、`lineage_status=GRAPH_LINKED_CANDIDATE`、`evaluation_eligible=false`、`formal_ready=false`。

> 面试点：**"每事件固定 3 家公司"不是数量凑数，而是可复现的构成规则**——它保证每个事件在"跨资产/单资产"与"行业/公司"两个维度上样本量对齐，便于做分层评测。

---

## 6. 推理链设计：市场六步链 + 行业/公司七节点链

### 6.1 市场六步链（`forecastReasoningChain.sequence`，const 硬约束）

1. `MACRO_REPORT`（宏观报告 / 事件陈述）
2. `DATA`（数据事实）
3. `PERIOD_DESCRIPTION`（阶段描述）
4. `FACT_TRANSMISSION_CHAIN`（事实传导链）
5. `MULTI_DATA_TREND_CONFIRMATION`（多数据趋势确认）
6. `SHORT_TERM_PREDICTION`（短期预测）

> 关键：`sequence` 是 **JSON Schema 的 `const`**——不是"建议顺序"，而是数据契约强制。任何样本只要六步顺序错位，校验直接失败。

### 6.2 行业七步链（`multi_event_closure_contract.json` 的 `step_contract`）

| 步 | 节点 | 证据类型 |
|---|---|---|
| 1 | `EVENT_FACT` | SOURCE_FACT |
| 2 | `BEHAVIOR_OR_POLICY_CHANGE` | SOURCE_FACT |
| 3 | `OBSERVABLE_DRIVER` | SOURCE_FACT |
| 4 | `INDUSTRY_OPERATING_VARIABLE` | SOURCE_FACT |
| 5 | `INDUSTRY_REVENUE_OR_COST_VARIABLE` | RESEARCH_INFERENCE |
| 6 | `DIRECTION_ASSESSMENT` | RESEARCH_INFERENCE |
| 7 | `PRICE_CONFOUNDER_AND_COUNTEREVIDENCE` | CALCULATED_FACT |

### 6.3 公司七节点链

`MAJOR_EVENT → INDUSTRY_MACRO_VARIABLE → COMPANY_BUSINESS_EXPOSURE → OPERATING_METRIC → FINANCIAL_RESULT → COMPETING_EXPLANATION → ATTRIBUTION_OR_FORECAST`

- 行业七步链与公司七节点链共享"**前三步是事实、后两步是推断、最后一步是计算/反证**"的分层逻辑（`SOURCE_FACT → RESEARCH_INFERENCE → CALCULATED_FACT`），体现"事实与推断必须分栏"的建模原则。

### 6.4 统一推理链元数据 v1（`fingoose-reasoning-chain-v1`）

顶层四块：`reasoning_chain` / `evidence_registry` / `conclusion_lineage` / `parent_chain_refs`。

- `node_type` **8 种**；`status` **6 种**：`VERIFIED_SOURCE / EVIDENCE_MISSING / SUPPORTED_INFERENCE / INFERENCE_ONLY / CALCULATED_ONLY / CUTOFF_BLOCKED`；
- `edge relation` **6 种**：`SUPPORTS / DERIVES / LIMITS / CONTRADICTS / CONFOUNDS / VALIDATES_ONLY`；
- **状态传播规则 8 条 + 验证门禁 16 项**；
- 模块边界：`reasoning_chain.py / unified_builder.py / sft_projector.py / validation.py`。

> 面试点：`CUTOFF_BLOCKED` 状态是"时间政策"落到推理链上的产物——一旦某个节点依赖的信息晚于预测截止日，它不是"删掉"，而是显式标记为被截止日阻断，**保留在链里但不参与结论**。这比"直接删节点"更可审计。

### 6.5 归因标签与置信度枚举

- 归因标签（`attribution.label`）：`PRIMARY_DRIVER / CONTRIBUTING_FACTOR / WEAK_RELATION / UNSUPPORTED`
  （v1 市场集实际分布：`PRIMARY_DRIVER=5`、`CONTRIBUTING_FACTOR=9`、`WEAK_RELATION=8`、`UNSUPPORTED=18`）。
- 置信度（`confidence`）：`HIGH / MEDIUM / LOW`。
- 竞争解释强弱：`LIMITED / MIXED / STRONG / UNKNOWN`。
- 公司归因 `association` 枚举：`VERIFIED_ASSOCIATION / CONTRIBUTING_ASSOCIATION / WEAK_RELATION / UNSUPPORTED`。
- **自动触发复审四条件**：`LOW_CONFIDENCE`、`STRONG_COMPETING_EXPLANATION`、`CORE_DIMENSION_UNKNOWN`、`CORE_DIMENSION_CONTRADICTED`。

> 面试点：`UNSUPPORTED=18` 占 40 条市场样本的 45%——**"承认一半样本没有可支撑的因果结论"恰恰是这个数据集的价值**，而不是缺陷。它把"强行给因果"的诱惑用 schema 挡掉了。

---

## 7. 数据防泄漏与可审计体系（核心）

这是本项目的**第一加分项**，面试务必讲到。

### 7.1 预测截止日（prediction cutoff）

- 公司预测截止 = **事件后第 3 个可交易日结束时点**。
- QA 层 `prediction_cutoff_policy = PRIMARY_ANCHOR_PUBLICATION_PLUS_72H_DATE_VALUES_USE_END_OF_DAY_UPPER_BOUND`，逐事件给出 `prediction_cutoff_at`（如 event-01 `2020-03-14T16:30:00Z`、event-10 `2025-04-05T21:19:04Z`）。

### 7.2 可见 / 隐藏窗口的 Schema 硬隔离

- `data_cutoff.visible_windows` **const `["D1","D3"]`**；`hidden_outcome_window` **const `"D20"`**（`fingoose_macro_attribution_sample_v1.schema.json`）。
- D20 结果与归因标签进入 hidden 层：v1 市场集 `hidden_attribution_label_count=40`、`hidden_outcome_count=40`。

### 7.3 audit_only / 评测隔离

- 评价专用数据 `answer_evaluation.distill.jsonl`（3,202,792 B）标记 `QA_EVALUATION_ONLY`、`included_in_handoff=false`（`restricted/RESTRICTED_DATA_MANIFEST.csv`）。
- v2 候选集 `hidden_evaluation_event_count=3`、`hidden_label_count=10`。
- **发布门禁明确拒绝**：含 hidden / evaluator_only / benchmark_labels 内容的样本不得进入训练集。

### 7.4 双时钟时间政策（temporal policy）

三种时间角色：`AS_OF_EVIDENCE` / `POST_EVENT_VALIDATION` / `CUTOFF_BLOCKED`；
字段级落地：`published_at` / `anchor_at` / `declared_role` / `temporal_role`。

> 面试点：**"双时钟"= 一条证据同时有两个时间坐标**——它"在事件发生时是否已存在"（as-of）与"它是什么类型的验证"（post-event validation）。只有 `AS_OF_EVIDENCE` 的证据才能支持预测；`POST_EVENT_VALIDATION` 只能用于事后核验。这是防 look-ahead 的核心机制。

### 7.5 事件级切分（防事件级泄漏）

- `split_policy = sha256_mod_100`（桶 0–79 → train、80–89 → validation、90–99 → test）。
- `training/configs/dataset.json` 与 `split_manifest.json` 固化：**train = event-01~08、validation = event-09、test = event-10**。

> 面试点：**按"事件"切分而非按"样本"随机切分**——否则同一事件的训练样本和测试样本会因事件级信息共享而泄漏，指标虚高。这是一个"懂行才会做"的细节。

### 7.6 缺失值的 fail-closed 策略

- `missing_evidence_policy = KEEP_PENDING_NEVER_INFER_AVAILABLE`
- `missing_market_policy = KEEP_NULL_NEVER_ZERO_IMPUTE`

> 面试点：**"宁缺毋滥"**——缺失就是缺失，绝不补 0、绝不"推断为可用"。因为一旦补值，下游就无法区分"真实为 0"和"没数据"。

### 7.7 可审计性（每条结论可回溯到原文）

- `evidence_snapshots/SNAPSHOT_PATH_MAP.csv`（47 行）：`original_local_snapshot_path → package_snapshot_path → content_sha256`，全部 `HASH_MATCHED`。
- 每条结论含 `source_ref` + 原文定位符（如 `locator="page=1, HIGHLIGHTS, bullet 1"`）+ 快照 SHA。
- `FILE_MANIFEST.csv` **201 文件逐一 SHA-256**，`VERIFY_HANDOFF.ps1` 一键核验输出 `HANDOFF VERIFIED`。
- **确定性重建**：同输入 → 相同 SHA-256（两次重建哈希一致）。

---

## 8. Schema 驱动、数据集规模与切分

### 8.1 21 个 JSON Schema（数据契约）

市场归因样本 `fingoose_macro_attribution_sample_v1`：`attribution.label` enum 四值；`confidence` enum 三值；`forecastReasoningChain.sequence` const 六步；`data_cutoff.visible_windows` const `["D1","D3"]`、`hidden_outcome_window` const `"D20"`。

公司归因 `fingoose_company_attribution_sample_v1`：`association` enum 四值；`forecast_labels` 必含 `REVENUE / PROFIT / OPERATING_CASH_FLOW`。

公司行情窗口 `fingoose_company_stock_window_v1`：`benchmark` const `"CSI300"`、`window_basis="COMPANY_TRADING_SESSIONS"`、窗口 `D1/D3/D5/D20`。

市场窗口 `fingoose_macro_market_window_v1`：`metric_type` enum `[price_return_pct, fx_return_pct, yield_basis_points]`、`quote_convention="LOCAL_CURRENCY_PER_USD"`、`estimation.window="PREVIOUS_60_SESSIONS"`。

其余 schema 覆盖：commodity_market_v0.2、commodity_vendor_main_v0.2、company_event_dossier_v1、company_forecast_sample_v1、company_metric_fact_v1、company_review_record_v1、macro_benchmark_case_v2、macro_benchmark_label_v2、macro_candidate_v0_3、macro_event_100_candidate_v1、macro_event_dossier_v1、macro_event_episode_v2、macro_event_milestone_v2、macro_market_window_v2、macro_review_decision_v1、macro_review_record_v1、macro_transmission_graph_v2 等。

> 面试点：**"Schema 先行"**——先定义数据契约（21 个 schema），再写构建器；构建器只负责"填"，校验器负责"守"。这样 100+ 个 `.py` 由多个阶段/多人产出也不会跑偏。

### 8.2 统一 SFT 数据集（`training/data/`）

- `unified_events.jsonl`（10 条）+ `sft_dataset.jsonl`（**157 条**）；字段 `sample_id / event_id / task_type / split / messages / metadata`（用字段区分任务，不拆多个文件）。
- **任务分布**：`EVENT_ANALYSIS 10` / `INDUSTRY_IMPACT 77` / `COMPANY_IMPACT 30` / `EVENT_QA 40` = **157**。
- **切分**（`validation_report.json` `split_counts`）：train **124** / validation **16** / test **17** = 157。
- event_counts：event-01~04 各 16、event-05~08 各 15、event-09 16、event-10 17。
- **推理链统计**（`reasoning_chain_stats`）：

| 任务 | chain | evidence | node | main_path |
|---|---|---|---|---|
| COMPANY_IMPACT | 30 | 1119 | 210 | 210 |
| EVENT_ANALYSIS | 10 | 343 | 152 | 56 |
| EVENT_QA | 40 | 486 | 416 | 280 |
| INDUSTRY_IMPACT | 77 | 2650 | 539 | 539 |
| **总计** | **157** | **4598** | **1317** | **1085** |

- `missing_node=0`、`open_closure=0`。
- `content_quality_stats`：complete_horizon 157 / content_contract 157 / placeholder **0** / review_boundary 157 / ui_parity_pass 157。
- `causal_identification_stats`：**NOT_IDENTIFIED=30**（其余全 0）→ 公司结论全部必须 ABSTAIN。
- `closure_reason_stats`：`CLOSED=157`。

> 面试点：`placeholder=0`、`missing_node=0`、`open_closure=0` 是三个"零"——**零占位、零缺节点、零开放闭环**。面试时用"三个零"概括数据清洁度非常有记忆点。

### 8.3 各数据集版本规模

| 数据集 | 关键数字 | 状态 |
|---|---|---|
| 市场归因 v1（`market_event_attribution_v1`） | event 10 / sample 40 / window 40 / single_asset 30 / cross_asset 10 / source 20 | **formal_ready=true**，gate_failures [] |
| 市场归因 v2 候选（`market_event_attribution_v2_candidate`） | benchmark_case 10 / challenge 4 / episode 21 / milestone 21 / transmission_graph 10 / hidden_eval_event 3 / window 40 | `release_tier=CANDIDATE`，formal_ready=false |
| 公司候选 v1（`company_candidate_v1`） | evidence_gap 180 / source 20 | candidate_ready=true |
| 公司增强候选 v1（`company_enriched_candidate_v1`） | candidate_sample 60 / company_dossier 30 / metric_fact 120 / stock_window 30 / evidence_gap 171 / source 26 | candidate_ready=true，formal_ready=false |
| 商品 v0.2（`commodity_market_v0_2`） | complete `[CU, AU, SC]`，I 缺失 | **status=blocked** |
| 历史正式宏观 v1（`legacy_formal_macro_v1`） | candidate 20 / projection 20 / verification 20 / rejected 0 | formal_ready=true |

- 公司公告正文抓取 47 / 正文审核 47 / 映射级检索审计 30 / 交易状态审核 30 / 公司级反证审核 30 / 中文论证 30；混杂等级 `{CLEAN: 15, MATERIAL: 2, MINOR: 13}`。

---

## 9. 工程门禁与质量保证

### 9.1 校验与测试

- Schema 校验：`validate_dataset.py` 输出 `validation passed: 0 errors, 0 warnings`。
- `pytest training/tests` → **46 passed**（`HANDOFF_CURRENT_2026-08-06.md`）。
- 历史专项口径（归档记录）：Skill tests 34 passed、FinGoose tests 134 passed、专项 43 passed、UI 19 passed、市场+时区 12 passed、QA 39/44 passed、reasoning chain 69 passed；全仓曾出现 `307 passed / 1 skipped / 29 failed / 26 errors`（均属旧版 v1 基线与环境缺口）。
- 另有 `compileall` 语法检查、`train_sft.py --dry-run` → `ready=true`、`model_loaded=false`。

> **版本差异提示**：仓库检索**未找到 "224 passed" 的任何匹配**；现存正式口径为 `training/tests` **46 passed**。撰写/面试引用时以 **46 passed** 为准。

### 9.2 哈希门禁

- `VERIFY_HANDOFF.ps1`：遍历 `FILE_MANIFEST.csv` 逐文件校验 SHA-256，并断言
  market `event_count=10 & sample_count=40`；company `event_count=10 & company_dossier_count=30 & candidate_sample_count=60`；
  market `formal_ready=true`；company `formal_ready=false & candidate_ready=true & release_tier=CANDIDATE`；成功输出 `HANDOFF VERIFIED`。
- 申万分类源哈希：`d0f92b795b3364da303d72c5a0464a79d7e4710c4b53f26f7fb510e8106c8843`。
- 确定性重建：同输入 → 相同 SHA-256。

### 9.3 formal_ready / candidate_ready 判定与阻断项

- 市场 v1：`formal_ready=true`、`gate_failures=[]`。
- 市场 v2：`release_tier=CANDIDATE`、`candidate_ready=true`、`formal_ready=false`。
- 公司 `company_enriched_candidate_v1` 的 **4 个阻断项**：
  1. `COMPANY_EVIDENCE_INCOMPLETE`
  2. `PRICE_WINDOWS_PENDING`
  3. `FORMAL_REVIEWS_INCOMPLETE`
  4. `TWENTY_SEVEN_COMPANIES_REQUIRE_OFFICIAL_ARCHIVES`（命名沿用旧口径，registry 现为 23 家）
- 公司 `company_candidate_v1` 的 4 个阻断项（**旧版本口径**）：`COMPANY_EVIDENCE_INCOMPLETE`、`PRICE_WINDOWS_PENDING`、`GOLD_LABELS_PENDING`、`FORMAL_REVIEWS_INCOMPLETE`。

### 9.4 发布门禁（11 条，review handbook v1 摘录）

含：`WEAK_RELATION + UNSUPPORTED >= 20%` 拒绝发布；任一标签占比 ≤ 60%；公开投影不得含隐藏标签 / D20；`formal_ready=true` 方可发布；`messages` 三条总字符数 ≤ 2000（超限进拒绝项）；含 hidden/evaluator_only/benchmark_labels 者拒绝。

### 9.5 strict-claim-closure-v2（Skill `building-auditable-macro-datasets`）

每行业七步节点须声明 `DIRECT_FACT / PREMISE_SUPPORT / CALCULATED_LINEAGE / NEGATIVE_SEARCH_AUDIT`；每行业固定 3 家公司，**每公司至少两份事件日前 T1/T2 证据**；行情覆盖 T-1/T0/D1/D3/D5/D20 状态 `CALCULATED`；批量发布若事件集不全则报 `ATOMIC_BATCH_EVENT_SET_INCOMPLETE`。

### 9.6 因果门禁

- 因果识别四级：`IDENTIFIED / NOT_IDENTIFIED / DESCRIPTIVE_EVENT_STUDY / QUASI_EXPERIMENTAL_CANDIDATE`；**非 IDENTIFIED 必须 ABSTAIN**。
- IDENTIFIED 需 **8 项门禁全过**（含 `pretrend_passed`、`robustness_passed`、`counterevidence_passed`），违者报 `CAUSAL_GATE_CONTRADICTION`。
- 来源分级 T1/T2/T3/T4，**仅 T1/T2 可支持 `SOURCE_FACT`**。

---

## 10. 人工审查制度（Review Handbook）

**四核心维度**：归因标签合理性 / 置信度 / 竞争解释强弱 / 证据边界。

**自动触发复审四条件**：`LOW_CONFIDENCE`、`STRONG_COMPETING_EXPLANATION`、`CORE_DIMENSION_UNKNOWN`、`CORE_DIMENSION_CONTRADICTED`。

**批次安排**：`review-batch-01-pilot`（event-01~02，8 条试审）→ `batch-02`（event-03~05，12 条）→ `batch-03`（event-06~08，12 条）→ `batch-04`（event-09~10，8 条）。

**角色分工**：初审人（40）/ 复审人（15）/ 仲裁人 / 发布负责人。

> 面试点：**这是一套"人机协同的数据产线 SOP"**——机器产出候选 + 门禁挡不合格项 + 人工按批次评审 + 四角色分工定责。它解释了一个"数据集项目"为什么需要"治理制度"，而不是"跑个脚本"。

---

## 11. 前端 Dashboard 与交付形态

- 主 UI：`work/company_impact_high_quality_v2_candidate/ui/index.html`（原生 HTML/CSS/JS），六段研究区段。
- **不可变版本链**：`versions/fingoose-ui-20260813-r000/`、`r001/`，每版含 `index.html` + `release_manifest.json` + `ui_data_bundle.js`——**UI 也进哈希门禁**。
- 双 dashboard：`fingoose_macro_event_company_deep_dashboard_v1.py`（deep，8776/8778）与 `fingoose_macro_event_v2_dashboard.py`（v2，8782）。
- 验收：Playwright 系统 Chrome，桌面 1440×1000 + 移动 390×844 双视口截图。
- `ui_parity_pass=157`——**UI 展示与数据集内容逐条一致**（避免"页面演示的是一套、数据集里是另一套"）。

> 面试点：把 UI 也纳入"哈希 + 版本链 + 一致性校验"，说明项目把"交付一致性"当成工程问题而非演示问题。

---

## 12. 版本演进：Canonical v0.1 → v2

**完整路线**（`00_总览/FinGoose_项目展示.html`）：`v0.1 Canonical 100` → `v0.1 五类 RLVR 试点` → `v0.2 双轨含商品行情` → `v0.3 公开官方来源` → 最终交接包 → 训练栈定型。

**数据层演进**：`legacy_formal_macro_v1`（20 candidate，正式）→ `market_event_attribution_v1`（40 样本，formal_ready）→ `market_event_attribution_v2_candidate`（10 基准 + 4 挑战 + 21 episode/milestone + 10 传导图，CANDIDATE）→ `company_candidate_v1` → `company_enriched_candidate_v1`。

**v2 相对 v1 的关键迭代**（`README_V2.md`）：
- 10 事件 / 21 证据里程碑 / 21 事件阶段 / 10 张动态传导图 / 40 市场窗口 / 10 三赛道基准案例；
- 新增 event-02/03/04 完整示例 + 3 隐藏评测 + 4 挑战集；
- 传导边保持 `PROPOSED`（AI 生成、未人工确认）；
- 行情从原始 FRED CSV 快照**按 SHA-256 重算** T60/T20/T1/D1/D3/D5/D20/M3；
- 页面默认端口从 v1 的 8778/8776/8765 演进到 v2 的 8782。

**训练目标演进**：早期单任务 → **统一多任务 SFT**（`fingoose-unified-sft-v1`，放弃 DPO/GRPO/RLVR）；推理链 metadata 从无到 v1（`fingoose-reasoning-chain-v1`）。

> 面试点：**"从 RLVR 试点回退到统一 SFT"**是一个可讲的技术决策故事——多任务统一格式比多阶段 RL 更容易做数据契约与可复现性；在 8GB 显存与 157 条样本的规模下，SFT 的性价比更高。

---

## 13. 工程踩坑与解决总览

| # | 踩坑 | 解决 | 面试价值 |
|---|---|---|---|
| 1 | 申万接口 **Brotli 解码失败** | 适配器仅在该接口期间固定 `Accept-Encoding: gzip, deflate`，调用后恢复原请求函数；**未修改 AKShare 安装文件**（`work/event_01_industry_closure_v2_candidate/HANDOFF.md`） | 展示"最小侵入式打补丁"与依赖治理 |
| 2 | 官方页面 **TLS 完整性错误 / HTTP 412** | 保持 `FETCH_FAILED`，**拒绝用搜索摘要冒充实证** | 展示"数据可得性优先于完整性"的诚信底线 |
| 3 | 正文逐字匹配的空白规范 | 只忽略中/数/标点边界的布局空白，**英文单词间空格仍参与匹配**；不用模糊相似度晋升来源 | 展示对"证据强度"的严格界定 |
| 4 | 交付包过大（**12.1GB / 6701 文件**） | 拆分为 `01_交付包`（503MB/1489 文件）+ `02_归档_历史路线` + `03_归档_临时产物`；受控文件进 `FILE_MANIFEST.csv` | 展示工程化交付与"可控面/历史面"的分层 |
| 5 | 缺失值补 0 的诱惑 | `KEEP_NULL_NEVER_ZERO_IMPUTE` + `KEEP_PENDING_NEVER_INFER_AVAILABLE` | 展示对"数据语义保真"的坚持 |
| 6 | 事件之间信息泄漏 | 按 `sha256_mod_100` 做**事件级切分** | 展示对评测有效性的理解 |

---

## 14. 面试加分点提炼

> 这一章是"拉开差距"的地方，建议背下 3~5 条。

### 14.1 数据工程严谨性

- **21 个 JSON Schema 驱动 + fail-closed**：非合规样本一律 ABSTAIN（157 条全部 `CLOSED`，`missing_node=0`、`open_closure=0`、`placeholder=0`）。
- **双时钟时间政策**（`AS_OF_EVIDENCE / POST_EVENT_VALIDATION / CUTOFF_BLOCKED`）+ 四个时间字段（`published_at / anchor_at / declared_role / temporal_role`）。
- **缺失值策略**：`KEEP_NULL_NEVER_ZERO_IMPUTE`、`KEEP_PENDING_NEVER_INFER_AVAILABLE`，杜绝补零/事后填充。

### 14.2 可复现性

- 确定性重建：同输入 → 相同 SHA-256。
- 行情从原始 FRED CSV 快照**按 SHA-256 核验后重算** T60/T20/T1/D1/D3/D5/D20/M3。

### 14.3 可审计性

- `SNAPSHOT_PATH_MAP.csv`（47 行，全部 `HASH_MATCHED`）：`原始路径 → 包内路径 → content_sha256`。
- 每条结论含原文定位符（如 `page=1, HIGHLIGHTS, bullet 1`）+ 快照 SHA。
- `FILE_MANIFEST.csv` 201 文件逐一 SHA-256，`VERIFY_HANDOFF.ps1` 一键 `HANDOFF VERIFIED`。

### 14.4 抗泄漏

- 事件级切分（`sha256_mod_100`）；
- `visible_windows` const `["D1","D3"]` 与 `hidden_outcome_window` const `"D20"` 的 **Schema 硬隔离**；
- `audit_only` / `QA_EVALUATION_ONLY` 隔离；
- 发布门禁拒绝 hidden 内容。

### 14.5 可背的量化成果数字

- 10 个宏观事件、**157 条统一 SFT 样本**、4 类任务、**124/16/17 事件级切分**；
- 30 条公司映射 / 23 家公司 / 77 条行业映射 / 40 个市场窗口 / 20 来源（v1）；
- 推理链总量：chain **157** / evidence **4598** / node **1317** / main_path_node **1085** / missing_node **0**；
- **0 校验错误 · 0 警告**、`ready=true`、两次重建 SHA 一致、**46 passed**；
- 交付包 12.1GB → 503MB 瘦身；1 个 Skill（统一 CLI：discover/audit/enrich/build/validate/reproduce）；1 个 `formal_ready` 数据集（market v1）。

### 14.6 一句话总结（面试收尾）

> "我做的是一个**把'金融因果推断'变成'可校验数据契约'的项目**：每条结论要么能回溯到原文快照，要么就 ABSTAIN；每个样本要么通过 21 个 schema 与 16 项门禁，要么就不进训练集。所以它的核心不是'生成了多少条数据'，而是'每条数据能不能被审计'。"

---

## 15. 已知局限与后续规划

### 15.1 已知局限

1. **商品集 v0.2 `status=blocked`**：四商品（CU/AU/SC/I）未全部完成，I（DCE 铁矿）`contract_record_count=0`；`license_scope=unknown`、`display_allowed=false`、`redistribution_allowed=false`、`forecast_labels_generated=false`。
2. **公司因果识别全部 `NOT_IDENTIFIED`**（30 条）→ 公司结论必须 ABSTAIN。
3. **公司候选集 `formal_ready=false`**，4 阻断项未清零；23 家公司全部 `dossier_status=DATA_PENDING`。
4. **传导边为 AI 生成 `PROPOSED`**，未人工确认；v2 `aggregate_score=null`（不生成综合总分）。
5. **行业市场数据缺口**：`market_data_availability.json` 显示申万指数历史 / 沪深300 历史 / A股历史在许可库中均不可用（`SHENWAN_INDEX_HISTORY_NOT_AVAILABLE`、`CSI300_HISTORY_NOT_AVAILABLE_IN_LICENSED_DATABASE`），`gap_status=OPEN`。
6. **训练未真正执行**：未下载 Qwen2.5-3B-Instruct、未跑真实 QLoRA GPU 训练、`training/runs/` 无 adapter；`--dry-run` 仅 `ready=true`、`model_loaded=false`。
7. **受限数据未复制**：约 1.1GB 许可供应商原始文件（wind/dce_iron_ore 主表 1,168,874,339 B 等），`source_class=LICENSED_VENDOR_DATA`、`formal_source_status=OFFICIAL_CROSSCHECK_REQUIRED`。
8. **部分来源抓取失败**：`event01-gov-diagnosis-v6`（TLS 完整性错误）、`event01-nmpa-test-kits`（HTTP 412）保持 `FETCH_FAILED`。
9. 全部映射/行业/公司记录 `review_status=NEEDS_HUMAN_REVIEW`、`sha_gate=DEFERRED`。
10. 该项目目录**非有效 Git 仓库**（`NO_VALID_GIT_METADATA`），未生成提交。

### 15.2 后续规划（`NEXT_STEPS.md`）

- **P1**：商品传导增强——优先品种 `EG/EB/L/PP/PG/I/J/JM`，范围"事件前 60 → 后 20 交易日"。
- 补齐公司官方档案（清零 `TWENTY_SEVEN_COMPANIES_REQUIRE_OFFICIAL_ARCHIVES` 等阻断项）。
- 完成行业市场数据缺口（申万/CSI300 历史），打通价格验证链。
- 真跑统一多任务 QLoRA 训练并产出 adapter。

---

## 16. 附录：关键数字速查表 & 高频追问题库

### 16.1 关键数字速查表

| 项目 | 数字 |
|---|---|
| 宏观事件 | 10 |
| 行业映射（申万一级） | 77 |
| 事件-公司映射 | 30 |
| 公司注册表 | 23 |
| 统一 SFT 样本 | 157（EVENT_ANALYSIS 10 / INDUSTRY_IMPACT 77 / COMPANY_IMPACT 30 / EVENT_QA 40） |
| 切分 | train 124 / val 16 / test 17 |
| 推理链证据总数 | 4598 |
| 推理链节点总数 | 1317 |
| 市场 v1 样本 | 40（formal_ready） |
| 公司候选样本 | 60（candidate_ready） |
| JSON Schema | 21 |
| 受控交付文件 | 201（逐一 SHA-256） |
| 测试 | 46 passed（`training/tests`） |
| 校验结果 | 0 errors / 0 warnings |
| 预测截止 | 事件后第 3 个可交易日 |
| 公开可见窗口 | D1 / D3（D20 进 hidden） |
| 申万分类源哈希 | `d0f92b79…06c8843` |

### 16.2 高频追问题库（附参考答法）

**Q1：你怎么保证数据里没有"事后诸葛"（look-ahead bias）？**
A：三层保障——①时间政策把证据分成 `AS_OF_EVIDENCE / POST_EVENT_VALIDATION / CUTOFF_BLOCKED`，只有 as-of 能支持预测；②Schema 把可见窗口 `const ["D1","D3"]`、隐藏结果 `const "D20"` 写死，物理隔离；③发布门禁拒绝任何含 hidden 内容的样本。

**Q2：为什么有 45% 的市场样本标签是 `UNSUPPORTED`？这不是质量差吗？**
A：恰恰相反。因果识别有四级，非 `IDENTIFIED` 必须 ABSTAIN。`UNSUPPORTED=18/40` 说明系统**拒绝为证据不足的事件编因果**。如果 100% 都有"强因果"，那才是危险信号。

**Q3：157 条样本会不会太少？**
A：这是"高质量、可审计、多任务"的 157 条，不是"爬来的" 157 条。每条含完整推理链（合计 4598 个证据节点、1317 个链节点），且 0 占位、0 缺节点、0 开放闭环。规模小是因为质量门槛高（T1/T2 来源 + 闭环 + 人工评审）。

**Q4：为什么按事件切分而不是随机切分？**
A：同一事件的样本共享大量事件级信息；随机切分会让训练集"见过"测试事件，指标虚高。按事件切分（`sha256_mod_100`）才能反映真实泛化能力。

**Q5：`CUTOFF_BLOCKED` 状态为什么不直接删掉节点？**
A：删掉会掩盖"这里本应有信息但被截止日挡住"的事实。标记为 blocked 保留在链中，既不参与结论、又让审计者看见"缺口的成因"。

**Q6：你怎么证明交付的包没被改动过？**
A：`FILE_MANIFEST.csv` 记录 201 个文件逐一 SHA-256；`VERIFY_HANDOFF.ps1` 一键遍历校验，并断言关键计数（event=10、sample=40、dossier=30 等），全部通过才输出 `HANDOFF VERIFIED`。

**Q7：项目最大的技术难点是什么？**
A：**把"因果"变成"可校验的数据契约"**。难点不在生成文本，而在：给每个结论挂可回溯来源、给每个时点定义时间角色、给每种缺失定义 fail-closed 策略、给每次发布定义门禁与阻断项。这些都必须在 Schema 层固化，否则 100+ 个构建器一定会跑偏。

---

*文档基于交付包内文件实测整理；标注"版本差异 / 未确认"处请以最新交付物为准。*
