# 行情公式与缺口状态

## 固定公式

使用事件定义的固定窗口和明确交易日端点：

```text
company_absolute_return = company_value / company_T_MINUS_1 - 1
market_return = market_value / market_T_MINUS_1 - 1
industry_return = industry_value / industry_T_MINUS_1 - 1
market_relative_return = company_absolute_return - market_return
industry_relative_return = company_absolute_return - industry_return
```

## 状态

- `CALCULATED`：公司、市场和行业三类输入齐全，端点日期与公式可回算。
- `PARTIAL_CALCULATED`：公司与市场齐全、行业缺失，并记录稳定原因码和缺失字段。
- `DATA_MISSING`：关键输入不足，并记录稳定原因码；不能输出伪造收益。

所有收益必须保留原始值、端点值、交易日、数据源和计算依据。禁止以零替代缺失值，禁止用行情一致性单独证明宏观事件因果关系。行情只能验证窗口表现和机制一致性；因果结论仍受 `causal-gates.md` 约束。

`strict-claim-closure-v2` 要求公司和行业代理均为 `CALCULATED`，完整包含 T-1、T0、D1、D3、D5、D20。审计器必须用 T-1 原始值重新计算绝对收益与相对收益，容差不超过 `1e-9`；端点存在不能替代连续交易或停复牌核验。
