# Building Auditable Macro Datasets Skill v1 Execution Report

执行日期：2026-08-12

## 交付范围

- 项目内 Skill：`skills/building-auditable-macro-datasets/`
- 统一 CLI：`scripts/macro_dataset_pipeline.py`
- 规范输出与门禁：`scripts/audit_outputs.py`
- 搜索登记与快照：`scripts/source_extractors.py`
- 六份来源、时间、证据、内容、行情和因果 reference
- FinGoose profile、34 条 Skill 测试和 3 个前向场景

未修改个人 Skill 目录，未解除 `NEEDS_HUMAN_REVIEW`，未把候选标记为 `formal_ready=true`。

## 自动验证

| 检查 | 结果 |
| --- | --- |
| Skill tests | `34 passed in 0.20s`（使用工作区本地 fixture 和 `-p no:tmpdir`，规避平台 pytest 临时目录 ACL） |
| FinGoose tests | `134 passed in 14.53s` |
| Skill quick validation | `Skill is valid!` |
| compileall | 退出码 0，无输出 |
| dataset validation | `validation passed: 0 errors, 0 warnings` |
| training dry-run | `ready=true`、`model_loaded=false`、157 条样本 |

## 前向场景

### specified-event

使用冻结输入执行交付面冒烟，不声称发生了新的联网研究。输出目录：

`work/skill_forward_tests/specified-event/`

结果：存在 `candidate_master_data.jsonl`、`candidate_sft_dataset.jsonl`、`search_audit.jsonl` 和 `validation_report.json`；验证报告为 `valid=true`、0 errors、0 warnings。

### controlled-discovery

使用 3 条候选搜索命中（其中 2 条指向相同锚点和官方 URL）执行 `discover`。输出目录：

`work/skill_forward_tests/controlled-discovery/`

结果：稳定去重为 2 条 `discovery_candidates`；未生成 `candidate_master_data.jsonl`，未选择事件没有进入 build。

### offline-replay

最终 run：

`work/skill_research_runs/run-fingoose-final-004/`

结果：两轮 build 返回 `[0]`，两轮 validation/dry-run 返回 `[0, 0]`；`stable=true`、`ready=true`、`network_accessed=false`、`prose_regenerated=false`、`model_loaded=false`。

## 黄金产物 SHA256

| 产物 | SHA256 |
| --- | --- |
| `candidate_master_data.jsonl` | `D90D2E31A61B0CB040F38DAB679D0E001E3A88F06947F35EEB79F5DDBD13E32D` |
| `candidate_sft_dataset.jsonl` | `BDBAAF3277FEE0FDCA0A45F9EEF41A405AB16C3CEE4C4677A98C54A877528810` |
| `split_manifest.json` | `72DD3FEF088EB2FF840C2C8B4371D819000203C4D34F21BBB3C4AE7F6DC3D75F` |
| `validation_report.json` | `E6E4A43D472C953EE93B6C0B7BC2B60F71A8A16C598381BADC2AD4770C9A245C` |
| `reproducibility_report.json` | `C137A2A21B7A73921A81D6930E0538927DEF03FD1AC042BABFECB044C617F016` |

## Skill 源码 SHA256

| 文件 | SHA256 |
| --- | --- |
| `SKILL.md` | `A7AE3ED505943B4192AD3815A3290313BB8FE63077E86E16CC7CC7C5F358F3C4` |
| `agents/openai.yaml` | `202EEA054F4E4AA1166283A0AE30784AA7D24E1E8D919772115C59B34B4E8987` |
| `scripts/audit_outputs.py` | `31CEEF6727D2A368BDBACB0F35C4B34AB5ECAECE2BC16B1E3DF446C4C139C8F2` |
| `scripts/macro_dataset_pipeline.py` | `F6571B0AC80C792AEA784D01AA3177CC3F14D7F5145DA514D1D5A34625798E79` |
| `scripts/source_extractors.py` | `D7DBB288221CBA39027BEEAA3D40EE8FFE36B46CA80EB106F6FDF5162E41FA63` |
| `assets/profiles/fingoose.json` | `967A84C2502E0BA342F6381D3839F7DC7F0B3D7EF3BC6982AFBF0E239AA0E3DF` |

## 失败留痕与修复

- `run-fingoose-golden-001`：子进程缺少 `training/` 的 `PYTHONPATH`，SFT 投影未产出。修复为显式传递确定性 Python 路径，并在 build 非零时带 stderr 立即失败。
- `run-fingoose-golden-002`：前三个产物 SHA 一致，验证报告因嵌入 replay 绝对路径而不同。修复为在 SHA 比较前把 `validated_artifacts.*.path` 规范为 run-local 文件名。
- `run-fingoose-golden-003`：四个 SHA 首次全部一致。
- `run-fingoose-final-004`：补充可审计的 `ready=true` 后完成最终验证。

## 永久边界

- 尚未执行人工审核；所有候选继续为 `NEEDS_HUMAN_REVIEW`、`formal_ready=false`。
- 尚未安装到 `C:\Users\LL\.codex\skills`；只有用户明确授权后才安装。
- 尚未执行真实 GPU/QLoRA 训练；只完成 `--dry-run`，并确认 `model_loaded=false`。
- 行情只验证窗口表现和机制一致性，不作为宏观事件因果证明；非 `IDENTIFIED` 继续 `ABSTAIN`。
