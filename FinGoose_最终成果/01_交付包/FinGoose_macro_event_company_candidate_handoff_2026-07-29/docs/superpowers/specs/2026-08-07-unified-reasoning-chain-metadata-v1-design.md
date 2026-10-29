# FinGoose 统一证据链 Metadata v1 设计

日期：2026-08-07

## 1. 背景

当前 `training/data/sft_dataset.jsonl` 已包含 `EVENT_ANALYSIS`、`INDUSTRY_IMPACT`、`COMPANY_IMPACT` 和 `EVENT_QA` 四类任务，但 metadata 主要保存扁平的 `evidence_ids`、`source_record_ids` 和关联外键。它不能表达“哪个证据支持哪个节点、节点之间如何推导、哪条路径真正支持最终结论”。

部分上游行业机制链也只在事件事实节点登记证据，后续行为、经营、财务和方向节点缺少逐节点证据状态。SFT 投影器的 `_short_chain()` 还会裁剪节点并移除节点级证据关系，最终训练产物无法保留完整证据链。

本设计将完整证据链提升为统一主数据中的规范对象，并由 SFT 投影器按任务复制到 metadata，同时在 messages 中保留可训练的精简推导摘要。

## 2. 目标

1. 十个事件及其四类任务采用同一套证据链 schema。
2. `unified_events.jsonl` 成为证据链的唯一规范来源。
3. 每条 SFT 样本 metadata 保存完整、可审计、可追溯的证据链。
4. assistant 消息包含精简的“前提—规则—中间结论—最终结论—边界”，避免 metadata 对常规 SFT 不可见。
5. 缺证、推断、计算事实和来源事实严格区分，不把行情验证或事件锚点扩张成经营因果证明。
6. 保持事件级 split、2000 字符消息门禁、隐藏字段门禁及候选审核状态不变。

## 3. 非目标

- 本阶段不执行人工审核。
- 不把候选结论提升为正式结论。
- 不下载模型，不执行真实 GPU 或 QLoRA 训练。
- 不将完整原文全部写入 assistant 消息。
- 不直接手工编辑两个核心训练 JSONL。

## 4. 总体架构

```text
宏观、行业、公司、问答候选数据
              |
              v
统一证据登记与证据链编译器
              |
              v
training/data/unified_events.jsonl
  - event.reasoning_chain
  - industries[].reasoning_chain
  - companies[].reasoning_chain
  - qa[].reasoning_chain
              |
              v
SFT 投影器按任务选择相关链
              |
              v
training/data/sft_dataset.jsonl
  - messages: 精简可训练推导
  - metadata: 完整可审计证据链
```

统一主数据负责生成和保存规范证据链。SFT 投影器不得重新猜测节点依赖，只能选择、裁剪和序列化统一主数据中的链。

## 5. 统一 Schema

每个事件、行业、公司和问答对象增加 `reasoning_chain`。每条 SFT metadata 增加以下字段：

```json
{
  "reasoning_chain_version": "fingoose-reasoning-chain-v1",
  "evidence_registry": [],
  "reasoning_chain": {
    "chain_id": "",
    "task_type": "",
    "nodes": [],
    "edges": [],
    "main_path_node_ids": [],
    "side_branch_node_ids": [],
    "final_node_id": "",
    "parent_chain_refs": [],
    "closure_gate": {}
  },
  "conclusion_lineage": {
    "final_conclusion_id": "",
    "supporting_node_ids": [],
    "supporting_evidence_ids": [],
    "missing_evidence_ids": []
  }
}
```

### 5.1 证据登记

`evidence_registry` 中每条记录包含：

```json
{
  "evidence_id": "",
  "evidence_kind": "",
  "publisher": "",
  "title": "",
  "first_public_at": "",
  "fact_zh": "",
  "original_quote": "",
  "locator": "",
  "source_url": "",
  "snapshot_sha256": "",
  "availability_scope": "PREDICTION_VISIBLE",
  "review_status": "",
  "supports_node_ids": []
}
```

缺少原文、定位或来源的证据 ID 仍登记，但必须设置 `evidence_status=EVIDENCE_MISSING`，不得补造原文、URL 或 SHA。

### 5.2 推理节点

```json
{
  "node_id": "",
  "step": 1,
  "node_type": "SOURCE_FACT",
  "statement_zh": "",
  "statement_class": "SOURCE_FACT",
  "status": "VERIFIED_SOURCE",
  "evidence_ids": [],
  "missing_evidence_ids": [],
  "premise_node_ids": [],
  "condition_zh": "",
  "invalidation_zh": "",
  "cutoff_status": "PREDICTION_VISIBLE"
}
```

`node_type` 允许：

- `SOURCE_FACT`
- `CALCULATED_FACT`
- `RULE`
- `RESEARCH_INFERENCE`
- `INTERMEDIATE_CONCLUSION`
- `FINAL_CONCLUSION`
- `COUNTEREVIDENCE`
- `CONFOUNDER`

`status` 允许：

- `VERIFIED_SOURCE`
- `SUPPORTED_INFERENCE`
- `INFERENCE_ONLY`
- `EVIDENCE_MISSING`
- `CALCULATED_ONLY`
- `CUTOFF_BLOCKED`

### 5.3 推理边

```json
{
  "edge_id": "",
  "source_node_id": "",
  "target_node_id": "",
  "relation": "SUPPORTS",
  "used_for_final_conclusion": true,
  "boundary_zh": ""
}
```

`relation` 允许 `SUPPORTS`、`DERIVES`、`LIMITS`、`CONTRADICTS`、`CONFOUNDS` 和 `VALIDATES_ONLY`。

行情、同行比较和事后验证只能使用 `VALIDATES_ONLY` 或进入旁证支路，不得直接生成经营事实节点。

## 6. 状态传播规则

1. 来源事实只有在证据登记中存在原文、定位和来源时才能标记 `VERIFIED_SOURCE`。
2. 来源事实登记了证据 ID 但缺少可核对内容时标记 `EVIDENCE_MISSING`。
3. 推断节点只有在所有关键前提存在且未被阻断时才能标记 `SUPPORTED_INFERENCE`。
4. 关键前提缺证时，下游节点保留陈述，但状态降为 `INFERENCE_ONLY` 或 `EVIDENCE_MISSING`。
5. 行情和公式结果标记为 `CALCULATED_ONLY`，只验证反应强弱。
6. 截止日后证据标记 `CUTOFF_BLOCKED`，不得进入主路径。
7. 反证和混杂必须保留在图中，不得只写在自然语言尾注。
8. `main_path_node_ids` 只能包含实际用于最终结论的节点；其余信息进入 `side_branch_node_ids`。

## 7. 四类任务映射

### 7.1 EVENT_ANALYSIS

主路径：事件来源事实 -> 时间线节点 -> 宏观行为或政策变化 -> 中间经济变量 -> 市场或经营结果 -> 事件级结论。

市场窗口、替代事件和宏观混杂进入旁证支路。最终结论必须明确归因边界。

### 7.2 INDUSTRY_IMPACT

保留完整七步行业机制：

1. 事件事实
2. 行为或政策变化
3. 可观察驱动
4. 行业经营变量
5. 行业收入或成本变量
6. 方向判断
7. 行情、混杂与反证验证

七步均必须存在节点和状态。无证据时保留缺口，不允许删除节点或用事件锚点证据覆盖整条链。

### 7.3 COMPANY_IMPACT

主路径：事件事实 -> 行业变量 -> 公司事件前业务暴露 -> 公司经营或财务变量 -> 三阶段方向 -> 公司结论。

公司行情、停复牌、公告混杂和反证进入验证或限制支路。行业方向不得直接复制为公司方向。

### 7.4 EVENT_QA

根据问题类型生成任务特定链：

- 证据查询：来源事实 -> 支持范围 -> 证据边界。
- 行情验证：窗口计算 -> 相对表现 -> 可辨识性 -> 混杂 -> 验证结论。
- 行业—公司：行业机制 -> 公司暴露 -> 公司变量 -> 公司结论 -> 失效条件。
- 主推理：事件事实 -> 三阶段机制 -> 行业结果 -> 公司边界 -> 最终回答。

QA metadata 必须自包含，同时通过 `parent_chain_refs` 记录所引用的事件、行业和公司链。

## 8. Messages 投影

完整证据链主要存放在 metadata，但 assistant 消息必须包含主路径摘要：

```text
前提事实：[证据ID] 中文事实。
适用规则：该事实通过什么机制影响哪个变量。
中间结论：经营或市场变量如何变化。
最终结论：即时、短期和中期分别是什么。
证据边界：缺失证据、混杂、反证和截止日限制。
```

消息只引用主路径中的关键证据 ID。完整原文、所有节点、所有边和旁证保留在 metadata。三段消息总字符数继续不超过 2000。

## 9. 验证门禁

构建后必须验证：

1. 四类任务全部具有 `reasoning_chain_version`。
2. 同一样本内节点 ID、边 ID 和证据 ID 唯一。
3. 每条边引用的节点存在。
4. 推理图为有向无环图。
5. `final_node_id` 存在并可由主路径到达。
6. `SOURCE_FACT` 的证据 ID 能在 `evidence_registry` 解析，或明确标记缺证。
7. `SUPPORTED_INFERENCE` 的关键前提全部存在且未阻断。
8. `supports_node_ids` 与节点 `evidence_ids` 双向一致。
9. `conclusion_lineage` 与主路径、最终节点一致。
10. assistant 中出现的证据 ID 均存在于 metadata。
11. `INDUSTRY_IMPACT` 保留七个机制步骤。
12. 截止日后证据不进入主路径。
13. 行情节点不直接生成经营事实结论。
14. 同一事件不跨 split。
15. 不出现 `hidden`、`evaluator_only` 或 `benchmark_labels`。
16. 两次重建的统一主数据、SFT、split manifest 和验证报告 SHA 完全一致。

## 10. 模块边界

新增独立证据链编译模块，避免把构建逻辑继续堆叠在投影器中：

- `reasoning_chain.py`：规范化证据、生成四类任务链、执行状态传播。
- `unified_builder.py`：连接候选数据并调用证据链编译器。
- `sft_projector.py`：复制规范链、裁剪任务相关证据并生成消息摘要。
- `validation.py`：验证 schema、图结构、证据双向映射和任务门禁。

投影器不得修改链状态或根据自然语言重新推断证据关系。

## 11. 兼容与迁移

1. 保留现有 `related_industry_ids`、`related_company_codes`、`evidence_ids` 和 `source_record_ids`，避免破坏现有加载器。
2. 新字段作为 metadata 增量字段加入。
3. `evidence_ids` 继续保存主路径证据 ID 的扁平集合，完整映射由新结构表达。
4. 从来源候选包和构建逻辑重建数据，不直接修改 `unified_events.jsonl` 或 `sft_dataset.jsonl`。
5. 旧训练配置仍可只读取 messages；新配置可以选择把 metadata 主路径动态展开到 messages。

## 12. 测试与验收

至少增加以下测试：

- 10 个事件和 157 条 SFT 样本全部具有统一证据链。
- 四类任务的任务特定结构符合约束。
- 77 条行业样本均保留七个机制步骤。
- 节点—证据双向映射一致。
- 缺证向下游传播，不被误标为已支持推断。
- event-07 截止日门禁继续生效。
- messages 中的证据引用均可在 metadata 解析。
- metadata 不包含 evaluator-only 字段。
- 现有 46 项训练测试继续通过。
- 构建、验证、compileall 和训练 dry-run 通过。
- 连续两次重建 SHA 一致。

## 13. 发布边界

本次升级只提高数据结构、训练可见推理和证据可追溯性，不改变任何人工审核状态。统一主数据和 SFT 仍是候选训练产物；证据存在不等于因果成立，计算结果不等于经营事实，完整链也不代表已通过人工原文复核。
