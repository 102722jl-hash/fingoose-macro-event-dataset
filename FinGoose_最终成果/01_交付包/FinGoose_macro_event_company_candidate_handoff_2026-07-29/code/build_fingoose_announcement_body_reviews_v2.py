"""Build body-level review candidates from retrieved official announcements."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from fingoose_company_confounder_evidence_closure_v2 import validate_body_review
from fingoose_company_impact_io_v2 import read_jsonl, write_jsonl


TYPE_KEYWORDS = {
    "CAPITAL_RETURN": ("回购", "持股", "股份", "减持", "增持", "员工持股"),
    "FINANCING": ("融资", "债券", "借款", "授信", "担保", "票据"),
    "EARNINGS": ("净利润", "营业收入", "业绩", "亏损", "盈利"),
    "MAJOR_CONTRACT": ("合同", "订单", "中标", "销售", "采购"),
    "REGULATORY": ("处罚", "调查", "监管", "批准", "许可"),
    "RESTRUCTURING": ("重组", "收购", "出售", "资产", "合并"),
    "LITIGATION": ("诉讼", "仲裁", "判决", "纠纷"),
    "MATERIAL_OPERATION": ("经营", "产量", "销量", "停产", "复产", "项目"),
}

MECHANISMS = {
    "CAPITAL_RETURN": "股份回购、员工持股或股东交易可能独立改变股份供求、持股预期和估值。",
    "FINANCING": "融资、债务或担保事项可能独立改变流动性、杠杆和资本成本预期。",
    "EARNINGS": "盈利或经营数据披露可能直接修正市场对收入和利润的预期。",
    "MAJOR_CONTRACT": "合同、订单或中标事项可能独立改变收入兑现和业务增长预期。",
    "REGULATORY": "监管、许可或处罚事项可能独立改变业务准入、合规成本和经营连续性预期。",
    "RESTRUCTURING": "资产交易或重组事项可能独立改变资产结构、盈利能力和估值框架。",
    "LITIGATION": "诉讼或仲裁事项可能独立改变潜在损失和经营不确定性。",
    "MATERIAL_OPERATION": "重大经营事项可能独立改变产量、销量、成本或收入预期。",
    "CONVERTIBLE_BOND_SUSPENSION": (
        "可转债转股或债券交易停牌可能影响转股节奏，但不能据此认定公司股票停牌。"
    ),
}

IRRELEVANT_TITLE_MARKERS = (
    "前十名股东",
    "法律意见书",
    "独立意见",
    "管理办法",
    "摘要",
    "异常波动",
)
MATERIAL_TITLE_MARKERS = (
    "业绩预告",
    "业绩快报",
    "重大合同",
    "中标",
    "诉讼",
    "处罚",
    "调查",
    "重大资产",
    "重组",
    "停牌",
    "复牌",
)


def _pages(text: str) -> list[tuple[int, str]]:
    matches = list(re.finditer(r"=== PAGE (\d+) ===\n", text))
    result = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        result.append((int(match.group(1)), text[match.end():end].strip()))
    return result or [(1, text.strip())]


def select_quote(text: str, title: str, confounder_type: str) -> tuple[str, str]:
    tokens = list(TYPE_KEYWORDS.get(confounder_type, ()))
    tokens.extend(
        token
        for token in re.findall(r"[\u4e00-\u9fff]{2,6}", title)
        if token not in {"公告", "公司", "股份有限公司"}
    )
    best: tuple[int, int, str] | None = None
    best_page = 1
    for page_number, page_text in _pages(text):
        positions = [page_text.find(token) for token in tokens if token and token in page_text]
        positions = [position for position in positions if position >= 0]
        position = min(positions) if positions else 0
        start = max(0, position - 70)
        end = min(len(page_text), position + 280)
        candidate = page_text[start:end].strip()
        if not candidate:
            continue
        score = sum(token in candidate for token in tokens) * 5
        score += min(5, len(re.findall(r"\d", candidate)))
        score += 2 if position > 40 else 0
        ranked = (score, -page_number, candidate)
        if best is None or ranked > best:
            best = ranked
            best_page = page_number
    if best is None:
        raise ValueError("EXTRACTED_TEXT_EMPTY")
    return best[2], f"PDF page {best_page}"


def disposition_for_announcement(title: str, confounder_type: str) -> dict[str, Any]:
    if confounder_type == "SUSPENSION" and any(
        marker in title for marker in ("转债", "可转换公司债券", "债券")
    ):
        return {
            "relevance_decision": "MINOR_RELEVANCE",
            "severity_candidate": "MINOR",
            "rejection_reason": None,
            "instrument_scope": "CONVERTIBLE_BOND",
            "equity_trading_status_evidence_eligible": False,
            "mechanism_zh": MECHANISMS["CONVERTIBLE_BOND_SUSPENSION"],
        }
    if any(marker in title for marker in IRRELEVANT_TITLE_MARKERS):
        return {
            "relevance_decision": "IRRELEVANT",
            "severity_candidate": "CLEAN",
            "rejection_reason": "该文件属于程序性、重复性或异常波动说明，未单独形成可量化的公司经营冲击候选。",
            "instrument_scope": "GENERAL",
            "equity_trading_status_evidence_eligible": False,
            "mechanism_zh": MECHANISMS.get(
                confounder_type, MECHANISMS["MATERIAL_OPERATION"]
            ),
        }
    if any(marker in title for marker in MATERIAL_TITLE_MARKERS) or confounder_type in {
        "EARNINGS",
        "MAJOR_CONTRACT",
        "LITIGATION",
        "RESTRUCTURING",
    }:
        relevance, severity = "RELEVANT", "MATERIAL"
    else:
        relevance, severity = "MINOR_RELEVANCE", "MINOR"
    equity_eligible = confounder_type == "SUSPENSION" and any(
        marker in title for marker in ("股票停牌", "公司股票", "股票复牌")
    )
    return {
        "relevance_decision": relevance,
        "severity_candidate": severity,
        "rejection_reason": None,
        "instrument_scope": "EQUITY" if equity_eligible else "GENERAL",
        "equity_trading_status_evidence_eligible": equity_eligible,
        "mechanism_zh": MECHANISMS.get(
            confounder_type, MECHANISMS["MATERIAL_OPERATION"]
        ),
    }


def _disposition(title: str, confounder_type: str) -> tuple[str, str, str | None]:
    result = disposition_for_announcement(title, confounder_type)
    return (
        str(result["relevance_decision"]),
        str(result["severity_candidate"]),
        result.get("rejection_reason"),
    )


def build_reviews(root: Path, candidate_root: Path) -> list[dict[str, Any]]:
    root = root.resolve()
    candidate_root = candidate_root.resolve()
    retrievals = read_jsonl(candidate_root / "announcement_body_retrieval.jsonl")
    title_candidates = read_jsonl(
        root / "configs/company_impact_high_quality_v2/confounders.jsonl"
    )
    candidates_by_id = {
        str(row["source_url"]).rsplit("/", 1)[-1].split(".", 1)[0]: row
        for row in title_candidates
    }
    reviews: list[dict[str, Any]] = []
    for retrieval in retrievals:
        announcement_id = str(retrieval["announcement_id"])
        candidate = candidates_by_id[announcement_id]
        base = {
            "review_id": f"body-review-{announcement_id}",
            "mapping_id": retrieval["mapping_id"],
            "event_id": retrieval["event_id"],
            "company_id": retrieval["company_id"],
            "company_code": retrieval.get("company_code"),
            "announcement_id": announcement_id,
            "announcement_title": retrieval.get("announcement_title"),
            "source_url": retrieval.get("source_url"),
            "first_public_at": retrieval.get("first_public_at"),
            "confounder_type": candidate.get("confounder_type"),
            "affected_windows": candidate.get("affected_windows") or [],
            "text_path": retrieval.get("text_path"),
            "review_status": "NEEDS_HUMAN_REVIEW",
            "formal_ready": False,
        }
        if retrieval.get("retrieval_status") != "RETRIEVED":
            review = base | {
                "body_review_status": "UNRESOLVED_RETRIEVAL",
                "body_locator": None,
                "original_quote": None,
                "relevance_decision": "UNRESOLVED",
                "severity_candidate": "UNRESOLVED",
                "mechanism_zh": None,
                "rejection_reason": retrieval.get("failure_reason"),
                "instrument_scope": "UNRESOLVED",
                "equity_trading_status_evidence_eligible": False,
            }
        else:
            text = (candidate_root / str(retrieval["text_path"])).read_text(
                encoding="utf-8"
            )
            confounder_type = str(candidate.get("confounder_type") or "MATERIAL_OPERATION")
            quote, locator = select_quote(
                text,
                str(retrieval.get("announcement_title") or ""),
                confounder_type,
            )
            disposition = disposition_for_announcement(
                str(retrieval.get("announcement_title") or ""), confounder_type
            )
            review = base | {
                "body_review_status": "BODY_REVIEWED",
                "body_locator": locator,
                "original_quote": quote,
                "confounder_type": confounder_type,
                "relevance_decision": disposition["relevance_decision"],
                "severity_candidate": disposition["severity_candidate"],
                "mechanism_zh": disposition["mechanism_zh"],
                "rejection_reason": disposition["rejection_reason"],
                "instrument_scope": disposition["instrument_scope"],
                "equity_trading_status_evidence_eligible": disposition[
                    "equity_trading_status_evidence_eligible"
                ],
            }
        failures = validate_body_review(review)
        if failures:
            raise ValueError(
                f"INVALID_BODY_REVIEW:{announcement_id}:{','.join(failures)}"
            )
        reviews.append(review)
    return sorted(reviews, key=lambda row: (str(row["event_id"]), str(row["announcement_id"])))


def build(root: Path, candidate_root: Path) -> dict[str, Any]:
    reviews = build_reviews(root, candidate_root)
    write_jsonl(candidate_root / "announcement_body_reviews.jsonl", reviews)
    return {
        "review_count": len(reviews),
        "relevant_count": sum(row["relevance_decision"] == "RELEVANT" for row in reviews),
        "minor_count": sum(row["relevance_decision"] == "MINOR_RELEVANCE" for row in reviews),
        "irrelevant_count": sum(row["relevance_decision"] == "IRRELEVANT" for row in reviews),
        "unresolved_count": sum(row["relevance_decision"] == "UNRESOLVED" for row in reviews),
        "formal_ready": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--candidate-root",
        type=Path,
        default=Path("work/company_impact_high_quality_v2_candidate"),
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    candidate = args.candidate_root
    if not candidate.is_absolute():
        candidate = root / candidate
    print(json.dumps(build(root, candidate), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
