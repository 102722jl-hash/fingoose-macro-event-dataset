# 双时钟与时间角色策略

每条候选证据都必须同时记录事件锚点时钟和资料发布时钟。时间比较使用可解析的 ISO 8601 时间；UTC 后缀 `Z` 等同于 `+00:00`。

## 输入字段

| 字段 | 要求 | 用途 |
| --- | --- | --- |
| `published_at` | 必填，ISO 8601 | 资料首次公开时间，不得以抓取时间代替 |
| `anchor_at` | 必填，ISO 8601 | 研究问题允许使用证据的事件锚点或截止时间 |
| `declared_role` | 必填 | 声明资料是否仅作事后验证 |
| `temporal_role` | 输出 | 门禁根据两个时钟和声明生成的最终角色 |

## 三种时间角色

| `temporal_role` | 判定 | 允许用途 |
| --- | --- | --- |
| `AS_OF_EVIDENCE` | 非事后验证材料，且 `published_at <= anchor_at` | 可进入截至锚点可见的主要推理链 |
| `POST_EVENT_VALIDATION` | `declared_role=POST_EVENT_VALIDATION` | 只能用于行情验证、反证或结果观察；不得作为事前结论的直接前提 |
| `CUTOFF_BLOCKED` | 非事后验证材料，且 `published_at > anchor_at` | 拒绝进入候选训练主路径并送入隔离记录 |

`POST_EVENT_VALIDATION` 声明优先保留原角色。除此之外，越过锚点的资料一律标为 `CUTOFF_BLOCKED`；未越过锚点的资料标为 `AS_OF_EVIDENCE`。事后公告、事后行情和后来发布的研究结论不得回填为事前可见事实。

