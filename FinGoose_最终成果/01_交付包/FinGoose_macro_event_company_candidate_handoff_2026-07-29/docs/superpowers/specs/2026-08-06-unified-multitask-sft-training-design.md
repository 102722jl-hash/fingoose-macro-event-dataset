# FinGoose 统一多任务 SFT 训练框架设计

## 1. 目标

在现有 FinGoose 宏观事件、行业影响、公司影响和事件问答候选包之上，新增独立的 `training/` 模块。模块将四类数据按 `event_id` 汇总为事件中心主数据，再投影为标准 `messages` SFT 样本，并提供事件级切分、数据验证、3B QLoRA 训练和训练后评测能力。

训练框架不得改写现有 `data/` 和 `work/` 产物，不得把问答建设成脱离十个宏观事件的独立任务，也不得将隐藏评测标签或预测截止日期后的资料泄漏到训练输入。

## 2. 已确认的约束

- 训练类型：基础监督微调（SFT），不包含 DPO、GRPO、奖励模型或强化学习。
- 任务组织：统一多任务，包含 `EVENT_ANALYSIS`、`INDUSTRY_IMPACT`、`COMPANY_IMPACT`、`EVENT_QA`。
- 样本格式：Hugging Face/TRL 通用 `messages` 格式。
- 数据主键：所有主数据和训练样本必须包含 `event_id`。
- 数据切分：按完整事件切分，同一事件的行业、公司和问答不得跨越 train、validation、test。
- 默认硬件：Windows 11、Ryzen 9 7940H、16GB 内存、RTX 4060 Laptop 8GB 显存。
- 默认训练基线：1.5B 至 3B 中文指令模型、4-bit QLoRA、序列长度 2048、batch size 1、梯度累积 16、梯度检查点开启。
- 7B 模型仅提供实验配置，不作为可稳定运行的验收基线。

## 3. 总体架构

```text
现有宏观事件数据 ─┐
现有行业影响数据 ─┼─> loaders -> unified_builder -> unified_events.jsonl
现有公司影响数据 ─┤                                  |
现有事件问答数据 ─┘                                  v
                                             sft_projector + splits
                                                        |
                                                        v
                                               sft_dataset.jsonl
                                                        |
                                                        v
                                             validate -> train -> evaluate
```

`unified_events.jsonl` 是事件中心的统一研究主数据。`sft_dataset.jsonl` 是由主数据自动生成、可直接交给训练器的标准训练投影。两个文件不是两套独立维护的数据；训练投影必须可由统一主数据确定性重建。

## 4. 文件分布

```text
training/
├─ README.md
├─ requirements.txt
├─ .gitignore
├─ configs/
│  ├─ dataset.json
│  ├─ sft_qlora_3b.json
│  └─ sft_qlora_7b_experimental.json
├─ fingoose_training/
│  ├─ __init__.py
│  ├─ loaders.py
│  ├─ unified_builder.py
│  ├─ sft_projector.py
│  ├─ splits.py
│  ├─ validation.py
│  └─ metrics.py
├─ scripts/
│  ├─ build_unified_dataset.py
│  ├─ build_sft_dataset.py
│  ├─ validate_dataset.py
│  ├─ train_sft.py
│  └─ evaluate_sft.py
├─ data/
│  ├─ unified_events.jsonl
│  ├─ sft_dataset.jsonl
│  ├─ split_manifest.json
│  ├─ manifest.json
│  └─ validation_report.json
├─ tests/
│  ├─ test_loaders.py
│  ├─ test_unified_builder.py
│  ├─ test_sft_projector.py
│  ├─ test_splits.py
│  └─ test_validation.py
└─ runs/
   └─ <run-id>/
      ├─ adapter_model/
      ├─ training_config.json
      ├─ dataset_manifest.json
      ├─ train_metrics.json
      └─ evaluation_metrics.json
```

现有候选包继续保存在原路径。训练模块通过 `configs/dataset.json` 读取它们，不复制原始来源快照，不覆盖候选包状态字段。

## 5. 统一事件主数据契约

`training/data/unified_events.jsonl` 每行保存一个完整事件，预期包含十条事件记录。顶层结构为：

```json
{
  "event_id": "event-01",
  "dataset_version": "fingoose-unified-sft-v1",
  "event": {},
  "industries": [],
  "companies": [],
  "qa": [],
  "lineage": {
    "source_files": [],
    "source_record_ids": []
  }
}
```

`event` 保存事件标题、日期、时间线、宏观证据、市场窗口和研究结论。`industries` 保存该事件的行业映射、机制链、方向、行情和证据。`companies` 保存公司代码、行业关联、业务暴露、机制链、方向、行情、混杂因素、反证和证据。`qa` 保存问题、答案、相关行业 ID、相关公司代码和证据 ID。

构建器以 `event_id` 为第一关联键，以稳定的行业 ID、公司代码和问题 ID 为次级关联键。无法解析的外键不能静默丢弃，必须写入验证错误并阻止正式训练。

## 6. SFT 训练样本契约

`training/data/sft_dataset.jsonl` 每行保存一条训练样本：

```json
{
  "sample_id": "event-01-company-600009-sh",
  "event_id": "event-01",
  "task_type": "COMPANY_IMPACT",
  "split": "train",
  "messages": [
    {"role": "system", "content": "系统约束"},
    {"role": "user", "content": "事件资料、证据和问题"},
    {"role": "assistant", "content": "有证据边界的标准答案"}
  ],
  "metadata": {
    "related_industry_ids": [],
    "related_company_codes": [],
    "evidence_ids": [],
    "source_record_ids": []
  }
}
```

训练器只使用 `messages` 计算 SFT 损失。`sample_id`、`event_id`、`task_type`、`split` 和 `metadata` 用于追溯、过滤、切分和评测，不拼入 assistant 答案。

## 7. 四类任务投影

### EVENT_ANALYSIS

每个事件至少生成一条样本。用户输入包含事件锚点、预测截止日期前证据、可见行情和分析问题。答案区分事实、行情验证、研究推断、即时/短期/中期影响和失效条件。

### INDUSTRY_IMPACT

每条事件—行业映射生成一条样本。输入包含事件事实、行业暴露、相关证据和可见行情。答案描述传导机制、影响方向、时间窗口、反证和不确定性。

### COMPANY_IMPACT

每条事件—公司映射生成一条样本。输入包含事件、所属行业、公司业务暴露、公司证据、行情和混杂因素。答案不得把行业方向直接等同于公司方向，不得在证据缺失时制造确定性结论。

### EVENT_QA

每个问题生成一条样本。问题必须保留 `event_id`，并按问题中的行业或公司引用选择相关上下文。问答不是独立数据产品，而是统一事件研究记录的训练投影。

## 8. 事件级切分

第一版使用显式 `split_manifest.json`，不依赖每次运行重新随机划分。默认分布为八个事件训练、一个事件验证、一个事件测试。具体事件列表由配置固定并写入清单。

验证器必须确认：

- 每个事件只属于一个 split。
- 同一事件派生的所有任务样本具有相同 split。
- validation 和 test 的事件 ID 不出现在训练样本中。
- hidden/evaluator_only 标签不进入任何 user 输入或 assistant 训练答案。

## 9. 数据构建与错误处理

`loaders.py` 读取 JSON/JSONL，并在错误中报告文件路径、行号和字段。`unified_builder.py` 负责关联和冲突检测。`sft_projector.py` 负责确定性生成 SFT 样本。`validation.py` 在训练前执行发布门禁。

以下情况必须返回非零退出码：

- JSON/JSONL 无法解析。
- `event_id`、`sample_id` 或必要消息角色缺失。
- 稳定 ID 重复且内容冲突。
- 问答引用不存在的行业、公司或证据。
- assistant 内容为空。
- 同一事件跨 split。
- 隐藏标签或预测截止日期后的受限字段进入训练输入。

候选数据中的 `UNKNOWN`、`INCONCLUSIVE`、`NEEDS_HUMAN_REVIEW` 和证据缺口必须原样保留语义，不允许转换为确定性正负方向。

## 10. 训练配置

默认 `sft_qlora_3b.json` 面向 RTX 4060 Laptop 8GB：

- `load_in_4bit=true`
- NF4 量化与双重量化
- `bf16=true`，硬件或运行时不支持时允许配置回退 `fp16`
- `max_seq_length=2048`
- `per_device_train_batch_size=1`
- `gradient_accumulation_steps=16`
- `gradient_checkpointing=true`
- LoRA 仅作用于配置指定的线性投影层
- 默认保存 LoRA adapter，不复制基础模型权重

训练入口启动前执行显存、CUDA、依赖和数据验证检查。配置中的模型 ID 可替换；代码不得把单一模型名称硬编码进数据构建逻辑。

## 11. 评测

训练后评测至少报告：

- 样本生成成功率和格式合规率。
- 事件识别与任务类型覆盖。
- 行业/公司影响方向字段匹配率。
- 证据 ID 引用有效率。
- 即时、短期、中期内容区分合规率。
- 无证据时的不确定性表达合规率。
- 按 `task_type` 和 `event_id` 分组的结果。

文本相似度只能作为辅助指标，不能替代证据、方向、时间窗口和泄漏检查。

## 12. 运行产物与可追溯性

每次训练在 `training/runs/<run-id>/` 创建新目录，不覆盖旧运行。目录保存 adapter、最终训练配置、输入数据 manifest、训练指标和评测指标。`dataset_manifest.json` 固定记录 `unified_events.jsonl`、`sft_dataset.jsonl` 和 `split_manifest.json` 的 SHA-256，以便重现实验。

基础模型由模型缓存管理，不纳入项目版本控制。`runs/` 中的大型权重和缓存默认由 `.gitignore` 排除。

## 13. 测试策略

采用测试驱动实现。测试使用临时的小型事件数据，不修改正式候选包。覆盖范围包括：

- 正常和损坏 JSONL 的读取。
- 宏观、行业、公司、问答按事件正确合并。
- 缺失或错误外键被拒绝。
- 四类任务生成标准三角色 `messages`。
- 同一事件的全部样本进入同一 split。
- 隐藏标签、未来资料和空答案被验证器拒绝。
- 相同输入和配置生成相同 sample ID、顺序和 manifest。

## 14. 实施边界

第一版不包含全量微调、分布式训练、在线推理服务、自动模型下载、DPO/GRPO、UI 训练控制台或模型部署。第一版的完成标准是：在不改变现有候选数据的前提下，能够确定性构建两个核心 JSONL，验证事件关联和防泄漏约束，并提供可在本机 RTX 4060 8GB 上启动的 3B QLoRA SFT 入口。

## 15. 验收标准

- `unified_events.jsonl` 覆盖十个事件，并在每个事件对象内包含相应行业、公司和问答。
- `sft_dataset.jsonl` 中每条记录都符合标准 `messages` 契约。
- 四类任务均有样本且全部保留 `event_id`。
- 同一事件不跨 train、validation、test。
- 所有验证测试通过后训练入口才允许启动。
- 默认配置适配 RTX 4060 Laptop 8GB 的 3B 4-bit QLoRA 基线。
- 每次运行可通过配置、数据哈希和指标文件完整追溯。
