# 因果识别门禁

证据闭环、行情完整和因果识别是独立状态。同期行情、机制一致性或字符串真值都不能替代严格因果门禁。

## 字段契约

| 字段 | 要求 |
| --- | --- |
| `status` | 必须是四种允许状态之一 |
| `causal_attribution_allowed` | 严格布尔值；只有 `IDENTIFIED` 可为 `true` |
| `causal_conclusion` | 非 `IDENTIFIED` 必须为 `ABSTAIN` |
| `method` | 识别方法；未识别时可为 `null` |
| `gate_results` | 逐项严格布尔门禁；`IDENTIFIED` 时必须非空且全部为 `true` |
| `unmet_conditions` | 尚未满足的识别条件列表 |
| `confounders` | 已知市场、行业和公司混杂因素列表 |
| `counterevidence` | 反证列表 |
| `boundary_zh` | 面向输出的中文因果边界说明 |

## 四种状态

| `status` | 含义 | 强制输出 |
| --- | --- | --- |
| `NOT_IDENTIFIED` | 仅有同期行情或机制一致性，不能排除其他因素 | `causal_attribution_allowed=false` 且 `causal_conclusion=ABSTAIN` |
| `DESCRIPTIVE_EVENT_STUDY` | 可描述事件窗口异常表现，但不能声称因果 | `causal_attribution_allowed=false` 且 `causal_conclusion=ABSTAIN` |
| `QUASI_EXPERIMENTAL_CANDIDATE` | 具备候选准实验条件，但尚未通过全部稳健性检查 | `causal_attribution_allowed=false` 且 `causal_conclusion=ABSTAIN` |
| `IDENTIFIED` | 全部识别门禁严格通过 | `causal_attribution_allowed=true`，并允许非 `ABSTAIN` 因果结论 |

未知状态、非 `IDENTIFIED` 但允许归因、非 `IDENTIFIED` 但结论不是 `ABSTAIN`，或 `IDENTIFIED` 未允许归因，均返回 `CAUSAL_GATE_CONTRADICTION`。

## `IDENTIFIED` 的全部门禁

只有同时满足行情窗口完整、基准完整、连续交易核验、比较组明确、前趋势通过、混杂因素控制、稳健性通过和反证通过，才允许 `IDENTIFIED`。

`gate_results` 必须非空，且以下每一项都以布尔值 `true` 通过；字符串 `"true"` 不算通过：

| 门禁 | 要求 |
| --- | --- |
| `market_window_complete` | 事件行情窗口及实际端点日期完整且可回算 |
| `benchmark_complete` | 市场和所需行业基准完整、窗口和收益口径一致 |
| `continuous_trading_verified` | 停复牌或连续交易状态已核验，不能只凭端点价格存在 |
| `comparison_group_defined` | 对照组明确且选择规则可复核 |
| `pretrend_passed` | 事件前趋势检验通过 |
| `confounders_controlled` | 市场、行业及公司层混杂因素已控制 |
| `robustness_passed` | 预设稳健性检查全部通过 |
| `counterevidence_passed` | 反证检查完成且未推翻识别结论 |

只要 `gate_results` 为空、存在缺项，或任一值不是严格布尔 `true`，就不得标记 `IDENTIFIED`，并返回 `CAUSAL_GATE_CONTRADICTION`。降级后的记录必须恢复 `causal_attribution_allowed=false` 和 `causal_conclusion=ABSTAIN`。
