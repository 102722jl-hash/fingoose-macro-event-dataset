"""Build AI desk-review evidence candidates from extracted official reports."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from fingoose_company_dossier_builder_v2 import select_evidence_passage
from fingoose_company_impact_io_v2 import make_id


PROFILES = {
    "BUSINESS_EXPOSURE": ["公司从事的主要业务", "主营业务包括", "主营业务为", "业务范围", "业务概述"],
    "GEOGRAPHIC_EXPOSURE": ["分地区", "境外收入", "海外收入", "地区分部", "地域分布", "国外销售", "国内销售", "境外销售"],
    "DEMAND_COST_EXPOSURE": [
        "市场需求", "原材料价格", "燃油成本", "航油价格", "原油价格",
        "运输成本", "利率风险", "汇率风险", "运价", "客户需求",
    ],
    "LIMITATION_OR_COUNTEREVIDENCE": [
        "套期保值", "长期合同", "价格传导", "风险因素", "不确定性",
        "影响有限", "风险管理",
    ],
}

INDUSTRY_TERMS = {
    "600009.SH": ["旅客吞吐量", "航空性业务", "非航空性业务"],
    "601111.SH": ["航空运输", "航油成本", "旅客周转量"],
    "600754.SH": ["酒店业务", "有限服务型酒店", "客房"],
    "601021.SH": ["航空运输", "航油成本", "客座率"],
    "601857.SH": ["原油价格", "天然气价格", "油气产量"],
    "601233.SH": ["涤纶长丝", "原材料价格", "PTA"],
    "600346.SH": ["炼化", "原材料价格", "PTA"],
    "600028.SH": ["原油价格", "炼油", "成品油"],
    "000301.SZ": ["化纤", "原材料价格", "炼化"],
    "601919.SH": ["集装箱航运", "运价", "燃油成本"],
    "601318.SH": ["保险业务", "投资收益", "利率风险"],
    "600036.SH": ["利率风险", "净利息收入", "信贷"],
    "601988.SH": ["利率风险", "信用风险", "净利息收入"],
    "601211.SH": ["证券业务", "资本市场", "自营投资"],
    "600048.SH": ["房地产开发", "销售回款", "融资成本"],
    "300059.SZ": ["证券业务", "基金销售", "资本市场"],
    "002030.SZ": ["体外诊断", "诊断试剂", "市场需求"],
    "002432.SZ": ["医疗器械", "检测试剂", "市场需求"],
    "300482.SZ": ["体外诊断", "检测试剂", "市场需求"],
    "688235.SH": ["药品销售", "研发投入", "商业化"],
    "601012.SH": ["光伏", "硅片", "原材料价格"],
    "002475.SZ": ["消费电子", "客户需求", "汇率风险"],
    "000333.SZ": ["家用电器", "海外市场", "原材料价格"],
}

DRIVER_TERMS = {
    "旅客吞吐量", "航油成本", "客座率", "原油价格", "天然气价格",
    "原材料价格", "运价", "燃油成本", "投资收益", "利率风险",
    "信用风险", "资本市场", "销售回款", "融资成本", "市场需求",
    "客户需求", "汇率风险", "海外市场",
}


def terms_for_claim(company_code: str, claim_type: str) -> list[str]:
    base_terms = PROFILES[claim_type]
    extra_terms = (
        [term for term in INDUSTRY_TERMS.get(company_code, []) if term in DRIVER_TERMS]
        if claim_type == "DEMAND_COST_EXPOSURE"
        else []
    )
    return list(dict.fromkeys(base_terms + extra_terms))

def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def build(root: Path) -> dict[str, object]:
    output = root / "work" / "company_impact_high_quality_v2_candidate"
    config = root / "configs" / "company_impact_high_quality_v2"
    companies = read_jsonl(config / "company_registry.jsonl")
    sources = read_jsonl(output / "source_manifest_seed.jsonl")
    pages_by_source: dict[str, list[dict[str, object]]] = defaultdict(list)
    for page in read_jsonl(output / "company_report_pages.jsonl"):
        pages_by_source[str(page["source_id"])].append(page)

    claims: list[dict[str, object]] = []
    evidence_rows: list[dict[str, object]] = []
    dossiers: list[dict[str, object]] = []
    for company in companies:
        company_sources = sorted(
            [row for row in sources if row["company_id"] == company["company_id"]],
            key=lambda row: (str(row["published_at"]), str(row["source_class"])),
        )
        claim_ids: list[str] = []
        claim_statuses: list[str] = []
        for claim_type, base_terms in PROFILES.items():
            terms = terms_for_claim(str(company["company_code"]), claim_type)
            claim_id = make_id(
                "company-claim",
                {"company_id": company["company_id"], "claim_type": claim_type},
            )
            claim_ids.append(claim_id)
            candidate_ids: list[str] = []
            source_ids: list[str] = []
            for source in company_sources:
                source_id = str(source["source_id"])
                selected = select_evidence_passage(pages_by_source[source_id], terms)
                if not selected:
                    continue
                evidence_id = make_id(
                    "company-evidence",
                    {
                        "claim_id": claim_id,
                        "source_id": source_id,
                        "page": selected["page_number"],
                    },
                )
                candidate_ids.append(evidence_id)
                source_ids.append(source_id)
                evidence_rows.append(
                    {
                        "evidence_id": evidence_id,
                        "claim_id": claim_id,
                        "claim_type": claim_type,
                        "company_id": company["company_id"],
                        "company_code": company["company_code"],
                        "source_id": source_id,
                        "document_id": source["document_id"],
                        "source_class": source["source_class"],
                        "source_url": source["source_url"],
                        "document_title": source["document_title"],
                        "issuer": source["issuer"],
                        "published_at": source["published_at"],
                        "published_at_precision": source["published_at_precision"],
                        "reporting_period": source["reporting_period"],
                        "original_quote": selected["original_quote"],
                        "page_or_section_locator": selected[
                            "page_or_section_locator"
                        ],
                        "matched_terms": selected["matched_terms"],
                        "availability_scope": source["availability_scope"],
                        "review_origin": "AI_DESK_REVIEW",
                        "review_status": "NEEDS_HUMAN_REVIEW",
                        "sha_gate": "DEFERRED",
                        "formal_ready": False,
                    }
                )
            document_count = len(set(source_ids))
            status = (
                "CANDIDATE_EXTRACTED"
                if document_count >= 2
                else "PARTIAL_CANDIDATE"
                if document_count == 1
                else "DATA_PENDING"
            )
            claim_statuses.append(status)
            claims.append(
                {
                    "claim_id": claim_id,
                    "claim_type": claim_type,
                    "company_id": company["company_id"],
                    "company_code": company["company_code"],
                    "normalized_claim": None,
                    "candidate_evidence_ids": candidate_ids,
                    "candidate_official_document_count": document_count,
                    "verification_status": status,
                    "review_origin": "AI_DESK_REVIEW",
                    "review_status": "NEEDS_HUMAN_REVIEW",
                    "gap_reason": (
                        None if candidate_ids else "NO_KEYWORD_EVIDENCE_FOUND"
                    ),
                    "formal_ready": False,
                }
            )
        dossiers.append(
            {
                **company,
                "official_document_count": len(
                    {str(row["document_id"]) for row in company_sources}
                ),
                "source_ids": [row["source_id"] for row in company_sources],
                "claim_ids": claim_ids,
                "candidate_claim_statuses": claim_statuses,
                "dossier_status": "PARTIALLY_VERIFIED",
                "business_exposure": None,
                "geographic_exposure": None,
                "demand_cost_exposure": None,
                "limitations_and_counterevidence": None,
                "review_origin": "AI_DESK_REVIEW",
                "review_status": "NEEDS_HUMAN_REVIEW",
                "gap_reason": "NORMALIZED_CLAIMS_PENDING_SEMANTIC_REVIEW",
                "sha_gate": "DEFERRED",
                "formal_ready": False,
            }
        )

    write_jsonl(output / "company_claim_candidates.jsonl", claims)
    write_jsonl(output / "company_evidence.jsonl", evidence_rows)
    write_jsonl(output / "company_master_dossiers.jsonl", dossiers)
    summary = {
        "company_count": len(dossiers),
        "claim_count": len(claims),
        "evidence_candidate_count": len(evidence_rows),
        "two_document_claim_candidate_count": sum(
            int(row["candidate_official_document_count"]) >= 2 for row in claims
        ),
        "partial_claim_candidate_count": sum(
            int(row["candidate_official_document_count"]) == 1 for row in claims
        ),
        "missing_claim_candidate_count": sum(
            int(row["candidate_official_document_count"]) == 0 for row in claims
        ),
        "verified_dossier_count": 0,
        "partial_dossier_count": len(dossiers),
        "review_status": "NEEDS_HUMAN_REVIEW",
        "sha_gate": "DEFERRED",
        "formal_ready": False,
    }
    (output / "dossier_candidate_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    print(json.dumps(build(project_root), ensure_ascii=False, indent=2))
