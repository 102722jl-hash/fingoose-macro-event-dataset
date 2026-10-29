"""Join confounder ledgers and derive evidence-backed Chinese arguments."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

from fingoose_company_confounder_evidence_closure_v2 import derive_grade
from fingoose_company_impact_io_v2 import read_jsonl, write_jsonl


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _clip(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def _index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["mapping_id"]): row for row in rows}


def _body_index(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result[str(row["mapping_id"])].append(row)
    return result


def _chain_statements(chain: dict[str, Any]) -> dict[str, str]:
    statements = {
        str(node.get("node_type")): str(node.get("statement") or "")
        for node in chain.get("nodes") or []
    }
    return statements


def _score_eligibility(grade: str) -> str:
    return (
        "CHALLENGE_ONLY"
        if grade in {"MATERIAL", "DOMINANT", "UNRESOLVED"}
        else "PRIMARY_SCORE_ELIGIBLE"
    )


def _unresolved_reasons(
    search: dict[str, Any],
    bodies: list[dict[str, Any]],
    trading: dict[str, Any],
    counter: dict[str, Any],
) -> list[str]:
    reasons = list(search.get("unresolved_reasons") or [])
    if search.get("search_status") != "COMPLETE":
        reasons.append("CONFOUNDER_SEARCH_INCOMPLETE")
    if any(row.get("relevance_decision") == "UNRESOLVED" for row in bodies):
        reasons.append("ANNOUNCEMENT_BODY_REVIEW_UNRESOLVED")
    if trading.get("overall_status") not in {
        "VERIFIED_TRADING",
        "VERIFIED_SUSPENDED",
    }:
        reasons.append("TRADING_STATUS_UNRESOLVED")
    if not counter.get("findings") and not counter.get("negative_search_basis"):
        reasons.append("COUNTEREVIDENCE_DISPOSITION_MISSING")
    return _unique(reasons)


def _argument(
    *,
    mapping: dict[str, Any],
    chain: dict[str, Any],
    search: dict[str, Any],
    bodies: list[dict[str, Any]],
    trading: dict[str, Any],
    counter: dict[str, Any],
    grade: str,
    unresolved: list[str],
) -> str:
    statements = _chain_statements(chain)
    event_fact = _clip(statements.get("EVENT_FACT") or mapping.get("event_id"), 80)
    behavior = _clip(statements.get("BEHAVIOR_OR_POLICY_CHANGE"), 62)
    operating = _clip(statements.get("OBSERVABLE_OPERATING_VARIABLE"), 55)
    exposure = _clip(statements.get("COMPANY_BUSINESS_EXPOSURE"), 62)
    company = str(mapping.get("company_name") or mapping.get("company_code"))

    hypothesis = (
        f"研究假设：事件锚点为“{event_fact}”。候选机制认为，该事实先引发“{behavior}”，"
        f"再通过“{operating}”传至{company}；公司暴露依据为“{exposure}”。"
        "这是一条待人工审核的传导假设，不以事件后的股价表现反向选择路径。"
    )
    relevant = [
        row
        for row in bodies
        if row.get("relevance_decision") in {"RELEVANT", "MINOR_RELEVANCE"}
    ]
    if relevant:
        titles = "；".join(_clip(row.get("announcement_title"), 35) for row in relevant[:2])
        windows = "、".join(
            _unique(
                str(window)
                for row in relevant
                for window in row.get("affected_windows") or []
            )
        )
        announcement = (
            f"公告检索：官方快照覆盖{search.get('window_start')}至{search.get('window_end')}，"
            f"复核{search.get('title_count')}条标题并完成{search.get('body_reviewed_count')}条候选正文处置。"
            f"其中需纳入竞争解释的公告包括“{titles}”，影响窗口候选为{windows or '未明确'}；"
            "公告正文仅用于判断独立公司因素，标题本身不构成等级证据。"
        )
    else:
        announcement = (
            f"公告检索：官方快照覆盖{search.get('window_start')}至{search.get('window_end')}，"
            f"共分类{search.get('title_count')}条标题，未发现经正文核对后可构成实质公司混杂的候选。"
            "该结论表示固定八类检索已完成，不等于证明不存在任何未披露事项。"
        )
    dates = [
        str((trading.get("window_reviews") or {}).get(window, {}).get("actual_date") or "缺失")
        for window in ("T_MINUS_1", "T0", "D1", "D3", "D5", "D20")
    ]
    trading_text = (
        f"交易核验：T-1至D20的六个实际交易日依次为{', '.join(dates)}，"
        f"总体状态为{trading.get('overall_status')}。非空行情只能证明该日可观测，"
        "不能单独证明宏观事件造成了收益变化，也不能替代停复牌公告。"
    )
    finding_count = len(counter.get("findings") or [])
    counter_text = (
        f"反证边界：已登记{finding_count}条公司年报限制因素或事件窗口公告证据；"
        "它们用于检验业务缓冲、传导失效条件及独立公司驱动，不会被回填为事件前已知事实。"
        if finding_count
        else f"反证边界：{counter.get('negative_search_basis')}"
    )
    conclusion = (
        f"综合门禁给出{grade}候选等级。"
        + (
            f"仍未关闭的项目为{'、'.join(unresolved)}，因此只能进入挑战集并拒绝直接归因。"
            if unresolved
            else "检索、正文处置和交易状态已闭合，但结论仍为NEEDS_HUMAN_REVIEW，且禁止据此作确定性因果归因。"
        )
    )
    text = hypothesis + announcement + trading_text + counter_text + conclusion
    if len(text) < 250:
        text += "所有证据均保留来源链接、原文定位和映射标识，最终采用前仍需人工逐项核对。"
    if len(text) > 600:
        boundary = "结论仍为待人工审核，禁止作确定性因果归因。"
        text = text[: 600 - len(boundary)] + boundary
    return text


def build_closure(
    root: Path, candidate_root: Path
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    del root
    mappings = read_jsonl(candidate_root / "event_company_map.jsonl")
    chains = _index(
        read_jsonl(candidate_root / "event_company_mechanism_chains.jsonl")
    )
    searches = _index(
        read_jsonl(candidate_root / "company_confounder_search_audits.jsonl")
    )
    bodies = _body_index(
        read_jsonl(candidate_root / "announcement_body_reviews.jsonl")
    )
    trading = _index(read_jsonl(candidate_root / "trading_status_reviews.jsonl"))
    counters = _index(
        read_jsonl(candidate_root / "company_counterevidence_reviews.jsonl")
    )

    confounders: list[dict[str, Any]] = []
    arguments: list[dict[str, Any]] = []
    for mapping in mappings:
        mapping_id = str(mapping["mapping_id"])
        search = searches[mapping_id]
        body_rows = bodies.get(mapping_id, [])
        trade = trading[mapping_id]
        counter = counters[mapping_id]
        chain = chains[mapping_id]
        grade = derive_grade(search, body_rows, trade, counter.get("findings") or [])
        unresolved = _unresolved_reasons(search, body_rows, trade, counter)
        if unresolved:
            grade = "UNRESOLVED"
        relevant_bodies = [
            row
            for row in body_rows
            if row.get("relevance_decision") in {"RELEVANT", "MINOR_RELEVANCE"}
        ]
        evidence_ids = _unique(
            [str(row["review_id"]) for row in relevant_bodies]
            + [
                str(finding["evidence_id"])
                for finding in counter.get("findings") or []
            ]
            + [
                str(review.get("source_record_id"))
                for review in (trade.get("window_reviews") or {}).values()
                if review.get("source_record_id")
            ]
        )
        section_lineage = {
            "event_hypothesis": [chain.get("chain_id")],
            "announcement_search": [search.get("search_audit_id")]
            + [row.get("review_id") for row in body_rows],
            "trading_status": [trade.get("trading_review_id")],
            "counterevidence": [
                finding.get("counterevidence_id")
                for finding in counter.get("findings") or []
            ]
            or [counter.get("counterevidence_review_id")],
        }
        state = (
            "UNRESOLVED"
            if grade == "UNRESOLVED"
            else (
                "SEARCH_COMPLETE_NO_MATERIAL_CONFOUNDER"
                if grade == "CLEAN"
                else "REVIEWED"
            )
        )
        confounder = {
            "company_confounder_id": f"company-confounder-{mapping_id}",
            "mapping_id": mapping_id,
            "event_id": mapping["event_id"],
            "company_id": mapping["company_id"],
            "company_code": mapping.get("company_code"),
            "company_name": mapping.get("company_name"),
            "anchor_id": mapping.get("anchor_id"),
            "window_scope": ["T_MINUS_1", "T0", "D1", "D3", "D5", "D20"],
            "suspension_status": trade["overall_status"],
            "trading_review_id": trade["trading_review_id"],
            "company_confounder_status": "REVIEWED" if not unresolved else "UNRESOLVED",
            "display_state": state,
            "search_audit_id": search["search_audit_id"],
            "registered_confounders": relevant_bodies,
            "overall_grade": grade,
            "score_eligibility": _score_eligibility(grade),
            "counterevidence_status": "REVIEWED",
            "counterevidence_review_id": counter["counterevidence_review_id"],
            "counterevidence": counter.get("findings") or [],
            "unresolved_reasons": unresolved,
            "review_status": "NEEDS_HUMAN_REVIEW",
            "formal_ready": False,
            "sha_gate": "DEFERRED",
            "causal_attribution_allowed": False,
        }
        argument = {
            "argument_id": f"confounder-argument-{mapping_id}",
            "mapping_id": mapping_id,
            "event_id": mapping["event_id"],
            "company_id": mapping["company_id"],
            "company_code": mapping.get("company_code"),
            "company_name": mapping.get("company_name"),
            "overall_grade": grade,
            "display_state": state,
            "argument_zh": _argument(
                mapping=mapping,
                chain=chain,
                search=search,
                bodies=body_rows,
                trading=trade,
                counter=counter,
                grade=grade,
                unresolved=unresolved,
            ),
            "evidence_ids": evidence_ids,
            "negative_search_audit_id": (
                search["search_audit_id"] if not relevant_bodies else None
            ),
            "section_lineage": section_lineage,
            "review_status": "NEEDS_HUMAN_REVIEW",
            "formal_ready": False,
            "sha_gate": "DEFERRED",
        }
        confounders.append(confounder)
        arguments.append(argument)
    key = lambda row: (str(row["event_id"]), str(row["company_code"]))
    return sorted(confounders, key=key), sorted(arguments, key=key)


def build(root: Path, candidate_root: Path) -> dict[str, Any]:
    confounders, arguments = build_closure(root, candidate_root)
    write_jsonl(candidate_root / "company_confounders.jsonl", confounders)
    write_jsonl(candidate_root / "company_confounder_arguments.jsonl", arguments)
    grade_counts: dict[str, int] = defaultdict(int)
    for row in confounders:
        grade_counts[str(row["overall_grade"])] += 1
    return {
        "confounder_count": len(confounders),
        "argument_count": len(arguments),
        "grade_counts": dict(sorted(grade_counts.items())),
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
    candidate_root = args.candidate_root
    if not candidate_root.is_absolute():
        candidate_root = root / candidate_root
    print(json.dumps(build(root, candidate_root), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
