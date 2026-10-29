from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping


def _id(prefix: str, value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}-{sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def normalize_search_hit(
    *, query: str, adapter: str, rank: int, url: str, title: str
) -> dict[str, Any]:
    return {
        "search_hit_id": _id("search-hit", {"query": query, "url": url}),
        "query": query,
        "adapter": adapter,
        "rank": int(rank),
        "candidate_url": url,
        "title": title,
    }


def normalize_evidence_candidate(record: Mapping[str, Any]) -> dict[str, Any]:
    clean = dict(record)
    clean["evidence_id"] = clean.get("evidence_id") or _id(
        "evidence",
        {"source_url": clean.get("source_url"), "locator": clean.get("locator")},
    )
    missing = next(
        (
            code
            for field, code in (
                ("original_quote", "ORIGINAL_QUOTE_MISSING"),
                ("locator", "LOCATOR_MISSING"),
                ("source_url", "SOURCE_URL_MISSING"),
            )
            if not clean.get(field)
        ),
        None,
    )
    clean["acceptance_status"] = "REJECTED" if missing else "CANDIDATE"
    clean["acceptance_reason"] = missing or "PENDING_GATES"
    return clean


def store_snapshot(
    root: Path,
    *,
    source_url: str,
    content_bytes: bytes,
    content_type: str,
    retrieved_at: str,
    allow_raw_storage: bool = True,
) -> dict[str, Any]:
    digest = sha256(content_bytes).hexdigest()
    suffix = {
        "text/html": ".html",
        "application/pdf": ".pdf",
        "application/json": ".json",
        "text/plain": ".txt",
    }.get(content_type.split(";", 1)[0].strip().lower(), ".bin")
    relative_path = None
    status = "NOT_STORED_BY_POLICY"
    if allow_raw_storage:
        snapshot_dir = root / "snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        target = snapshot_dir / f"{digest}{suffix}"
        if target.exists() and target.read_bytes() != content_bytes:
            raise ValueError("snapshot hash collision")
        if not target.exists():
            target.write_bytes(content_bytes)
        relative_path = target.relative_to(root).as_posix()
        status = "STORED"
    return {
        "source_url": source_url,
        "retrieved_at": retrieved_at,
        "content_type": content_type,
        "snapshot_path": relative_path,
        "snapshot_sha256": digest,
        "raw_storage_status": status,
    }
