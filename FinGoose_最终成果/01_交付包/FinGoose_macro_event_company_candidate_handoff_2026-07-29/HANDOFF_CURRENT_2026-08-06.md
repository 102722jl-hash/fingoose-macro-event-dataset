# FinGoose 当前任务交接

更新时间：2026-08-06

项目根目录：

`D:\桌面\workspace\codex1\handoff\FinGoose_macro_event_company_candidate_handoff_2026-07-29`

新任务界面接手时，应先阅读本文件，再根据具体目标读取 `training/README.md`、相关候选包 HANDOFF 和设计文档。旧的 `README_HANDOFF.md` 是 2026-07-29 的初始交接记录，本文件描述当前最新状态。

## 1. 用户的核心任务目标

构建和完善 FinGoose 宏观事件研究数据，使十个宏观事件能够沿以下主线统一呈现和训练：

```text
宏观事件 -> 时间线与传导机制 -> 行业影响 -> 公司影响 -> 事件研究问答
```

问答的作用是补足宏观事件内容、证据查询、行情验证和行业—公司分析，不是脱离十个事件的独立问答任务。

最终需要同时具备：

- 可在 UI 中查看的宏观事件研究工作台。
- 十个事件关联的宏观、行业、公司和问答主数据。
- 一个标准 `messages` 格式的统一多任务 SFT 数据集。
- 可重复构建、可验证、可追溯的数据发布流程。

## 2. 用户已经明确的需求

### 2.1 内容组织

- 所有宏观、行业、公司和问答内容必须通过 `event_id` 关联十个事件。
- 问答并入原有 UI 和事件研究内容，不单独建设问答产品。
- UI 应保留原有事件、时间线、传导链、行业和公司内容，研究问答作为其中一个完整研究区段。
- 来源事实、计算事实和研究推断需要明确区分。
- 即时、短期和中期必须表达具体变化，不能三段内容完全相同。
- 证据查询必须回答证据是什么、支持什么结论以及证据边界。
- 行情验证必须回答窗口内实际变化、相对表现、可辨识性和混杂因素。
- 行业—公司问题必须区分行业影响和公司自身暴露，不能把行业方向直接等同于公司方向。
- 页面与训练文本以中文为主；来源原文可保留，但界面标签和研究解释应中文化。

### 2.2 SFT 数据

- 训练类型是基础监督微调 SFT，不是 DPO、GRPO 或强化学习。
- 使用 Hugging Face/TRL 通用 `messages` 格式。
- 四类任务统一存放在同一个 `sft_dataset.jsonl`：
  - `EVENT_ANALYSIS`
  - `INDUSTRY_IMPACT`
  - `COMPANY_IMPACT`
  - `EVENT_QA`
- 不额外拆分三个训练文件；通过每条样本的 `split` 字段区分 train、validation、test。
- 同一事件派生的所有任务样本必须位于同一 split，防止事件级数据泄漏。
- 最终训练文件必须可直接加载，且所有消息为非空 `system/user/assistant`。
- 当前目标只要求数据集可用于训练，不要求在本任务中下载模型或执行真实 GPU 训练。

## 3. 当前 UI 状态

主 UI 文件：

`work/company_impact_high_quality_v2_candidate/ui/index.html`

该文件是在原有公司影响 UI 基础上扩展的单页工作台，当前研究区段顺序为：

1. 事件概览
2. 研究问答
3. 事件时间线
4. 动态传导链
5. 行业影响
6. 公司影响

研究问答已经包含或预留以下呈现：

- 四类问答标签和问题切换。
- 直接回答。
- 来源事实和原始来源展开。
- 机制链。
- 即时、短期、中期推断。
- 行业影响与行业阶段变化。
- 行情验证与窗口细节。
- 公司层结论、混杂因素、反证和边界。

局域网查看方式：

```powershell
python -m http.server 8000 --bind 0.0.0.0 `
  --directory work/company_impact_high_quality_v2_candidate/ui
```

本机可访问 `http://localhost:8000/`；局域网地址需要使用当前电脑实际 IPv4，例如先前使用过 `http://192.168.1.227:8000/#qa`。IP 可能随网络变化。

## 4. 当前数据来源

### 4.1 宏观事件

目录：`data/market_event_attribution_v2_candidate/`

主要文件：

- `event_episodes.jsonl`
- `event_milestones.jsonl`
- `transmission_graphs.jsonl`
- `market_windows.jsonl`
- `source_manifest.jsonl`

### 4.2 行业影响

目录：`work/industry_impact_high_quality_v2_candidate/`

主要文件：

- `event_industry_mappings.jsonl`
- `industry_mechanism_chains.jsonl`
- `industry_market_windows.jsonl`
- `industry_evidence.jsonl`

### 4.3 公司影响

目录：`work/company_impact_high_quality_v2_candidate/`

主要文件包括事件—公司映射、公司机制链、方向判断、公司证据、行情窗口、混杂因素、反证审查和交易状态审查。

### 4.4 事件研究问答

目录：`work/qa_reasoning_pilot_v2_candidate/`

主要文件：

- `qa_cases.jsonl`
- `qa_answer_candidates.jsonl`
- `source_fetches.jsonl`
- `HANDOFF.md`

## 5. 已完成的统一训练框架

训练框架位于 `training/`，已包含：

- 数据配置和 3B/7B QLoRA 配置。
- 严格 JSON/JSONL 加载器。
- 事件级 split 管理。
- 十事件统一主数据构建器。
- 四任务标准 SFT 投影器。
- 数据发布验证器。
- 构建、验证、训练 dry-run 和评估入口。
- 数据 manifest、split manifest 和验证报告。
- 46 项独立测试。

详细说明见：`training/README.md`。

## 6. 两个核心数据文件

### 6.1 统一事件主数据

`training/data/unified_events.jsonl`

- 记录数：10
- 每行一个宏观事件。
- 每个事件内部关联事件资料、行业、公司和问答。
- SHA-256：`7d8a73a38e0006812e6be927081a6b85280909bac6dbf6c4f4a1fd59445a886c`

### 6.2 最终 SFT 训练样本

`training/data/sft_dataset.jsonl`

- 总样本数：157
- 标准字段：`sample_id`、`event_id`、`task_type`、`split`、`messages`、`metadata`
- SHA-256：`c7c143319662d18d9a61b82409d5b002c5777cdb566ba00cee957b371c3b369b`

任务分布：

| 任务类型 | 数量 |
| --- | ---: |
| `EVENT_ANALYSIS` | 10 |
| `INDUSTRY_IMPACT` | 77 |
| `COMPANY_IMPACT` | 30 |
| `EVENT_QA` | 40 |

数据分区：

| split | 数量 | 事件 |
| --- | ---: | --- |
| train | 124 | event-01 至 event-08 |
| validation | 16 | event-09 |
| test | 17 | event-10 |

## 7. 已完成的数据发布门禁

验证器当前会拒绝：

- 十事件缺失、重复或出现未配置事件。
- 四类任务缺失。
- 某个事件没有任何 SFT 样本。
- 无效 split 或同一事件跨 split。
- 非标准消息角色、空消息或非字符串消息。
- 行业和公司 metadata 外键无法在同一事件解析。
- metadata 追溯字段不是字符串列表。
- 隐藏标签、`hidden`、`evaluator_only` 或 `benchmark_labels` 内容。
- `[内容已按训练长度上限截断]` 硬截断标记。
- 三段消息总字符数超过 2000。
- 重复样本 ID、空 assistant 或未知事件引用。

`training/data/validation_report.json` 已与以下三个文件的 SHA-256 绑定：

- `unified_events.jsonl`
- `sft_dataset.jsonl`
- `split_manifest.json`

旧验证报告不能放行已经变化的 SFT 文件。

## 8. 最新验收结果

最近一次完整验证：

- `training/tests`：46 passed
- Python 编译检查：通过
- 数据验证：0 errors、0 warnings
- 统一事件：10
- SFT 样本：157
- 当前数据无空消息、无硬截断标记
- 当前行业和公司 metadata 外键错误：0
- 最大单样本消息总字符数不超过 2000
- 连续两次重建两个核心 JSONL，SHA-256 完全一致
- `train_sft.py --dry-run`：`ready=true`

这里的 `ready=true` 只表示数据集通过发布门禁，不代表本机 CUDA、训练依赖或模型已经准备完成。

## 9. 重建与验证命令

在项目根目录执行：

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
$env:PYTHONUTF8='1'

python training/scripts/build_unified_dataset.py `
  --config training/configs/dataset.json

python training/scripts/build_sft_dataset.py `
  --config training/configs/dataset.json

python training/scripts/validate_dataset.py `
  --config training/configs/dataset.json

python -m pytest training/tests -q

python -m compileall -q `
  training/fingoose_training training/scripts

python training/scripts/train_sft.py `
  --config training/configs/sft_qlora_3b.json `
  --dry-run
```

预期关键输出：

```text
wrote 10 unified events
wrote 157 SFT samples
validation passed: 0 errors, 0 warnings
46 passed
ready: true
```

## 10. 当前边界与未执行内容

- 尚未下载 `Qwen/Qwen2.5-3B-Instruct`。
- 尚未执行真实 QLoRA GPU 训练。
- `training/runs/` 尚无 adapter、真实训练指标或生成式评估结果。
- 当前 Python 环境是否具备 CUDA 训练能力，不属于数据集合格判断。
- 规则型评测只检查格式、证据引用、时间段词项和不确定性表达，不代表语义正确率。
- 项目目录当前不是有效 Git 仓库，不能依赖 Git commit、branch 或 worktree 追踪本轮改动。
- 旧项目完整测试可能需要额外安装 `reportlab`；独立的 `training/tests` 不受影响。

## 11. 新任务界面接手原则

1. 不要把 `EVENT_QA` 拆成脱离十个事件的独立数据任务。
2. 不要手工分别修改两个核心 JSONL；应修改来源或投影逻辑后重新构建。
3. 不要让同一 `event_id` 跨 train、validation、test。
4. 不要把隐藏评测标签或 evaluator-only 数据加入训练消息。
5. 不要将候选、未知、证据不足或待人工复核状态改写为确定结论。
6. UI 修改必须基于现有 `work/company_impact_high_quality_v2_candidate/ui/index.html`，保留原有事件、时间线、行业和公司内容。
7. 每次修改训练数据后，必须按“统一构建 -> SFT 构建 -> 验证 -> 测试 -> dry-run”的顺序验收。

## 12. 建议的下一步

如果新任务继续完善数据质量，建议按以下顺序：

1. 对 157 条 SFT 样本进行人工抽样，重点检查证据查询、行情验证和行业—公司问答是否精确回答问题。
2. 检查每个事件的即时、短期、中期是否真正表达不同阶段，而不是仅改变方向标签。
3. 对来源事实中的英文原文补充中文摘要，但保留原始出处和证据 ID。
4. 在不破坏 2000 字符门禁的前提下，改善信息密度和回答完整性。
5. 数据质量确认后，再在独立 CUDA 环境中安装训练依赖并执行 3B 4-bit QLoRA。

## 13. 相关设计与实施记录

- `docs/superpowers/specs/2026-08-06-unified-multitask-sft-training-design.md`
- `docs/superpowers/plans/2026-08-06-unified-multitask-sft-training.md`
- `docs/superpowers/specs/2026-08-06-sft-dataset-release-gates-design.md`
- `docs/superpowers/plans/2026-08-06-sft-dataset-release-gates.md`

本文件就是当前阶段交接入口。新任务界面只需读取本文件，即可了解用户目标、已完成内容、可用产物、验证证据和继续工作的边界。
