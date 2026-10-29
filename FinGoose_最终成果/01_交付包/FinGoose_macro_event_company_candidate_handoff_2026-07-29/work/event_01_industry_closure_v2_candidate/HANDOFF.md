# FinGoose event-01 八行业候选闭环交接

生成日期：2026-08-04

## 交付状态

- 数据集版本：`fingoose-event-01-industry-closure-v2-candidate`
- 范围：仅 `event-01` 八个行业覆盖层，其他九个事件和 69 条行业基线记录未替换
- 映射 / 机制链 / 机制节点：`8 / 8 / 56`
- 完成门禁：`7 CANDIDATE_COMPLETE / 1 OPEN`
- 审核与发布边界：`PROPOSED / NEEDS_HUMAN_REVIEW / formal_ready=false / sha_gate=DEFERRED`
- Git 状态：`NO_VALID_GIT_METADATA`，本目录没有有效 Git 仓库，未生成或声称任何提交

## 官方来源

- 注册来源：14 条
- `RETRIEVED_QUOTE_VERIFIED`：12 条
- `FETCH_FAILED`：2 条
- `CONTENT_MISMATCH`：0 条

未完成来源：

1. `event01-gov-diagnosis-v6`：国家卫健委官方页面在 Python 与系统 curl 中均出现 TLS 完整性错误，保持 `FETCH_FAILED`。
2. `event01-nmpa-test-kits`：国家药监局官方页面返回 HTTP 412，保持 `FETCH_FAILED`；搜索摘要没有写入 `verified_quote` 或驱动数值。

正文匹配只忽略中文、数字和标点边界的 HTML/PDF 布局空白；英文单词间空格继续参与逐字匹配，不使用模糊相似度晋升来源。

## 行情与驱动

- 申万事件日行业指数：`801150 / 801170 / 801210 / 801200 / 801760 / 801020 / 801750 / 801120` 全部 `AVAILABLE`
- 沪深300：`CSI300`，`AVAILABLE`
- 行情窗口：八条映射全部具有共同交易日、`T-20` 至 `D20` 连续序列及 `T-1/T0/D1/D3/D5/D20/M3` 固定窗口
- T0：WHO 事件时间转换为北京时间 `2020-03-12 00:30`，对应同日开盘前，行业与沪深300共同 `T0=2020-03-12`
- `801020` 保持事件日历史名称“采掘”，只在细分标签中说明石油石化暴露
- 缺失值策略：保持 `null / DATA_PENDING`，未补零，未根据事后价格选择行业或驱动

申万接口曾因 Brotli 解码失败。适配器现仅在调用该接口期间固定 `Accept-Encoding: gzip, deflate`，调用后恢复原请求函数；未修改 AKShare 安装文件。

## 完成矩阵

- `医药生物 801150`：`OPEN`，阻塞项为 `FOUR_FACT_PILLARS_INCOMPLETE` 与 `DRIVER_DATA_INCOMPLETE`
- `交通运输 801170`：`CANDIDATE_COMPLETE`
- `社会服务 801210`：`CANDIDATE_COMPLETE`
- `商贸零售 801200`：`CANDIDATE_COMPLETE`
- `传媒 801760`：`CANDIDATE_COMPLETE`
- `采掘 801020`：`CANDIDATE_COMPLETE`
- `计算机 801750`：`CANDIDATE_COMPLETE`
- `食品饮料 801120`：`CANDIDATE_COMPLETE`

八条映射均登记结构化混杂：七条为 `MATERIAL`，采掘为 `DOMINANT`；全部只进入挑战集，不能计入干净归因主分数。

## 数值抽查

已独立复算以下行业的 `T-1 / T0 / D3`：

- 交通运输 `801170`
- 商贸零售 `801200`
- 采掘 `801020`

行业收益、沪深300收益、相对收益和两条归一化序列的最大绝对误差均不超过 `1e-10`。明细保存在 `validation_report.json.manual_spot_checks`。

## UI

- 页面：`work/company_impact_high_quality_v2_candidate/ui/index.html`
- 数据包：`work/company_impact_high_quality_v2_candidate/ui/ui_data_bundle.js`
- 本机：`http://127.0.0.1:8000/`
- 局域网：`http://192.168.1.227:8000/`
- 截图：`ui-1440.png`、`ui-390.png`

Playwright 使用系统 Chrome 验证 `1440x1000` 与 `390x844`：八行业分支常驻、交通运输七步链为 7 个节点、归一化/原始值两张 SVG 存在、证据链接存在、无控制台错误、无页面级横向溢出。主驱动的技术选择代码已在研究主视图中文化，原代码仍保留在底层 JSONL。

## 测试

- 专项回归：`43 passed`
- UI 单元测试：`19 passed`
- 市场与时区测试：`12 passed`
- Playwright 桌面/移动验收：通过
- Python 编译检查：通过
- 发布边界扫描：0 条 `formal_ready=true / sha_gate=PASSED / review_status=CONFIRMED`
- 覆盖隔离：基线 77 个唯一 ID，覆盖层 8 个唯一 `event-01` ID，投影后仍为 77 个 ID

全仓测试现状：`307 passed / 1 skipped / 29 failed / 26 errors`。这些失败属于旧版 v1 基线资源和环境缺口，主要包括：

- 缺少 `reportlab`，导致 `test_fingoose_official_pdf_plumber_v2.py` 无法收集；
- 缺少 `outputs/fingoose_macro_event_attribution_v1/source_manifest.jsonl`；
- 缺少 `inputs/macro_event_attribution_v1/sources/event01_who_pandemic.html` 等旧版快照；
- 旧版 Schema/100 样本测试存在既有断言失败。

本轮专项测试不依赖这些旧版缺失资产，且全部通过。

## 主要变更路径

- `configs/industry_impact_v2/event_01_closure_profiles.json`
- `configs/industry_impact_v2/event_01_source_registry.jsonl`
- `configs/industry_impact_v2/event_01_market_registry.json`
- `code/fingoose_event_01_industry_closure_v2.py`
- `code/fingoose_industry_source_snapshot_v2.py`
- `code/fingoose_industry_market_v2.py`
- `code/fingoose_company_impact_market_v2.py`
- `code/fingoose_company_impact_ui_v2.py`
- `tests/test_fingoose_event_01_industry_closure_v2.py`
- `tests/test_fingoose_industry_source_snapshot_v2.py`
- `tests/test_fingoose_industry_market_v2.py`
- `tests/test_fingoose_company_impact_market_v2.py`
- `tests/test_fingoose_industry_ui_v2.py`
- `tests/verify_event_01_industry_ui.mjs`
- `requirements-event01-industry.txt`
- `work/event_01_industry_closure_v2_candidate/`
- `work/company_impact_high_quality_v2_candidate/ui/`
