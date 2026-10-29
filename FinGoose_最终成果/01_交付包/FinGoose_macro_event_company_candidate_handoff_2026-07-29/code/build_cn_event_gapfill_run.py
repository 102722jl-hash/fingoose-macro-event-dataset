from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
import build_event12_gapfill_run as gap


CONFIGS = {
    "event-11": {
        "anchor_date": "2026-03-11",
        "benchmarks": {
            "石油开采": ("801960", "石油石化", "申万石油石化指数作为石油开采上位行业代理"),
            "炼油": ("801960", "石油石化", "申万石油石化指数作为炼油代理"),
            "天然气与LNG": ("801960", "石油石化", "申万石油石化指数作为天然气与LNG上位行业代理"),
            "航运": ("801170", "交通运输", "申万交通运输指数作为航运上位行业代理"),
            "航空运输": ("801170", "交通运输", "申万交通运输指数作为航空运输上位行业代理"),
            "化工": ("801030", "基础化工", "申万基础化工指数作为化工代理"),
            "化肥": ("801030", "基础化工", "申万基础化工指数作为化肥上位行业代理"),
        },
        "keywords": {
            "石油开采": ["公司从事的主要业务", "主营业务", "油气", "石油", "钻井"],
            "炼油": ["公司从事的主要业务", "主营业务", "炼油", "石化", "成品油"],
            "天然气与LNG": ["公司从事的主要业务", "主营业务", "天然气", "LNG", "燃气"],
            "航运": ["公司从事的主要业务", "主营业务", "航运", "集装箱", "油轮"],
            "航空运输": ["公司从事的主要业务", "主营业务", "航空运输", "航油", "客运"],
            "化工": ["公司从事的主要业务", "主营业务", "化工", "化学品", "新材料"],
            "化肥": ["公司从事的主要业务", "主营业务", "化肥", "尿素", "钾肥"],
        },
    },
    "event-14": {
        "anchor_date": "2026-03-16",
        "benchmarks": {
            "建筑与基础设施": ("801720", "建筑装饰", "申万建筑装饰指数作为建筑与基础设施代理"),
            "工程机械": ("801890", "机械设备", "申万机械设备指数作为工程机械上位行业代理"),
            "建材": ("801710", "建筑材料", "申万建筑材料指数作为建材代理"),
            "银行": ("801780", "银行", "申万银行指数作为银行代理"),
            "消费品": ("801120", "食品饮料", "样本公司均为食品饮料企业，使用申万食品饮料指数"),
            "汽车": ("801880", "汽车", "申万汽车指数作为汽车代理"),
            "家电": ("801110", "家用电器", "申万家用电器指数作为家电代理"),
        },
        "keywords": {
            "建筑与基础设施": ["公司从事的主要业务", "主营业务", "基础设施", "工程承包", "建筑"],
            "工程机械": ["公司从事的主要业务", "主营业务", "工程机械", "装备制造"],
            "建材": ["公司从事的主要业务", "主营业务", "建材", "水泥", "防水材料"],
            "银行": ["公司业务概要", "主营业务", "公司金融", "贷款", "银行"],
            "消费品": ["公司从事的主要业务", "主营业务", "白酒", "乳制品", "食品"],
            "汽车": ["公司从事的主要业务", "主营业务", "汽车", "整车", "新能源汽车"],
            "家电": ["公司从事的主要业务", "主营业务", "家用电器", "空调", "冰箱"],
        },
    },
    "event-15": {
        "anchor_date": "2026-02-27",
        "benchmarks": {
            "银行": ("801780", "银行", "申万银行指数作为银行代理"),
            "证券": ("801790", "非银金融", "申万非银金融指数作为证券上位行业代理"),
            "航空运输": ("801170", "交通运输", "申万交通运输指数作为航空运输上位行业代理"),
            "石油石化": ("801960", "石油石化", "申万石油石化指数作为石油石化代理"),
            "电子": ("801080", "电子", "申万电子指数作为电子代理"),
            "家用电器": ("801110", "家用电器", "申万家用电器指数作为家用电器代理"),
            "汽车": ("801880", "汽车", "申万汽车指数作为汽车代理"),
        },
        "keywords": {
            "银行": ["公司业务概要", "主营业务", "外汇", "衍生金融工具", "银行"],
            "证券": ["公司从事的主要业务", "主营业务", "证券", "衍生品", "外汇"],
            "航空运输": ["公司从事的主要业务", "主营业务", "航空运输", "航油", "汇率"],
            "石油石化": ["公司从事的主要业务", "主营业务", "石油", "炼化", "汇率"],
            "电子": ["公司从事的主要业务", "主营业务", "电子", "出口", "汇率"],
            "家用电器": ["公司从事的主要业务", "主营业务", "家用电器", "出口", "汇率"],
            "汽车": ["公司从事的主要业务", "主营业务", "汽车", "出口", "汇率"],
        },
    },
    "event-16": {
        "anchor_date": "2026-03-04",
        "benchmarks": {
            "钢铁": ("801040", "钢铁", "申万钢铁指数作为钢铁代理"),
            "水泥": ("801710", "建筑材料", "申万建筑材料指数作为水泥上位行业代理"),
            "铝": ("801050", "有色金属", "申万有色金属指数作为铝上位行业代理"),
            "汽车": ("801880", "汽车", "申万汽车指数作为汽车代理"),
            "电池": ("801730", "电力设备", "申万电力设备指数作为电池上位行业代理"),
            "光伏": ("801730", "电力设备", "申万电力设备指数作为光伏上位行业代理"),
            "风电设备": ("801730", "电力设备", "申万电力设备指数作为风电设备上位行业代理"),
        },
        "keywords": {
            "钢铁": ["公司从事的主要业务", "主营业务", "钢铁", "低碳", "出口"],
            "水泥": ["公司从事的主要业务", "主营业务", "水泥", "低碳", "海外"],
            "铝": ["公司从事的主要业务", "主营业务", "铝", "低碳", "出口"],
            "汽车": ["公司从事的主要业务", "主营业务", "汽车", "欧洲", "出口"],
            "电池": ["公司从事的主要业务", "主营业务", "电池", "欧洲", "海外"],
            "光伏": ["公司从事的主要业务", "主营业务", "光伏", "欧洲", "海外"],
            "风电设备": ["公司从事的主要业务", "主营业务", "风电", "欧洲", "海外"],
        },
    },
    "event-17": {
        "anchor_date": "2026-04-10",
        "benchmarks": {
            "证券": ("801790", "非银金融", "申万非银金融指数作为证券上位行业代理"),
            "创投": ("801790", "非银金融", "申万非银金融指数作为创投相关金融活动上位代理"),
            "信息技术": ("801750", "计算机", "申万计算机指数作为信息技术代理"),
            "新能源": ("801730", "电力设备", "申万电力设备指数作为新能源代理"),
            "高端装备": ("801890", "机械设备", "申万机械设备指数作为高端装备代理"),
            "新消费": ("801120", "食品饮料", "样本公司均为食品企业，使用申万食品饮料指数"),
            "金融信息服务": ("801750", "计算机", "申万计算机指数作为金融信息服务上位行业代理"),
        },
        "keywords": {
            "证券": ["公司从事的主要业务", "主营业务", "证券", "投资银行", "创业板"],
            "创投": ["公司从事的主要业务", "主营业务", "股权投资", "创业投资", "投资"],
            "信息技术": ["公司从事的主要业务", "主营业务", "软件", "信息技术", "数字化"],
            "新能源": ["公司从事的主要业务", "主营业务", "光伏", "新能源汽车", "新能源"],
            "高端装备": ["公司从事的主要业务", "主营业务", "工程机械", "高端装备", "装备制造"],
            "新消费": ["公司从事的主要业务", "主营业务", "食品", "调味品", "消费"],
            "金融信息服务": ["公司从事的主要业务", "主营业务", "金融信息", "证券信息", "金融科技"],
        },
    },
}


def configure(event_id: str) -> None:
    config = CONFIGS[event_id]
    anchor = config["anchor_date"]
    gap.EVENT_ID = event_id
    gap.ANCHOR_DATE = anchor
    gap.CUTOFF_DATE = anchor
    gap.RETRIEVED_AT = datetime.now(timezone.utc).isoformat()
    gap.INDUSTRY_BENCHMARKS = config["benchmarks"]
    gap.KEYWORDS = config["keywords"]


def seed_raw_cache(output: Path, event_id: str, seed_runs: list[Path]) -> None:
    for seed in seed_runs:
        for relative in (Path("online/company_reports/query_responses"), Path("online/company_reports/pdf")):
            source_root = seed / relative
            target_root = output / relative
            if not source_root.exists():
                continue
            target_root.mkdir(parents=True, exist_ok=True)
            for source in source_root.iterdir():
                target = target_root / source.name
                if source.is_file() and not target.exists():
                    shutil.copy2(source, target)
        source_market = seed / "online" / "market" / "company"
        target_market = output / "online" / "market" / "company"
        if source_market.exists():
            target_market.mkdir(parents=True, exist_ok=True)
            for source in source_market.glob("public-price-event-*-*.json"):
                suffix = source.name.split("-", 4)[-1]
                target = target_market / f"public-price-{event_id}-{suffix}"
                if not target.exists():
                    shutil.copy2(source, target)
        source_industry = seed / "online" / "market" / "industry"
        target_industry = output / "online" / "market" / "industry"
        if source_industry.exists():
            target_industry.mkdir(parents=True, exist_ok=True)
            for source in source_industry.glob("*.csv"):
                target = target_industry / source.name
                if not target.exists():
                    shutil.copy2(source, target)


def build(event_id: str, source: Path, output: Path, resume: bool, seed_runs: list[Path]) -> dict:
    configure(event_id)
    gap.init_run(source, output, resume=resume)
    seed_raw_cache(output, event_id, seed_runs)
    content_path = source / "accepted_content.jsonl"
    rows = gap.read_jsonl(content_path) if content_path.exists() and content_path.stat().st_size else gap.read_jsonl(source / "content_candidates.jsonl")
    target = next(deepcopy(row) for row in rows if row["event_id"] == event_id)
    unified = target["unified_event"]
    if event_id == "event-11":
        replacements = {
            "XOM": ("601808.SH", "中海油服", "company-601808-sh", "埃克森美孚"),
            "600938.SH": ("600871.SH", "石化油服", "company-600871-sh", "中国海油"),
            "603393.SH": ("600917.SH", "重庆燃气", "company-600917-sh", "新天然气"),
        }
        for old_code, (new_code, new_name, new_id, old_name) in replacements.items():
            company = next(row for row in unified["companies"] if row["company_code"] == old_code)
            company.update({"company_code": new_code, "company_name": new_name, "company_id": new_id})
            for key in ("business_exposure_zh", "mechanism_zh"):
                company[key] = str(company.get(key) or "").replace(old_name, new_name).replace(old_code, new_code)
    if event_id == "event-16":
        replacements = [
            ("600019.SH", "宝钢股份"), ("000932.SZ", "华菱钢铁"), ("600010.SH", "包钢股份"),
            ("600585.SH", "海螺水泥"), ("000877.SZ", "天山股份"), ("600801.SH", "华新水泥"),
            ("601600.SH", "中国铝业"), ("000807.SZ", "云铝股份"), ("002532.SZ", "天山铝业"),
            ("002594.SZ", "比亚迪"), ("601633.SH", "长城汽车"), ("600104.SH", "上汽集团"),
            ("300750.SZ", "宁德时代"), ("002460.SZ", "赣锋锂业"), ("002466.SZ", "天齐锂业"),
            ("601012.SH", "隆基绿能"), ("300274.SZ", "阳光电源"), ("688223.SH", "晶科能源"),
            ("002202.SZ", "金风科技"), ("601615.SH", "明阳智能"), ("688349.SH", "三一重能"),
        ]
        for company, (new_code, new_name) in zip(unified["companies"], replacements):
            old_code, old_name = company["company_code"], company["company_name"]
            company.update({"company_code": new_code, "company_name": new_name, "company_id": "company-" + new_code.lower().replace(".", "-")})
            for key in ("business_exposure_zh", "mechanism_zh"):
                company[key] = str(company.get(key) or "").replace(old_name, new_name).replace(old_code, new_code)
    evidence_cache = output / "accepted_company_evidence.jsonl"
    if resume and evidence_cache.exists():
        evidence = gap.read_jsonl(evidence_cache)
        current_codes = {company["company_code"] for company in unified["companies"]}
        evidence = [row for row in evidence if row["company_code"] in current_codes]
        audits = gap.read_jsonl(output / "company_search_audit.jsonl")
        quarantine = gap.read_jsonl(output / "quarantine.company.jsonl") if (output / "quarantine.company.jsonl").exists() else []
        if len(evidence) < len(unified["companies"]) * 2:
            counts = {company["company_code"]: len({row["document_id"] for row in evidence if row["company_code"] == company["company_code"]}) for company in unified["companies"]}
            missing_unified = deepcopy(unified)
            missing_unified["companies"] = [company for company in unified["companies"] if counts[company["company_code"]] < 2]
            new_audits, new_evidence, new_quarantine = gap.acquire_company_evidence(missing_unified, output)
            audits = list({(row["company_code"], row["response_sha256"]): row for row in [*audits, *new_audits]}.values())
            evidence = list({row["evidence_id"]: row for row in [*evidence, *new_evidence]}.values())
            quarantine = new_quarantine
            gap.write_jsonl(output / "company_search_audit.jsonl", audits)
            gap.write_jsonl(output / "company_evidence_candidates.jsonl", evidence)
            gap.write_jsonl(evidence_cache, evidence)
            gap.write_jsonl(output / "quarantine.company.jsonl", quarantine)
    else:
        audits, evidence, quarantine = gap.acquire_company_evidence(unified, output)
        gap.write_jsonl(output / "company_search_audit.jsonl", audits)
        gap.write_jsonl(output / "company_evidence_candidates.jsonl", evidence)
        gap.write_jsonl(evidence_cache, evidence)
        gap.write_jsonl(output / "quarantine.company.jsonl", quarantine)
    prices, price_quarantine = gap.acquire_company_market(unified, output)
    gap.write_jsonl(output / "company_market_windows.jsonl", prices)
    windows, fetch_records = gap.industry_market(unified, output)
    gap.write_jsonl(output / "industry_market_windows.jsonl", windows)
    gap.write_jsonl(output / "market_fetch_audit.jsonl", fetch_records)
    quarantine.extend(price_quarantine)
    enriched = gap.enrich(unified, evidence, prices, windows)
    target["unified_event"] = enriched
    target["closure_status"] = "STRICT_AUDIT_PENDING"
    target["errors"] = []
    target["warnings"] = []
    target["evidence_ids"] = sorted(set([*target.get("evidence_ids", []), *[item["evidence_id"] for item in evidence]]))
    target["content_sha256"] = gap.content_sha(enriched)
    gap.write_jsonl(output / "quarantine.acquisition.jsonl", quarantine)
    gap.write_jsonl(output / "content_candidates.jsonl", [target])
    event_evidence = gap.read_jsonl(source / "accepted_evidence.jsonl")
    accepted_event_evidence = [row for row in event_evidence if row.get("event_id") == event_id]
    gap.write_jsonl(output / "accepted_evidence.jsonl", [*accepted_event_evidence, *evidence])
    summary = {
        "event_id": event_id,
        "run_id": output.name,
        "company_count": len(unified["companies"]),
        "company_evidence_count": len(evidence),
        "companies_with_two_documents": sum(len({row["document_id"] for row in evidence if row["company_code"] == company["company_code"]}) >= 2 for company in unified["companies"]),
        "company_market_window_count": len(prices),
        "full_company_window_count": sum(row["status"] == "WINDOW_AVAILABLE" for row in prices),
        "industry_market_window_count": len(windows),
        "available_industry_window_count": sum(row["window_status"] == "AVAILABLE" for row in windows),
        "acquisition_quarantine_count": len(quarantine),
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "causal_conclusion": "ABSTAIN",
    }
    gap.write_json(output / "gapfill_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-id", choices=sorted(CONFIGS), required=True)
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--output-run", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--seed-run", type=Path, action="append", default=[])
    args = parser.parse_args()
    summary = build(args.event_id, args.source_run.resolve(), args.output_run.resolve(), args.resume, [path.resolve() for path in args.seed_run])
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
