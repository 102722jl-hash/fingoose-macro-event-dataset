# 数据字典（company_event_map_v1_candidate）

> 本目录为 FinGoose 事件-公司候选映射与 A 股行情采购首版（CANDIDATE 层）。
> 生成日期：2026-07-31。所有新增文件，不改动既有 v2 数据。

## company_event_map.csv（50 行 = 30 种子 + 20 待选占位）
| 字段 | 说明 |
|---|---|
| event_id | 事件编号 event-01..event-10 |
| event_anchor_id | 事件锚点 id（首版 = event_id） |
| event_t0_date | A 股证券 T0（由 anchor_at + 盘后取下一交易日推导） |
| ts_code | 交易所代码，如 600009.SH / 000001.SZ；待选占位行为空 |
| company_name | 公司中文名 |
| exchange | SSE / SZSE / BSE |
| listing_and_delisting_dates | 上市~退市日期（待供应商回填，须含退市公司） |
| exposure_role | 暴露角色（待证据审核填） |
| transmission_path_id | 传导路径 id |
| expected_impact_direction | 预期影响方向 |
| selected_at / selection_cutoff_at | 选择时间与截止时间（冻结用） |
| price_selection_used | 固定 false（禁止用事后价格选样） |
| exposure_status | VERIFIED / PARTIAL / PENDING / REJECTED / PENDING_SELECTION |
| reviewer / review_time / reject_or_gap_reason | 审核信息 |
| event_day_sw_l1_code / name / sw_version / effective_from / effective_to / sw_index_code | 事件日生效的申万一级行业归属（**禁止 2026 分类回填**） |
| evidence_ids / source_status | 证据与来源状态 |

## price_data_request.csv
| 字段 | 说明 |
|---|---|
| request_id | 请求编号 |
| event_id | 关联事件（基准/日历为 ALL） |
| ts_code | 证券或指数代码；日历行为空 |
| exchange | 交易所 |
| instrument_type | EQUITY / INDEX / TRADING_CALENDAR / CORPORATE_ACTIONS |
| start_date / end_date | 取数区间（设计 §4.2：T0-40月 ~ T0+2月） |
| window_purpose | 用途 |
| notes | 备注 |

## 行情字段口径（供应商交付须含）
- 个股：ts_code, trade_date, exchange, open, high, low, close, pre_close, volume, amount,
  turnover_rate, cumulative_adj_factor, is_suspended, limit_up_price, limit_down_price,
  limit_status, is_st, listing/delisting_status, source_provider, source_updated_at
- 指数：index_code, index_name, trade_date, open, high, low, close, pre_close,
  volume, amount, total_return/adj_factor, index_version, source_provider
- 单位：价格=元/股，成交量=股，成交额=元，换手率=百分点
- 复权：收益用**后复权总回报价** TRP_t = raw_close_t × cumulative_adj_factor_t
- 停牌日不插值；无交易的目标日按交易日历映射并记录偏移
