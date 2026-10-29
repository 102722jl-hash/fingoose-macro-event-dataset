"""Fetch and extract official announcement bodies for confounder review."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from fingoose_company_impact_io_v2 import read_jsonl, write_jsonl


OFFICIAL_HOSTS = {
    "static.cninfo.com.cn",
    "www.cninfo.com.cn",
    "www.sse.com.cn",
    "www.szse.cn",
}


def normalize_official_url(value: str) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS:
        raise ValueError(f"OFFICIAL_HOST_REQUIRED:{url}")
    return url


def _announcement_id(url: str) -> str:
    token = urlparse(url).path.rsplit("/", 1)[-1].split(".", 1)[0]
    if not token:
        raise ValueError(f"ANNOUNCEMENT_ID_REQUIRED:{url}")
    return token


def load_candidate_jobs(root: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(
        root.resolve() / "configs/company_impact_high_quality_v2/confounders.jsonl"
    )
    jobs: list[dict[str, Any]] = []
    for row in rows:
        source_url = normalize_official_url(str(row.get("source_url") or ""))
        jobs.append(
            {
                "announcement_id": _announcement_id(source_url),
                "mapping_id": row["mapping_id"],
                "event_id": row["event_id"],
                "company_id": row["company_id"],
                "company_code": row.get("company_code"),
                "announcement_title": row.get("quote"),
                "source_url": source_url,
                "first_public_at": row.get("first_public_at"),
                "title_candidate": dict(row),
            }
        )
    jobs.sort(key=lambda row: (str(row["event_id"]), str(row["announcement_id"])))
    ids = [str(row["announcement_id"]) for row in jobs]
    if len(ids) != len(set(ids)):
        raise ValueError("DUPLICATE_ANNOUNCEMENT_ID")
    return jobs


def retrieval_failure(
    job: Mapping[str, Any],
    reason: str,
    *,
    status: str = "FAILED",
) -> dict[str, Any]:
    return {
        key: job.get(key)
        for key in (
            "announcement_id",
            "mapping_id",
            "event_id",
            "company_id",
            "company_code",
            "announcement_title",
            "source_url",
            "first_public_at",
        )
    } | {
        "retrieval_status": status,
        "body_review_eligible": False,
        "failure_reason": reason,
        "pdf_path": None,
        "text_path": None,
        "text_character_count": 0,
        "extraction_method": None,
        "formal_ready": False,
    }


def _download(url: str, destination: Path, timeout: float, retries: int) -> None:
    if destination.exists() and destination.stat().st_size > 4:
        return
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 FinGooseCandidateResearch/2.0",
            "Accept": "application/pdf,*/*;q=0.8",
        },
    )
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
            if not payload.startswith(b"%PDF"):
                raise ValueError("RESPONSE_NOT_PDF")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            return
        except Exception as error:  # persisted below with a stable reason
            last_error = error
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def _extract_with_pypdf(pdf_path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        value = (page.extract_text() or "").strip()
        if value:
            pages.append(f"=== PAGE {index} ===\n{value}")
    return "\n\n".join(pages)


def _extract_with_pdfplumber(pdf_path: Path) -> str:
    import pdfplumber

    pages = []
    with pdfplumber.open(str(pdf_path)) as document:
        for index, page in enumerate(document.pages, start=1):
            value = (page.extract_text() or "").strip()
            if value:
                pages.append(f"=== PAGE {index} ===\n{value}")
    return "\n\n".join(pages)


def retrieve_job(
    job: Mapping[str, Any],
    candidate_root: Path,
    *,
    timeout: float = 30.0,
    retries: int = 2,
) -> dict[str, Any]:
    announcement_id = str(job["announcement_id"])
    pdf_path = candidate_root / "sources/company_announcements/pdf" / f"{announcement_id}.pdf"
    text_path = candidate_root / "sources/company_announcements/text" / f"{announcement_id}.txt"
    try:
        _download(str(job["source_url"]), pdf_path, timeout, retries)
        text = _extract_with_pypdf(pdf_path)
        method = "PYPDF"
        if not text.strip():
            text = _extract_with_pdfplumber(pdf_path)
            method = "PDFPLUMBER"
        if not text.strip():
            return retrieval_failure(job, "NO_EXTRACTABLE_TEXT", status="TEXT_EMPTY")
        text_path.parent.mkdir(parents=True, exist_ok=True)
        text_path.write_text(text + "\n", encoding="utf-8")
        return {
            key: job.get(key)
            for key in (
                "announcement_id",
                "mapping_id",
                "event_id",
                "company_id",
                "company_code",
                "announcement_title",
                "source_url",
                "first_public_at",
            )
        } | {
            "retrieval_status": "RETRIEVED",
            "body_review_eligible": True,
            "failure_reason": None,
            "pdf_path": pdf_path.relative_to(candidate_root).as_posix(),
            "text_path": text_path.relative_to(candidate_root).as_posix(),
            "text_character_count": len(text),
            "extraction_method": method,
            "formal_ready": False,
        }
    except urllib.error.HTTPError as error:
        return retrieval_failure(job, f"HTTP_{error.code}")
    except urllib.error.URLError as error:
        return retrieval_failure(job, f"URL_ERROR:{error.reason}")
    except Exception as error:
        return retrieval_failure(job, f"{type(error).__name__}:{error}")


def build(
    root: Path,
    candidate_root: Path,
    *,
    timeout: float = 30.0,
    retries: int = 2,
) -> dict[str, Any]:
    root = root.resolve()
    candidate_root = candidate_root.resolve()
    records = [
        retrieve_job(job, candidate_root, timeout=timeout, retries=retries)
        for job in load_candidate_jobs(root)
    ]
    write_jsonl(candidate_root / "announcement_body_retrieval.jsonl", records)
    return {
        "record_count": len(records),
        "retrieved_count": sum(row["retrieval_status"] == "RETRIEVED" for row in records),
        "failed_count": sum(row["retrieval_status"] == "FAILED" for row in records),
        "text_empty_count": sum(row["retrieval_status"] == "TEXT_EMPTY" for row in records),
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
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    candidate = args.candidate_root
    if not candidate.is_absolute():
        candidate = root / candidate
    print(
        json.dumps(
            build(root, candidate, timeout=args.timeout, retries=args.retries),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
