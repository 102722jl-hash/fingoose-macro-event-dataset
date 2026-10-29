# Unified Reasoning Chain Metadata v1 执行报告

执行日期：2026-08-07

## 结果

- 统一事件：10
- SFT 样本：157
- 任务分布：EVENT_ANALYSIS 10、INDUSTRY_IMPACT 77、COMPANY_IMPACT 30、EVENT_QA 40
- split 分布：train 124、validation 16、test 17
- 规范链：157
- 节点：1317
- 主路径节点：1039
- 证据登记：714
- 缺证节点：112
- 开放闭环：102
- 验证：0 errors、0 warnings
- dry-run：ready=true；未加载模型，未执行 GPU 训练

## 验证命令

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests -q
python -m compileall -q training/fingoose_training training/scripts
python training/scripts/validate_dataset.py --config training/configs/dataset.json
python training/scripts/train_sft.py --config training/configs/sft_qlora_3b.json --dry-run
```

最终输出：`69 passed`、`compileall passed`、`validation passed: 0 errors, 0 warnings`、`ready=true`。

## 确定性 SHA-256

连续两次完整重建结果一致：

- `training/data/unified_events.jsonl`：`d10e56104a15dcc80f8d8aa32864d61bb3c67aea598c5b8461e8f5750de36c9f`
- `training/data/sft_dataset.jsonl`：`e738133df977b2f4d049fac83a01dcb0f64836e3450dda2b198ce0bcf5b4cd68`
- `training/data/split_manifest.json`：`72dd3fef088eb2ff840c2c8b4371d819000203c4d34f21bbb3c4ae7f6dc3d75f`
- `training/data/validation_report.json`：`df03af393d1bab410aafe08ceac3139a8908d02ea37c9ea6cea410251022e155`

## 边界

项目目录不是有效 Git 仓库，因此未创建提交、分支或 PR。`ready=true` 仅表示数据与训练配置可用，不表示已完成人工审核或真实模型训练。
