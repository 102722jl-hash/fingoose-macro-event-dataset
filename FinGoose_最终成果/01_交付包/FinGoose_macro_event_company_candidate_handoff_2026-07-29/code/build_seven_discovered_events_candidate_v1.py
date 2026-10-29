from __future__ import annotations

import argparse
import json
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = ROOT / "skills" / "building-auditable-macro-datasets" / "scripts"
import sys

sys.path.insert(0, str(SKILL_SCRIPTS))

from audit_outputs import canonical_sha256, evaluate_candidate_evidence, init_run, write_json
from source_extractors import store_snapshot


RUN_ID = "run-fingoose-seven-events-20260813-001"
DISCOVER_RUN = ROOT / "work" / "skill_research_runs" / "run-fingoose-discover-20260101-20260813-001"


EVENTS = [
    {
        "event_id": "event-11",
        "candidate_id": "candidate-event-ed4447a9d8bd61a0",
        "date": "2026-03-11",
        "title": "IEA成员国实施史上最大规模紧急石油库存释放",
        "region": "全球/中东",
        "publisher": "International Energy Agency",
        "source_url": "https://www.iea.org/news/iea-member-countries-to-carry-out-largest-ever-oil-stock-release-amid-market-disruptions-from-middle-east-conflict",
        "quote": "IEA Member countries to carry out largest ever oil stock release amid market disruptions from Middle East conflict",
        "locator": "official news release heading and opening paragraphs",
        "fact": "32个IEA成员国决定向市场提供4亿桶紧急石油库存，以缓解中东冲突造成的供应中断。",
        "industries": ["石油开采", "炼油", "天然气与LNG", "航运", "航空运输", "化工", "化肥"],
        "companies": [("XOM", "Exxon Mobil", "石油开采"), ("SHEL", "Shell", "石油开采"), ("601857.SH", "中国石油", "石油开采")],
        "shock": "协调释放库存增加短期可用原油供给并压低供应风险溢价",
        "observable": "商业库存、现货升贴水、油轮流量、裂解价差和航煤成本",
    },
    {
        "event_id": "event-12",
        "candidate_id": "candidate-event-78e9e6c476db53c2",
        "date": "2026-03-13",
        "title": "中国发布“十五五”规划纲要",
        "region": "中国",
        "publisher": "中国政府网",
        "source_url": "https://www.gov.cn/yaowen/liebiao/202603/content_7062633.htm",
        "quote": "中华人民共和国国民经济和社会发展第十五个五年（2026－2030年）规划纲要，根据《中共中央关于制定国民经济和社会发展第十五个五年规划的建议》编制，主要阐明国家战略意图，明确政府工作重点，引导规范社会主体行为。",
        "locator": "HTML正文，第245行，目录后总纲第一段",
        "fact": "国家级五年规划正式确定现代化产业体系、科技自立自强、扩大内需和绿色转型等方向。",
        "industries": ["人工智能与算力", "半导体", "高端装备", "新能源", "电网与储能", "消费", "医疗养老"],
        "companies": [("688981.SH", "中芯国际", "半导体"), ("000977.SZ", "浪潮信息", "人工智能与算力"), ("300750.SZ", "宁德时代", "电网与储能")],
        "shock": "中期国家规划改变产业政策预期、资本开支方向和公共资源配置",
        "observable": "专项规划、财政资金、重大项目、产业投资和订单落地",
    },
    {
        "event_id": "event-13",
        "candidate_id": "candidate-event-9598a2c6d32893ad",
        "date": "2026-06-16",
        "title": "日本央行将政策利率提高至约1.0%",
        "region": "日本",
        "publisher": "Bank of Japan",
        "source_url": "https://www.boj.or.jp/en/mopo/mpmdeci/mpr_2026/k260616a.pdf",
        "quote": "The Bank will encourage the uncollateralized overnight call rate to remain at around 1.0 percent.",
        "locator": "PDF page 1, paragraph 1, money market operations guideline",
        "fact": "日本央行将无担保隔夜拆借利率目标提高至约1.0%，并调整相关操作安排。",
        "industries": ["银行", "保险", "证券", "房地产", "航空运输", "汽车", "电子"],
        "companies": [("8306.T", "Mitsubishi UFJ Financial Group", "银行"), ("8316.T", "Sumitomo Mitsui Financial Group", "银行"), ("7203.T", "Toyota Motor", "汽车")],
        "shock": "政策利率上升抬高日元融资成本并改变收益率曲线与汇率预期",
        "observable": "隔夜利率、国债收益率曲线、日元汇率、净息差和融资成本",
    },
    {
        "event_id": "event-14",
        "candidate_id": "candidate-event-769c8372b781c372",
        "date": "2026-03-16",
        "title": "中国公布约4%赤字率及更加积极的财政政策",
        "region": "中国",
        "publisher": "中华人民共和国财政部",
        "source_url": "https://www.mof.gov.cn/zhengwuxinxi/caizhengxinwen/202603/t20260316_3985331.htm",
        "quote": "全国一般公共预算支出规模达到300100亿元，比上年增长4.4%。赤字率按照4%左右安排，全国财政赤字规模58900亿元、比上年增加2300亿元。",
        "locator": "HTML正文，第334段，2026年继续实施更加积极的财政政策第一项",
        "fact": "预算报告安排约4%的赤字率，并以一般公共预算、特别国债和地方专项债实施更加积极的财政政策。",
        "industries": ["建筑与基础设施", "工程机械", "建材", "银行", "消费品", "汽车", "家电"],
        "companies": [("601668.SH", "中国建筑", "建筑与基础设施"), ("600031.SH", "三一重工", "工程机械"), ("000786.SZ", "北新建材", "建材")],
        "shock": "更高财政赤字和政府债券发行扩大公共需求并改变资金供给",
        "observable": "政府债发行、财政支出进度、基建投资、设备订单和社零增速",
    },
    {
        "event_id": "event-15",
        "candidate_id": "candidate-event-759c846182a345fa",
        "date": "2026-02-27",
        "title": "人民银行将远期售汇风险准备金率降至0",
        "region": "中国",
        "publisher": "中国人民银行",
        "source_url": "https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2026022708004828142/index.html",
        "quote": "中国人民银行决定自2026年3月2日起，将远期售汇业务的外汇风险准备金率从20%下调至0。",
        "locator": "HTML正文，第319行，正文第一段",
        "fact": "中国人民银行决定将远期售汇业务的外汇风险准备金率下调为0。",
        "industries": ["银行", "证券", "航空运输", "石油石化", "电子", "家用电器", "汽车"],
        "companies": [("601988.SH", "中国银行", "银行"), ("601111.SH", "中国国航", "航空运输"), ("000333.SZ", "美的集团", "家用电器")],
        "shock": "准备金成本取消降低远期售汇交易成本并影响企业套保与人民币预期",
        "observable": "远期点、套保成交、银行衍生品业务、人民币汇率和进口成本",
    },
    {
        "event_id": "event-16",
        "candidate_id": "candidate-event-b625392b827934d5",
        "date": "2026-03-04",
        "title": "欧盟提出《工业加速法案》",
        "region": "欧盟",
        "publisher": "European Commission",
        "source_url": "https://ec.europa.eu/commission/presscorner/api/files/document/print/en/ip_26_515/IP_26_515_EN.pdf",
        "quote": "the IAA introduces targeted and proportionate 'Made in EU' and / or low-carbon requirements for public procurement and public support schemes.",
        "locator": "PDF page 1, paragraph beginning 'Building on the recommendations of the Draghi report'",
        "fact": "欧盟委员会提出工业加速法案，将欧洲制造和低碳偏好引入公共支持与采购框架。",
        "industries": ["钢铁", "水泥", "铝", "汽车", "电池", "光伏", "风电设备"],
        "companies": [("MT.AS", "ArcelorMittal", "钢铁"), ("VOW3.DE", "Volkswagen", "汽车"), ("300750.SZ", "宁德时代", "电池")],
        "shock": "本地制造与低碳偏好改变公共采购准入和战略产业投资条件",
        "observable": "立法进度、采购规则、本地含量、外资项目条件和订单份额",
    },
    {
        "event_id": "event-17",
        "candidate_id": "candidate-event-2254e08009f1ac4c",
        "date": "2026-04-10",
        "title": "证监会发布深化创业板改革意见",
        "region": "中国",
        "publisher": "中国证券监督管理委员会",
        "source_url": "http://www.csrc.gov.cn/csrc/c100028/c7625370/content.shtml",
        "quote": "增设创业板第四套上市标准，为新兴产业和未来产业领域优质创新创业企业提供更好金融服务。建立IPO预先审阅机制。",
        "locator": "HTML正文，第181行，第二项改革举措",
        "fact": "证监会发布深化创业板改革意见，涉及上市标准、预先审阅、再融资、做市和ETF交易机制。",
        "industries": ["证券", "创投", "信息技术", "新能源", "高端装备", "新消费", "金融信息服务"],
        "companies": [("300059.SZ", "东方财富", "证券"), ("600030.SH", "中信证券", "证券"), ("300033.SZ", "同花顺", "金融信息服务")],
        "shock": "发行、再融资和交易制度改革改变创新企业融资可得性与中介业务机会",
        "observable": "IPO受理、再融资、做市覆盖、ETF成交和券商投行业务收入",
    },
]


COMPANY_POOLS = {
    "石油开采": [("601857.SH", "中国石油"), ("600938.SH", "中国海油"), ("XOM", "Exxon Mobil")],
    "炼油": [("600028.SH", "中国石化"), ("000703.SZ", "恒逸石化"), ("002493.SZ", "荣盛石化")],
    "天然气与LNG": [("600803.SH", "新奥股份"), ("600256.SH", "广汇能源"), ("603393.SH", "新天然气")],
    "航运": [("601919.SH", "中远海控"), ("601872.SH", "招商轮船"), ("600026.SH", "中远海能")],
    "航空运输": [("601111.SH", "中国国航"), ("600115.SH", "中国东航"), ("600029.SH", "南方航空")],
    "化工": [("600309.SH", "万华化学"), ("002648.SZ", "卫星化学"), ("600426.SH", "华鲁恒升")],
    "化肥": [("600096.SH", "云天化"), ("000792.SZ", "盐湖股份"), ("600470.SH", "六国化工")],
    "人工智能与算力": [("000977.SZ", "浪潮信息"), ("603019.SH", "中科曙光"), ("688256.SH", "寒武纪")],
    "半导体": [("688981.SH", "中芯国际"), ("603501.SH", "豪威集团"), ("002371.SZ", "北方华创")],
    "高端装备": [("600031.SH", "三一重工"), ("000157.SZ", "中联重科"), ("601100.SH", "恒立液压")],
    "新能源": [("601012.SH", "隆基绿能"), ("002594.SZ", "比亚迪"), ("600905.SH", "三峡能源")],
    "电网与储能": [("600406.SH", "国电南瑞"), ("000400.SZ", "许继电气"), ("600089.SH", "特变电工")],
    "消费": [("600519.SH", "贵州茅台"), ("000858.SZ", "五粮液"), ("600887.SH", "伊利股份")],
    "医疗养老": [("600276.SH", "恒瑞医药"), ("300760.SZ", "迈瑞医疗"), ("000963.SZ", "华东医药")],
    "银行": [("601398.SH", "工商银行"), ("601988.SH", "中国银行"), ("600036.SH", "招商银行")],
    "保险": [("601318.SH", "中国平安"), ("601601.SH", "中国太保"), ("601628.SH", "中国人寿")],
    "证券": [("600030.SH", "中信证券"), ("601688.SH", "华泰证券"), ("601211.SH", "国泰海通")],
    "房地产": [("000002.SZ", "万科A"), ("600048.SH", "保利发展"), ("001979.SZ", "招商蛇口")],
    "汽车": [("601633.SH", "长城汽车"), ("600104.SH", "上汽集团"), ("000625.SZ", "长安汽车")],
    "电子": [("002475.SZ", "立讯精密"), ("000725.SZ", "京东方A"), ("601138.SH", "工业富联")],
    "建筑与基础设施": [("601668.SH", "中国建筑"), ("601390.SH", "中国中铁"), ("601186.SH", "中国铁建")],
    "工程机械": [("600031.SH", "三一重工"), ("000157.SZ", "中联重科"), ("000425.SZ", "徐工机械")],
    "建材": [("000786.SZ", "北新建材"), ("600585.SH", "海螺水泥"), ("002271.SZ", "东方雨虹")],
    "消费品": [("600519.SH", "贵州茅台"), ("000858.SZ", "五粮液"), ("600887.SH", "伊利股份")],
    "家电": [("000333.SZ", "美的集团"), ("000651.SZ", "格力电器"), ("600690.SH", "海尔智家")],
    "家用电器": [("000333.SZ", "美的集团"), ("000651.SZ", "格力电器"), ("600690.SH", "海尔智家")],
    "石油石化": [("600028.SH", "中国石化"), ("601857.SH", "中国石油"), ("002493.SZ", "荣盛石化")],
    "钢铁": [("600019.SH", "宝钢股份"), ("000932.SZ", "华菱钢铁"), ("600010.SH", "包钢股份")],
    "水泥": [("600585.SH", "海螺水泥"), ("000877.SZ", "天山股份"), ("600801.SH", "华新水泥")],
    "铝": [("601600.SH", "中国铝业"), ("000807.SZ", "云铝股份"), ("600219.SH", "南山铝业")],
    "电池": [("300750.SZ", "宁德时代"), ("002074.SZ", "国轩高科"), ("300014.SZ", "亿纬锂能")],
    "光伏": [("601012.SH", "隆基绿能"), ("600438.SH", "通威股份"), ("300274.SZ", "阳光电源")],
    "风电设备": [("002202.SZ", "金风科技"), ("601615.SH", "明阳智能"), ("688349.SH", "三一重能")],
    "创投": [("600783.SH", "鲁信创投"), ("000532.SZ", "华金资本"), ("600895.SH", "张江高科")],
    "信息技术": [("600588.SH", "用友网络"), ("002230.SZ", "科大讯飞"), ("000977.SZ", "浪潮信息")],
    "新消费": [("300999.SZ", "金龙鱼"), ("603288.SH", "海天味业"), ("002507.SZ", "涪陵榨菜")],
    "金融信息服务": [("300033.SZ", "同花顺"), ("600570.SH", "恒生电子"), ("300059.SZ", "东方财富")],
}


EVENT_COMPANY_POOLS = {
    "event-13": {
        "银行": [("8306.T", "Mitsubishi UFJ Financial Group"), ("8316.T", "Sumitomo Mitsui Financial Group"), ("8411.T", "Mizuho Financial Group")],
        "保险": [("8766.T", "Tokio Marine Holdings"), ("8725.T", "MS&AD Insurance Group"), ("8630.T", "Sompo Holdings")],
        "证券": [("8604.T", "Nomura Holdings"), ("8601.T", "Daiwa Securities Group"), ("8473.T", "SBI Holdings")],
        "房地产": [("8801.T", "Mitsui Fudosan"), ("8802.T", "Mitsubishi Estate"), ("8830.T", "Sumitomo Realty & Development")],
        "航空运输": [("9201.T", "Japan Airlines"), ("9202.T", "ANA Holdings"), ("9204.T", "Skymark Airlines")],
        "汽车": [("7203.T", "Toyota Motor"), ("7267.T", "Honda Motor"), ("7201.T", "Nissan Motor")],
        "电子": [("6758.T", "Sony Group"), ("6501.T", "Hitachi"), ("6702.T", "Fujitsu")],
    },
    "event-16": {
        "钢铁": [("MT.AS", "ArcelorMittal"), ("TKA.DE", "thyssenkrupp"), ("SSAB-A.ST", "SSAB")],
        "水泥": [("HEI.DE", "Heidelberg Materials"), ("HOLN.SW", "Holcim"), ("CRH", "CRH")],
        "铝": [("NHY.OL", "Norsk Hydro"), ("CSTM", "Constellium"), ("KALU.DE", "Kaiser Aluminum Europe exposure")],
        "汽车": [("VOW3.DE", "Volkswagen"), ("MBG.DE", "Mercedes-Benz Group"), ("BMW.DE", "BMW")],
        "电池": [("UMI.BR", "Umicore"), ("VAR1.DE", "Varta"), ("BAS.DE", "BASF")],
        "光伏": [("S92.DE", "SMA Solar Technology"), ("MBTN.SW", "Meyer Burger Technology"), ("ENR.DE", "Siemens Energy")],
        "风电设备": [("VWS.CO", "Vestas Wind Systems"), ("NDX1.DE", "Nordex"), ("ENR.DE-WIND", "Siemens Gamesa exposure via Siemens Energy")],
    },
}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8", newline="\n")


def horizons(subject: str, shock: str, observable: str) -> dict[str, str]:
    return {
        "IMMEDIATE": f"公告后0至1个交易日，{shock}首先进入预期和价格；观察{observable}的即时变化。",
        "SHORT_TERM": f"公告后2至20个交易日，{subject}开始调整订单、套保、融资或库存决策；观察{observable}能否连续确认。",
        "MEDIUM_TERM": f"公告后1至4个季度，政策执行和企业经营兑现决定影响是否持续；以财报、项目落地及{observable}复核，不从短窗外推。",
    }


def mechanism_nodes(event_id: str, industry: str, evidence_id: str, shock: str, observable: str) -> list[dict[str, Any]]:
    steps = [
        ("SHOCK", f"官方事件冲击：{shock}。"),
        ("CHANNEL", f"冲击通过成本、需求、融资或准入渠道传导至{industry}。"),
        ("OPERATING_VARIABLE", f"经营变量转为订单、价格、销量、库存或资产负债结构变化；跟踪{observable}。"),
        ("FINANCIAL_VARIABLE", "经营变化进一步映射为收入、毛利率、费用、现金流或信用成本变化。"),
        ("VALUATION_EXPECTATION", "投资者据此修正盈利预期、风险溢价和估值，但方向取决于暴露净额。"),
        ("MARKET_VALIDATION", "T0/D1/D3/D5/D20窗口仅用于检验表现是否与机制一致，不单独证明因果。"),
        ("COUNTEREVIDENCE", "若执行弱于预期、反向政策或公司特有因素主导，则原传导判断失效或减弱。"),
    ]
    result = []
    for index, (kind, statement) in enumerate(steps, 1):
        result.append({
            "node_id": f"{event_id}-{industry}-node-{index}",
            "node_type": kind,
            "statement_zh": statement,
            "premise_node_ids": [] if index == 1 else [f"{event_id}-{industry}-node-{index-1}"],
            "evidence_ids": [evidence_id] if index == 1 else [],
            "status": "PROPOSED",
        })
    return result


def market_record(event_id: str, scope_id: str, security: str, benchmark: str) -> dict[str, Any]:
    return {
        "market_window_id": f"market-{event_id}-{scope_id}",
        "event_id": event_id,
        "security_id": security,
        "market_benchmark_id": benchmark,
        "industry_benchmark_id": None,
        "status": "DATA_MISSING",
        "missing_reason_codes": ["POST_EVENT_PRICE_SERIES_NOT_ACQUIRED", "INDUSTRY_BENCHMARK_NOT_ACQUIRED"],
        "formula": "company_value/company_T_MINUS_1-1; market_relative=company_return-market_return; industry_relative=company_return-industry_return",
        "endpoints": {key: {"date": None, "raw_value": None, "return": None} for key in ("T_MINUS_1", "T0", "D1", "D3", "D5", "D20")},
        "data_source": None,
        "causal_use": "VALIDATION_ONLY",
    }


def event_reasoning_chain(event: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    event_id = event["event_id"]
    evidence_id = evidence["evidence_id"]
    node_ids = [f"{event_id}-fact", f"{event_id}-mechanism", f"{event_id}-market"]
    nodes = [
        {"node_id": node_ids[0], "node_type": "SOURCE_FACT", "statement_class": "SOURCE_FACT", "statement_zh": event["fact"], "evidence_ids": [evidence_id], "premise_node_ids": [], "status": "VERIFIED_SOURCE"},
        {"node_id": node_ids[1], "node_type": "RESEARCH_INFERENCE", "statement_class": "RESEARCH_INFERENCE", "statement_zh": event["shock"], "evidence_ids": [], "premise_node_ids": [node_ids[0]], "status": "SUPPORTED_INFERENCE"},
        {"node_id": node_ids[2], "node_type": "MARKET_VALIDATION", "statement_class": "CALCULATED_FACT", "statement_zh": "行情数据缺失；窗口表现即使取得也只用于机制一致性验证。", "evidence_ids": [], "premise_node_ids": [node_ids[1]], "status": "CALCULATED_ONLY"},
    ]
    registry = [{
        "evidence_id": evidence_id, "publisher": evidence["publisher"], "published_at": evidence["published_at"],
        "original_quote": evidence["original_quote"], "locator": evidence["locator"], "source_url": evidence["source_url"],
        "snapshot_sha256": evidence["snapshot_sha256"], "supports_node_ids": [node_ids[0]], "missing": False,
    }]
    graph = {
        "task_type": "EVENT_ANALYSIS", "scope_id": event_id, "nodes": nodes,
        "edges": [{"edge_id": f"{event_id}-edge-1", "from_node_id": node_ids[0], "to_node_id": node_ids[1]}, {"edge_id": f"{event_id}-edge-2", "from_node_id": node_ids[1], "to_node_id": node_ids[2]}],
        "root_node_ids": [node_ids[0]], "main_path_node_ids": node_ids, "side_branch_node_ids": [],
        "final_node_id": node_ids[2], "closure_gate": {"status": "CLOSED", "blockers": [], "graph_errors": []},
    }
    return {
        "reasoning_chain_version": "v1", "parent_chain_refs": [], "evidence_registry": registry,
        "reasoning_chain": graph,
        "conclusion_lineage": {"scope_id": event_id, "final_node_id": node_ids[2], "main_path_node_ids": node_ids, "evidence_ids": [evidence_id], "closure_status": "CLOSED"},
    }


def make_unified(event: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    event_id = event["event_id"]
    evidence_id = evidence["evidence_id"]
    event_horizons = horizons("相关行业和公司", event["shock"], event["observable"])
    industries = []
    for index, industry in enumerate(event["industries"], 1):
        mapping_id = f"{event_id}-industry-{index:02d}"
        industries.append({
            "event_industry_mapping_id": mapping_id,
            "event_id": event_id,
            "industry_id": f"industry-{sha256(industry.encode('utf-8')).hexdigest()[:10]}",
            "industry_name_zh": industry,
            "display_name_zh": industry,
            "impact_direction": "MIXED",
            "impact_tier": "CORE" if index <= 3 else "SECONDARY",
            "observable_driver_zh": event["observable"],
            "industry_operating_variable_zh": f"{industry}的订单、销量、定价、库存和产能利用率",
            "industry_financial_variable_zh": f"{industry}的收入、毛利率、现金流和资本开支",
            "condition_zh": "官方措施按公告路径实施且没有更强反向冲击主导。",
            "invalidation_condition_zh": "执行被推迟、撤回，或需求、汇率、商品价格等反向因素占主导。",
            "counterevidence_zh": ["同期宏观与公司特有因素可能解释行情", "政策公告不等于执行效果"],
            "horizon_directions": {"IMMEDIATE": "MIXED", "SHORT_TERM": "MIXED", "MEDIUM_TERM": "MIXED"},
            "horizon_analysis": horizons(industry, event["shock"], event["observable"]),
            "mechanism_nodes": mechanism_nodes(event_id, industry, evidence_id, event["shock"], event["observable"]),
            "market_window": market_record(event_id, mapping_id, f"INDUSTRY:{industry}", "MARKET:REGIONAL"),
            "evidence_ids": [evidence_id],
            "review_status": "NEEDS_HUMAN_REVIEW",
            "formal_ready": False,
            "causal_attribution_allowed": False,
        })
    companies = []
    industry_by_name = {row["industry_name_zh"]: row for row in industries}
    pools = EVENT_COMPANY_POOLS.get(event_id, COMPANY_POOLS)
    selected_companies = [
        (code, name, industry)
        for industry in event["industries"]
        for code, name in pools[industry]
    ]
    for index, (code, name, industry) in enumerate(selected_companies, 1):
        parent = industry_by_name[industry]
        companies.append({
            "mapping_id": f"{event_id}-company-{index:02d}",
            "event_id": event_id,
            "industry_id": parent["industry_id"],
            "company_code": code,
            "company_name": name,
            "industry": industry,
            "business_exposure_zh": f"事前业务暴露：{name}的主营业务直接处于{industry}渠道，选样不依据事件后涨跌。",
            "mechanism_zh": f"{event['shock']}，再通过{industry}经营变量影响{name}的收入、利润率和现金流。",
            "horizon_analysis": horizons(name, event["shock"], event["observable"]),
            "horizon_directions": {"IMMEDIATE": "MIXED", "SHORT_TERM": "MIXED", "MEDIUM_TERM": "MIXED"},
            "relative_return": {"status": "DATA_MISSING", "value": None, "reason": "POST_EVENT_PRICE_SERIES_NOT_ACQUIRED"},
            "market_window": market_record(event_id, code.replace(".", "-"), code, "MARKET:REGIONAL"),
            "confounders": ["同期市场风险偏好", "行业价格与汇率变化", "公司公告和财报因素"],
            "counterevidence": [{
                "claim_zh": "若同业无一致反应或公司基本面反向变化，事件解释力下降。",
                "effect_on_thesis": "LIMITS_DIRECT_ATTRIBUTION",
                "affected_horizons": ["IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM"],
            }],
            "evidence_ids": [evidence_id],
            "review_status": "NEEDS_HUMAN_REVIEW",
            "formal_ready": False,
            "causal_attribution_allowed": False,
        })
    qa_types = [
        ("EVIDENCE_QUERY", "官方来源确认了什么？", event["fact"], [evidence_id], [f"{event_id}-fact"]),
        ("MECHANISM_STAGE", "三个阶段的传导有何区别？", "即时阶段反映预期定价，短期阶段观察经营决策调整，中期阶段核验执行与财报兑现。", [evidence_id], [f"{event_id}-mechanism"]),
        ("MARKET_VALIDATION", "行情能否证明事件因果？", "不能。当前行情为DATA_MISSING；即使窗口齐全也只验证表现或机制一致性，因果结论仍为ABSTAIN。", [], [f"{event_id}-market"]),
        ("INDUSTRY_COMPANY", "哪些行业和公司具有事前暴露？", f"重点行业包括{'、'.join(event['industries'])}；每个行业选择3家公司，共{len(selected_companies)}家，均依据事件前主营业务与行业暴露选取，而非事件后涨跌。", [evidence_id], [row["industry_id"] for row in industries] + [code for code, _, _ in selected_companies]),
    ]
    qa = []
    for index, (kind, question, answer, evidence_ids, refs) in enumerate(qa_types, 1):
        qa.append({
            "case_id": f"{event_id}-qa-{index:02d}", "event_id": event_id, "qa_type": kind,
            "task_type": "EVENT_QA", "task_label_zh": kind, "question_zh": question,
            "direct_answer_zh": answer, "evidence_ids": evidence_ids, "reference_ids": refs,
            "answer": {"task_answer": {"direct_answer_zh": answer}},
            "review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False,
        })
    causal = {
        "status": "NOT_IDENTIFIED", "causal_attribution_allowed": False, "causal_conclusion": "ABSTAIN",
        "method": None, "gate_results": {},
        "unmet_conditions": ["行情窗口不完整", "行业基准缺失", "未定义比较组", "未通过前趋势与稳健性检验"],
        "confounders": ["同期宏观消息", "行业供需变化", "公司特有公告"],
        "counterevidence": ["短窗行情方向可能与机制不一致"],
        "boundary_zh": "该记录仅描述官方事实与候选机制，行情不能单独证明因果，结论保持ABSTAIN。",
    }
    return {
        "dataset_version": "fingoose-unified-sft-v1-candidate-seven-events",
        "event_id": event_id,
        "event": {
            "event_id": event_id, "candidate_event_id": event["candidate_id"], "title_zh": event["title"],
            "region_zh": event["region"], "anchor_at": event["date"] + "T00:00:00+00:00",
            "published_at": evidence["published_at"], "source_fact_zh": event["fact"],
            "dual_clock": {"anchor_at": event["date"] + "T00:00:00+00:00", "published_at": evidence["published_at"], "temporal_role": "AS_OF_EVIDENCE"},
            "milestones": [{"milestone_id": f"{event_id}-milestone-01", "occurred_at": event["date"] + "T00:00:00+00:00", "statement_zh": event["fact"], "evidence_ids": [evidence_id]}],
            "transmission_mechanism_zh": event["shock"], "horizon_analysis": event_horizons,
            "invalidation_conditions": ["官方撤回或实质修正", "政策执行未落地", "反向冲击占主导"],
            "review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False,
            "reasoning_chain": event_reasoning_chain(event, evidence),
        },
        "industries": industries,
        "companies": companies,
        "qa": qa,
        "research_content": {
            "schema_version": "research-content-v1", "event_id": event_id, "title_zh": event["title"],
            "source_facts": [{"node_id": f"{event_id}-fact", "statement_zh": event["fact"], "occurred_at": event["date"], "first_public_at": evidence["published_at"], "evidence_ids": [evidence_id], "evidence_status": "GATES_PASSED", "phase": "INITIAL_SHOCK"}],
            "macro_mechanism": {"summary_zh": event["shock"], "paths": [event["shock"]]},
            "horizon_analysis": {key: {"summary_zh": value, "impact_rows": [], "mechanism_node_ids": [], "evidence_ids": [evidence_id]} for key, value in event_horizons.items()},
            "market_validation": [market_record(event_id, "event", "MACRO:BASKET", "MARKET:REGIONAL")],
            "industry_impacts": industries, "company_impacts": companies, "qa_sections": qa,
            "evidence_registry": [evidence], "main_path_node_ids": [f"{event_id}-fact", f"{event_id}-mechanism", f"{event_id}-market"],
            "precondition_node_ids": [], "statement_by_node_id": {f"{event_id}-fact": event["fact"], f"{event_id}-mechanism": event["shock"], f"{event_id}-market": "行情只作验证且当前数据缺失。"},
            "boundaries": {"causal_claim_allowed": False, "market_is_validation_only": True, "review_status": "NEEDS_HUMAN_REVIEW", "limitations_zh": causal["boundary_zh"]},
            "review_state": {"formal_ready": False, "review_status": "NEEDS_HUMAN_REVIEW", "sha_gate": "DEFERRED"},
            "answer_evidence_ids": [evidence_id], "primary_answer_evidence_ids": [evidence_id],
        },
        "causal_assessment": causal,
        "lineage": {"discover_run_id": DISCOVER_RUN.name, "candidate_event_id": event["candidate_id"], "evidence_ids": [evidence_id]},
        "review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--run-id", default=RUN_ID)
    parser.add_argument("--refresh-existing", action="store_true")
    args = parser.parse_args()
    run_root = ROOT / "work" / "skill_research_runs"
    run_dir = run_root / args.run_id
    resume_incomplete = run_dir.exists() and (
        not (run_dir / "acquisition_summary.json").exists() or args.refresh_existing
    )
    if run_dir.exists() and not resume_incomplete:
        raise SystemExit(f"run already exists: {run_dir}")
    request = {
        "mode": "selected-discover-batch", "requested_at": datetime.now(timezone.utc).isoformat(),
        "source_discover_run": str(DISCOVER_RUN), "selected_candidate_count": 7,
        "selection_authority": "USER_SELECTED_ALL", "NEEDS_HUMAN_REVIEW": True, "formal_ready": False,
    }
    if not resume_incomplete:
        init_run(run_root, run_id=args.run_id, request=request)
    for source_name, target_name in (("profile.json", "profile.json"), ("base_dataset_config.json", "base_dataset_config.json"), ("base_training_config.json", "base_training_config.json"), ("base_unified_events.jsonl", "base_unified_events.jsonl")):
        source = ROOT / "work" / "skill_research_runs" / "run-fingoose-golden-001" / source_name
        shutil.copy2(source, run_dir / target_name)
    profile = json.loads((run_dir / "profile.json").read_text(encoding="utf-8"))
    profile["project_root"] = "../../.."
    write_json(run_dir / "profile.json", profile)
    discovery = [json.loads(line) for line in (DISCOVER_RUN / "discovery_candidates_deduplicated.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    write_jsonl(run_dir / "discovery_candidates.jsonl", discovery)
    shutil.copy2(DISCOVER_RUN / "search_audit.jsonl", run_dir / "search_audit.jsonl")
    statuses: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    accepted_evidence: list[dict[str, Any]] = []
    rejected_evidence: list[dict[str, Any]] = []
    content_candidates: list[dict[str, Any]] = []
    accepted_content: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    for event in EVENTS:
        raw_path = args.raw_dir / f"{event['event_id']}.bin"
        meta_path = args.raw_dir / f"{event['event_id']}.meta.json"
        if not raw_path.is_file() or raw_path.stat().st_size == 0 or not meta_path.is_file():
            reason = "ACCESS_RESTRICTED"
            statuses.append({
                "event_id": event["event_id"], "candidate_event_id": event["candidate_id"],
                "title_zh": event["title"], "status": "QUARANTINED", "reason_codes": [reason],
                "evidence_count": 0, "industry_count": 0, "company_count": 0, "qa_count": 0,
                "market_status": "NOT_EVALUATED", "market_missing_reasons": ["SOURCE_EVENT_QUARANTINED"],
                "review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False,
            })
            quarantine.append({"event_id": event["event_id"], "quarantine_reasons": [reason]})
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
        body = raw_path.read_bytes()
        snapshot = store_snapshot(run_dir, source_url=event["source_url"], content_bytes=body, content_type=meta.get("content_type") or "application/octet-stream", retrieved_at=meta["retrieved_at"])
        evidence_id = f"evidence-{event['event_id']}-{snapshot['snapshot_sha256'][:12]}"
        evidence = {
            "evidence_id": evidence_id, "event_id": event["event_id"], "statement_class": "SOURCE_FACT",
            "source_url": event["source_url"], "publisher": event["publisher"],
            "published_at": event["date"] + "T00:00:00+00:00", "anchor_at": event["date"] + "T23:59:59+00:00",
            "retrieved_at": meta["retrieved_at"], "original_quote": event["quote"], "locator": event["locator"],
            "source_tier": "T1", "supports_node_ids": [f"{event['event_id']}-fact"],
            "declared_role": "AS_OF_EVIDENCE", "temporal_role": "AS_OF_EVIDENCE",
            "acceptance_status": "CANDIDATE", "acceptance_reason": "PENDING_GATES", **snapshot,
            "review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False,
        }
        result = evaluate_candidate_evidence(evidence)
        evidence["acceptance_status"] = "ACCEPTED" if result["accepted"] else "REJECTED"
        evidence["acceptance_reason"] = result["reason"]
        candidates.append(deepcopy(evidence))
        if not result["accepted"]:
            rejected_evidence.append(evidence)
            quarantine.append({"event_id": event["event_id"], "quarantine_reasons": [result["reason"]]})
            statuses.append({"event_id": event["event_id"], "status": "QUARANTINED", "reason_codes": [result["reason"]]})
            continue
        accepted_evidence.append(evidence)
        unified = make_unified(event, evidence)
        content = {"event_id": event["event_id"], "operation": "UPSERT", "unified_event": unified, "evidence_ids": [evidence_id], "content_sha256": canonical_sha256(unified), "closure_status": "CLOSED", "errors": [], "warnings": []}
        content_candidates.append(deepcopy(content))
        accepted_content.append(content)
        statuses.append({
            "event_id": event["event_id"], "candidate_event_id": event["candidate_id"], "title_zh": event["title"],
            "status": "ACCEPTED_CONTENT_FROZEN", "evidence_count": 1, "industry_count": len(unified["industries"]),
            "company_count": len(unified["companies"]), "qa_count": len(unified["qa"]), "market_status": "DATA_MISSING",
            "market_missing_reasons": ["POST_EVENT_PRICE_SERIES_NOT_ACQUIRED", "INDUSTRY_BENCHMARK_NOT_ACQUIRED"],
            "review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False,
        })
    write_jsonl(run_dir / "evidence_candidates.jsonl", candidates)
    write_jsonl(run_dir / "accepted_evidence.jsonl", accepted_evidence)
    write_jsonl(run_dir / "rejected_evidence.jsonl", rejected_evidence)
    write_jsonl(run_dir / "content_candidates.jsonl", content_candidates)
    write_jsonl(run_dir / "accepted_content.jsonl", accepted_content)
    write_jsonl(run_dir / "quarantine.jsonl", quarantine)
    write_jsonl(run_dir / "event_processing_status.jsonl", statuses)
    write_json(run_dir / "acquisition_summary.json", {"run_id": args.run_id, "selected": 7, "accepted": len(accepted_content), "quarantined": len(quarantine), "NEEDS_HUMAN_REVIEW": True, "formal_ready": False})
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
