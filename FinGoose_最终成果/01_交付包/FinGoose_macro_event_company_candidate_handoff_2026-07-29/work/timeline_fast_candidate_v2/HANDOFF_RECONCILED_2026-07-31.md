# FinGoose Timeline FAST_CANDIDATE 对账后交接

更新时间：2026-07-31

## 发布边界

- `release_tier=FAST_CANDIDATE`
- `formal_ready=false`
- `production_dataset_modified=false`
- 候选快照 SHA 暂不作为证据接受门禁。
- 生产 v2 三个基线文件仍执行哈希保护，防止误改。

## 当前可调用数据

目录：`work/timeline_fast_candidate_v2/`

- `candidate_source_intake.jsonl`：50 条原始候选来源台账。
- `candidate_source_audit.jsonl`：25 `ACCEPTED`、23 `PENDING`、2 `REJECTED`。
- `candidate_source_manifest.jsonl`：与 audit 一对一镜像的来源路径和状态。
- `timeline_nodes.jsonl`：50 个节点，42 `VERIFIED_EXISTING`、8 `PENDING_EVIDENCE`。
- `timeline_episodes.jsonl`：37 个按 `event_id + phase` 重算的 episode。
- `promotable_milestones.jsonl`：18 条通过当前晋升门禁的里程碑。
- `timeline_gap_report.json`：逐事件、逐节点证据包检查和缺口。
- `validation_report.json`：当前 `hard_failures=[]`。

## 8 个待补节点

- `fast-event-02-M01`：EIA 前置背景事实与 Kremlin 冲突起点候选语义错位。
- `fast-event-05-M01`：来源已定位，但双时间状态仅为 `SOURCE_LOCATED`。
- `fast-event-05-M04`：FINMA 页面时间未证明时区，不能复算当前精确时间。
- `fast-event-06-M01`：来源已定位，但双时间状态仅为 `SOURCE_LOCATED`。
- `fast-event-07-M05`：缺少可用的一手正文快照。
- `fast-event-10-M01`：当前声明时间与页面时间戳冲突。
- `fast-event-10-M04`：有效时间可定位，但首次公开精确时间不能由快照复算。
- `fast-event-10-M05`：签署日和实施条款可定位，但首次公开精确时间不能由快照复算。

## 已恢复的生产节点

以下 5 个节点曾被不可复算的补充候选覆盖，现已恢复为生产 v2 原始事实、时间和来源：

- `fast-event-01-M04`
- `fast-event-02-M03`
- `fast-event-05-M02`
- `fast-event-05-M03`
- `fast-event-10-M02`

## 24 锚点动态传导候选

目录：`work/transmission_24_anchor_v2_candidate/`

- 24 个稳定锚点，覆盖 10 个事件。
- 14 个 `CAUSAL_CANDIDATE`，10 个 `OBSERVATION_ONLY`。
- 111 条动态边绑定，全部为 `PROPOSED`。
- 输入计数：42 verified、8 pending。
- 1 个固定锚点输入状态差异：`fast-event-02-M01`；锚点使用不可变生产里程碑，时间线节点仍保持待补。
- `hard_failures=[]`。

## 可重复执行

```powershell
$env:PYTHONPATH='code'
python code/reconcile_fingoose_timeline_fast_candidate_v2.py --root .
python code/build_fingoose_24_anchor_transmission_graphs.py --root .
```

不要运行旧的临时脚本 `finalize*.py`、`pkg_data.py` 或 `regenerate_reports.py` 覆盖当前结果。

