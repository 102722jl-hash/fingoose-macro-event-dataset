from __future__ import annotations

from typing import Any


EVENT_CONFIGS: dict[str, dict[str, Any]] = {
    "event-01": {
        "title_zh": "WHO 宣布 COVID-19 构成全球大流行",
        "core_series_ids": ["SP500", "VIXCLS", "DCOILWTICO", "DEXCHUS"],
        "optional_series_ids": [],
        "primary_anchor_strategy": "VERIFIED_PRIMARY",
    },
    "event-02": {
        "title_zh": "俄罗斯对乌克兰发动全面进攻及后续能源制裁",
        "core_series_ids": ["DCOILBRENTEU", "DHHNGSP", "VIXCLS", "SP500"],
        "optional_series_ids": ["DGS10"],
        "primary_anchor_strategy": "VERIFIED_PRIMARY",
    },
    "event-03": {
        "title_zh": "美联储开启 2022 年加息周期",
        "core_series_ids": ["DGS10", "SP500", "DTWEXBGS", "DEXCHUS"],
        "optional_series_ids": [],
        "primary_anchor_strategy": "VERIFIED_PRIMARY",
    },
    "event-04": {
        "title_zh": "中国发布防疫优化措施并转向重新开放",
        "core_series_ids": ["SP500", "DCOILWTICO", "VIXCLS", "DEXCHUS"],
        "optional_series_ids": [],
        "primary_anchor_strategy": "VERIFIED_PRIMARY",
    },
    "event-05": {
        "title_zh": "硅谷银行关闭及银行业压力升级",
        "core_series_ids": ["VIXCLS", "DGS10", "SP500", "DEXCHUS"],
        "optional_series_ids": [],
        "primary_anchor_strategy": "VERIFIED_PRIMARY",
    },
    "event-06": {
        "title_zh": "OPEC+ 宣布额外自愿减产",
        "core_series_ids": ["DCOILBRENTEU", "DCOILWTICO", "SP500", "DEXCHUS"],
        "optional_series_ids": [],
        "primary_anchor_strategy": "VERIFIED_PRIMARY",
    },
    "event-07": {
        "title_zh": "2023 年 10 月中东冲突与航运风险升级",
        "core_series_ids": ["DCOILBRENTEU", "VIXCLS", "SP500", "DEXCHUS"],
        "optional_series_ids": [],
        "primary_anchor_strategy": "VERIFIED_PRIMARY",
    },
    "event-08": {
        "title_zh": "日本央行结束负利率政策",
        "core_series_ids": ["DEXJPUS", "DGS10", "SP500", "DEXCHUS"],
        "optional_series_ids": [],
        "primary_anchor_strategy": "VERIFIED_PRIMARY",
    },
    "event-09": {
        "title_zh": "中国宣布一揽子货币、住房与资本市场支持",
        "core_series_ids": ["DEXCHUS", "SP500", "DGS10", "DTWEXBGS"],
        "optional_series_ids": [],
        "primary_anchor_strategy": "VERIFIED_PRIMARY",
    },
    "event-10": {
        "title_zh": "美国建立广泛对等关税框架",
        "core_series_ids": ["SP500", "DGS10", "DTWEXBGS", "DEXCHUS"],
        "optional_series_ids": [],
        "primary_anchor_strategy": "VERIFIED_PRIMARY",
    },
}


MECHANISM_SOURCES: list[dict[str, Any]] = [
    {
        "source_id": "mechanism-event-01-imf-covid-financial",
        "publisher": "International Monetary Fund",
        "source_tier": "A",
        "url": "https://www.imf.org/-/media/files/publications/covid19-special-notes/enspecial-series-on-covid19monetary-and-financial-policy-responses-for-emerging-market-and-developin.pdf",
        "published_at": "2020-04-01",
        "locator": "Opening section on confidence, liquidity and monetary transmission",
        "quote": "The COVID-19 pandemic and related adverse confidence effects are having severe negative impacts on global markets.",
        "evidence_scope": "POST_EVENT_MECHANISM_CORROBORATION",
        "visibility": "HIDDEN_FROM_PRIMARY_PREDICTION",
    },
    {
        "source_id": "mechanism-event-02-fed-ukraine",
        "publisher": "Board of Governors of the Federal Reserve System",
        "source_tier": "A",
        "url": "https://www.federalreserve.gov/econres/notes/feds-notes/the-effect-of-the-war-in-ukraine-on-global-activity-and-inflation-20220527.html",
        "published_at": "2022-05-27",
        "locator": "Summary and transmission-channel discussion",
        "quote": "The effects operate through lower consumer sentiment, higher commodity prices, and tighter financial conditions.",
        "evidence_scope": "POST_EVENT_MECHANISM_CORROBORATION",
        "visibility": "HIDDEN_FROM_PRIMARY_PREDICTION",
    },
    {
        "source_id": "mechanism-event-03-fed-transmission",
        "publisher": "Board of Governors of the Federal Reserve System",
        "source_tier": "A",
        "url": "https://www.federalreserve.gov/pubs/feds/2010/201026/201026pap.pdf",
        "published_at": "2010-05-01",
        "locator": "Sections on interest-rate, asset-price, credit and exchange-rate channels",
        "quote": "Monetary transmission can be categorized into channels operating through financial markets and credit frictions.",
        "evidence_scope": "MECHANISM_PRIOR",
        "visibility": "PUBLIC_PREDICTION",
    },
    {
        "source_id": "mechanism-event-04-worldbank-china",
        "publisher": "World Bank",
        "source_tier": "A",
        "url": "https://documents1.worldbank.org/curated/en/099640106102210762/pdf/P17579708f26d5018098840f1ad978bb54b.pdf",
        "published_at": "2022-06-08",
        "locator": "China Economic Update sections on lockdowns, growth and commodity trade",
        "quote": "COVID-related restrictions weakened activity and disrupted trade, production and demand.",
        "evidence_scope": "MECHANISM_PRIOR",
        "visibility": "PUBLIC_PREDICTION",
    },
    {
        "source_id": "mechanism-event-05-fed-svb-review",
        "publisher": "Board of Governors of the Federal Reserve System",
        "source_tier": "A",
        "url": "https://www.federalreserve.gov/publications/files/svb-review-20230428.pdf",
        "published_at": "2023-04-28",
        "locator": "Executive summary and contagion discussion",
        "quote": "The failure of SVB demonstrated weaknesses in governance, liquidity and interest-rate risk management.",
        "evidence_scope": "POST_EVENT_MECHANISM_CORROBORATION",
        "visibility": "HIDDEN_FROM_PRIMARY_PREDICTION",
    },
    {
        "source_id": "mechanism-event-06-eia-opec",
        "publisher": "U.S. Energy Information Administration",
        "source_tier": "A",
        "url": "https://www.eia.gov/finance/markets/crudeoil/supply-opec.php",
        "published_at": "2023-01-01",
        "locator": "OPEC supply decisions and crude-oil price discussion",
        "quote": "OPEC production targets can influence expectations about future petroleum supply and prices.",
        "evidence_scope": "MECHANISM_PRIOR",
        "visibility": "PUBLIC_PREDICTION",
    },
    {
        "source_id": "mechanism-event-07-unctad-shipping",
        "publisher": "United Nations Conference on Trade and Development",
        "source_tier": "A",
        "url": "https://unctad.org/news/red-sea-black-sea-and-panama-canal-three-global-trade-chokepoints-under-pressure",
        "published_at": "2024-01-26",
        "locator": "Sections on rerouting, freight costs and energy shipments",
        "quote": "Disruptions at major trade routes raise shipping distances, freight costs and supply-chain uncertainty.",
        "evidence_scope": "POST_EVENT_MECHANISM_CORROBORATION",
        "visibility": "HIDDEN_FROM_PRIMARY_PREDICTION",
    },
    {
        "source_id": "mechanism-event-08-boj-yen",
        "publisher": "Bank of Japan",
        "source_tier": "A",
        "url": "https://www.boj.or.jp/en/research/wps_rev/wps_2024/data/wp24e23.pdf",
        "published_at": "2024-12-01",
        "locator": "Results on interest-rate differentials and the yen",
        "quote": "The interest-rate differential channel is an important mechanism linking policy shocks to the yen.",
        "evidence_scope": "POST_EVENT_MECHANISM_CORROBORATION",
        "visibility": "HIDDEN_FROM_PRIMARY_PREDICTION",
    },
    {
        "source_id": "mechanism-event-09-pbc-report",
        "publisher": "People's Bank of China",
        "source_tier": "A",
        "url": "https://www.pbc.gov.cn/en/3688229/3688353/3688356/4583781/4584048/2022062209443031445.pdf",
        "published_at": "2022-05-09",
        "locator": "Liquidity, credit, interest-rate and RMB exchange-rate sections",
        "quote": "Monetary instruments support liquidity, credit growth and transmission while the exchange rate remains market based.",
        "evidence_scope": "MECHANISM_PRIOR",
        "visibility": "PUBLIC_PREDICTION",
    },
    {
        "source_id": "mechanism-event-10-imf-tariffs",
        "publisher": "International Monetary Fund",
        "source_tier": "A",
        "url": "https://www.imf.org/en/blogs/articles/2025/04/22/the-global-economy-enters-a-new-era",
        "published_at": "2025-04-22",
        "locator": "Paragraphs on tariff effects on U.S. growth, inflation and trading partners",
        "quote": "Tariffs lower growth, raise U.S. inflation and act as a negative demand shock for trading partners.",
        "evidence_scope": "POST_EVENT_MECHANISM_CORROBORATION",
        "visibility": "HIDDEN_FROM_PRIMARY_PREDICTION",
    },
]


_PATH_ROWS = [
    ("event-01", "pandemic-risk-appetite", "疫情冲击经风险偏好传导至股票与波动率", "PANDEMIC_SHOCK", "RISK_APPETITE", ["SP500", "VIXCLS"], {"IMMEDIATE": "SP500_DOWN__VIX_UP", "SHORT_TERM": "SP500_DOWN__VIX_UP", "MEDIUM_TERM": "MIXED"}),
    ("event-01", "pandemic-oil-demand", "封控与出行下降压低石油需求", "PANDEMIC_SHOCK", "GLOBAL_DEMAND", ["DCOILWTICO"], {"IMMEDIATE": "DOWN", "SHORT_TERM": "DOWN", "MEDIUM_TERM": "MIXED"}),
    ("event-01", "pandemic-safe-haven", "全球不确定性推动美元避险需求", "PANDEMIC_SHOCK", "SAFE_HAVEN_DEMAND", ["DEXCHUS"], {"IMMEDIATE": "UP", "SHORT_TERM": "UP", "MEDIUM_TERM": "MIXED"}),
    ("event-01", "pandemic-policy-response", "WHO 结束 PHEIC 确认疫情冲击进入常态化阶段（非 2020 年政策刺激）", "PANDEMIC_NORMALIZATION", "GLOBAL_DEMAND", ["SP500", "VIXCLS"], {"IMMEDIATE": "MIXED", "SHORT_TERM": "MIXED", "MEDIUM_TERM": "MIXED"}),
    ("event-02", "energy-supply", "战争冲击推高能源供应风险", "GEOPOLITICAL_CONFLICT", "ENERGY_SUPPLY", ["DCOILBRENTEU", "DHHNGSP"], {"IMMEDIATE": "UP", "SHORT_TERM": "UP", "MEDIUM_TERM": "MIXED"}),
    ("event-02", "inflation-rates", "能源涨价经通胀预期影响利率", "ENERGY_PRICE_SHOCK", "INFLATION_EXPECTATIONS", ["DCOILBRENTEU"], {"IMMEDIATE": "UP", "SHORT_TERM": "UP", "MEDIUM_TERM": "MIXED"}),
    ("event-02", "risk-appetite", "地缘尾部风险冲击股票与波动率", "GEOPOLITICAL_CONFLICT", "RISK_APPETITE", ["VIXCLS", "SP500"], {"IMMEDIATE": "VIX_UP__SP500_DOWN", "SHORT_TERM": "MIXED", "MEDIUM_TERM": "MIXED"}),
    ("event-02", "sanctions-trade", "制裁与能源贸易摩擦影响供应连续性", "SANCTIONS", "ENERGY_TRADE", ["DCOILBRENTEU"], {"IMMEDIATE": "MIXED", "SHORT_TERM": "MIXED", "MEDIUM_TERM": "MIXED"}),
    ("event-03", "rate-expectations", "政策利率路径带动国债收益率重定价", "RATE_HIKE", "RATE_EXPECTATIONS", ["DGS10"], {"IMMEDIATE": "UP", "SHORT_TERM": "UP", "MEDIUM_TERM": "MIXED"}),
    ("event-03", "equity-duration", "贴现率上升压低权益久期估值", "RATE_HIKE", "DISCOUNT_RATE", ["SP500"], {"IMMEDIATE": "DOWN", "SHORT_TERM": "DOWN", "MEDIUM_TERM": "MIXED"}),
    ("event-03", "dollar-liquidity", "利差与美元流动性推动美元走强", "RATE_HIKE", "DOLLAR_LIQUIDITY", ["DTWEXBGS", "DEXCHUS"], {"IMMEDIATE": "UP", "SHORT_TERM": "UP", "MEDIUM_TERM": "MIXED"}),
    ("event-03", "growth-expectations", "金融条件收紧压低增长预期", "RATE_HIKE", "FINANCIAL_CONDITIONS", ["SP500", "DGS10"], {"IMMEDIATE": "MIXED", "SHORT_TERM": "DOWN", "MEDIUM_TERM": "DOWN"}),
    ("event-04", "china-growth", "重新开放改善中国增长预期", "REOPENING", "GROWTH_EXPECTATIONS", ["SP500"], {"IMMEDIATE": "UP", "SHORT_TERM": "UP", "MEDIUM_TERM": "MIXED"}),
    ("event-04", "commodity-demand", "活动恢复提高大宗商品需求预期", "REOPENING", "COMMODITY_DEMAND", ["DCOILWTICO"], {"IMMEDIATE": "UP", "SHORT_TERM": "UP", "MEDIUM_TERM": "MIXED"}),
    ("event-04", "risk-appetite", "政策转向改善全球风险偏好", "REOPENING", "RISK_APPETITE", ["SP500", "VIXCLS"], {"IMMEDIATE": "SP500_UP__VIX_DOWN", "SHORT_TERM": "MIXED", "MEDIUM_TERM": "MIXED"}),
    ("event-04", "yuan-repricing", "增长与资本流预期推动人民币重定价", "REOPENING", "FX_EXPECTATIONS", ["DEXCHUS"], {"IMMEDIATE": "DOWN", "SHORT_TERM": "DOWN", "MEDIUM_TERM": "MIXED"}),
    ("event-05", "banking-stress", "存款外流和流动性风险推高银行压力", "BANK_FAILURE", "BANKING_STRESS", ["VIXCLS", "SP500"], {"IMMEDIATE": "VIX_UP__SP500_DOWN", "SHORT_TERM": "MIXED", "MEDIUM_TERM": "MIXED"}),
    ("event-05", "rate-repricing", "金融稳定风险压低加息路径预期", "BANK_FAILURE", "RATE_REPRICING", ["DGS10"], {"IMMEDIATE": "DOWN", "SHORT_TERM": "DOWN", "MEDIUM_TERM": "MIXED"}),
    ("event-05", "safe-haven", "系统性担忧推动避险与美元需求", "BANK_FAILURE", "SAFE_HAVEN_DEMAND", ["DEXCHUS", "VIXCLS"], {"IMMEDIATE": "UP", "SHORT_TERM": "MIXED", "MEDIUM_TERM": "MIXED"}),
    ("event-06", "oil-supply", "减产承诺收紧预期石油供给", "PRODUCTION_CUT", "OIL_SUPPLY", ["DCOILBRENTEU", "DCOILWTICO"], {"IMMEDIATE": "UP", "SHORT_TERM": "UP", "MEDIUM_TERM": "MIXED"}),
    ("event-06", "inflation-pass-through", "油价上涨抬升成本与通胀压力", "PRODUCTION_CUT", "INFLATION_PASS_THROUGH", ["DCOILBRENTEU", "DCOILWTICO"], {"IMMEDIATE": "UP", "SHORT_TERM": "UP", "MEDIUM_TERM": "MIXED"}),
    ("event-06", "global-growth", "能源成本上升压低风险资产增长预期", "PRODUCTION_CUT", "GLOBAL_GROWTH", ["SP500", "DEXCHUS"], {"IMMEDIATE": "MIXED", "SHORT_TERM": "SP500_DOWN", "MEDIUM_TERM": "MIXED"}),
    ("event-07", "energy-supply", "冲突扩散风险抬高能源风险溢价", "MIDDLE_EAST_CONFLICT", "ENERGY_SUPPLY", ["DCOILBRENTEU"], {"IMMEDIATE": "UP", "SHORT_TERM": "UP", "MEDIUM_TERM": "MIXED"}),
    ("event-07", "risk-appetite", "地缘不确定性压低全球风险偏好", "MIDDLE_EAST_CONFLICT", "RISK_APPETITE", ["VIXCLS", "SP500"], {"IMMEDIATE": "VIX_UP__SP500_DOWN", "SHORT_TERM": "MIXED", "MEDIUM_TERM": "MIXED"}),
    ("event-07", "safe-haven", "尾部风险推动美元避险需求", "MIDDLE_EAST_CONFLICT", "SAFE_HAVEN_DEMAND", ["DEXCHUS"], {"IMMEDIATE": "UP", "SHORT_TERM": "MIXED", "MEDIUM_TERM": "MIXED"}),
    ("event-07", "shipping-disruption", "航运绕行提高运费与供应链成本", "MIDDLE_EAST_CONFLICT", "SHIPPING_COSTS", ["DCOILBRENTEU", "SP500"], {"IMMEDIATE": "MIXED", "SHORT_TERM": "OIL_UP__SP500_DOWN", "MEDIUM_TERM": "MIXED"}),
    ("event-08", "yen-rate-differential", "政策正常化缩小利差并影响日元", "BOJ_NORMALIZATION", "RATE_DIFFERENTIAL", ["DEXJPUS"], {"IMMEDIATE": "DOWN", "SHORT_TERM": "MIXED", "MEDIUM_TERM": "MIXED"}),
    ("event-08", "japan-rates", "负利率退出推动日本收益率重定价", "BOJ_NORMALIZATION", "JAPAN_RATES", ["DGS10"], {"IMMEDIATE": "MIXED", "SHORT_TERM": "MIXED", "MEDIUM_TERM": "MIXED"}),
    ("event-08", "global-risk", "日元融资交易调整影响全球风险资产", "BOJ_NORMALIZATION", "GLOBAL_RISK", ["SP500", "DEXCHUS"], {"IMMEDIATE": "MIXED", "SHORT_TERM": "MIXED", "MEDIUM_TERM": "MIXED"}),
    ("event-09", "china-growth", "信贷与住房支持改善增长预期", "CHINA_STIMULUS", "GROWTH_EXPECTATIONS", ["SP500", "DGS10"], {"IMMEDIATE": "UP", "SHORT_TERM": "UP", "MEDIUM_TERM": "MIXED"}),
    ("event-09", "yuan-repricing", "宽松与增长预期共同影响人民币", "CHINA_STIMULUS", "FX_EXPECTATIONS", ["DEXCHUS", "DTWEXBGS"], {"IMMEDIATE": "MIXED", "SHORT_TERM": "MIXED", "MEDIUM_TERM": "MIXED"}),
    ("event-09", "risk-assets", "政策组合改善风险偏好与权益估值", "CHINA_STIMULUS", "RISK_APPETITE", ["SP500"], {"IMMEDIATE": "UP", "SHORT_TERM": "UP", "MEDIUM_TERM": "MIXED"}),
    ("event-10", "trade-costs", "关税提高进口成本与供应链摩擦", "RECIPROCAL_TARIFFS", "TRADE_COSTS", ["SP500", "DEXCHUS"], {"IMMEDIATE": "SP500_DOWN", "SHORT_TERM": "SP500_DOWN", "MEDIUM_TERM": "MIXED"}),
    ("event-10", "inflation-rates", "关税成本经通胀预期影响利率", "RECIPROCAL_TARIFFS", "INFLATION_EXPECTATIONS", ["DGS10", "DTWEXBGS"], {"IMMEDIATE": "MIXED", "SHORT_TERM": "UP", "MEDIUM_TERM": "MIXED"}),
    ("event-10", "global-growth-risk", "贸易政策不确定性压低全球增长与风险偏好", "RECIPROCAL_TARIFFS", "GLOBAL_GROWTH", ["SP500", "DTWEXBGS", "DEXCHUS"], {"IMMEDIATE": "RISK_OFF", "SHORT_TERM": "RISK_OFF", "MEDIUM_TERM": "MIXED"}),
]


_EVENT_COMPETITORS = {
    "event-01": "同期石油价格战与紧急政策响应可能主导部分资产走势。",
    "event-02": "冲突前能源紧张、后续制裁与政策利率重估会竞争解释。",
    "event-03": "会议前指引与同期通胀数据可能已提前完成部分定价。",
    "event-04": "房地产政策、全球增长与美元周期会同时影响市场。",
    "event-05": "通胀数据与央行流动性措施会改变银行压力的资产表现。",
    "event-06": "全球需求预期与库存变化可能压过名义减产信号。",
    "event-07": "冲突范围未扩大时，初始风险溢价可能迅速回吐。",
    "event-08": "政策退出已被沟通，且美日利差仍受美联储路径主导。",
    "event-09": "财政落实程度与房地产基本面会限制货币支持效果。",
    "event-10": "豁免、谈判与报复措施会改变实际税率和传导方向。",
}


_ACTIVATION_TAG_BY_CHANNEL = {
    "RISK_APPETITE": "RISK_APPETITE",
    "GLOBAL_DEMAND": "GLOBAL_DEMAND",
    "SAFE_HAVEN_DEMAND": "SAFE_HAVEN_DEMAND",
    "ENERGY_SUPPLY": "ENERGY_SUPPLY",
    "INFLATION_EXPECTATIONS": "INFLATION_EXPECTATIONS",
    "RATE_EXPECTATIONS": "RATE_EXPECTATIONS",
    "DISCOUNT_RATE": "DISCOUNT_RATE",
    "DOLLAR_LIQUIDITY": "DOLLAR_LIQUIDITY",
    "BANKING_STRESS": "BANKING_STRESS",
    "RATE_DIFFERENTIAL": "RATE_DIFFERENTIAL",
    "TRADE_COSTS": "TRADE_COSTS",
    "GLOBAL_GROWTH": "GLOBAL_GROWTH",
}

_ACTIVATION_OVERRIDES = {
    "event-01-P-pandemic-safe-haven": {
        "activation_tags": ["LIQUIDITY_STRESS"],
    },
    "event-01-P-pandemic-policy-response": {
        "activation_phases": ["POLICY_RESPONSE"],
        "activation_actions": ["AMPLIFIES"],
        "activation_tags": ["GLOBAL_DEMAND", "LIQUIDITY_STRESS"],
    },
    "event-02-P-sanctions-trade": {
        "activation_phases": ["POLICY_RESPONSE"],
        "activation_actions": ["AMPLIFIES"],
        "activation_tags": ["DOLLAR_LIQUIDITY", "ENERGY_SUPPLY"],
    },
    "event-03-P-growth-expectations": {
        "activation_tags": ["RATE_EXPECTATIONS"],
    },
    "event-04-P-china-growth": {
        "activation_tags": ["CHINA_REOPENING"],
    },
    "event-04-P-commodity-demand": {
        "activation_tags": ["GLOBAL_DEMAND"],
    },
    "event-04-P-yuan-repricing": {
        "activation_tags": ["CHINA_REOPENING"],
    },
    "event-05-P-rate-repricing": {
        "activation_tags": ["RATE_EXPECTATIONS"],
    },
    "event-06-P-oil-supply": {
        "activation_tags": ["ENERGY_SUPPLY"],
    },
    "event-06-P-inflation-pass-through": {
        "activation_tags": ["INFLATION_EXPECTATIONS"],
    },
    "event-06-P-global-growth": {
        "activation_tags": ["RISK_APPETITE"],
    },
    "event-07-P-risk-appetite": {
        "activation_tags": ["GEOPOLITICAL_RISK"],
    },
    "event-07-P-shipping-disruption": {
        "activation_phases": ["SECONDARY_SHOCK"],
        "activation_actions": ["AMPLIFIES"],
        "activation_tags": ["SHIPPING_DISRUPTION", "ENERGY_SUPPLY"],
    },
    "event-08-P-japan-rates": {
        "activation_tags": ["RATE_DIFFERENTIAL"],
    },
    "event-08-P-global-risk": {
        "activation_tags": ["GLOBAL_LIQUIDITY"],
    },
    "event-09-P-china-growth": {
        "activation_tags": ["MONETARY_EASING", "PROPERTY_SUPPORT"],
    },
    "event-09-P-yuan-repricing": {
        "activation_tags": ["MONETARY_EASING"],
    },
    "event-10-P-inflation-rates": {
        "activation_tags": ["INFLATION_EXPECTATIONS"],
    },
}


def _build_path_specs() -> list[dict[str, Any]]:
    sources = {
        event_id: f"mechanism-{event_id.replace('-', '-')}-"
        for event_id in EVENT_CONFIGS
    }
    source_ids = {
        "event-01": "mechanism-event-01-imf-covid-financial",
        "event-02": "mechanism-event-02-fed-ukraine",
        "event-03": "mechanism-event-03-fed-transmission",
        "event-04": "mechanism-event-04-worldbank-china",
        "event-05": "mechanism-event-05-fed-svb-review",
        "event-06": "mechanism-event-06-eia-opec",
        "event-07": "mechanism-event-07-unctad-shipping",
        "event-08": "mechanism-event-08-boj-yen",
        "event-09": "mechanism-event-09-pbc-report",
        "event-10": "mechanism-event-10-imf-tariffs",
    }
    rows: list[dict[str, Any]] = []
    for event_id, slug, name, shock, channel, assets, directions in _PATH_ROWS:
        path_id = f"{event_id}-P-{slug}"
        activation = {
            "activation_phases": ["INITIAL_SHOCK"],
            "activation_actions": ["STARTS"],
            "activation_tags": [_ACTIVATION_TAG_BY_CHANNEL.get(channel, channel)],
        }
        activation.update(_ACTIVATION_OVERRIDES.get(path_id, {}))
        rows.append({
            "path_id": path_id,
            "event_id": event_id,
            "name_zh": name,
            "activation_phases": activation["activation_phases"],
            "activation_actions": activation["activation_actions"],
            "activation_tags": activation["activation_tags"],
            "chain": [shock, channel, f"{event_id.upper()}_{slug.upper().replace('-', '_')}", "|".join(assets)],
            "asset_series_ids": assets,
            "expected_direction": directions,
            "lag": {"minimum": "P0D", "maximum": "P20D"},
            "conditions": [
                "主锚点事实未被官方实质更正。",
                f"{channel} 渠道在所选窗口内仍具经济相关性。",
            ],
            "invalidation_conditions": [
                "政策响应或后续事件成为窗口内主导冲击。",
                _EVENT_COMPETITORS[event_id],
            ],
            "counterevidence": [_EVENT_COMPETITORS[event_id]],
            "mechanism_source_ids": [source_ids[event_id]],
            "selection_status": "CORE_REVIEWED",
            "confirmation_status": "PROPOSED",
            "review_basis": "AI_DESK_REVIEW_NO_HUMAN_CONFIRMATION",
        })
    return rows


CORE_PATH_SPECS = _build_path_specs()

_CONFOUNDER_ROWS = {
    "event-01": ("2020-03-08", "DOMINANT", "同期石油价格战、封控升级和紧急政策响应共同主导中长窗口。"),
    "event-02": ("2022-02-26", "DOMINANT", "持续战事、金融制裁、能源限制与央行路径重估进入 D3 以后窗口。"),
    "event-03": ("2022-03-10", "MATERIAL", "高通胀数据、会前指引和资产负债表沟通已影响利率与美元定价。"),
    "event-04": ("2022-12-08", "MATERIAL", "房地产支持、全球增长预期与美元周期和重新开放政策重叠。"),
    "event-05": ("2023-03-12", "DOMINANT", "Signature Bank 关闭、流动性工具和存款担保改变银行压力路径。"),
    "event-06": ("2023-04-03", "MATERIAL", "全球需求预期、库存变化与成员国产量执行度竞争解释油价。"),
    "event-07": ("2023-10-08", "DOMINANT", "冲突持续升级、地区外溢与后续航运扰动主导较长窗口。"),
    "event-08": ("2024-03-19", "MATERIAL", "政策退出已被预告，美联储路径与美日利差继续主导日元。"),
    "event-09": ("2024-09-24", "MATERIAL", "财政落实、房地产基本面和同期全球利率变化影响政策效果。"),
    "event-10": ("2025-04-03", "DOMINANT", "豁免、报复、谈判与政策调整持续改变实际关税冲击。"),
}


def _build_confounder_configs() -> dict[str, dict[str, Any]]:
    source_by_event = {
        event_id: next(
            row["source_id"]
            for row in MECHANISM_SOURCES
            if event_id in row["source_id"]
        )
        for event_id in EVENT_CONFIGS
    }
    result: dict[str, dict[str, Any]] = {}
    for event_id, (active_from, level, description) in _CONFOUNDER_ROWS.items():
        path_ids = [
            row["path_id"]
            for row in CORE_PATH_SPECS
            if row["event_id"] == event_id
        ]
        result[event_id] = {
            "event_id": event_id,
            "clean_attribution_decision": (
                "CHALLENGE_ONLY"
                if level == "DOMINANT"
                else "WINDOW_DEPENDENT"
            ),
            "reason": description,
            "by_horizon": {
                "T0": "MINOR",
                "D1": "MINOR",
                "D3": "MATERIAL",
                "D5": "MATERIAL",
                "D20": level,
            },
            "items": [{
                "confounder_id": f"{event_id}-C01-overlapping-developments",
                "level": level,
                "active_from": active_from,
                "description": description,
                "affected_path_ids": path_ids,
                "affected_windows": ["D3", "D5", "D20"],
                "evidence_source_ids": [source_by_event[event_id]],
            }],
        }
    return result


CONFOUNDER_CONFIGS = _build_confounder_configs()
