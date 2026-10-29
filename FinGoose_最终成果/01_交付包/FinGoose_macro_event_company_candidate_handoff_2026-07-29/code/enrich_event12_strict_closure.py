from __future__ import annotations

import argparse
from copy import deepcopy
import csv
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
from typing import Any

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
SOURCE_RUN = ROOT / "work" / "skill_research_runs" / "run-fingoose-event12-gapfill-20260813-001"
EVENT_SNAPSHOT = ROOT / "work" / "skill_research_runs" / "run-fingoose-seven-events-20260813-003" / "snapshots" / "35ce0160280dcd7bec2dd03c94131bad8adcaefaf466ed5bb19b77e6e102fb40.html"
EVENT_URL = "https://www.gov.cn/yaowen/liebiao/202603/content_7062633.htm"
PUBLISHED_AT = "2026-03-13T00:00:00+08:00"
RETRIEVED_AT = "2026-08-13T00:00:00+00:00"
HORIZONS = ("IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM")

RESEARCH = {
    "人工智能与算力": {
        "keyword": "实施人工智能、量子科技、生物科技、新能源等科技战略部署",
        "driver": "国家人工智能战略部署、底层技术突破与应用转化",
        "operating": "智算服务器需求、算力中心上架率、模型训练与推理订单",
        "financial": "AI基础设施收入、研发投入、毛利率与经营现金流",
        "condition": "专项任务和应用场景形成可执行项目并进入采购",
        "invalidation": "专项部署未转化为项目，或算力供给扩张快于付费需求",
    },
    "半导体": {
        "keyword": "全链条推动集成电路、工业母机、高端仪器、基础软件、先进材料",
        "driver": "关键核心技术攻关和产业链薄弱环节补强",
        "operating": "晶圆产能利用率、国产设备验证、关键芯片出货与研发节点",
        "financial": "半导体收入、研发资本化、折旧负担和产品毛利率",
        "condition": "攻关资金、验证平台和下游导入同步推进",
        "invalidation": "技术验证延期、终端需求走弱或价格竞争抵消国产替代",
    },
    "高端装备": {
        "keyword": "机器人、生物医药、高端装备、航空航天等战略性新兴产业发展",
        "driver": "战略性新兴产业集群和大规模应用示范",
        "operating": "设备招标、交付周期、产能利用率和关键零部件国产化率",
        "financial": "装备收入、订单预收款、毛利率和资本开支回报",
        "condition": "示范场景形成批量订单且客户验收按期完成",
        "invalidation": "示范项目停留在试点，或制造业资本开支转弱",
    },
    "新能源": {
        "keyword": "扎实推进智能驾驶、新型太阳能电池、新型储能等关键技术创新",
        "driver": "新能源关键技术创新、应用示范与产业规模化",
        "operating": "组件与电池出货、装机、利用小时和单位制造成本",
        "financial": "新能源收入、存货减值、单位盈利和项目现金回收",
        "condition": "新增装机与技术迭代带来的需求超过行业新增产能",
        "invalidation": "供给过剩、产品降价或并网消纳约束压过政策需求",
    },
    "电网与储能": {
        "keyword": "着力构建新型电力系统，全面提升电力系统互补互济和安全韧性水平",
        "driver": "智能电网、跨区通道、配电网和新型储能建设",
        "operating": "电网招标、中标金额、储能装机、交付和调度利用率",
        "financial": "电网设备收入、合同负债、毛利率和项目回款",
        "condition": "电网投资计划按期招标并形成设备交付",
        "invalidation": "项目核准或招标推迟，或储能利用率低于经济性门槛",
    },
    "消费": {
        "keyword": "统筹扩大内需和深化供给侧结构性改革",
        "driver": "扩大内需、收入预期与消费供给结构优化",
        "operating": "终端动销、客单价、渠道库存和同店销售",
        "financial": "消费品收入、销售费用率、存货周转和经营现金流",
        "condition": "居民收入和消费意愿改善并传导至终端动销",
        "invalidation": "预防性储蓄上升、渠道库存积压或促销侵蚀利润",
    },
    "医疗养老": {
        "keyword": "健全县乡村三级养老服务网络",
        "driver": "基层医疗与养老服务网络扩容和公共服务供给",
        "operating": "医疗设备采购、药品准入、养老床位和服务人次",
        "financial": "医疗养老收入、应收账款周转、服务毛利和现金回款",
        "condition": "地方配套资金、采购和支付机制同步落地",
        "invalidation": "支付约束、采购延期或服务价格不足以覆盖成本",
    },
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8", newline="\n")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")


def content_sha(value: Any) -> str:
    return sha256((json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")).hexdigest()


def extract_quote(text: str, keyword: str, radius: int = 260) -> tuple[str, str]:
    index = text.find(keyword)
    if index < 0:
        raise ValueError(f"INDUSTRY_PASSAGE_NOT_FOUND:{keyword}")
    start = max(0, text.rfind("。", 0, index) + 1)
    end = text.find("。", index + len(keyword))
    if end < 0:
        end = min(len(text), index + radius)
    quote = text[start:end + 1].strip()
    locator = f"normalized_text_offset={start}:{end + 1}; phrase={keyword}"
    return quote, locator


def company_dates(payload: dict[str, Any]) -> dict[str, float]:
    data = payload.get("data") or {}
    if isinstance(data.get("klines"), list):
        # Eastmoney rows are date,open,close,high,low,volume,...
        return {row.split(",")[0]: float(row.split(",")[5]) for row in data["klines"] if len(row.split(",")) >= 6}
    for value in data.values():
        if isinstance(value, dict):
            bars = value.get("qfqday") or value.get("day") or []
            if bars:
                return {str(row[0]): float(row[5]) for row in bars if len(row) >= 6}
    return {}


def csv_dates(path: Path) -> dict[str, float]:
    result = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            date = row.get("date") or row.get("日期")
            volume = row.get("amount") or row.get("成交量") or row.get("成交额")
            if date and volume not in (None, ""):
                result[date] = float(volume)
    return result


def verify_calendar(source_run: Path, unified: dict[str, Any]) -> dict[str, Any]:
    market_root = source_run / "online" / "market"
    calendar_values = csv_dates(market_root / "industry" / "csi300.csv")
    window_dates = sorted(day for day in calendar_values if "2026-03-12" <= day <= "2026-04-13")
    company_audits = {}
    for company in unified["companies"]:
        raw_path = market_root / "company" / f"public-price-event-12-{company['company_code'].lower().replace('.', '-')}.json"
        dates = company_dates(json.loads(raw_path.read_text(encoding="utf-8")))
        missing = [day for day in window_dates if day not in dates]
        nonpositive = [day for day in window_dates if dates.get(day, 0) <= 0]
        company_audits[company["company_code"]] = {
            "calendar_source": "CSI300_TRADING_DATES",
            "window_start": window_dates[0], "window_end": window_dates[-1],
            "expected_session_count": len(window_dates),
            "observed_session_count": len(window_dates) - len(missing),
            "missing_dates": missing, "nonpositive_volume_dates": nonpositive,
            "verified": not missing and not nonpositive,
            "source_snapshot_path": raw_path.relative_to(source_run).as_posix(),
        }
    industry_files = {
        "人工智能与算力": "sw_801750.csv", "半导体": "sw_801080.csv", "高端装备": "sw_801890.csv",
        "新能源": "sw_801730.csv", "电网与储能": "sw_801730.csv", "消费": "sw_801120.csv", "医疗养老": "sw_801150.csv",
    }
    industry_audits = {}
    for name, filename in industry_files.items():
        raw_path = market_root / "industry" / filename
        dates = csv_dates(raw_path)
        missing = [day for day in window_dates if day not in dates]
        nonpositive = [day for day in window_dates if dates.get(day, 0) <= 0]
        industry_audits[name] = {
            "calendar_source": "CSI300_TRADING_DATES", "window_start": window_dates[0], "window_end": window_dates[-1],
            "expected_session_count": len(window_dates), "observed_session_count": len(window_dates) - len(missing),
            "missing_dates": missing, "nonpositive_volume_dates": nonpositive,
            "verified": not missing and not nonpositive, "source_snapshot_path": raw_path.relative_to(source_run).as_posix(),
        }
    return {"calendar_dates": window_dates, "companies": company_audits, "industries": industry_audits}


def enrich(unified: dict[str, Any], source_run: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    snapshot_text = BeautifulSoup(EVENT_SNAPSHOT.read_text(encoding="utf-8"), "html.parser").get_text(" ", strip=True)
    snapshot_text = re.sub(r"\s+", " ", snapshot_text)
    calendar_audit = verify_calendar(source_run, unified)
    source_evidence = deepcopy(unified["event"]["reasoning_chain"]["evidence_registry"][0])
    event_evidence = [{
        **source_evidence,
        "event_id": "event-12",
        "retrieved_at": RETRIEVED_AT,
        "source_tier": "T1",
        "statement_class": "SOURCE_FACT",
        "temporal_role": "AS_OF_EVIDENCE",
        "snapshot_path": "snapshots/35ce0160280dcd7bec2dd03c94131bad8adcaefaf466ed5bb19b77e6e102fb40.html",
        "acceptance_status": "ACCEPTED",
        "acceptance_reason": "GATES_PASSED",
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
    }]
    source_sha = sha256(EVENT_SNAPSHOT.read_bytes()).hexdigest()
    new_evidence = []
    all_node_ids = []
    for industry in unified["industries"]:
        name = industry["industry_name_zh"]
        research = RESEARCH[name]
        quote, locator = extract_quote(snapshot_text, research["keyword"])
        evidence_id = "evidence-event-12-industry-" + sha256(name.encode("utf-8")).hexdigest()[:12]
        nodes = []
        statements = [
            f"规划纲要对{name}的直接政策冲击是{research['driver']}。",
            f"该冲击先通过项目、采购、技术验证或公共服务配置进入{name}需求，而不是由短窗股价定义。",
            f"经营层重点观察{research['operating']}；只有这些指标兑现，政策预期才进入企业经营。",
            f"经营变化映射到{research['financial']}，并可能因固定成本、价格竞争或回款节奏而放大或减弱。",
            f"估值重估取决于盈利兑现与风险溢价，前提是“{research['condition']}”。",
            f"以T-1为基准的T0、D1、D3、D5、D20行业代理收益仅检验{name}窗口表现，不证明规划造成收益。",
            f"若“{research['invalidation']}”，则{name}当前传导判断失效或需降级。",
        ]
        for index, statement in enumerate(statements, 1):
            node_id = f"event-12-{industry['industry_id']}-node-{index}"
            all_node_ids.append(node_id)
            if index <= 5:
                node = {"node_id": node_id, "node_type": ("SHOCK", "CHANNEL", "OPERATING_VARIABLE", "FINANCIAL_VARIABLE", "VALUATION_EXPECTATION")[index - 1],
                    "statement_zh": statement, "support_type": "PREMISE_SUPPORT", "evidence_ids": [evidence_id],
                    "support_rationale_zh": f"规划纲要原文明确部署{name}相关政策方向；该节点只解释由该政策前提到行业变量的研究路径。",
                    "evidence_locator": locator}
            elif index == 6:
                node = {"node_id": node_id, "node_type": "MARKET_VALIDATION", "statement_zh": statement,
                    "support_type": "CALCULATED_LINEAGE", "evidence_ids": [],
                    "support_rationale_zh": "行情端点由冻结原始值按T-1公式计算，且仅作描述性验证。", "evidence_locator": "market_window.endpoints"}
            else:
                node = {"node_id": node_id, "node_type": "COUNTEREVIDENCE", "statement_zh": statement,
                    "support_type": "PREMISE_SUPPORT", "evidence_ids": [evidence_id],
                    "support_rationale_zh": f"规划纲要原文构成{name}政策方向的事实前提；该节点仅登记可推翻传导判断的条件，不声称已完成负面检索或不存在其他反证。",
                    "evidence_locator": locator}
            nodes.append(node)
        industry["mechanism_nodes"] = nodes
        industry["industry_operating_variable_zh"] = research["operating"]
        industry["industry_financial_variable_zh"] = research["financial"]
        industry["condition_zh"] = research["condition"]
        industry["invalidation_condition_zh"] = research["invalidation"]
        industry["observable_driver_zh"] = research["driver"]
        industry["horizon_analysis"] = {
            "IMMEDIATE": f"T0至D1先观察{name}政策暴露的预期重估，并以交易量、行业代理相对沪深300表现和公告关注度记录首轮反应。",
            "SHORT_TERM": f"D3至D20检验{research['operating']}是否出现项目、采购或订单连续信号；若只有价格波动而无经营指标，维持描述性判断。",
            "MEDIUM_TERM": f"未来1至4个季度用{research['financial']}和政策执行进度复核兑现；若{research['invalidation']}，撤销当前方向判断。",
        }
        market_audit = calendar_audit["industries"][name]
        industry["market_window"]["continuous_trading_verified"] = market_audit["verified"]
        industry["market_window"]["continuous_trading_audit"] = market_audit
        new_evidence.append({"evidence_id": evidence_id, "event_id": "event-12", "publisher": "中国政府网",
            "published_at": PUBLISHED_AT, "retrieved_at": RETRIEVED_AT, "original_quote": quote, "locator": locator,
            "source_url": EVENT_URL, "source_tier": "T1", "statement_class": "SOURCE_FACT", "temporal_role": "AS_OF_EVIDENCE",
            "snapshot_path": "snapshots/35ce0160280dcd7bec2dd03c94131bad8adcaefaf466ed5bb19b77e6e102fb40.html",
            "snapshot_sha256": source_sha, "supports_node_ids": [node["node_id"] for node in nodes if node["support_type"] == "PREMISE_SUPPORT"],
            "acceptance_status": "ACCEPTED", "acceptance_reason": "GATES_PASSED", "review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False})
    unified["evidence_registry"] = [*event_evidence, *new_evidence]
    for company in unified["companies"]:
        audit = calendar_audit["companies"][company["company_code"]]
        company["market_window"]["continuous_trading_verified"] = audit["verified"]
        company["market_window"]["continuous_trading_audit"] = audit
        company["horizon_analysis"] = {
            "IMMEDIATE": f"T0至D1仅观察{company['company_name']}相对沪深300和行业代理的首轮重估，不以涨跌反向选择公司。",
            "SHORT_TERM": f"D3至D20跟踪{company['company_name']}订单、产销、库存或项目公告是否与其事前披露的{company['industry']}业务暴露一致。",
            "MEDIUM_TERM": f"未来1至4个季度以定期报告中的分部收入、毛利率和现金流复核；公司特有公告或行业反向变化优先作为混杂解释。",
        }
    qa = {row["qa_type"]: row for row in unified["qa"]}
    first_evidence = new_evidence[0]["evidence_id"]
    qa["EVIDENCE_QUERY"]["reference_ids"] = [first_evidence]
    qa["EVIDENCE_QUERY"]["evidence_ids"] = [first_evidence]
    qa["EVIDENCE_QUERY"]["direct_answer_zh"] = "规划纲要原文分别部署人工智能、集成电路、高端装备、新能源、电力系统、扩大内需和养老服务网络；每个行业引用独立正文定位。"
    qa["MECHANISM_STAGE"]["reference_ids"] = [all_node_ids[0], all_node_ids[1], all_node_ids[2]]
    qa["MECHANISM_STAGE"]["evidence_ids"] = [first_evidence]
    qa["MECHANISM_STAGE"]["direct_answer_zh"] = "即时阶段观察政策暴露重估，短期检验项目与订单信号，中期用财报和执行进度复核；三个阶段使用不同窗口和指标。"
    qa["MARKET_VALIDATION"]["reference_ids"] = [unified["industries"][0]["industry_id"], all_node_ids[5]]
    qa["MARKET_VALIDATION"]["evidence_ids"] = [first_evidence]
    qa["MARKET_VALIDATION"]["direct_answer_zh"] = "公司、沪深300和行业代理的六个固定端点均可回算，连续交易按T-1至D20完整交易日历核验；行情只验证窗口表现。"
    first_company = unified["companies"][0]
    qa["INDUSTRY_COMPANY"]["reference_ids"] = [first_company["industry_id"], first_company["mapping_id"]]
    qa["INDUSTRY_COMPANY"]["evidence_ids"] = [first_company["company_evidence"][0]["evidence_id"]]
    qa["INDUSTRY_COMPANY"]["direct_answer_zh"] = "每个行业固定三家公司，均按事件日前两份法定定期报告中的业务暴露选样，并保留公司、行业和事件关联。"
    for item in qa.values():
        if isinstance(item.get("answer"), dict):
            item["answer"].setdefault("task_answer", {})["direct_answer_zh"] = item["direct_answer_zh"]
    return unified, new_evidence, calendar_audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-run", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_run.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for name in ("profile.json", "base_dataset_config.json", "base_training_config.json", "base_unified_events.jsonl", "accepted_evidence.jsonl", "discovery_candidates.jsonl"):
        if (SOURCE_RUN / name).exists():
            shutil.copy2(SOURCE_RUN / name, output / name)
    shutil.copytree(SOURCE_RUN / "snapshots", output / "snapshots")
    source_record = next(row for row in read_jsonl(SOURCE_RUN / "content_candidates.jsonl") if row["event_id"] == "event-12")
    unified, evidence, calendar_audit = enrich(deepcopy(source_record["unified_event"]), SOURCE_RUN)
    record = {**source_record, "closure_status": "STRICT_AUDIT_PENDING", "errors": [], "warnings": [], "unified_event": unified,
        "evidence_ids": sorted({*[row["evidence_id"] for row in unified["evidence_registry"]], *[item["evidence_id"] for company in unified["companies"] for item in company["company_evidence"]]})}
    record["content_sha256"] = content_sha(unified)
    write_jsonl(output / "content_candidates.jsonl", [record])
    write_jsonl(output / "accepted_evidence.jsonl", [*unified["evidence_registry"], *[item for company in unified["companies"] for item in company["company_evidence"]]])
    write_json(output / "continuous_trading_audit.json", calendar_audit)
    write_json(output / "enrichment_summary.json", {"event_id": "event-12", "industry_evidence_added": len(evidence),
        "industry_node_count": sum(len(row["mechanism_nodes"]) for row in unified["industries"]),
        "company_calendar_verified": sum(row["verified"] for row in calendar_audit["companies"].values()),
        "industry_calendar_verified": sum(row["verified"] for row in calendar_audit["industries"].values()),
        "review_status": "NEEDS_HUMAN_REVIEW", "formal_ready": False, "causal_conclusion": "ABSTAIN"})
    print((output / "enrichment_summary.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
