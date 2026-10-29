# 内容契约

## 事件层

事件候选必须包含来源事实、双时钟时间线、里程碑、机制链、即时/短期/中期三个阶段、行情窗口和失效条件。三个阶段必须描述不同的传导和可观测变量；三个阶段不得复用同一陈述。

## 行业层

为每个事件选择 5–10 个有证据支持的相关行业。每个行业记录七步机制（冲击、渠道、经营变量、财务变量、估值/预期、行情、反证）、经营与财务变量、即时/短期/中期影响、行业行情和反证。每个节点必须使用 `DIRECT_FACT`、`PREMISE_SUPPORT`、`CALCULATED_LINEAGE` 或 `NEGATIVE_SEARCH_AUDIT` 之一闭环，并登记独立定位、支持说明和 `supports_node_ids` 反向映射。行业映射必须能回指事件和证据。

## 公司层

每个行业固定选择 3 家公司，按事前业务暴露而非事后涨跌选样。每家公司至少保留两份事件日前 T1/T2 官方或法定披露，并记录经营路径、三个不同阶段、相对收益、混杂因素和反证，保留所属事件、行业和证据 ID。

## QA 层

QA 分为证据查询、机制阶段、行情验证、行业公司四类。QA 必须保留所属事件 ID，并能回指对应证据、节点、行业或公司；不能成为脱离事件的独立问答任务。

## 冻结与重放

`content_candidates.jsonl` 保存机器门禁前的研究内容候选；`accepted_content.jsonl` 每行必须包含 `event_id`、`operation=UPSERT`、完整 `unified_event`、`evidence_ids`、`content_sha256` 和可选 `split_assignment`。

`accepted_content` 的 `unified_event` 必须同时包含事件、行业、公司和事件关联 QA 的完整候选内容，不保存依赖隐式会话状态的增量自然语言指令。`online-acquire` 冻结 `accepted_content`；offline-replay 不得重新生成或改写研究文字。

严格批次只有在所有要求事件均进入 accepted 集合时才具备发布资格。任一事件失败仍完成其余事件处理，但整个 UI 批次不得发布。
