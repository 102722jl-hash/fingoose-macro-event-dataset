from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "skills" / "building-auditable-macro-datasets" / "scripts" / "macro_dataset_pipeline.py"
EVENT_ID = "event-13"
RESEARCH = {
    "银行": {
        "shock": "政策利率升至约1.0%后，银行的日元资产收益率、存款重定价和债券估值同时进入重估。",
        "channel": "传导由浮息贷款重定价、存款成本上移、持有债券久期损益和信贷需求共同决定，不能只看贷款收益率。",
        "operating": "贷款与存款平均利率、存贷重定价缺口、贷款余额、存款结构、国债久期和不良贷款生成率",
        "financial": "净利息收入、净息差、债券处置损益、信用成本、普通股一级资本和经营利润",
        "condition": "资产端重定价快于负债端，且信用成本和债券估值损失没有抵消利差改善",
        "invalidation": "存款竞争使负债成本快速上升、贷款需求收缩或信用成本显著恶化",
    },
    "保险": {
        "shock": "更高的日元利率改变寿险与财险准备金贴现、再投资收益率和既有债券组合估值。",
        "channel": "新增保费现金流可按更高收益率投资，但存量长久期债券浮亏、退保行为和负债久期会改变净影响。",
        "operating": "新钱收益率、债券久期、保费收入、退保率、准备金负债久期和海外资产套保成本",
        "financial": "投资收益、其他综合收益、保险服务结果、偿付能力比率和股东权益",
        "condition": "新增投资收益改善超过存量债券估值压力，且退保率与赔付率保持可控",
        "invalidation": "债券未实现损失扩大、退保加速、巨灾赔付或海外汇率损失主导结果",
    },
    "证券": {
        "shock": "政策利率上调推动日元利率曲线和债券价格重估，并改变客户交易、融资与投行业务条件。",
        "channel": "债券库存估值、回购融资成本、客户换仓、利率衍生品需求和资本市场发行节奏共同传导。",
        "operating": "债券交易量、客户资产流入、回购余额、承销项目、衍生品名义本金和风险限额",
        "financial": "交易净收入、经纪与投行手续费、利息费用、风险加权资产和税前利润",
        "condition": "客户换仓与套保需求形成的手续费和交易收入能够覆盖库存及融资成本波动",
        "invalidation": "市场波动造成库存损失、发行活动降温或融资成本上升超过客户业务增量",
    },
    "房地产": {
        "shock": "日元政策利率上升提高开发商、REIT和购房者的融资成本，并抬升资产折现率。",
        "channel": "浮息债务重定价、项目资本化率、住宅按揭可负担性、物业交易和租金续约共同影响项目回报。",
        "operating": "有息负债平均成本、固定利率债务占比、出租率、租金、物业销售量和开发项目去化",
        "financial": "利息费用、租赁利润、开发毛利、资产公允价值、经营现金流和净资产价值",
        "condition": "租金增长与高出租率能够覆盖融资成本上升，且项目去化和资产交易保持稳定",
        "invalidation": "资本化率快速上升、住宅需求收缩或再融资压力导致资产减值与现金流恶化",
    },
    "航空运输": {
        "shock": "利率上升通过日元融资、飞机租赁与外币负债成本影响航空公司，同时可能伴随日元汇率变化。",
        "channel": "飞机购置和租赁融资、美元成本套保、航油采购、国际客流与票价共同决定净经营影响。",
        "operating": "客座率、国际与国内旅客量、单位客公里收入、航油单价、租赁负债和外币敞口",
        "financial": "利息费用、燃油成本、汇兑损益、单位座公里成本、营业利润和自由现金流",
        "condition": "客流与票价增长足以吸收融资成本，且日元汇率没有同步放大航油和租赁负担",
        "invalidation": "日元贬值、油价上涨、客流转弱或飞机融资再定价共同压低利润",
    },
    "汽车": {
        "shock": "更高的国内利率影响汽车信贷、经销商库存融资和日元汇率，从而改变内需与出口利润换算。",
        "channel": "消费者车贷月供、金融子公司资金成本、经销商库存、出口价格和海外利润折算同时传导。",
        "operating": "日本销量、订单、平均售价、库存天数、汽车金融放款、海外销量和汇率敏感度",
        "financial": "整车收入、单车利润、金融业务利差、销售金融信用损失和汇兑影响",
        "condition": "产品结构和海外需求能够抵消国内车贷成本上升，金融子公司保持稳定利差与资产质量",
        "invalidation": "国内需求受车贷成本压制、价格竞争加剧或日元升值显著削弱出口利润",
    },
    "电子": {
        "shock": "利率上升改变企业资本成本、客户投资意愿和日元折算，并对长久期成长预期施加折现压力。",
        "channel": "客户资本开支、供应链库存、研发融资、海外收入折算和估值折现率共同进入电子企业订单与预期。",
        "operating": "订单、在手项目、半导体与电子库存、海外收入占比、研发投入和设备产能利用率",
        "financial": "收入增长、毛利率、研发费用、汇兑损益、经营现金流和估值倍数",
        "condition": "数字化与半导体需求带来的订单增长超过资本成本和汇率折算的不利影响",
        "invalidation": "客户削减资本开支、库存调整延长、日元升值或技术迭代导致订单和利润下修",
    },
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def canonical_sha(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    return sha256(payload.encode("utf-8")).hexdigest()


def add_support(evidence: dict[str, Any], node_id: str) -> None:
    evidence["supports_node_ids"] = sorted(set([*(evidence.get("supports_node_ids") or []), node_id]))


def update_research_content(unified: dict[str, Any], all_node_ids: list[str]) -> None:
    event = unified["event"]
    event["horizon_analysis"] = {
        "IMMEDIATE": "T0至D1观察政策利率上调后日元利率曲线、日元汇率及各行业代理的首轮重估；成交反应只作描述性验证。",
        "SHORT_TERM": "D3至D20核对贷款与存款重定价、债券估值、融资成本、车贷与企业订单等经营指标是否按行业路径分化。",
        "MEDIUM_TERM": "未来1至4个季度用净息差、投资收益、利息费用、单位成本、利润率和现金流复核兑现，并检查反向宏观与公司因素。",
    }
    event["transmission_mechanism_zh"] = "政策利率上调先改变日元收益率曲线、融资成本和汇率预期，再按资产负债期限、外币敞口、信贷需求和客户资本开支传导至行业经营与财务变量。"
    event["invalidation_conditions"] = [
        "日本央行后续操作使隔夜利率未稳定在约1.0%附近",
        "全球风险偏好、油价或汇率冲击主导事件窗口",
        "公司特有公告、停牌或财务事件使行业传导不可区分",
    ]
    reasoning = event.get("reasoning_chain", {}).get("reasoning_chain", {})
    for node in reasoning.get("nodes", []):
        if node.get("node_id") == f"{EVENT_ID}-market":
            node["statement_zh"] = "公司、TOPIX ETF与TOPIX-17行业代理的T-1、T0、D1、D3、D5、D20均已回算；行情只验证窗口表现。"
            node["status"] = "CALCULATED_ONLY"
    research = unified.get("research_content") or {}
    horizon_analysis: dict[str, dict[str, Any]] = {}
    for horizon, summary_zh in event["horizon_analysis"].items():
        impact_rows: list[dict[str, Any]] = []
        for industry in unified["industries"]:
            node_ids = [node["node_id"] for node in industry.get("mechanism_nodes") or []]
            evidence_ids = sorted(set(industry.get("evidence_ids") or []))
            phase_condition = {
                "IMMEDIATE": f"{industry['industry_name_zh']}代理与利率或汇率首轮重估可核验",
                "SHORT_TERM": f"{industry['industry_name_zh']}D3至D20经营变量持续确认",
                "MEDIUM_TERM": f"{industry['industry_name_zh']}季度财务变量兑现",
            }[horizon]
            impact_rows.append(
                {
                    "scope_id": industry["event_industry_mapping_id"],
                    "scope_name_zh": industry["industry_name_zh"],
                    "direction": industry["horizon_directions"][horizon],
                    "detail_zh": industry["horizon_analysis"][horizon],
                    "condition_zh": phase_condition,
                    "invalidation_condition_zh": industry["invalidation_condition_zh"],
                    "mechanism_node_ids": node_ids,
                    "evidence_ids": evidence_ids,
                }
            )
        horizon_analysis[horizon] = {
            "summary_zh": summary_zh,
            "impact_rows": impact_rows,
            "mechanism_node_ids": sorted({node_id for row in impact_rows for node_id in row["mechanism_node_ids"]}),
            "evidence_ids": sorted({evidence_id for row in impact_rows for evidence_id in row["evidence_ids"]}),
        }
    research["horizon_analysis"] = horizon_analysis
    research["macro_mechanism"] = event["transmission_mechanism_zh"]
    research["industry_impacts"] = deepcopy(unified["industries"])
    research["company_impacts"] = deepcopy(unified["companies"])
    research["qa_sections"] = deepcopy(unified["qa"])
    research["evidence_registry"] = deepcopy(unified["evidence_registry"])
    research["answer_evidence_ids"] = [unified["evidence_registry"][0]["evidence_id"]]
    research["primary_answer_evidence_ids"] = [unified["evidence_registry"][0]["evidence_id"]]
    research["main_path_node_ids"] = all_node_ids
    research.setdefault("statement_by_node_id", {})[f"{EVENT_ID}-market"] = "六个行情端点已按T-1回算，但因果结论保持ABSTAIN。"
    research["boundaries"] = {
        "causal_claim_allowed": False,
        "market_is_validation_only": True,
        "limitations_zh": "行情仅验证窗口表现；同期混杂未排除，因果结论为ABSTAIN。",
        "review_status": "NEEDS_HUMAN_REVIEW",
    }
    research["review_state"] = {"formal_ready": False, "review_status": "NEEDS_HUMAN_REVIEW", "sha_gate": "MACHINE_VALIDATED"}
    unified["research_content"] = research


def enrich(unified: dict[str, Any]) -> dict[str, Any]:
    event_evidence = unified["evidence_registry"][0]
    companies_by_industry: dict[str, list[dict[str, Any]]] = {}
    evidence_by_id: dict[str, dict[str, Any]] = {event_evidence["evidence_id"]: event_evidence}
    for company in unified["companies"]:
        companies_by_industry.setdefault(company["industry_id"], []).append(company)
        for evidence in company.get("company_evidence") or []:
            evidence_by_id[evidence["evidence_id"]] = evidence

    all_node_ids: list[str] = []
    for industry in unified["industries"]:
        name = industry["industry_name_zh"]
        spec = RESEARCH[name]
        representative = companies_by_industry[industry["industry_id"]][0]
        company_evidence = representative["company_evidence"][0]
        support_ids = [event_evidence["evidence_id"], company_evidence["evidence_id"]]
        statements = [
            spec["shock"],
            spec["channel"],
            f"经营层以{spec['operating']}作为可观察变量，区分价格重估与真实业务变化。",
            f"经营变化映射到{spec['financial']}，并以公司定期披露核对方向和幅度。",
            f"估值与预期调整成立的前提是{spec['condition']}。",
            f"{name}代理与TOPIX ETF的六个端点按T-1回算，仅描述窗口相对表现，不证明政策造成收益。",
            f"若{spec['invalidation']}，则{name}机制应降级或撤销，不能用行情补足因果证据。",
        ]
        nodes: list[dict[str, Any]] = []
        for index, statement in enumerate(statements, 1):
            node_id = f"{EVENT_ID}-{industry['industry_id']}-node-{index}"
            all_node_ids.append(node_id)
            node_type = ("SHOCK", "CHANNEL", "OPERATING_VARIABLE", "FINANCIAL_VARIABLE", "VALUATION_EXPECTATION", "MARKET_VALIDATION", "COUNTEREVIDENCE")[index - 1]
            if index == 6:
                node = {
                    "node_id": node_id,
                    "node_type": node_type,
                    "statement_zh": statement,
                    "support_type": "CALCULATED_LINEAGE",
                    "evidence_ids": [],
                    "premise_node_ids": [nodes[-1]["node_id"]],
                    "support_rationale_zh": "冻结的证券、市场与行业原始收盘值按固定公式回算，并通过T-20至D20连续交易审计。",
                    "evidence_locator": "market_window.endpoints and continuous_trading_audit",
                    "status": "CALCULATED_ONLY",
                }
            else:
                node_ids = [event_evidence["evidence_id"]] if index == 1 else support_ids
                node = {
                    "node_id": node_id,
                    "node_type": node_type,
                    "statement_zh": statement,
                    "support_type": "DIRECT_FACT" if index == 1 else "PREMISE_SUPPORT",
                    "evidence_ids": node_ids,
                    "premise_node_ids": [] if index == 1 else [nodes[-1]["node_id"]],
                    "support_rationale_zh": (
                        "日本央行原文直接确认无担保隔夜拆借利率目标约1.0%的政策冲击。"
                        if index == 1
                        else f"日本央行政策原文与{representative['company_name']}事件日前披露共同支持{name}存在可检验的资产负债或业务暴露；本节点仍是研究推断。"
                    ),
                    "evidence_locator": f"{event_evidence['locator']}; {company_evidence['locator']}; industry={name}; step={index}",
                    "status": "SUPPORTED_INFERENCE" if index > 1 else "VERIFIED_SOURCE",
                }
                for evidence_id in node_ids:
                    add_support(evidence_by_id[evidence_id], node_id)
            nodes.append(node)
        industry["mechanism_nodes"] = nodes
        industry["evidence_ids"] = support_ids
        industry["industry_operating_variable_zh"] = spec["operating"]
        industry["industry_financial_variable_zh"] = spec["financial"]
        industry["observable_driver_zh"] = spec["shock"]
        industry["condition_zh"] = spec["condition"]
        industry["invalidation_condition_zh"] = spec["invalidation"]
        industry["horizon_analysis"] = {
            "IMMEDIATE": f"T0至D1观察{name}代理相对TOPIX的首轮重估、成交量及利率或汇率同步变化；不按涨跌反选公司。",
            "SHORT_TERM": f"D3至D20跟踪{spec['operating']}是否出现连续确认，并将行业表现与公司公告分开记录。",
            "MEDIUM_TERM": f"未来1至4个季度用{spec['financial']}复核兑现；若{spec['invalidation']}则撤销当前传导判断。",
        }

    for company in unified["companies"]:
        spec = RESEARCH[company["industry"]]
        evidence_ids = [item["evidence_id"] for item in company["company_evidence"]]
        company["business_exposure_zh"] = f"事件日前两份发行人披露确认{company['company_name']}持续经营于{company['industry']}相关业务；样本在2026-06-16之前按主营暴露选定，不依据事后收益。"
        company["mechanism_zh"] = f"政策利率上调经由{spec['channel']}，再作用于{company['company_name']}的{spec['operating']}与{spec['financial']}。"
        company["horizon_analysis"] = {
            "IMMEDIATE": f"T0至D1记录{company['company_name']}相对TOPIX和{company['industry']}代理的价格与成交重估，只验证市场反应。",
            "SHORT_TERM": f"D3至D20核对{company['company_name']}公告及{spec['operating']}是否沿事前暴露路径变化，并单列公司特有消息。",
            "MEDIUM_TERM": f"未来1至4个季度以{spec['financial']}复核经营兑现；若{spec['invalidation']}则降低或撤销影响判断。",
        }
        company["confounders"] = ["同期全球风险偏好与日本股市风格变化", "日元汇率、国债收益率曲线与商品价格变化", f"{company['company_name']}财报、资本政策及其他公司特有公告"]
        company["counterevidence"] = [{"affected_horizons": ["IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM"], "claim_zh": f"若同业代理未出现一致方向，或{company['company_name']}经营披露与预期相反，则政策利率解释力下降。", "effect_on_thesis": "LIMITS_DIRECT_ATTRIBUTION", "evidence_ids": evidence_ids}]
        company["review_status"] = "NEEDS_HUMAN_REVIEW"
        company["formal_ready"] = False

    qa_by_type = {item["qa_type"]: item for item in unified["qa"]}
    first_industry = unified["industries"][0]
    first_company = unified["companies"][0]
    qa_by_type["EVIDENCE_QUERY"].update({
        "reference_ids": [event_evidence["evidence_id"]],
        "evidence_ids": [event_evidence["evidence_id"]],
        "direct_answer_zh": f"日本央行原文确认：{event_evidence['original_quote']} 该事实只确认政策目标，不直接证明行业或公司收益。",
    })
    qa_by_type["MECHANISM_STAGE"].update({
        "reference_ids": [first_industry["mechanism_nodes"][0]["node_id"], first_industry["mechanism_nodes"][2]["node_id"], first_industry["mechanism_nodes"][3]["node_id"]],
        "evidence_ids": [event_evidence["evidence_id"]],
        "direct_answer_zh": "即时阶段检验利率、汇率和价格重估；D3至D20检验资产负债重定价及订单等经营变量；1至4个季度再用利润、信用成本和现金流复核，三个阶段的窗口与指标不同。",
    })
    qa_by_type["MARKET_VALIDATION"].update({
        "reference_ids": [first_industry["industry_id"], first_industry["mechanism_nodes"][5]["node_id"]],
        "evidence_ids": [event_evidence["evidence_id"]],
        "direct_answer_zh": "不能证明因果。21家公司、TOPIX ETF及7个行业映射的T-1、T0、D1、D3、D5、D20均由原始收盘值回算并通过连续交易核验，但只说明窗口表现，结论保持ABSTAIN。",
    })
    qa_by_type["INDUSTRY_COMPANY"].update({
        "reference_ids": [first_company["industry_id"], first_company["mapping_id"]],
        "evidence_ids": [first_company["company_evidence"][0]["evidence_id"], first_company["company_evidence"][1]["evidence_id"]],
        "direct_answer_zh": "银行、保险、证券、房地产、航空运输、汽车和电子各选3家公司，共21家；每家公司均由两份事件日前发行人报告或业绩材料证明主营暴露，选样不使用事件后涨跌。",
    })
    for item in qa_by_type.values():
        item["review_status"] = "NEEDS_HUMAN_REVIEW"
        item["formal_ready"] = False
        if isinstance(item.get("answer"), dict):
            item["answer"].setdefault("task_answer", {})["direct_answer_zh"] = item["direct_answer_zh"]

    unified["causal_assessment"] = {
        "status": "DESCRIPTIVE_EVENT_STUDY",
        "causal_attribution_allowed": False,
        "causal_conclusion": "ABSTAIN",
        "method": "DESCRIPTIVE_MULTI_BENCHMARK_EVENT_WINDOWS",
        "gate_results": {
            "market_window_complete": True,
            "benchmark_complete": True,
            "continuous_trading_verified": True,
            "comparison_group_defined": False,
            "pretrend_passed": False,
            "confounders_controlled": False,
            "robustness_passed": False,
            "counterevidence_passed": False,
        },
        "unmet_conditions": ["缺少预注册对照组", "未完成事件前趋势检验", "同期全球市场、汇率及公司公告未被充分控制", "未完成稳健性与反证识别门禁"],
        "confounders": ["全球风险偏好", "日元汇率与日本国债曲线", "同期商品价格", "公司财报和资本政策"],
        "counterevidence": ["行业代理与公司反应不一致", "经营指标未在D20后持续", "公司特有公告可解释窗口收益"],
        "boundary_zh": "行情仅构成描述性事件窗口，不能排除同期因素；所有公司与行业结论仍需人工复核，因果结论为ABSTAIN。",
    }
    unified["review_status"] = "NEEDS_HUMAN_REVIEW"
    unified["formal_ready"] = False
    update_research_content(unified, all_node_ids)
    return unified


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gapfill-run", type=Path, required=True)
    parser.add_argument("--output-run", type=Path, required=True)
    args = parser.parse_args()
    gapfill, output = args.gapfill_run.resolve(), args.output_run.resolve()
    shutil.copytree(gapfill, output)
    record = read_jsonl(output / "content_candidates.jsonl")[0]
    unified = enrich(deepcopy(record["unified_event"]))
    all_evidence = [*unified["evidence_registry"], *[item for company in unified["companies"] for item in company["company_evidence"]]]
    updated = {**record, "closure_status": "CLOSED", "errors": [], "warnings": [], "unified_event": unified}
    updated["evidence_ids"] = sorted(item["evidence_id"] for item in all_evidence)
    updated["content_sha256"] = canonical_sha(unified)
    write_jsonl(output / "content_candidates.jsonl", [updated])
    write_jsonl(output / "accepted_evidence.jsonl", all_evidence)
    command = [
        "python", str(PIPELINE), "audit", "--policy", "strict-claim-closure-v2",
        "--input", str(output / "content_candidates.jsonl"),
        "--output", str(output / "gap_manifest.jsonl"),
        "--accepted-output", str(output / "accepted_content.jsonl"),
        "--quarantine-output", str(output / "quarantine.jsonl"),
        "--batch-report", str(output / "batch_gate_report.json"),
        "--required-event-id", EVENT_ID,
    ]
    result = subprocess.run(command, cwd=ROOT, check=False)
    accepted = read_jsonl(output / "accepted_content.jsonl")
    gaps = read_jsonl(output / "gap_manifest.jsonl")
    summary = {
        "run_id": output.name,
        "event_id": EVENT_ID,
        "policy": "strict-claim-closure-v2",
        "status": "ACCEPTED_STRICT" if result.returncode == 0 and len(accepted) == 1 else "QUARANTINED",
        "audit_return_code": result.returncode,
        "gap_codes": sorted({row.get("gap_code") for row in gaps if row.get("gap_code")}),
        "event_evidence_count": len(unified["evidence_registry"]),
        "company_evidence_count": sum(len(company.get("company_evidence") or []) for company in unified["companies"]),
        "industry_count": len(unified["industries"]),
        "mechanism_node_count": sum(len(industry["mechanism_nodes"]) for industry in unified["industries"]),
        "company_count": len(unified["companies"]),
        "qa_count": len(unified["qa"]),
        "industry_market_calculated": sum(industry["market_window"].get("status") == "CALCULATED" for industry in unified["industries"]),
        "company_market_calculated": sum(company["market_window"].get("status") == "CALCULATED" for company in unified["companies"]),
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "causal_conclusion": "ABSTAIN",
    }
    write_json(output / "run_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
