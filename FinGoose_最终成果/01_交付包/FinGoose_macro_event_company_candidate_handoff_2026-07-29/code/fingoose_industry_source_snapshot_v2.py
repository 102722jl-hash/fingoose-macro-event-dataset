"""Fetch official source snapshots and verify registered quotations."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)
REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


class VisibleTextParser(HTMLParser):
    """Collect visible HTML text while excluding executable and style blocks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and data.strip():
            self.parts.append(data)


def html_text(payload: bytes) -> str:
    parser = VisibleTextParser()
    parser.feed(payload.decode("utf-8", errors="replace"))
    return " ".join(" ".join(parser.parts).split())


def payload_text(payload: bytes, media_type: str) -> str:
    if media_type == "application/pdf":
        from pypdf import PdfReader

        return " ".join(
            " ".join((page.extract_text() or "").split())
            for page in PdfReader(BytesIO(payload)).pages
        )
    return html_text(payload)


def _is_compact_boundary_char(value: str) -> bool:
    codepoint = ord(value)
    is_cjk = (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
    )
    category = unicodedata.category(value)
    return is_cjk or value.isdigit() or category.startswith(("P", "S"))


def _quote_match_text(value: str) -> str:
    collapsed = " ".join(value.split())

    def replace_layout_whitespace(match: re.Match[str]) -> str:
        before = collapsed[match.start() - 1] if match.start() else ""
        after = collapsed[match.end()] if match.end() < len(collapsed) else ""
        if before and after and _is_compact_boundary_char(before) and _is_compact_boundary_char(after):
            return ""
        return " "

    return re.sub(r"\s+", replace_layout_whitespace, collapsed)


def snapshot_source(
    target: Mapping[str, Any],
    *,
    output_root: Path,
    fetch_bytes: Callable[[str], bytes],
    accessed_at: str,
) -> dict[str, Any]:
    suffix = ".pdf" if target.get("media_type") == "application/pdf" else ".html"
    relative = Path("raw/evidence") / f"{target['source_id']}{suffix}"
    try:
        payload = fetch_bytes(str(target["source_url"]))
    except Exception as exc:
        return {
            **dict(target),
            "accessed_at": accessed_at,
            "raw_snapshot_path": None,
            "verified_quote": None,
            "fetch_status": "FETCH_FAILED",
            "failure_reason": f"{type(exc).__name__}:{exc}",
        }

    destination = output_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    try:
        text = payload_text(payload, str(target.get("media_type") or "text/html"))
    except Exception as exc:
        return {
            **dict(target),
            "accessed_at": accessed_at,
            "raw_snapshot_path": relative.as_posix(),
            "verified_quote": None,
            "fetch_status": "CONTENT_MISMATCH",
            "failure_reason": f"CONTENT_PARSE_FAILED:{type(exc).__name__}:{exc}",
        }

    quote = " ".join(str(target["required_quote"]).split())
    status = (
        "RETRIEVED_QUOTE_VERIFIED"
        if _quote_match_text(quote) in _quote_match_text(text)
        else "CONTENT_MISMATCH"
    )
    return {
        **dict(target),
        "accessed_at": accessed_at,
        "raw_snapshot_path": relative.as_posix(),
        "verified_quote": quote if status == "RETRIEVED_QUOTE_VERIFIED" else None,
        "fetch_status": status,
        "failure_reason": None if status == "RETRIEVED_QUOTE_VERIFIED" else "REQUIRED_QUOTE_NOT_FOUND",
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _fetch_url(url: str) -> bytes:
    request = urllib.request.Request(url, headers=REQUEST_HEADERS)
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def snapshot_registry(
    registry_path: Path,
    output_root: Path,
    accessed_at: str,
    *,
    fetch_bytes: Callable[[str], bytes] = _fetch_url,
) -> list[dict[str, Any]]:
    rows = [
        snapshot_source(
            target,
            output_root=output_root,
            fetch_bytes=fetch_bytes,
            accessed_at=accessed_at,
        )
        for target in _read_jsonl(registry_path)
    ]
    _write_jsonl(output_root / "industry_source_fetches.jsonl", rows)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("configs/industry_impact_v2/event_01_source_registry.jsonl"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("work/event_01_industry_closure_v2_candidate")
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    registry = args.registry if args.registry.is_absolute() else root / args.registry
    output = args.output if args.output.is_absolute() else root / args.output
    accessed_at = datetime.now(timezone.utc).isoformat()
    rows = snapshot_registry(registry, output, accessed_at)
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row["fetch_status"])
        counts[status] = counts.get(status, 0) + 1
    print(json.dumps({"source_count": len(rows), "status_counts": counts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
