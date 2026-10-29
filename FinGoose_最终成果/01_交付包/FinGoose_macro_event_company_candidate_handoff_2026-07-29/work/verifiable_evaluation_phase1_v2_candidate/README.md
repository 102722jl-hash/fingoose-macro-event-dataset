# FinGoose 第一阶段可验证评测候选包

本目录是隔离生成的 `CANDIDATE` 数据包，不修改现有 UI、生产 v1/v2 数据或以下只读输入：

- `../timeline_fast_candidate_v2/`
- `../transmission_24_anchor_v2_candidate/`
- `../event_industry_impact_v1_candidate/`
- `../company_price_windows_public_vendor_v1_candidate/`

## 当前状态

- 时间线：10 个事件、50 个已验证节点、0 个待补证节点、13 个可晋升里程碑。
- 传导图：24 个锚点、111 条动态绑定；全部为 `NEEDS_HUMAN_REVIEW`，均不作为边级评分真值。
- 行业层：43 条行业影响候选、72 个公司候选提及，其中 33 个具备图谱链路；验证后的公司链路仍为 0。
- 市场层：30 个公司窗口，覆盖 T-20、T-1、T0、D1、D3、D5、D20；绝对收益可复算。
- 评测层：10 个公开案例，其中 event-02/03/04 含示例答案；其余 7 个事件的标签仅进入评测方包。时间线赛道可用，图构造与方向赛道因无人工评分真值标为 `BLOCKED_NO_SCORING_LABELS`。

本包始终保持 `formal_ready=false` 和 `sha_gate=DEFERRED`。已有快照哈希和来源链保留，但暂不将 SHA 作为正式发布门禁。自动审核只允许输出 `AI_REVIEWED`、`REJECTED` 或 `NEEDS_HUMAN_REVIEW`，禁止生成 `CONFIRMED`。

## 发布边界

- 被测方只允许取得 `public/`，其 allowlist 仅包含 `benchmark_cases.jsonl`。
- 评测方标签只允许取得 `evaluator_only/`，其 allowlist 仅包含 `benchmark_labels.jsonl`。
- 不得将整个候选目录交给被测方；根目录包含时间线、绑定、行业和市场派生产物。

## 已知限制

- 111 条传导边只有事件级机制来源，尚无逐边人工确认，因此 `scoring_eligible=false`；门禁会从可信机制来源重算支持状态，不接受绑定自身声明。
- 43 条行业方向均需人工审核，不能用于干净因果归因。
- 30 个公司官方暴露 dossier 仍未关闭，当前只有候选公司窗口。
- 本地只读 MySQL 未发现 A 股个股、宽基指数或申万指数日行情表；宽基和行业相对收益为 `UNAVAILABLE/null`。
- 交易所停复牌数据尚未接入，`suspension_alignment=UNVERIFIED`。
- 公共供应商行情的许可范围仍为 `UNKNOWN`，禁止再分发。
- 来源 manifest 现含 50 份文档和全部证据 excerpts；25 份有 SHA-256，25 份缺 SHA，`source_snapshot_hash_coverage_complete=false`。
- D3 使用带时区的 72 小时 cutoff 和日期上界策略；公开文档仍沿用节点级 `first_public_at`，独立文档发布时间覆盖尚未完成。

## 构建与验证

从项目根目录运行：

```powershell
python work\verifiable_evaluation_phase1_v2_candidate\src\timeline.py --build
python work\verifiable_evaluation_phase1_v2_candidate\src\bindings.py --build
python work\verifiable_evaluation_phase1_v2_candidate\src\market.py --build
python work\verifiable_evaluation_phase1_v2_candidate\src\gates.py --build-all
python -m unittest discover -s work\verifiable_evaluation_phase1_v2_candidate\tests -v
```
