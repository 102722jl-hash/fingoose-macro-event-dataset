# FinGoose 问答中文化与三阶段具体化交接

## 本轮定位

问答继续作为十个宏观事件的补充研究层，不是独立问答应用。页面顺序保持：

`事件概览 → 研究问答 → 事件时间线 → 动态传导链 → 行业影响 → 公司影响`

候选状态保持：

`PROPOSED / NEEDS_HUMAN_REVIEW / formal_ready=false / sha_gate=DEFERRED`

## 内容增强

- 46 条去重官方证据新增中文机构名、中文事实释义与中文定位说明。
- 原语言引文、原始发布机构、原始定位、首次公开时间、URL 和 SHA-256 全部保留在“审计原文”折叠区。
- 77 个行业映射分别新增即时、短期、中期三段具体说明，共 231 个事件—行业—阶段结论。
- 每段说明均列出方向、可观察驱动、经营变量、财务变量、成立条件与失效条件。
- 研究推断中的方向、影响层级、七步机制节点和拒答原因均改为中文显示。
- 每个阶段总览列出正向、负向、分化与未知的行业数量及代表行业。
- `event-07` 的截止日后红海锚点仍保持未知与暂不判断，不因中文化而补造结论。

## 新增实现

- `configs/qa_reasoning_v2/qa_evidence_localization_zh.json`
- `code/fingoose_qa_reasoning_v2_impl_002.py`
- `code/fingoose_company_impact_qa_ui_v2_impl_004.py`
- `tests/test_fingoose_qa_chinese_detail_v2.py`
- `tests/verify_qa_chinese_detail_v2.mjs`
- `tests/verify_qa_chinese_detail_all_v2.mjs`

## 正确重建命令

```powershell
python code\build_fingoose_qa_reasoning_v2.py --root . --output work\qa_reasoning_pilot_v2_candidate

python code\fingoose_company_impact_qa_ui_v2.py --root . --candidate work\company_impact_high_quality_v2_candidate --industry work\industry_impact_high_quality_v2_candidate --qa work\qa_reasoning_pilot_v2_candidate --output work\company_impact_high_quality_v2_candidate\ui
```

第二条命令不要传单一 `--industry-overlay`。省略该参数时，底层构建器会自动合并 event-01 与 event-02～10 两套行业覆盖包；传入单一路径会有意限制覆盖范围。

## 验证

- Python 专项与原 UI 回归：`44 passed`
- 中文细节 Chrome 验收：十事件、`1440x1000` 与 `390x844` 通过
- 原问答、event-01 行业、十事件行业 Chrome 回归通过
- 77 个行业行情窗口全部为可用状态
- 10 事件、40 问题、40 答案、40 隐藏标签、30 公司、50 时间线节点、111 条传导边保持不变

本轮未创建 Git 提交，不得描述为正式发布。
