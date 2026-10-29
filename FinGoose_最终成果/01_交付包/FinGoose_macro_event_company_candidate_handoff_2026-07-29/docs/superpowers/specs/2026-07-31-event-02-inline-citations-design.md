# Event-02 Inline Citations Design

## Goal

在 event-02 只读成果页中，把可点击引用放到事实和机制出现的位置，避免用户必须切换到独立证据页才能找到来源。保持 `RAPID_CANDIDATE / formal_ready=false`，不修改生产 v2 数据。

## Selected Layout

采用用户确认的 A 方案：行内引用标签。

- 每个时间线节点在事实与影响摘要下方显示“事实来源”标签。
- 每条核心传导路径在条件、失效条件和反证之后显示两组标签：“事件事实依据”和“机制依据”。
- 标签文字包含发布者和证据角色，点击后打开原始网页。
- 独立“证据来源”页继续保留，作为完整来源目录，不替代行内引用。

## Evidence Semantics

构建页面时，以 `sources.json` 的 `source_id` 为键建立来源索引。

- 时间线使用节点的 `source_ids` 解析 `EVENT_FACT_AND_TIME` 来源。
- 传导链使用 `event_fact_evidence` 解析事件事实来源。
- 传导链使用 `mechanism_evidence[].source_id` 解析机制来源。
- 机制来源如果晚于主锚点，标签必须显示“事后机制验证”，不得显示成预测时可见证据。
- `fast-event-02-M01` 保持 `PENDING_EVIDENCE`，显示不可点击的“暂无已验证引用”，不得链接语义错位的 Kremlin 候选。
- 找不到来源记录或 URL 时显示不可点击的 `UNKNOWN`，并进入页面构建验证失败。

## Interaction And Accessibility

- 链接使用普通 `<a>`，在新标签页打开，并设置 `target="_blank"` 与 `rel="noopener noreferrer"`。
- 链接保持紧凑但有明确文字，不只显示图标或裸 `source_id`。
- 事实与机制使用不同的文本标签，不依赖颜色区分。
- 移动端允许标签换行，不产生横向页面溢出。

## Data Flow

1. 生成器读取时间线、核心传导路径和来源注册表。
2. 页面脚本建立 `sourceById` 索引。
3. 时间线节点按 `source_ids` 渲染事实引用。
4. 传导路径分别按事实引用和机制引用渲染两组标签。
5. 原有独立来源页继续从同一注册表渲染，避免两套 URL 数据漂移。

## Validation

- 四个已验证时间线节点至少有一条可点击事实来源。
- `M01` 没有可点击链接，并明确显示待补证状态。
- 四条核心路径均同时显示事件事实依据和机制依据。
- 所有行内链接均能在 `sources.json` 解析到非空 URL。
- 事后机制来源带有泄漏隔离提示。
- 桌面与移动端截图中标签不遮挡正文、不超出容器。
- 现有 event-02 与 v2 回归测试继续通过。

## Scope Boundary

本次只修改 event-02 生成器、测试和独立成果页。不会修改生产 `event_milestones.jsonl`、`transmission_graphs.jsonl`、`market_windows.jsonl`，也不会把任何 `PROPOSED` 路径晋升为 `CONFIRMED`。
