# FinGoose 统一多任务 SFT 训练框架

本模块把现有宏观事件、行业影响、公司影响和事件问答候选包合并为事件中心主数据，再生成标准 Hugging Face/TRL `messages` SFT 样本。现有 `data/` 和 `work/` 目录只读，所有训练数据和运行产物写入 `training/`。

## 核心数据文件

- `data/unified_events.jsonl`：统一研究主数据，每个宏观事件一条记录，内部包含事件、行业、公司和问答。
- `data/sft_dataset.jsonl`：最终训练样本，每行包含 `sample_id`、`event_id`、`task_type`、`split`、`messages` 和 `metadata`。
- `data/split_manifest.json`：固定事件级 train/validation/test 切分。
- `data/manifest.json`：来源与产物 SHA-256、版本和记录数量。
- `data/validation_report.json`：关联、格式、隐藏数据和分区泄漏验证结果。

`sft_dataset.jsonl` 由 `unified_events.jsonl` 自动生成，不应单独手工维护。

当前投影包含四类任务：

- `EVENT_ANALYSIS`：10 条宏观事件分析。
- `INDUSTRY_IMPACT`：77 条事件—行业影响。
- `COMPANY_IMPACT`：30 条事件—公司影响。
- `EVENT_QA`：40 条与十个事件关联的问答。

## 环境

数据构建和验证只依赖 Python 3.12 标准库与 pytest。真实训练需要 NVIDIA CUDA 环境以及 `requirements.txt` 中的 PyTorch、Transformers、Datasets、TRL、PEFT、Accelerate 和 bitsandbytes。

建议在独立环境安装：

```powershell
python -m venv training/.venv
training\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r training/requirements.txt
```

当前本机基线为 RTX 4060 Laptop 8GB、16GB 内存。默认配置使用 Qwen2.5-3B-Instruct、4-bit NF4 QLoRA、长度 2048、batch size 1、梯度累积 16和梯度检查点。`sft_qlora_7b_experimental.json` 不是稳定基线。

## 构建数据

在交接包根目录运行：

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python training/scripts/build_unified_dataset.py --config training/configs/dataset.json
python training/scripts/build_sft_dataset.py --config training/configs/dataset.json
python training/scripts/validate_dataset.py --config training/configs/dataset.json
```

验证失败时第三条命令返回非零退出码。训练入口拒绝使用验证失败或 SHA-256 与 manifest 不一致的数据。

发布验证还会强制检查：

- 十个事件和四类任务完整覆盖，且每个事件至少生成一条样本。
- split 取值有效，同一事件不跨数据分区。
- messages 严格为非空字符串形式的 system/user/assistant。
- 行业和公司 metadata 引用能够在同一事件中解析。
- 不包含隐藏标签、硬截断标记，且消息总字符数不超过 2000。
- validation_report.json 记录的核心产物 SHA-256 与当前文件一致。

## 测试

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests -q
python -m compileall -q training/fingoose_training training/scripts
```

旧项目完整测试还需要额外安装 `reportlab`；这不影响独立运行 `training/tests/`。

## 训练前检查

`--dry-run` 不下载或加载模型，只检查训练配置、核心数据哈希、验证报告、消息角色和数据分区：

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python training/scripts/train_sft.py `
  --config training/configs/sft_qlora_3b.json `
  --dry-run
```

输出中的 `ready=true` 才允许开始真实训练。

这里的 ready=true 表示数据集已通过发布门禁，可以交给标准 SFT 训练器。
它不代表当前 Python 环境已经安装 CUDA 版 PyTorch、bitsandbytes 或其他训练
依赖，也不代表模型已经下载；这些属于实际训练环境准备。

## 真实 QLoRA SFT

真实训练会从 Hugging Face 下载基础模型，并在 `training/runs/<run-id>/` 创建新的运行目录：

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python training/scripts/train_sft.py `
  --config training/configs/sft_qlora_3b.json
```

每次运行保存：

- `adapter_model/`：LoRA adapter 和 tokenizer。
- `training_config.json`：实际训练配置。
- `dataset_manifest.json`：训练使用的数据版本及哈希。
- `train_metrics.json`：训练指标。

基础模型保存在 Hugging Face 缓存中，不复制到本项目。

## 评测

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python training/scripts/evaluate_sft.py `
  --config training/configs/sft_qlora_3b.json `
  --adapter training/runs/<run-id>/adapter_model `
  --output-dir training/runs/<run-id>/evaluation
```

评测输出 `predictions.jsonl` 和 `evaluation_metrics.json`。当前指标用于检查格式、证据 ID、即时/短期/中期词项、不确定性表达以及按事件和任务的样本数量；这些合规指标不等于语义正确率，也不证明严格因果。

## 数据边界

- 同一个 `event_id` 的宏观、行业、公司和问答样本必须位于同一 split。
- `hidden/`、`evaluator_only/` 和隐藏标签不得进入 SFT 样本。
- 公司通过同一事件下的申万一级 `sw1_id` 关联到统一行业映射；旧行业锚点 ID 只保留用于追溯。
- 候选状态、证据缺口和 `NEEDS_HUMAN_REVIEW` 语义不得被转换为确定性结论。
- 每段 user/assistant 文本设有确定性长度上限，任务和问题放在上下文之前，避免 2048 长度训练时截掉核心指令。
