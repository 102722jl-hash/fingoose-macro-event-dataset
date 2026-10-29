# Ten-Event Timeline FAST_CANDIDATE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在120分钟内，将十个事件整理为约40至50个结构化任务节点，形成可继续补证的 `FAST_CANDIDATE`，不覆盖当前 v2 候选数据。

**Architecture:** 读取现有 v2 的21个里程碑与 `configs/fingoose_macro_events_v1.json` 中已归档来源，在独立工作目录生成“已验证节点 + 待补证节点”工作簿。只有来源、时间和可见性完整的记录进入可晋升清单；其他记录作为研究任务保留，不伪装成生产 `event_milestones.jsonl`。

**Tech Stack:** UTF-8 JSONL/JSON、现有 Python v2 构建器与校验函数、PowerShell、本地证据快照。

---

## 时间盒与停止条件

严格按120分钟停止：

| 时间 | 任务 |
| --- | --- |
| 0-10分钟 | 冻结基线与建立独立输出目录 |
| 10-20分钟 | 建立任务节点工作簿契约 |
| 20-40分钟 | 整理 event-01 至 event-03 |
| 40-60分钟 | 整理 event-04 至 event-06 |
| 60-85分钟 | 整理 event-07 至 event-10 |
| 85-100分钟 | 统一排序、阶段、锚点和节点作用 |
| 100-115分钟 | 校验、分流可晋升节点与证据缺口 |
| 115-120分钟 | 输出摘要并停止 |

停止时允许节点不足50个，但不允许为达到数量伪造事实、来源、精确时间或共识值。

## 文件边界

**只读输入：**

- `data/market_event_attribution_v2_candidate/event_milestones.jsonl`
- `data/market_event_attribution_v2_candidate/event_episodes.jsonl`
- `data/market_event_attribution_v2_candidate/source_manifest.jsonl`
- `data/market_event_attribution_v2_candidate/manifest.json`
- `configs/fingoose_macro_events_v1.json`
- `evidence_snapshots/macro_event_attribution_v1/`
- `schemas/fingoose_macro_event_milestone_v2.schema.json`
- `schemas/fingoose_macro_event_episode_v2.schema.json`

**创建：**

- `work/timeline_fast_candidate_v2/timeline_nodes.jsonl`
- `work/timeline_fast_candidate_v2/timeline_episodes.jsonl`
- `work/timeline_fast_candidate_v2/promotable_milestones.jsonl`
- `work/timeline_fast_candidate_v2/timeline_gap_report.json`
- `work/timeline_fast_candidate_v2/validation_report.json`
- `work/timeline_fast_candidate_v2/README.md`

**禁止修改：**

- `data/market_event_attribution_v2_candidate/`
- `data/market_event_attribution_v1/`
- `transmission_graphs.jsonl`
- `market_windows.jsonl`
- 公司候选数据、KPI、个股行情、Neo4j/PostgreSQL、Dashboard

## 工作簿记录契约

`timeline_nodes.jsonl` 每行字段固定为：

```json
{
  "fast_node_id": "fast-event-01-M01",
  "event_id": "event-01",
  "sequence": 1,
  "occurred_at": null,
  "first_public_at": "2020-03-11T16:26:00+00:00",
  "phase": "INITIAL_SHOCK",
  "fact": "只写来源能够支持的事实摘要",
  "source_ids": ["existing-source-id"],
  "evidence_status": "VERIFIED_EXISTING",
  "visibility": "PUBLIC_PREDICTION",
  "anchor_role": "PRIMARY",
  "node_action": "STARTS",
  "impact_tags": ["RISK_PREMIUM"],
  "status": "PROPOSED",
  "promotion_eligible": false,
  "gap_reason": "事件发生时刻尚无现有快照证明"
}
```

约束：

- `phase` 只能是 `PRECONDITION / INITIAL_SHOCK / ESCALATION / POLICY_RESPONSE / EASING / SECONDARY_SHOCK`。
- `node_action` 只能是 `STARTS / AMPLIFIES / WEAKENS / REVERSES / TERMINATES / OBSERVES`。
- `evidence_status` 只能是 `VERIFIED_EXISTING / PENDING_EVIDENCE`。
- `visibility` 只能是 `PUBLIC_PREDICTION / HIDDEN_VALIDATION / UNRESOLVED`。
- `status` 固定为 `PROPOSED`。
- 不确定的时间为 `null`，不能用发布日期冒充发生时间。
- `PENDING_EVIDENCE` 记录的 `source_ids` 为空，`promotion_eligible=false`，并填写具体 `gap_reason`。
- 只有能转换为当前 milestone Schema 的记录才能写入 `promotable_milestones.jsonl`。

### Task 1: 冻结当前基线（0-10分钟）

**Files:**
- Read: `data/market_event_attribution_v2_candidate/manifest.json`
- Create: `work/timeline_fast_candidate_v2/README.md`

- [ ] **Step 1: 记录当前计数与哈希**

运行：

```powershell
Get-FileHash -Algorithm SHA256 `
  data/market_event_attribution_v2_candidate/event_milestones.jsonl, `
  data/market_event_attribution_v2_candidate/event_episodes.jsonl, `
  data/market_event_attribution_v2_candidate/manifest.json
```

预期：三个文件均返回64位 SHA-256。

- [ ] **Step 2: 建立独立工作目录**

```powershell
New-Item -ItemType Directory -Force work/timeline_fast_candidate_v2
```

预期：目录存在，当前 v2 数据目录无变化。

- [ ] **Step 3: 在 README 写明边界**

`README.md` 必须明确写入：

```text
release_tier=FAST_CANDIDATE
formal_ready=false
production_dataset_modified=false
scope=timeline_nodes_only
company_analysis=OUT_OF_SCOPE
market_recalculation=OUT_OF_SCOPE
```

### Task 2: 建立十事件节点矩阵（10-20分钟）

**Files:**
- Read: `data/market_event_attribution_v2_candidate/event_milestones.jsonl`
- Read: `configs/fingoose_macro_events_v1.json`
- Create: `work/timeline_fast_candidate_v2/timeline_nodes.jsonl`

- [ ] **Step 1: 复制现有21个里程碑的事实内容到工作簿结构**

每条现有里程碑对应一条工作簿记录。保留双时间、阶段、来源、可见性和锚点；`evidence_status=VERIFIED_EXISTING`，`status=PROPOSED`。

- [ ] **Step 2: 为十个事件建立目标槽位**

每个事件最多使用以下六种槽位：

```text
PRECONDITION
INITIAL_SHOCK
ESCALATION
POLICY_RESPONSE
EASING
SECONDARY_SHOCK
```

没有现有证据的槽位不强行填充。每个事件目标4至5个节点，最低2个已验证节点加若干待补证任务。

- [ ] **Step 3: 检查事件覆盖**

运行：

```powershell
$rows = Get-Content work/timeline_fast_candidate_v2/timeline_nodes.jsonl |
  ForEach-Object { $_ | ConvertFrom-Json }
$rows | Group-Object event_id | Sort-Object Name |
  Select-Object Name, Count
```

预期：显示 `event-01` 至 `event-10`，不得缺失事件。

### Task 3: 整理 event-01 至 event-03（20-40分钟）

**Files:**
- Modify: `work/timeline_fast_candidate_v2/timeline_nodes.jsonl`

- [ ] **Step 1: event-01**

从已有来源中区分疫情扩散背景、WHO公开定性、后续政策/市场反应。无法证明精确发生时刻的记录将 `occurred_at=null`。不把后续病例或市场结果写成预测时可见事实。

- [ ] **Step 2: event-02**

保留低库存与地缘紧张背景、NATO确认大规模进攻、NATO防御响应等已有节点。未经快照证明的具体开战时刻不得新增为已验证事实。

- [ ] **Step 3: event-03**

区分加息前通胀背景、FOMC决定和会后补充材料。6月17日材料保持 `HIDDEN_VALIDATION`；共识缺失继续为 `UNKNOWN`。

- [ ] **Step 4: 检查三事件排序**

对非空 `occurred_at` 按时间升序；同一时间按 `sequence`。`first_public_at` 不得晚于预测可见截止日后仍标记为公开。

### Task 4: 整理 event-04 至 event-06（40-60分钟）

**Files:**
- Modify: `work/timeline_fast_candidate_v2/timeline_nodes.jsonl`

- [ ] **Step 1: event-04**

区分防控优化背景、十条措施发布、次日官方简报。配置中的精确时刻继续注明 provisional，不升级为已确认发生时刻。

- [ ] **Step 2: event-05**

区分银行压力背景、硅谷银行关闭、监管稳定措施。不要把后续市场恢复当作初始冲击事实。

- [ ] **Step 3: event-06**

区分油市背景、额外自愿减产公告和后续执行/政策节点。没有现有执行证据时只建立 `PENDING_EVIDENCE` 任务。

### Task 5: 整理 event-07 至 event-10（60-85分钟）

**Files:**
- Modify: `work/timeline_fast_candidate_v2/timeline_nodes.jsonl`

- [ ] **Step 1: event-07**

区分10月7日首次冲击、冲突升级、航运或政策响应。红海航运后续节点必须保持独立时间和来源，不能与首次冲击合并。

- [ ] **Step 2: event-08**

区分负利率政策背景、日本银行决定和会后政策指引。作为预定发布事件，只有已有可靠共识来源时才填写共识。

- [ ] **Step 3: event-09**

区分政策前背景、组合政策首次公告和细则/执行节点。不同部门同日公告若日频无法区分，标记 `UNRESOLVED`。

- [ ] **Step 4: event-10**

区分关税政策背景、首次正式公告、实施细则与后续调整。不得将公告后的行情或公司结果写入公开节点。

### Task 6: 统一阶段、锚点和节点作用（85-100分钟）

**Files:**
- Modify: `work/timeline_fast_candidate_v2/timeline_nodes.jsonl`
- Create: `work/timeline_fast_candidate_v2/timeline_episodes.jsonl`

- [ ] **Step 1: 强制每个事件只有一个主锚点**

每个事件必须恰好一个 `anchor_role=PRIMARY`。次级节点使用 `SECONDARY`，背景或观察节点使用 `NONE`。

- [ ] **Step 2: 标记节点作用**

首次冲击通常为 `STARTS`；升级为 `AMPLIFIES`；缓和为 `WEAKENS` 或 `REVERSES`；政策响应按事实选择 `STARTS/WEAKENS/OBSERVES`。不能仅根据事后行情选择作用。

- [ ] **Step 3: 生成阶段记录**

按 `event_id + phase` 聚合，输出 `start_at`、`end_at`、节点 ID 和来源覆盖。含 `null occurred_at` 的阶段不得伪造起止时间，应在阶段记录中标记 `time_status=UNRESOLVED`。

### Task 7: 校验与晋升分流（100-115分钟）

**Files:**
- Create: `work/timeline_fast_candidate_v2/promotable_milestones.jsonl`
- Create: `work/timeline_fast_candidate_v2/timeline_gap_report.json`
- Create: `work/timeline_fast_candidate_v2/validation_report.json`

- [ ] **Step 1: 验证JSONL可解析**

```powershell
Get-Content work/timeline_fast_candidate_v2/timeline_nodes.jsonl |
  ForEach-Object { $_ | ConvertFrom-Json | Out-Null }
```

预期：无异常。

- [ ] **Step 2: 执行完整性规则**

检查：10个事件均存在、每个事件恰好一个主锚点、ID唯一、枚举合法、非空时间带时区、来源ID可在 `source_manifest.jsonl` 解析、隐藏记录未标为公开。

- [ ] **Step 3: 生成可晋升清单**

仅选择同时满足下列条件的记录：

```text
evidence_status=VERIFIED_EXISTING
occurred_at 非空
first_public_at 非空
visibility 不是 UNRESOLVED
source_ids 全部可解析
gap_reason 为空
```

转换为当前 `fingoose_macro_event_milestone_v2.schema.json` 后调用现有 `validate_schema_record('milestone', record)`。只有返回空错误数组时，`promotion_eligible=true` 并写入 `promotable_milestones.jsonl`。

- [ ] **Step 4: 生成缺口报告**

`timeline_gap_report.json` 按事件统计：总节点、已验证、待补证、时间未解决、公开/隐藏数量，以及每个缺口需要的来源类型。不得写空泛的“需要更多研究”。

- [ ] **Step 5: 生成验证报告**

`validation_report.json` 必须包含：

```json
{
  "release_tier": "FAST_CANDIDATE",
  "formal_ready": false,
  "production_dataset_modified": false,
  "event_count": 10,
  "node_count": 0,
  "promotable_count": 0,
  "pending_evidence_count": 0,
  "hard_failures": [],
  "warnings": []
}
```

计数字段使用实际结果替换0。任何伪造来源、跨事件来源、公开/隐藏泄漏或重复ID进入 `hard_failures`。

### Task 8: 最终交接并停止（115-120分钟）

**Files:**
- Modify: `work/timeline_fast_candidate_v2/README.md`

- [ ] **Step 1: 复核生产文件未改变**

重新计算三个基线文件 SHA-256，与 Task 1 完全一致。

- [ ] **Step 2: 写入实际交付摘要**

README记录十事件节点分布、可晋升数量、待补证数量、硬失败、下一阶段优先补证事件。

- [ ] **Step 3: 到时停止**

120分钟到达后不继续公司行业暴露、传导图、市场窗口或UI。主任务回报实际完成度，不把 `FAST_CANDIDATE` 描述为已审计 v2。

## 完成定义

满足以下条件即可结束本次两小时任务：

- 十个事件均有结构化节点记录；
- 总节点目标40至50，未达到时有明确缺口解释；
- 每个事件恰好一个主锚点；
- 每条记录区分已验证与待补证；
- 已验证来源均能在现有清单中解析；
- 隐藏信息没有进入公开预测节点；
- 当前 v2 数据与 manifest 哈希未改变；
- 输出可晋升节点、缺口报告和验证报告；
- 状态始终为 `FAST_CANDIDATE / formal_ready=false`。
