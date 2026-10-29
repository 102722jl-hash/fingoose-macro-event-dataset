---
name: building-auditable-macro-datasets
description: Use when expanding macro events, filling missing evidence or market data, building event-linked industry/company/QA records, updating the approved FinGoose research UI with candidate data, or verifying reproducible macro research datasets.
---

# Building Auditable Macro Datasets

构建可审计、可隔离、可离线复现的宏观事件候选数据。保持来源事实、研究推断、行情验证和因果识别的边界。

## 选择入口

支持扩展新的宏观事件、补足现有事件内容和验证可复现候选数据。

1. 对给定事件和官方种子 URL 执行 `online-acquire`。
2. 对受控时间范围先执行 `discover`，只输出候选清单；未经选择不得继续构建。
3. 对现有统一事件执行 `audit`，只输出缺口代码；不得臆造补充值。

严格研究闭环必须指定：

```powershell
python scripts/macro_dataset_pipeline.py audit --policy strict-claim-closure-v2 `
  --input content_candidates.jsonl --output gap_manifest.jsonl `
  --accepted-output accepted_content.jsonl --quarantine-output quarantine.jsonl
```

运行统一 CLI：

```powershell
python scripts/macro_dataset_pipeline.py --help
```

## 执行工作流

1. 初始化独立 run 目录，冻结请求、profile、基础 dataset/training 配置和基础统一事件。不得覆盖既有 run 或 `training/data`。
2. 在 `discover` 中登记 query、adapter、rank、候选 URL 和官方锚点，去重后停止等待事件选择。
3. 在 `audit` 中扫描事件、证据、行业、公司、QA 和行情缺口，写 `gap_manifest.jsonl`。
4. 在 `online-acquire` 中执行搜索、正文提取、快照、来源分级和双时钟判断。先写 `search_audit.jsonl` 与 `evidence_candidates.jsonl`，通过门禁后才写 `accepted_evidence.jsonl`。
5. 在 `enrich` 中只写候选工作区。生成完整事件、5–10 个行业、默认 3 家事前暴露公司和 4 类事件关联 QA；冻结到 `content_candidates.jsonl`，通过机器门禁后写 `accepted_content.jsonl`。
6. 在 `build` 中只读取冻结的 baseline、accepted evidence/content 和配置，装配事件/行业/公司/事件关联 QA，并运行现有 SFT projector。不得联网、调用模型或重新解释自然语言补丁。
7. 在 `validate` 中检查证据、双时钟、行情、因果、编码、事件关联和字段一致性。只有命令全部返回 0 且报告为 0 errors / 0 warnings 时，标记 `CANDIDATE_SFT_ELIGIBLE`。
8. 接入 UI 前，读取 UI 接入契约；只通过适配层将候选数据写入已确认的页面栏目。先完成单事件接入、截图核对和数据映射验收，确认后才批量接入。
9. 在 `quarantine` 中隔离失败事件并继续处理其他事件。保留稳定原因码、证据 lineage 和失败产物，不以单个事件失败阻塞整个 run。
10. 在 `offline-replay` / `reproduce` 中只读取冻结的 accepted evidence/content、baseline、profile 和配置，分别构建两轮并比较 `candidate_master_data.jsonl`、`candidate_sft_dataset.jsonl`、`split_manifest.json`、`validation_report.json` 的 SHA256。不得重新生成或改写研究文字。

## 严格闭环策略

`strict-claim-closure-v2` 不接受自报 `CLOSED`。每个行业七步节点必须声明 `DIRECT_FACT`、`PREMISE_SUPPORT`、`CALCULATED_LINEAGE` 或 `NEGATIVE_SEARCH_AUDIT`，并保留节点级定位、支持说明和双向引用。每个行业固定三家公司，每家公司至少两份事件日前 T1/T2 官方或法定披露。行业代理和公司行情必须覆盖 T-1、T0、D1、D3、D5、D20，状态为 `CALCULATED`，保留原始值、日期、公式、来源和连续交易核验，并通过重新计算。

四类 QA 必须直接回答并引用真实事件、证据、机制节点、行业或公司 ID。通用模板、占位文本、悬空引用、补零行情、不可回算收益和虚假 `CLOSED` 均进入隔离。批量发布使用重复的 `--required-event-id` 声明完整事件集合；集合不完全时返回 `ATOMIC_BATCH_EVENT_SET_INCOMPLETE`，不生成 UI 发布候选。

## 版本化 UI

旧 UI 先复制为不可变基线版本，并将旧事件标记 `FROZEN_UNDER_PREVIOUS_GATE`，不得宣称通过当前门禁。新版本只复用原 `index.html` 和现有六栏目顺序，只替换版本目录内的 `ui_data_bundle.js`。版本 manifest 必须记录父版本、run ID、逐事件规范化哈希、bundle/build/validation/replay/screenshot SHA、门禁版本与审核状态。

人工确认只允许以临时文件加 `os.replace` 原子提升稳定入口和 `latest_release.json`；不得改变 `NEEDS_HUMAN_REVIEW`、`formal_ready=false` 或 `ABSTAIN`。冻结版本禁止原地修改，任何内容调整都创建新的递增版本。

## 读取 Reference

- 扩展事件、行业、公司或 QA 前，读取 [data-contracts.md](references/data-contracts.md)。
- 搜索、抓取或浏览器回退前，读取 [source-policy.md](references/source-policy.md)。
- 判断事前证据与事后验证时，读取 [temporal-policy.md](references/temporal-policy.md)。
- 合并证据、处理冲突或隔离时，读取 [evidence-gates.md](references/evidence-gates.md)。
- 计算 T0/D1/D3/D5/D20 收益时，读取 [market-formulas.md](references/market-formulas.md)。行业缺失但公司和市场齐全时只能标记 `PARTIAL_CALCULATED`；关键输入不足时标记 `DATA_MISSING`，禁止补零。
- 输出任何因果措辞前，读取 [causal-gates.md](references/causal-gates.md)。非 `IDENTIFIED` 必须 `ABSTAIN`。
- 向 FinGoose 现有 UI 接入或展示数据前，读取 [ui-integration-contract.md](references/ui-integration-contract.md)。

## 停止与隔离

遇到以下任一情况时停止当前事件的晋级并写入 `quarantine.jsonl`：

- 关键来源冲突且无法按原文、定位和时间消解。
- 找不到可复核原文或稳定定位，只有搜索摘要。
- 事件、行业、公司或 QA 映射存在歧义。
- 行情端点、交易状态或基准不可回算。
- 离线模式触发搜索、HTTP、浏览器或研究文字生成入口。

## 永久边界

- 只允许 T1/T2 直接支持 `SOURCE_FACT`。
- 将事前推理与事后验证分开；行情只能验证表现或机制一致性，不能单独证明因果。
- 非 `IDENTIFIED` 一律 `ABSTAIN`。
- 所有候选持续保留 `NEEDS_HUMAN_REVIEW` 和 `formal_ready=false`。
- 不自动安装到个人 Skill 目录，不自动执行真实 GPU 训练，不自动解除人工审核。
- 现有 UI 是唯一展示基线；不得重构、删除或替换现有 UI。新增数据只能通过兼容适配层进入既有栏目。
