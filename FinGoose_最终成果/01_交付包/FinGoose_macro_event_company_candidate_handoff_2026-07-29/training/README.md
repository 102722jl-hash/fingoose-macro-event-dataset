# FinGoose 统一多任务 SFT 训练框架

本模块把宏观事件、行业影响、公司影响和事件问答候选包合并为事件中心主数据，再生成标准 Hugging Face/TRL `messages` SFT 样本。历史说明保留在 `README_legacy_v1.md`。

## 数据与任务

- `data/unified_events.jsonl`：10 个事件的统一主数据。
- `data/sft_dataset.jsonl`：157 条最终训练样本。
- `data/split_manifest.json`：事件级 train/validation/test 切分。
- `data/manifest.json`：来源和产物 SHA-256。
- `data/validation_report.json`：格式、链路、隐藏数据和分区泄漏验证结果。

四类任务数量固定为：`EVENT_ANALYSIS=10`、`INDUSTRY_IMPACT=77`、`COMPANY_IMPACT=30`、`EVENT_QA=40`。`sft_dataset.jsonl` 由统一主数据生成，不应手工维护。

## 规范推理链 metadata v1

统一主数据中的事件、行业、公司和问答对象均包含 `reasoning_chain`。SFT 样本保留原有扁平 metadata 字段，并增加：

- `reasoning_chain_version`：当前为 `v1`。
- `evidence_registry`：证据原文、定位、来源 URL、SHA、发布时间和反向节点索引；缺证 ID 保留并标记 `missing=true`。
- `reasoning_chain`：规范节点、边、根节点、主路径、侧分支、最终节点和闭环门禁。
- `conclusion_lineage`：最终节点、主路径和主路径证据 ID。
- `parent_chain_refs`：公司或问答链引用的上游事件/行业链 ID。

节点状态包括：

- `VERIFIED_SOURCE`：原文、定位和来源可以核对。
- `EVIDENCE_MISSING`：来源事实登记了证据缺口。
- `SUPPORTED_INFERENCE`：所有关键前提均未阻断。
- `INFERENCE_ONLY`：无直接前提或关键前提存在缺证。
- `CALCULATED_ONLY`：公式或行情计算，只能用于验证。
- `CUTOFF_BLOCKED`：公开时间晚于预测截止时间。

状态传播会递归检查前提节点。截止日阻断节点不得进入主路径，隐藏验证节点不得进入训练主数据。缺证记录不生成伪造原文或 URL。

`messages` 与 metadata 分工明确：

- `messages` 只保留可训练的精简主路径、关键证据 ID 和证据边界。
- metadata 保存完整节点、边、证据登记和结论血缘，用于单条样本独立审计。
- 三条消息总字符数不得超过 2000，不复制完整长原文。

## 构建与验证

在交接包根目录运行：

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
$env:PYTHONUTF8='1'
python training/scripts/build_unified_dataset.py --config training/configs/dataset.json
python training/scripts/build_sft_dataset.py --config training/configs/dataset.json
python training/scripts/validate_dataset.py --config training/configs/dataset.json
```

## 证据、行情与因果口径

- 事件证据可以被行业和公司链继承，但不会放宽“原文 + 定位 + URL”的完整性门禁；稀疏引用只保留 evidence ID、来源文档 lineage 和支持节点。
- 行业行情使用 `T0/D1/D3/D5/D20` 固定窗口，同时展示行业收益、沪深300收益和行业相对沪深300收益。
- 公司相对收益按公司实际交易日期连接基准，并统一使用该公司的 `T_MINUS_1` 作为基期；缺少行业基准时保留 `PARTIAL_CALCULATED` 和原因码，不写成零。
- `NOT_IDENTIFIED`、`DESCRIPTIVE_EVENT_STUDY`、`QUASI_EXPERIMENTAL_CANDIDATE` 均要求 `causal_attribution_allowed=false`、`causal_conclusion=ABSTAIN`。行情只验证机制一致性，不能单独证明宏观事件造成公司或行业收益。
- 数据仍保留 `NEEDS_HUMAN_REVIEW` 与 `formal_ready=false`。当前流程未执行人工审核，也未执行真实 GPU 训练；`--dry-run` 仅验证配置和数据是否可被训练入口读取。

验证器同时检查：

- 10 个事件、157 条样本和四类任务完整覆盖。
- 同一事件不跨 split。
- messages 角色、内容和总字符数合法。
- 行业和公司外键可在同一事件内解析。
- 不包含隐藏评测字段或硬截断标记。
- 推理链节点唯一、边引用有效、无环、最终节点可达。
- 节点与 evidence registry 双向索引一致。
- 行业链保持七步，公司链包含业务暴露节点。
- 行情节点不成为经营事实的唯一直接前提。
- 截止日阻断节点不进入主路径。

## 测试

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests -q
python -m compileall -q training/fingoose_training training/scripts
```

## 训练前 dry-run

`--dry-run` 不下载模型、不执行 GPU 训练，只核对配置、数据哈希、验证报告、消息角色和 split：

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python training/scripts/train_sft.py `
  --config training/configs/sft_qlora_3b.json `
  --dry-run
```

只有输出 `ready=true` 才表示数据与配置可交给训练器；这不代表已经完成人工审核、模型下载或真实训练。

## 真实训练与评测

真实训练需要 NVIDIA CUDA 环境以及 `requirements.txt` 中的 PyTorch、Transformers、Datasets、TRL、PEFT、Accelerate 和 bitsandbytes。默认稳定配置为 Qwen2.5-3B-Instruct 4-bit NF4 QLoRA；`sft_qlora_7b_experimental.json` 不是稳定基线。

```powershell
python training/scripts/train_sft.py --config training/configs/sft_qlora_3b.json
python training/scripts/evaluate_sft.py `
  --config training/configs/sft_qlora_3b.json `
  --adapter training/runs/<run-id>/adapter_model `
  --output-dir training/runs/<run-id>/evaluation
```

候选状态、证据缺口和 `NEEDS_HUMAN_REVIEW` 不得被转换为确定性结论。合规指标不等于语义正确率，也不证明严格因果。

## research-content-v1 内容对齐

本版本增加受控 UI reference：`work/company_impact_high_quality_v2_candidate/ui/ui_data_bundle.js`。该文件只作为严格 JSON wrapper 解析的结构化参考，不执行 JavaScript，也不把展示 HTML 当作事实来源。

内容契约覆盖：来源事实、宏观机制、行业/公司作用域、即时/短期/中期阶段、行情验证、问答分层、证据登记和审核边界。`messages` 使用中文任务答案，metadata 保存完整 `research_content` 与 reasoning-chain；候选、待人工审核、证据缺失和不允许确定性归因均保持原状态。

内容门禁检查三层一致性：UI reference、统一主数据/metadata、assistant 引用必须共享事件、作用域和 evidence ID；答案不得包含占位语、截断 JSON 或 Python 对象碎片；行情只作验证，不补齐缺失证据。

标准重建命令仍为：

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
$env:PYTHONUTF8='1'
python training/scripts/build_unified_dataset.py --config training/configs/dataset.json
python training/scripts/build_sft_dataset.py --config training/configs/dataset.json
python training/scripts/validate_dataset.py --config training/configs/dataset.json
```
