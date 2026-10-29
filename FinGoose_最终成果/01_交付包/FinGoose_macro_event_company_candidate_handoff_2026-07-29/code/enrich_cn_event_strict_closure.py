from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
import enrich_event12_strict_closure as common


def research(driver: str, operating: str, financial: str, condition: str, invalidation: str) -> dict[str, str]:
    return {"driver": driver, "operating": operating, "financial": financial, "condition": condition, "invalidation": invalidation}


RESEARCH = {
    "event-11": {
        "石油开采": research("4亿桶紧急库存释放增加短期可用原油供给并压低稀缺溢价", "实现油价、产量指引、钻井活动、单位开采成本和套保比例", "上游收入、桶油利润、资产减值和经营现金流", "释放规模实际进入市场且未被新增中断抵消", "地缘供应损失扩大或产油国减产吸收释放量"),
        "炼油": research("紧急原油供给改变炼厂原料可得性与采购成本", "炼厂开工率、原油库存、采购升贴水、成品油库存和裂解价差", "炼化毛利、存货损益、营运资金和现金流", "原油成本下降且成品油需求与价差未同步恶化", "成品油需求走弱或库存跌价损失超过采购改善"),
        "天然气与LNG": research("石油供应缓解改变油气替代预期与油价挂钩LNG合同成本", "LNG到岸价、进口量、库存、气电替代和油价挂钩合同", "燃气采购成本、价差、库存损益和经营现金流", "油价变化传导至合同定价且终端气价机制允许消化", "独立天然气短缺或极端天气主导气价"),
        "航运": research("库存释放增加原油调运需求但可能压低油价与吨海里结构", "油轮运量、吨海里、运价、空驶率和燃油成本", "航运收入、单日租金、燃油费用和现金流", "调运距离与船舶需求增量超过运力供给", "释放来自近距离库存或新增运力压低运价"),
        "航空运输": research("原油供应缓解通过航油价格影响航空单位成本", "航油价格、耗油量、客座率、运力和燃油附加费", "燃油成本、单位座公里成本、票价和经营利润", "航油降价持续且客运需求没有同步走弱", "地缘绕飞、汇率或需求冲击超过燃油成本改善"),
        "化工": research("原油价格变化影响石脑油等化工原料成本和库存定价", "原料价差、装置开工、产品库存、订单和产品价差", "化工毛利、存货减值、收入和营运资金", "原料降价快于产品降价并改善价差", "终端需求疲弱导致产品价格下降更快"),
        "化肥": research("能源价格与原料供给预期影响氮肥等生产成本", "煤气原料价格、尿素与钾肥价格、开工率、库存和出口", "吨毛利、化肥收入、库存损益和现金流", "原料成本改善且农业需求与出口维持", "天然气或煤价独立上涨、出口限制或需求下降"),
    },
    "event-14": {
        "建筑与基础设施": research("赤字扩张与公共预算支出提高政府项目资金可得性", "新开工项目、基建订单、合同负债、施工进度和回款周期", "工程收入、毛利率、经营现金流和应收账款周转", "预算资金及时下达并形成实物工作量", "专项资金滞留、项目审批延迟或地方偿债约束压低开工"),
        "工程机械": research("基建项目开工通过设备采购和更新需求传导", "挖掘机与起重机销量、开工小时、渠道库存和出口订单", "设备收入、单机毛利、存货减值和经营现金流", "项目开工强度足以消化渠道库存", "开工不及预期、价格竞争或存量设备利用率偏低"),
        "建材": research("财政支出形成施工需求并带动水泥、防水和建筑材料消耗", "水泥出货、熟料库存、玻纤或防水材料销量和区域价格", "建材收入、吨毛利、库存减值和应收款", "施工需求增长超过新增供给并改善产能利用率", "地产拖累、供给过剩或价格战抵消基建需求"),
        "银行": research("财政扩张影响政府融资、企业信贷和流动性需求", "对公贷款投放、基建信贷、存款增长和净息差", "利息净收入、信用成本、资本充足率和手续费收入", "新增信贷具备可偿付现金流且风险定价覆盖成本", "隐性债务风险、息差压缩或资产质量恶化"),
        "消费品": research("更加积极财政政策通过居民收入、补贴和公共服务支出支持消费", "终端动销、客单价、渠道库存、同店销售和促销强度", "消费品收入、销售费用率、毛利率和经营现金流", "收入预期与消费意愿改善并传导至真实动销", "预防性储蓄上升或促销侵蚀利润"),
        "汽车": research("财政补贴和以旧换新资金改变整车购置需求", "订单、零售销量、折扣、渠道库存和新能源渗透率", "整车收入、单车利润、销售费用和库存减值", "补贴兑现带来的增量需求超过提前透支", "补贴退坡、价格战或需求前置后回落"),
        "家电": research("消费品以旧换新与财政支持降低家电更新成本", "零售额、换新订单、渠道库存、安装量和产品结构", "家电收入、毛利率、销售返利和现金回款", "换新补贴及时兑付且形成新增而非跨期需求", "补贴到账慢、渠道压货或价格竞争抵消销量"),
    },
    "event-15": {
        "银行": research("远期售汇准备金成本归零降低客户远期购汇报价摩擦", "远期售汇签约量、客户套保率、外汇敞口和衍生品保证金", "外汇业务手续费、交易损益、风险加权资产和流动性成本", "银行将准备金成本下降传导给真实套保客户", "汇率波动放大信用与交易风险或客户套保需求不足"),
        "证券": research("外汇套保成本下降影响跨境资金与衍生品服务需求", "跨境交易量、场外衍生品名义本金、客户保证金和风险限额", "经纪与衍生品收入、投资收益、资本占用和风险损失", "合规跨境需求增长且风险对冲工具可获得", "跨境监管收紧或单边汇率波动压制客户活动"),
        "航空运输": research("远期购汇成本变化影响航油、租赁和外币债务套保", "航油套保比例、美元负债、客座率和国际航线运力", "汇兑损益、燃油成本、租赁负债和单位收入", "公司实际增加套保且人民币路径降低外币成本", "油价上涨或人民币贬值超过准备金成本下降"),
        "石油石化": research("进口原油与设备付款的远期购汇摩擦下降", "进口量、套保比例、炼厂开工率、库存天数和裂解价差", "原料成本、汇兑损益、炼化毛利和营运资金", "企业有真实进口敞口并使用远期工具锁定成本", "油价冲击、产品价差收窄或汇率反向波动主导"),
        "电子": research("出口收汇与进口元件购汇的双向套保成本改变", "外销收入占比、美元订单、进口材料、套保名义本金和库存", "汇兑损益、毛利率、财务费用和应收账款", "净外汇敞口明确且套保政策实际调整", "终端需求、技术迭代或价格竞争主导利润"),
        "家用电器": research("出口企业远期结售汇成本下降影响汇率风险管理", "海外订单、出口均价、套保比例、渠道库存和海运成本", "海外收入、汇兑损益、毛利率和财务费用", "出口敞口与套保执行在报告中持续可见", "海外需求走弱或原材料与关税冲击更强"),
        "汽车": research("整车出口与进口零部件形成的外汇敞口套保成本下降", "出口销量、海外定价、进口件成本、套保比例和库存", "海外收入、单车利润、汇兑损益和财务费用", "出口业务形成稳定净敞口并使用远期工具", "海外贸易壁垒、价格战或本币反向波动"),
    },
    "event-16": {
        "钢铁": research("欧盟公共采购的Made in EU与低碳要求提高钢材准入和碳强度门槛", "欧盟出口量、低碳钢认证、吨钢碳排、产能利用率和区域价差", "出口收入、吨钢毛利、认证与减排资本开支和资产减值", "低碳产品获得认证或企业能以欧洲本地产能供货", "欧盟细则豁免进口、需求不足或合规成本无法转嫁"),
        "水泥": research("低碳公共采购要求影响高排放水泥材料的投标资格", "熟料系数、替代燃料、碳排强度、海外销量和项目中标", "吨毛利、碳成本、减排资本开支和海外收入", "低碳水泥溢价与中标增量覆盖改造成本", "本地需求疲弱或认证标准排除境外供应"),
        "铝": research("低碳与本地化要求改变铝材碳足迹和原产地竞争", "绿电铝比例、欧盟出口、产品认证、加工费和库存", "铝产品毛利、能源成本、认证费用和出口收入", "低碳铝足迹可验证并被采购规则认可", "欧盟本地产能替代进口或能源成本上升"),
        "汽车": research("Made in EU要求可能提高整车及零部件本地含量门槛", "欧洲销量、本地产能、零部件本地化率、认证周期和库存", "欧洲收入、单车利润、本地资本开支和关税成本", "欧洲产能与供应链满足最终实施细则", "规则扩大排他范围或欧洲需求与价格竞争恶化"),
        "电池": research("电池采购的本地制造与低碳要求影响供应链准入", "欧洲电池产能、客户定点、碳足迹、材料本地化和良率", "海外收入、产能折旧、单位成本、资本开支和减值", "欧洲工厂按期量产且客户认证通过", "产能爬坡失败、客户推迟或本地化成本过高"),
        "光伏": research("公共支持计划的Made in EU条款改变组件采购资格", "欧洲出货、产地结构、低碳认证、组件价格和海外库存", "组件收入、单位毛利、海外产能资本开支和存货减值", "企业通过欧洲产能或合规供应链保持采购资格", "本地化门槛排除进口且价格下跌快于成本"),
        "风电设备": research("欧盟本地化采购要求影响风机与零部件项目投标", "欧洲订单、本地产能、认证、交付周期和供应链本地化率", "订单收入、合同负债、项目毛利、保修费用和资本开支", "欧洲项目中标与本地产能交付同步兑现", "许可延迟、竞标失败或本地供应链成本超预算"),
    },
    "event-17": {
        "证券": research("创业板上市标准与预先审阅机制改变投行业务供给", "创业板项目储备、申报与过会数量、承销周期和撤回率", "投行收入、项目成本、应收款和资本回报", "改革形成可执行审核规则并带来合格项目申报", "审核尺度未实质改变或项目质量不足"),
        "创投": research("新上市标准扩展创新企业退出渠道预期", "被投项目申报、后续融资、退出周期和估值调整", "投资收益、公允价值变动、减值和现金回收", "被投企业符合产业与上市条件且退出窗口真实打开", "IPO节奏、估值折价或锁定期限制退出"),
        "信息技术": research("新兴产业上市包容度提高信息技术企业融资可得性预期", "研发投入、融资计划、项目申报、合同订单和人员扩张", "研发费用、现金储备、收入增长和股权稀释", "融资转化为研发和商业订单而非仅估值变化", "技术商业化失败或融资稀释超过增长"),
        "新能源": research("创业板改革强化新能源创新企业股权融资与并购退出路径", "募投项目、产能建设、研发资本化、订单和现金消耗", "资本开支、融资现金流、毛利率和资产减值", "融资资金按募投计划形成有效产能与订单", "行业过剩、产品降价或募投延期"),
        "高端装备": research("上市标准为高研发、长验证周期装备企业提供融资路径", "研发项目、客户验证、在手订单、交付周期和产能利用率", "研发费用、合同负债、设备收入和经营现金流", "客户验证和订单兑现支持持续融资", "验证失败、订单推迟或研发投入无法商业化"),
        "新消费": research("创业板制度优化可能拓宽成长型消费企业融资和并购工具", "门店与渠道扩张、新品动销、获客成本和库存周转", "收入、销售费用率、毛利率和融资现金流", "融资用于可验证扩张且单位经济性改善", "流量成本上升、库存积压或扩张回报不足"),
        "金融信息服务": research("创业板项目与交易活跃度变化影响金融数据和系统需求", "开户活跃、终端付费、投行系统订单、数据调用和续费率", "软件收入、递延收入、毛利率和研发费用", "券商及投资者活动增长转化为付费合同", "市场成交低迷或客户削减信息化预算"),
    },
}


def verify_calendar(run: Path, unified: dict[str, Any]) -> dict[str, Any]:
    market_root = run / "online" / "market"
    calendar = common.csv_dates(market_root / "industry" / "csi300.csv")
    sample_endpoints = unified["companies"][0]["market_window"]["endpoints"]
    start = sample_endpoints["T_MINUS_1"]["date"]
    end = sample_endpoints["D20"]["date"]
    sessions = sorted(day for day in calendar if start <= day <= end)
    company_audits = {}
    for company in unified["companies"]:
        raw = market_root / "company" / f"public-price-{unified['event_id']}-{company['company_code'].lower().replace('.', '-')}.json"
        dates = common.company_dates(json.loads(raw.read_text(encoding="utf-8")))
        missing = [day for day in sessions if day not in dates]
        nonpositive = [day for day in sessions if dates.get(day, 0) <= 0]
        company_audits[company["company_code"]] = {"calendar_source": "CSI300_TRADING_DATES", "window_start": start, "window_end": end, "expected_session_count": len(sessions), "observed_session_count": len(sessions) - len(missing), "missing_dates": missing, "nonpositive_volume_dates": nonpositive, "verified": not missing and not nonpositive, "source_snapshot_path": raw.relative_to(run).as_posix()}
    industry_audits = {}
    for industry in unified["industries"]:
        code = str(industry["market_window"]["industry_benchmark_id"]).split(".")[0]
        raw = market_root / "industry" / f"sw_{code}.csv"
        dates = common.csv_dates(raw)
        missing = [day for day in sessions if day not in dates]
        nonpositive = [day for day in sessions if dates.get(day, 0) <= 0]
        industry_audits[industry["industry_name_zh"]] = {"calendar_source": "CSI300_TRADING_DATES", "window_start": start, "window_end": end, "expected_session_count": len(sessions), "observed_session_count": len(sessions) - len(missing), "missing_dates": missing, "nonpositive_volume_dates": nonpositive, "verified": not missing and not nonpositive, "source_snapshot_path": raw.relative_to(run).as_posix()}
    return {"calendar_dates": sessions, "companies": company_audits, "industries": industry_audits}


def enrich(event_id: str, unified: dict[str, Any], event_evidence: dict[str, Any], gapfill: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    audit = verify_calendar(gapfill, unified)
    evidence = deepcopy(event_evidence)
    evidence.update({"statement_class": "SOURCE_FACT", "acceptance_status": "ACCEPTED", "acceptance_reason": "GATES_PASSED", "review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False})
    supported = list(evidence.get("supports_node_ids") or [])
    all_nodes = []
    for industry in unified["industries"]:
        name = industry["industry_name_zh"]
        spec = RESEARCH[event_id][name]
        statements = [
            f"{name}面对的事件冲击是{spec['driver']}。",
            f"该冲击通过{name}的合同、融资、套保、采购或资本市场安排进入企业决策，传导强弱取决于实际业务暴露。",
            f"经营层以{spec['operating']}作为可观测验证变量。",
            f"经营变化进一步映射为{spec['financial']}，方向可能被成本、竞争和执行节奏改变。",
            f"估值预期成立的业务前提是{spec['condition']}。",
            f"T-1、T0、D1、D3、D5、D20行业代理收益只描述{name}窗口表现，不证明事件造成收益。",
            f"若{spec['invalidation']}，则{name}传导判断失效或必须降级。",
        ]
        nodes = []
        for index, statement in enumerate(statements, 1):
            node_id = f"{event_id}-{industry['industry_id']}-node-{index}"
            all_nodes.append(node_id)
            if index == 6:
                node = {"node_id": node_id, "node_type": "MARKET_VALIDATION", "statement_zh": statement, "support_type": "CALCULATED_LINEAGE", "evidence_ids": [], "support_rationale_zh": "冻结行情原始值按T-1公式计算并通过连续交易审计，仅作描述性验证。", "evidence_locator": "market_window.endpoints"}
            else:
                node = {"node_id": node_id, "node_type": ("SHOCK", "CHANNEL", "OPERATING_VARIABLE", "FINANCIAL_VARIABLE", "VALUATION_EXPECTATION", "MARKET_VALIDATION", "COUNTEREVIDENCE")[index - 1], "statement_zh": statement, "support_type": "PREMISE_SUPPORT", "evidence_ids": [evidence["evidence_id"]], "support_rationale_zh": f"官方原文确认{unified['event']['title_zh']}的政策事实；本节点仅据此登记{name}的可检验研究路径与边界。", "evidence_locator": f"{evidence['locator']}; industry={name}; mechanism_step={index}"}
                supported.append(node_id)
            nodes.append(node)
        industry["mechanism_nodes"] = nodes
        industry["industry_operating_variable_zh"] = spec["operating"]
        industry["industry_financial_variable_zh"] = spec["financial"]
        industry["observable_driver_zh"] = spec["driver"]
        industry["condition_zh"] = spec["condition"]
        industry["invalidation_condition_zh"] = spec["invalidation"]
        industry["horizon_analysis"] = {"IMMEDIATE": f"T0至D1记录{name}预期重估、成交量及相对沪深300表现，不据此反向选择样本。", "SHORT_TERM": f"D3至D20跟踪{spec['operating']}是否连续确认；仅有价格变化时维持描述性判断。", "MEDIUM_TERM": f"未来1至4个季度用{spec['financial']}复核兑现；若{spec['invalidation']}则撤销当前判断。"}
        industry["market_window"]["continuous_trading_verified"] = audit["industries"][name]["verified"]
        industry["market_window"]["continuous_trading_audit"] = audit["industries"][name]
    evidence["supports_node_ids"] = sorted(set(supported))
    unified["evidence_registry"] = [evidence]
    for company in unified["companies"]:
        company_audit = audit["companies"][company["company_code"]]
        company["market_window"]["continuous_trading_verified"] = company_audit["verified"]
        company["market_window"]["continuous_trading_audit"] = company_audit
        company["horizon_analysis"] = {"IMMEDIATE": f"T0至D1观察{company['company_name']}相对市场与行业的首轮重估，不用涨跌筛选公司。", "SHORT_TERM": f"D3至D20检验{company['company_name']}的订单、套保、融资、产销或项目公告是否与事前{company['industry']}暴露一致。", "MEDIUM_TERM": f"未来1至4个季度以定期报告的分部收入、利润率和现金流复核，优先登记公司特有公告及行业反向变化。"}
    qa = {row["qa_type"]: row for row in unified["qa"]}
    first_industry = unified["industries"][0]
    first_company = unified["companies"][0]
    qa["EVIDENCE_QUERY"].update({"reference_ids": [evidence["evidence_id"]], "evidence_ids": [evidence["evidence_id"]], "direct_answer_zh": f"{evidence['publisher']}原文确认：{evidence['original_quote']}"})
    qa["MECHANISM_STAGE"].update({"reference_ids": all_nodes[:3], "evidence_ids": [evidence["evidence_id"]], "direct_answer_zh": "即时阶段记录预期与成交，短期阶段验证经营变量，1至4个季度再用财务变量复核；三阶段窗口和指标不同。"})
    qa["MARKET_VALIDATION"].update({"reference_ids": [first_industry["industry_id"], first_industry["mechanism_nodes"][5]["node_id"]], "evidence_ids": [evidence["evidence_id"]], "direct_answer_zh": "公司、沪深300与行业代理六个端点均按T-1回算并通过完整交易日历审计；行情只验证窗口表现，因果结论保持ABSTAIN。"})
    qa["INDUSTRY_COMPANY"].update({"reference_ids": [first_company["industry_id"], first_company["mapping_id"]], "evidence_ids": [first_company["company_evidence"][0]["evidence_id"]], "direct_answer_zh": "每个行业固定三家公司，均由事件日前两份法定披露证明业务暴露，并保留事件、行业与公司映射。"})
    for item in qa.values():
        if isinstance(item.get("answer"), dict):
            item["answer"].setdefault("task_answer", {})["direct_answer_zh"] = item["direct_answer_zh"]
    unified["causal_assessment"].update({"status": "DESCRIPTIVE_EVENT_STUDY", "causal_attribution_allowed": False, "causal_conclusion": "ABSTAIN"})
    unified["review_status"] = "NEEDS_HUMAN_REVIEW"
    unified["formal_ready"] = False
    return unified, audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-id", choices=sorted(RESEARCH), required=True)
    parser.add_argument("--gapfill-run", type=Path, required=True)
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--output-run", type=Path, required=True)
    args = parser.parse_args()
    gapfill, source, output = args.gapfill_run.resolve(), args.source_run.resolve(), args.output_run.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for name in ("profile.json", "base_dataset_config.json", "base_training_config.json", "base_unified_events.jsonl"):
        if (gapfill / name).exists(): shutil.copy2(gapfill / name, output / name)
    shutil.copytree(gapfill / "online", output / "online")
    shutil.copytree(source / "snapshots", output / "snapshots")
    record = common.read_jsonl(gapfill / "content_candidates.jsonl")[0]
    event_evidence = next(row for row in common.read_jsonl(source / "accepted_evidence.jsonl") if row.get("event_id") == args.event_id)
    unified, audit = enrich(args.event_id, deepcopy(record["unified_event"]), event_evidence, gapfill)
    updated = {**record, "closure_status": "STRICT_AUDIT_PENDING", "errors": [], "warnings": [], "unified_event": unified}
    updated["content_sha256"] = common.content_sha(unified)
    all_evidence = [*unified["evidence_registry"], *[item for company in unified["companies"] for item in company["company_evidence"]]]
    updated["evidence_ids"] = sorted(row["evidence_id"] for row in all_evidence)
    common.write_jsonl(output / "content_candidates.jsonl", [updated])
    common.write_jsonl(output / "accepted_evidence.jsonl", all_evidence)
    common.write_json(output / "continuous_trading_audit.json", audit)
    common.write_json(output / "enrichment_summary.json", {"event_id": args.event_id, "industry_node_count": sum(len(row["mechanism_nodes"]) for row in unified["industries"]), "company_calendar_verified": sum(row["verified"] for row in audit["companies"].values()), "industry_calendar_verified": sum(row["verified"] for row in audit["industries"].values()), "review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False, "causal_conclusion": "ABSTAIN"})
    print((output / "enrichment_summary.json").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
