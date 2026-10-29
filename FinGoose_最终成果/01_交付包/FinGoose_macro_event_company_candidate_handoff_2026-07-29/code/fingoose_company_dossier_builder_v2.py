"""Candidate claim extraction for company-impact master dossiers."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence


def _is_toc_page(page: Mapping[str, Any]) -> bool:
    text = str(page.get("text") or "")
    page_number = int(page.get("page_number") or 0)
    return page_number <= 3 or ("目录" in text[:120] and "..." in text)


def _quote_window(text: str, start: int, limit: int) -> str:
    if len(text) <= limit:
        return text.strip()
    left = max(0, start - limit // 3)
    right = min(len(text), left + limit)
    left = max(0, right - limit)
    return text[left:right].strip()


def select_evidence_passage(
    pages: Iterable[Mapping[str, Any]],
    keywords: Sequence[str],
    *,
    quote_limit: int = 360,
) -> dict[str, Any] | None:
    if quote_limit < 80:
        raise ValueError("QUOTE_LIMIT_TOO_SMALL")
    candidates: list[tuple[int, int, Mapping[str, Any], list[str]]] = []
    for page in pages:
        if _is_toc_page(page):
            continue
        text = str(page.get("text") or "").strip()
        matched = [term for term in keywords if term and term in text]
        if not matched:
            continue
        score = sum(text.count(term) for term in matched) + len(matched) * 10
        candidates.append((score, -int(page.get("page_number") or 0), page, matched))
    if not candidates:
        return None
    _, _, page, matched_terms = max(candidates, key=lambda row: (row[0], row[1]))
    text = str(page.get("text") or "").strip()
    start = min(text.index(term) for term in matched_terms)
    return {
        "page_number": int(page["page_number"]),
        "page_or_section_locator": f"page={int(page['page_number'])}",
        "original_quote": _quote_window(text, start, quote_limit),
        "matched_terms": matched_terms,
        "review_origin": "AI_DESK_REVIEW",
        "review_status": "NEEDS_HUMAN_REVIEW",
    }
