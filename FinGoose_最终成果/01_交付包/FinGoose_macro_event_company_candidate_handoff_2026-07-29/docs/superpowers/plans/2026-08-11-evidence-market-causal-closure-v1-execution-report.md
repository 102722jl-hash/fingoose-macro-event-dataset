# FinGoose Evidence, Market, and Causal Closure v1 Execution Report

执行日期：2026-08-11

## 结果

- 统一事件：10 条。
- SFT 样本：157 条，任务分布为 `EVENT_ANALYSIS=10`、`INDUSTRY_IMPACT=77`、`COMPANY_IMPACT=30`、`EVENT_QA=40`。
- 非 QA 推理链：117 条，全部 `CLOSED`，`OPEN=0`。
- 行业行情：77 条均含 `T0/D1/D3/D5/D20` 固定窗口。
- 公司行情：30 家公司均含五个相对收益窗口；117 个窗口为 `CALCULATED`，33 个窗口为 `PARTIAL_CALCULATED`，部分窗口保留行业基准缺口，不填零。
- 因果识别：30 家公司均为 `NOT_IDENTIFIED`、`causal_conclusion=ABSTAIN`、`causal_attribution_allowed=false`。
- 中文乱码扫描：0 个命中。

## 验证

- `python -m pytest training/tests -q`：134 passed。
- `python -m compileall -q training/fingoose_training training/scripts`：通过，无输出。
- `python training/scripts/validate_dataset.py --config training/configs/dataset.json`：0 errors，0 warnings。
- `python training/scripts/train_sft.py --config training/configs/sft_qlora_3b.json --dry-run`：`ready=true`、`model_loaded=false`。

两轮重建 SHA256 一致：

- `unified_events.jsonl`: `3121FB6288E349A8B33A6A03E14A1AF4CD7C77439E73C1662BD6574C8D27A614`
- `sft_dataset.jsonl`: `BDBAAF3277FEE0FDCA0A45F9EEF41A405AB16C3CEE4C4677A98C54A877528810`
- `split_manifest.json`: `72DD3FEF088EB2FF840C2C8B4371D819000203C4D34F21BBB3C4AE7F6DC3D75F`
- `validation_report.json`: `A5256FB6B6D90A6241446463EF00C58A8B9905B9BB4487D5720C0ADC35B2FCD3`

## 边界

- 证据继承不放宽“原文 + 定位 + URL”的完整性门禁。
- 行情只验证机制一致性，不能证明宏观事件与行业或公司收益之间的严格因果关系。
- 数据保留 `NEEDS_HUMAN_REVIEW` 与 `formal_ready=false`；本次未执行人工审核。
- dry-run 不下载模型、不加载模型，也不代表已完成真实 GPU 训练。
