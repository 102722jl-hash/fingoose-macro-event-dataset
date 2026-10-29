# 可审计宏观事件数据集 Skill 设计

日期：2026-08-11

## 1. 目标

创建项目型 Skill `building-auditable-macro-datasets`，把宏观事件发现、缺口扫描、联网证据补全、行业与公司扩展、事件关联问答、行情计算、因果门禁、候选 SFT 构建和确定性验证整合为可复用流水线。

该 Skill 必须能够：

- 扩展用户指定的新宏观事件；
- 按时间范围或主题发现候选事件，并在选定后扩展内容；
- 扫描现有事件并自动补足可补足的缺口；
- 使用公开可复核来源生成候选证据；
- 保持事件、行业、公司和 QA 的统一关联；
- 在证据不足、来源冲突或行情不可回算时主动隔离；
- 从冻结快照离线重建相同产物；
- 永远不自动解除人工审核状态或宣称完成真实训练。

## 2. 已确认的产品决策

- 运行权限：自动生成并写入候选数据。
- 运行范围：支持新增事件和修复现有缺口。
- 事件发现：支持用户指定与受控发现，不允许未经选择直接发布事件。
- 来源范围：正式事实只接受公开可复核来源。
- 时间策略：使用事前推理与事后验证分离的双时钟。
- 失败处理：隔离失败记录并继续处理其他事件。
- 复用方式：通用核心加 FinGoose 适配配置。
- 默认规模：每事件 5 至 10 个行业、3 家公司、4 条 QA。
- 联网方式：搜索 API、正文提取和浏览器回退的分层检索。
- 留档方式：许可允许时保存 HTML/PDF，同时保存摘录、定位、抓取时间和 SHA。
- 输出边界：只生成候选主数据与候选 SFT，不自动生成正式数据集。

## 3. Skill 结构

项目内维护可版本化的 Skill 源码，验证通过后再安装到个人 Skill 目录：

```text
skills/building-auditable-macro-datasets/
├─ SKILL.md
├─ agents/
│  └─ openai.yaml
├─ scripts/
│  ├─ macro_dataset_pipeline.py
│  ├─ source_extractors.py
│  └─ audit_outputs.py
├─ references/
│  ├─ data-contracts.md
│  ├─ source-policy.md
│  ├─ temporal-policy.md
│  ├─ evidence-gates.md
│  ├─ market-formulas.md
│  └─ causal-gates.md
└─ assets/
   └─ profiles/
      └─ fingoose.json
```

`SKILL.md` 只包含触发条件、阶段选择、核心门禁、资源路由和停止条件。字段契约与公式进入 `references`，确定性操作进入 `scripts`，避免在上下文中重复展开大段说明。

## 4. 统一流水线

主命令提供以下子命令：

```text
discover     按主题和时间范围生成候选事件清单
audit        扫描现有事件、行业、公司、QA、证据和行情缺口
enrich       联网检索、提取、快照并生成候选补充内容
build        构建候选统一事件和候选 SFT
validate     执行全套证据、行情、因果、关联和文本验证
reproduce    从冻结输入离线重建两次并比较 SHA
```

阶段顺序固定为：

```text
请求登记
→ 事件发现或缺口扫描
→ 搜索计划
→ 候选 URL 获取
→ 正文提取与快照
→ 来源分级与时间分类
→ 证据合并和冲突检测
→ 事件/行业/公司/QA 扩展
→ 行情连接与回算
→ 因果识别
→ 隔离与候选资格判定
→ 构建
→ 验证
→ 离线复现
```

每个阶段只消费前一阶段的显式产物，不读取隐式会话状态。

## 5. 运行审计目录

每次运行创建不可变 `run_id`，中间产物写入独立目录：

```text
research_runs/<run_id>/
├─ request.json
├─ profile.json
├─ base_dataset_config.json
├─ base_training_config.json
├─ base_unified_events.jsonl
├─ discovery_candidates.jsonl
├─ gap_manifest.jsonl
├─ search_plan.jsonl
├─ search_audit.jsonl
├─ evidence_candidates.jsonl
├─ accepted_evidence.jsonl
├─ rejected_evidence.jsonl
├─ content_candidates.jsonl
├─ accepted_content.jsonl
├─ snapshots/
├─ quarantine.jsonl
├─ candidate_master_data.jsonl
├─ candidate_sft_dataset.jsonl
├─ build_report.json
├─ validation_report.json
└─ manifest.json
```

运行产物使用稳定 ID、UTF-8、规范字段顺序、稳定数组排序和 SHA256。旧运行目录不得被原地覆盖。

## 6. 事件发现

Skill 接受三类请求：

1. 用户提供事件名称、锚点日期或初始来源；
2. 用户提供主题与时间范围，Skill 先返回候选事件；
3. 用户要求扫描现有数据缺口。

候选事件至少保存：

```text
candidate_event_id
title_zh
anchor_at
event_scope
official_seed_urls
materiality_reason_zh
deduplication_fingerprint
selection_status
```

受控发现只生成清单。只有选中的候选事件才能进入联网补全和候选构建阶段。

## 7. 联网检索与来源政策

联网采用三层适配：

1. 搜索适配器获取候选 URL；
2. 结构化提取器读取 HTML、PDF 和公开 JSON；
3. 动态页面无法直接提取时使用浏览器回退。

核心 Skill 不绑定单一搜索服务。FinGoose profile 可以配置 AnySearch 或其他搜索适配器。

来源分级如下：

| 等级 | 来源 | 可支持内容 |
|---|---|---|
| T1 | 政府、央行、国际组织、交易所、公司公告 | 来源事实 |
| T2 | 统计机构、行业协会、公开权威行情 | 统计事实与计算事实 |
| T3 | 主流媒体 | 检索线索与交叉验证 |
| T4 | 研究报告、分析文章 | 研究推断 |

Skill 不得绕过登录、付费墙、访问控制或网站限制。只有搜索摘要时不得生成来源事实。

每条候选证据必须包含：

```text
evidence_id
source_url
publisher
published_at
retrieved_at
original_quote
locator
snapshot_path
snapshot_sha256
source_tier
supports_node_ids
temporal_role
acceptance_status
acceptance_reason
```

## 8. 受控快照

许可允许时保存原始 HTML 或 PDF。无权保存原文件时，只保存允许的正文摘录、URL、定位、响应元数据和内容 SHA。

快照必须记录抓取时间、最终 URL、内容类型、HTTP 状态、重定向链和哈希。解析器只从快照生成结构化证据，使后续离线运行不依赖网页仍然在线。

## 9. 双时钟

每条证据必须分配一个时间角色：

- `AS_OF_EVIDENCE`：事件锚点时已经公开，可进入主要推理链；
- `POST_EVENT_VALIDATION`：事件后公开，只能用于行情验证、反证或结果观察；
- `CUTOFF_BLOCKED`：越过允许时间且不属于验证材料，不得进入训练主路径。

事后公告、事后行情和后来发布的研究结论不得回填为事前可见事实。构建器必须阻止 `POST_EVENT_VALIDATION` 和 `CUTOFF_BLOCKED` 成为事前结论的直接前提。

## 10. 证据门禁

来源事实只有同时具备以下字段才算完整：

```text
original_quote
locator
source_url
```

稀疏子链引用可以继承完整父事件证据，但只能贡献 evidence ID、支持节点和来源 lineage。两条完整同 ID 证据的关键字段发生冲突时必须 fail closed。

以下情况进入隔离区：

- 找不到可核验原文；
- 只有搜索摘要；
- 发布时间不明确；
- 页面无法稳定定位；
- 关键来源互相冲突；
- 公司或行业映射存在歧义；
- 行情日期与基准无法对齐；
- 证据越过允许截止时间。

## 11. 内容扩展契约

### 11.1 事件层

每个事件生成来源事实、时间线、关键里程碑、宏观传导机制、即时/短期/中期影响、行情验证、失效条件和研究边界。

三个阶段不得复用同一陈述：

- 即时：冲击首先改变的变量；
- 短期：经营、定价和库存等传导；
- 中期：供需、政策和竞争格局的再平衡。

### 11.2 行业层

按证据相关性选择 5 至 10 个行业。每个行业生成事件事实入口、七步机制链、经营变量、财务变量、三阶段方向、行业行情、失效条件、支持证据和反证。

行业不足 5 个时允许少于默认值，但必须记录 `INSUFFICIENT_SUPPORTED_INDUSTRIES`，不得为凑数量建立弱关联。

### 11.3 公司层

默认选择 3 家业务暴露明确且有公开披露的公司。公司必须先有业务暴露或官方披露依据，禁止按事后股价涨跌选样。

每家公司生成业务暴露、经营路径、三阶段方向、绝对收益、相对沪深300收益、相对行业收益、混杂因素、反证和因果状态。

### 11.4 QA 层

每个事件默认生成四类 QA：

1. 证据查询；
2. 机制与阶段影响；
3. 行情验证；
4. 行业与公司关联。

每条 QA 包含直接回答、来源事实、研究推断、即时/短期/中期影响、行情计算和证据/因果边界。QA 必须保留所属事件 ID，不得输出为脱离事件的独立数据集。

## 12. 行情计算

固定窗口为：

```text
T_MINUS_1 / T0 / D1 / D3 / D5 / D20
```

公司行情按公司真实交易日期连接行业基准与沪深300，并使用共同 `T_MINUS_1` 基期。

状态包括：

- `CALCULATED`：公司、行业和沪深300均可回算；
- `PARTIAL_CALCULATED`：公司和沪深300可回算，行业基准缺失；
- `DATA_MISSING`：关键输入缺失并登记原因。

禁止以零替代缺失值。每个窗口保存实际日期、公式版本、公式输入和计算输出。验证器必须使用保存的输入重新计算，误差超过配置容差时拒绝候选资格。

## 13. 因果门禁

因果状态为：

```text
NOT_IDENTIFIED
DESCRIPTIVE_EVENT_STUDY
QUASI_EXPERIMENTAL_CANDIDATE
IDENTIFIED
```

只有同时满足行情窗口完整、基准完整、连续交易核验、比较组明确、前趋势通过、混杂因素控制、稳健性通过和反证通过，才允许 `IDENTIFIED`。

其余三种状态一律要求：

```text
causal_attribution_allowed=false
causal_conclusion=ABSTAIN
```

字符串真值、行情端点存在或一般性混杂因素搜索不得替代严格布尔门禁。

## 14. 输出分层

### 14.1 candidate_master_data

保存全部候选事件、缺口、接受证据、拒绝证据和隔离原因。

### 14.2 candidate_sft_dataset

只接收证据链闭环、没有关键冲突且验证通过的样本。样本仍保持：

```text
NEEDS_HUMAN_REVIEW
formal_ready=false
```

### 14.3 quarantine

保存 `OPEN`、来源冲突、时间穿越、映射歧义、行情不可回算和解析失败记录。

Skill 不生成 `formal_sft_dataset`，也不执行人工审核状态升级。

## 15. 可复现运行模式

### 15.1 online-acquire

执行搜索、抓取、快照、候选证据生成和研究内容生成。搜索结果允许随时间变化，但必须登记查询词、搜索适配器、返回顺序、候选 URL、页面状态以及接受或拒绝原因。

联网阶段必须把机器门禁前的事件/行业/公司/QA 研究内容写入 `content_candidates.jsonl`。通过来源、双时钟、证据、行情、因果和关联门禁后，把完整统一事件记录冻结到 `accepted_content.jsonl`；每条记录必须包含 `event_id`、`operation=UPSERT`、完整 `unified_event`、引用的 evidence ID、内容 SHA 和可选的显式 split。同期冻结构建基线为 `base_unified_events.jsonl`。冻结内容仍保持 `NEEDS_HUMAN_REVIEW` 和 `formal_ready=false`。

### 15.2 offline-replay

禁止联网，只使用冻结的 profile、基础 dataset/training 配置、`base_unified_events.jsonl`、`accepted_evidence.jsonl`、`accepted_content.jsonl` 和快照重新执行确定性装配、SFT 投影、验证和 SHA 比较。离线复现不得再次生成、改写或摘要研究文字，也不得重新运行搜索、HTTP、浏览器或模型生成步骤。确定性 SHA 只比较离线复现产物，不要求不同日期的在线搜索结果完全相同。

## 16. 异常处理

- 网络超时：有限重试，仍失败时登记 `FETCH_FAILED`；
- 登录或访问限制：登记 `ACCESS_RESTRICTED`；
- 正文解析失败：登记 `PARSE_FAILED` 并隔离；
- 搜索无结果：登记稳定缺口码，不生成占位事实；
- 来源冲突：保留全部候选并隔离，不按预设结论选择来源；
- 行情缺失：保留缺口，不填零；
- 单事件失败：隔离事件，其他事件继续；
- 程序异常：保留已完成阶段产物，重新运行从最后一个完整检查点恢复。

## 17. 验证与候选资格

验证顺序为：

1. schema 与稳定 ID；
2. 原文、定位与 URL；
3. 双时钟与截止时间；
4. 推理链与 evidence registry；
5. 行情公式回算；
6. 因果门禁一致性；
7. 事件、行业、公司和 QA 关联；
8. 中文乱码与占位符；
9. 样本长度和任务分布；
10. 离线双轮 SHA。

候选 SFT 必须满足：

- `OPEN=0`；
- `0 errors / 0 warnings`；
- 未知 evidence ID 为 0；
- 非 `IDENTIFIED` 且非 `ABSTAIN` 为 0；
- 行情数字可回算或具有稳定缺口码；
- QA 全部关联所属事件；
- 中文乱码和占位符为 0；
- 两次 `offline-replay` 产物 SHA 相同；
- dry-run 为 `ready=true`、`model_loaded=false`。

## 18. 测试策略

- 单元测试：来源分级、时间门禁、证据合并、行情公式和因果状态；
- 合约测试：FinGoose 字段、目录与四类任务；
- 黄金样本测试：一个冻结事件完整通过全部阶段；
- 缺口测试：断网、冲突来源、行业基准缺失和时间越界；
- 隔离测试：失败事件不污染其他事件；
- 离线复现测试：两轮输出 SHA 一致；
- 联网冒烟测试：验证搜索与提取适配器可用，不作为确定性测试；
- Skill 前向测试：在不提供本次会话结论的情况下，用一个新事件验证 Skill 是否能独立完成工作流。

## 19. FinGoose Profile

`assets/profiles/fingoose.json` 配置：

```text
project_root
dataset_config
training_config
source_paths
candidate_work_dir
snapshot_dir
output_paths
dataset_version
task_types
event_discovery_filters
source_domain_policy
knowledge_cutoff_policy
industry_min
industry_max
company_default
qa_default
market_window_keys
search_adapters
price_data_adapters
split_policy
validation_commands
```

默认值为行业 5 至 10 个、公司 3 家、QA 4 条、窗口 `T0/D1/D3/D5/D20`、公开可复核来源、双时钟、隔离并继续和候选输出。

`split_policy` 默认使用 `sha256_mod_100`：哈希桶 0–79 分配到 `train`，80–89 分配到 `validation`，90–99 分配到 `test`。现有事件保留原配置中的 split；新事件允许在 `accepted_content.jsonl` 中显式指定 `train`、`validation` 或 `test`，否则使用稳定哈希分配。相同 `event_id`、profile 和策略版本必须始终得到相同 split。

## 20. 命令接口

```powershell
python scripts/macro_dataset_pipeline.py discover --profile fingoose --topic "半导体出口管制"
python scripts/macro_dataset_pipeline.py audit --profile fingoose
python scripts/macro_dataset_pipeline.py enrich --profile fingoose --run-id <id>
python scripts/macro_dataset_pipeline.py build --profile fingoose --run-id <id>
python scripts/macro_dataset_pipeline.py validate --profile fingoose --run-id <id>
python scripts/macro_dataset_pipeline.py reproduce --profile fingoose --run-id <id>
```

构建成功后通过原子替换更新候选输出，原始来源和旧 manifest 不得直接覆盖。

## 21. Skill 触发范围

以下请求应触发该 Skill：

- 扩展新的宏观事件；
- 搜索特定时期的重要宏观事件；
- 补足宏观事件、行业、公司或 QA 缺口；
- 补全证据或行情数据；
- 重新构建可审计宏观训练数据；
- 验证宏观事件数据集是否可复现。

该 Skill 不用于一般新闻摘要、无来源观点写作、实时交易建议、人工审核替代或自动正式发布。

## 22. 安全与边界

- 不伪造来源、原文、定位、行情或公司映射；
- 不绕过访问控制；
- 不把媒体转述升级为官方事实；
- 不把事后材料回填为事前知识；
- 不把行情同步性表述为严格因果；
- 不自动将候选数据标记为正式可训练；
- 不宣称执行了未实际运行的人工审核或 GPU 训练。

## 23. 完成定义

Skill 源码、FinGoose profile 和必要 references/scripts 创建完成；所有脚本通过定向测试；`quick_validate.py` 通过；黄金样本能够从冻结输入完成 `offline-replay`；新增事件前向测试能够生成完整审计目录、候选主数据、候选 SFT 或明确隔离结果；候选产物满足第 17 节门禁。
