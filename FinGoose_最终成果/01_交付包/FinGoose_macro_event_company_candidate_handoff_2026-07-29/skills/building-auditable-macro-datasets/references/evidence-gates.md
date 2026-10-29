# 证据门禁

## 来源等级与允许范围

| `source_tier` | 来源 | 允许范围 |
| --- | --- | --- |
| `T1` | 政府、央行、监管机构、国际组织及事件责任主体的原始文件或数据 | 可直接支持 `SOURCE_FACT` |
| `T2` | 交易所公告、公司法定披露、经审计报告及可核验的一手数据库 | 可直接支持 `SOURCE_FACT` |
| `T3` | 具名媒体、研究机构或券商的二手报道和分析 | 只作线索、背景或交叉验证；不得直接支持 `SOURCE_FACT` |
| `T4` | 聚合页、匿名转载、论坛或责任主体不明的内容 | 只登记检索线索；不得直接支持 `SOURCE_FACT` |

`statement_class=SOURCE_FACT` 时仅 `T1`、`T2` 有资格；其他等级返回 `SOURCE_TIER_NOT_ELIGIBLE`。搜索摘要和 AI 摘要都不是来源事实。

## 候选证据字段

| 字段 | 要求 |
| --- | --- |
| `evidence_id` | 稳定且在注册表中唯一的证据标识 |
| `source_url` | 必填的最终来源 URL，也是完整性门禁字段 |
| `publisher` | 发布责任主体 |
| `published_at` | 可核验的首次公开时间 |
| `retrieved_at` | 实际抓取时间 |
| `original_quote` | 必填的原文摘录，不得由摘要或推断替代 |
| `locator` | 必填的页码、段落、表格单元格或稳定正文定位 |
| `snapshot_path` | 允许保存时的受控快照路径；策略禁止保存原文时可为 `null` |
| `snapshot_sha256` | 快照或许可范围内内容的 SHA256 |
| `source_tier` | `T1`、`T2`、`T3` 或 `T4` |
| `supports_node_ids` | 该证据直接支持的推理节点 ID 列表 |
| `temporal_role` | `AS_OF_EVIDENCE`、`POST_EVENT_VALIDATION` 或 `CUTOFF_BLOCKED` |
| `acceptance_status` | 接受、拒绝或隔离状态 |
| `acceptance_reason` | 稳定的门禁原因码 |

来源事实完整性要求 `original_quote`、`locator`、`source_url` 三个字段同时非空；任一缺失返回 `SOURCE_EVIDENCE_INCOMPLETE`。`temporal_role=CUTOFF_BLOCKED` 返回 `CUTOFF_BLOCKED`。通过来源、时间和完整性检查后返回 `GATES_PASSED`。

## 主张闭环

- `DIRECT_FACT`：仅 T1/T2 原文可直接支持。
- `PREMISE_SUPPORT`：至少一条 T1/T2 支持推理前提；T3 只能辅助。
- `CALCULATED_LINEAGE`：保留原始值、端点、公式、来源和重算结果。
- `NEGATIVE_SEARCH_AUDIT`：只支持“在给定查询与时间窗未发现”，必须记录 query、起止时间、结果数和正文审查数，不能支持事实不存在。

同一证据可以精确复用，但每个节点都必须有独立 `evidence_locator`、`support_rationale_zh` 和证据侧 `supports_node_ids` 映射。

## 冲突处理

相同 `evidence_id` 的完整记录按关键字段比较。若 `source_url`、`publisher`、`published_at`、`original_quote`、`locator`、`source_tier`、`supports_node_ids` 或 `temporal_role` 存在冲突，必须 fail closed：保留全部候选及 lineage，标记来源冲突并送入隔离区，不静默覆盖、不按预设结论挑选来源，也不自动解除人工审核。

稀疏子链引用只能继承完整父事件证据的 `evidence_id`、`supports_node_ids` 和来源 lineage，不能用稀疏引用替代完整证据字段。找不到可核验原文、只有搜索摘要、发布时间不明、页面无法稳定定位或关键来源冲突时均不得接受。
