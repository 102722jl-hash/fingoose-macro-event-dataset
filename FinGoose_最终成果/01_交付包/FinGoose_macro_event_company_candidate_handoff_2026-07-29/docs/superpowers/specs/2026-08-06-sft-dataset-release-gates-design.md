# FinGoose SFT 数据集发布门禁设计

## 1. 目标与边界

本次完善只负责交付可直接用于监督微调的标准 SFT 数据集，不负责安装 CUDA、下载模型、执行真实训练或验证 LoRA adapter。数据集是否合格与当前 Python/GPU 环境是否可训练分开判断。

最终训练样本继续集中保存在 `training/data/sft_dataset.jsonl`。不额外拆分 train、validation、test 文件，而是使用每条记录的 `split` 字段区分数据分区。

## 2. 核心产物

- `training/data/unified_events.jsonl`：十个宏观事件的统一研究主数据，保存事件、行业、公司和问答的完整关联与来源追溯。
- `training/data/sft_dataset.jsonl`：唯一最终训练样本文件，采用 Hugging Face/TRL 通用 `messages` 格式。
- `training/data/split_manifest.json`：事件级固定分区。
- `training/data/manifest.json`：来源文件和生成产物的 SHA-256 与数量清单。
- `training/data/validation_report.json`：发布门禁结果，并记录本次验证对应的核心产物 SHA-256。

`sft_dataset.jsonl` 必须能够由 `unified_events.jsonl` 和配置确定性重建，不允许分别手工维护两个文件。

## 3. SFT 样本契约

每条训练样本必须包含：

```json
{
  "sample_id": "稳定且唯一的样本编号",
  "event_id": "event-01",
  "task_type": "EVENT_ANALYSIS",
  "split": "train",
  "messages": [
    {"role": "system", "content": "非空系统约束"},
    {"role": "user", "content": "非空研究材料与任务"},
    {"role": "assistant", "content": "非空标准答案"}
  ],
  "metadata": {
    "related_industry_ids": [],
    "related_company_codes": [],
    "evidence_ids": [],
    "source_record_ids": []
  }
}
```

`messages` 必须严格按 `system`、`user`、`assistant` 排列，且 `role` 与 `content` 都必须是字符串。任何空内容、额外角色或角色顺序错误均阻止发布。

## 4. 覆盖与关联门禁

验证器必须确认：

- 统一主数据覆盖 `event-01` 至 `event-10`，无缺失、重复或额外事件。
- SFT 数据覆盖 `EVENT_ANALYSIS`、`INDUSTRY_IMPACT`、`COMPANY_IMPACT`、`EVENT_QA` 四类任务。
- 每个统一事件至少生成一条 SFT 样本。
- 同一事件的全部样本只能属于一个 split。
- 每个 split 值只能是 `train`、`validation` 或 `test`。
- `metadata.related_industry_ids` 必须能在同一事件的行业映射中解析。
- `metadata.related_company_codes` 必须能在同一事件的公司映射中解析。
- `metadata.evidence_ids` 与 `metadata.source_record_ids` 必须是字符串列表；证据 ID 保留用于追溯，不要求全部来源都被压入消息正文。

## 5. 内容与防泄漏门禁

验证器必须递归拒绝包含 `hidden`、`evaluator_only`、`benchmark_labels` 或等价隐藏标签字段/路径的 SFT 样本。

每条样本必须满足：

- 不包含 `[内容已按训练长度上限截断]` 硬截断标记。
- 三段消息总字符数不超过 2000，作为 2048 token 配置下的保守训练预算。
- 问题和任务位于 user 内容前部，不因上下文压缩丢失核心指令。
- assistant 保留来源事实、计算事实、研究推断、即时/短期/中期逻辑及必要的不确定性边界。

本数据集用于宏观事件的回顾性研究训练，不作为严格的时间序列预测基准。因此预测截止时间作为问答来源追溯字段保留，但不对 assistant 中的事后行情验证实施一刀切日期拒绝。隐藏评测标签仍严格禁止进入训练样本。

## 6. 验证报告与哈希绑定

`validate_dataset.py` 每次验证时必须计算并写入：

- `unified_events.jsonl` SHA-256
- `sft_dataset.jsonl` SHA-256
- `split_manifest.json` SHA-256
- 数据集版本、事件数、样本数、任务分布和 split 分布

训练前的数据 readiness 只能在以下条件同时满足时判定为数据就绪：

- `validation_report.json` 的 `valid=true`
- 验证报告中的 SFT SHA-256 等于当前文件 SHA-256
- manifest 中的 SFT SHA-256 等于当前文件 SHA-256

CUDA、显存、训练依赖和模型文件不属于本次数据集发布门禁。

## 7. 测试与验收

新增或扩展测试必须覆盖：

- 缺少任一任务类型时验证失败。
- 某事件没有任何 SFT 样本时验证失败。
- 无效 split、空 system/user/assistant、非字符串消息字段验证失败。
- 行业或公司 metadata 外键无法解析时验证失败。
- 硬截断标记或消息总长度超限时验证失败。
- 隐藏字段或受限路径进入样本时验证失败。
- 验证报告哈希与当前 SFT 不一致时数据 readiness 失败。
- 当前十事件、157 条真实样本通过全部发布门禁。
- 连续两次重建两个核心 JSONL 的 SHA-256 完全一致。

完成标准是：`training/tests` 全部通过，真实数据验证为 0 errors，两个核心数据文件可确定性重建，且 `sft_dataset.jsonl` 可直接作为标准 `messages` SFT 数据源加载。
