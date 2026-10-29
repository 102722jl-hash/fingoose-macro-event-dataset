# company_event_map_v1_candidate

FinGoose 宏观事件-公司候选映射与 A 股行情采购首版交付物（CANDIDATE 层，formal_ready=false）。

## 本目录文件
- `company_event_map.csv` — 50 条事件-公司记录（30 种子 + 每事件 2 条待选占位）
- `price_data_request.csv` — 行情采购请求（个股 / 基准指数 / 交易日历 / 公司行动）
- `company_exposure_evidence.jsonl` — 事件前证据（待填）
- `rejected_candidates.jsonl` — 被拒候选与理由（待填）
- `data_dictionary.md` — 字段与口径说明
- `validation_report.json` — 验收检查
- `summary.json` — 汇总
- 行情到货后另建数据目录，不写入本公开候选包

## 已知待决事项
1. **取数区间冲突**：本包用设计文档 §4.2 的 T0±月规则；与早期需求单的更早起始日不一致，需负责人拍板。
2. **event-09 T0**：已固定为 2024-09-24（设计文档定稿）。
3. **待选 20 家**：需依据事件前公开材料补选，禁止编造 ts_code。
4. **申万一级行业历史归属**：须按事件日生效版本填，禁止当前分类回填。
5. **供应商数据**：equity_daily / index_daily 等需 Wind/Choice/CSMAR 等授权源，本包不含原始价格。

## 验收（摘要，详见 validation_report.json）
- 10 事件 × 5 记录 = 50 行
- price_selection_used 全为 false
- 30 种子为 PENDING_EVIDENCE，20 为 PENDING_SELECTION
