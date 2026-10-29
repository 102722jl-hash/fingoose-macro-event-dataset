"""Public-vendor A-share price-window candidate builder."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence


DATASET_VERSION = "fingoose-public-company-price-windows-v1.0"
RELEASE_TIER = "PUBLIC_VENDOR_CANDIDATE"
EASTMONEY_ENDPOINT = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
WINDOW_OFFSETS = {"T0": 0, "D1": 1, "D3": 3, "D5": 5, "D20": 20}


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(_canonical_bytes(value))


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _number(value: Any) -> float | None:
    if value in (None, "", "-", "NULL"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def eastmoney_secid(company_code: str) -> str:
    code, separator, market = company_code.upper().partition(".")
    if not separator or len(code) != 6 or not code.isdigit():
        raise ValueError(f"unsupported A-share company code: {company_code}")
    if market == "SH":
        return f"1.{code}"
    if market == "SZ":
        return f"0.{code}"
    raise ValueError(f"unsupported A-share market: {company_code}")


def build_eastmoney_url(company_code: str, anchor_date: str) -> str:
    anchor = date.fromisoformat(anchor_date)
    params = {
        "secid": eastmoney_secid(company_code),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "beg": (anchor - timedelta(days=90)).strftime("%Y%m%d"),
        "end": (anchor + timedelta(days=90)).strftime("%Y%m%d"),
    }
    return EASTMONEY_ENDPOINT + "?" + urllib.parse.urlencode(params)


def parse_eastmoney_payload(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        return []
    bars = []
    for raw in data.get("klines") or []:
        fields = str(raw).split(",")
        if len(fields) < 11:
            continue
        bars.append({
            "trade_date": fields[0],
            "open": _number(fields[1]),
            "close": _number(fields[2]),
            "high": _number(fields[3]),
            "low": _number(fields[4]),
            "volume": _number(fields[5]),
            "amount": _number(fields[6]),
            "amplitude_pct": _number(fields[7]),
            "daily_return_pct": _number(fields[8]),
            "daily_change": _number(fields[9]),
            "turnover_pct": _number(fields[10]),
        })
    return sorted(bars, key=lambda row: row["trade_date"])


def _missing_observation(offset: int, reason: str) -> dict[str, Any]:
    return {
        "trading_session_offset": offset,
        "date": None,
        "close": None,
        "raw_return_from_t_minus_1": None,
        "status": "MISSING_OBSERVATION",
        "reason": reason,
    }


def calculate_price_window(bars: Sequence[Mapping[str, Any]], anchor_date: str) -> dict[str, dict[str, Any]]:
    ordered = sorted((dict(row) for row in bars), key=lambda row: str(row["trade_date"]))
    t0_index = next((i for i, row in enumerate(ordered) if str(row["trade_date"]) >= anchor_date), None)
    if t0_index is None:
        result = {"T_MINUS_1": _missing_observation(-1, "NO_TRADING_DAY_ON_OR_AFTER_ANCHOR")}
        result.update({label: _missing_observation(offset, "NO_TRADING_DAY_ON_OR_AFTER_ANCHOR") for label, offset in WINDOW_OFFSETS.items()})
        return result

    baseline_index = t0_index - 1
    baseline_close = _number(ordered[baseline_index].get("close")) if baseline_index >= 0 else None
    if baseline_index >= 0:
        baseline = ordered[baseline_index]
        result = {
            "T_MINUS_1": {
                "trading_session_offset": -1,
                "date": baseline["trade_date"],
                "close": baseline_close,
                "raw_return_from_t_minus_1": 0.0 if baseline_close is not None else None,
                "status": "OBSERVED" if baseline_close is not None else "MISSING_OBSERVATION",
                "reason": None if baseline_close is not None else "BASELINE_CLOSE_MISSING",
            }
        }
    else:
        result = {"T_MINUS_1": _missing_observation(-1, "NO_PREVIOUS_TRADING_DAY")}

    for label, offset in WINDOW_OFFSETS.items():
        index = t0_index + offset
        if index >= len(ordered):
            result[label] = _missing_observation(offset, "INSUFFICIENT_FUTURE_TRADING_DAYS")
            continue
        bar = ordered[index]
        close = _number(bar.get("close"))
        raw_return = close / baseline_close - 1 if close is not None and baseline_close not in (None, 0) else None
        result[label] = {
            "trading_session_offset": offset,
            "date": bar["trade_date"],
            "close": close,
            "raw_return_from_t_minus_1": raw_return,
            "status": "OBSERVED" if close is not None else "MISSING_OBSERVATION",
            "reason": None if close is not None else "CLOSE_MISSING",
        }
    return result


def _window_id(company: Mapping[str, Any]) -> str:
    code = str(company["company_code"]).lower().replace(".", "-")
    return f"public-price-{company['event_id']}-{code}"


def build_price_candidate(company: Mapping[str, Any], payload: Mapping[str, Any], source_url: str) -> dict[str, Any]:
    price_window_id = _window_id(company)
    bars = parse_eastmoney_payload(payload)
    observations = calculate_price_window(bars, str(company["anchor_date"]))
    observed = sum(item["status"] == "OBSERVED" for item in observations.values())
    return {
        "price_window_id": price_window_id,
        "dataset_version": DATASET_VERSION,
        "release_tier": RELEASE_TIER,
        "event_id": company["event_id"],
        "anchor_id": company.get("anchor_id"),
        "anchor_date": company["anchor_date"],
        "company_code": company["company_code"],
        "company_name": company["company_name"],
        "frequency": "DAILY",
        "adjustment": "FORWARD_ADJUSTED_FQT_1",
        "t0_rule": "FIRST_TRADING_DAY_ON_OR_AFTER_ANCHOR_DATE",
        "source_class": "PUBLIC_VENDOR_DATA",
        "source_provider": "EASTMONEY_PUBLIC_ENDPOINT",
        "source_url": source_url,
        "snapshot_path": f"snapshots/{price_window_id}.json",
        "source_snapshot_sha256": hashlib.sha256(_canonical_bytes(payload)).hexdigest(),
        "bar_count": len(bars),
        "status": "WINDOW_AVAILABLE" if observed == len(observations) else "PARTIAL_OR_MISSING_WINDOW",
        "observations": observations,
        "formal_ready": False,
        "financial_attribution_allowed": False,
        "causal_attribution_allowed": False,
        "redistribution_allowed": False,
    }


def _fetch_json(url: str, retries: int = 2) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 FinGooseCandidate/1.0",
            "Referer": "https://quote.eastmoney.com/",
        },
    )
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # Network failures must remain explicit candidate data.
            last_error = exc
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
    return {"data": None, "candidate_fetch_error": type(last_error).__name__ if last_error else "UNKNOWN"}


def write_price_bundle(
    output_root: Path,
    candidates: Sequence[Mapping[str, Any]],
    snapshots: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    snapshot_root = output_root / "snapshots"
    snapshot_root.mkdir(parents=True, exist_ok=True)
    ordered = sorted((dict(row) for row in candidates), key=lambda row: row["price_window_id"])
    for row in ordered:
        _write_json(snapshot_root / f"{row['price_window_id']}.json", snapshots[row["price_window_id"]])
    _write_jsonl(output_root / "company_price_windows.jsonl", ordered)
    hard_failures = []
    ids = [row["price_window_id"] for row in ordered]
    if len(ids) != len(set(ids)):
        hard_failures.append("DUPLICATE_PRICE_WINDOW_ID")
    for row in ordered:
        snapshot = output_root / row["snapshot_path"]
        if not snapshot.exists() or _sha256(snapshot) != row["source_snapshot_sha256"]:
            hard_failures.append(f"SNAPSHOT_HASH_MISMATCH:{row['price_window_id']}")
        if row.get("formal_ready") or row.get("financial_attribution_allowed") or row.get("causal_attribution_allowed"):
            hard_failures.append(f"RELEASE_BOUNDARY_VIOLATION:{row['price_window_id']}")
    validation = {
        "valid": not hard_failures,
        "hard_failures": hard_failures,
        "record_count": len(ordered),
        "full_window_count": sum(row["status"] == "WINDOW_AVAILABLE" for row in ordered),
        "partial_or_missing_count": sum(row["status"] != "WINDOW_AVAILABLE" for row in ordered),
        "formal_ready": False,
    }
    summary = {
        "dataset_version": DATASET_VERSION,
        "release_tier": RELEASE_TIER,
        "record_count": len(ordered),
        "full_window_count": validation["full_window_count"],
        "partial_or_missing_count": validation["partial_or_missing_count"],
        "formal_ready": False,
        "financial_attribution_allowed": False,
        "causal_attribution_allowed": False,
    }
    _write_json(output_root / "validation_report.json", validation)
    _write_json(output_root / "summary.json", summary)
    (output_root / "README.md").write_text(
        "# Public Company Price Window Candidate\n\n"
        "Daily forward-adjusted A-share observations from the Eastmoney public endpoint. "
        "These records are observational vendor candidates, not official evidence or causal attribution.\n",
        encoding="utf-8",
    )
    files = [output_root / "company_price_windows.jsonl", output_root / "validation_report.json", output_root / "summary.json", output_root / "README.md"]
    files.extend(sorted(snapshot_root.glob("*.json")))
    manifest = {
        "dataset_version": DATASET_VERSION,
        "release_tier": RELEASE_TIER,
        "formal_ready": False,
        "files": [
            {
                "path": path.relative_to(output_root).as_posix(),
                "record_count": sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()) if path.suffix == ".jsonl" else 1,
                "sha256": _sha256(path),
            }
            for path in files
        ],
    }
    _write_json(output_root / "manifest.json", manifest)
    return manifest


def build_public_price_windows(root: Path, output_root: Path, workers: int = 6) -> dict[str, Any]:
    root = root.resolve()
    output_root = output_root.resolve()
    protected = [(root / name).resolve() for name in ("data", "code", "ui")]
    if any(output_root == path or path in output_root.parents for path in protected):
        raise ValueError("output_root must remain outside protected production and UI directories")
    companies = _read_jsonl(root / "work/mysql_company_enhancement_v1_candidate/company_impact_candidates.jsonl")
    jobs = []
    for company in companies:
        if not company.get("anchor_date"):
            continue
        jobs.append((company, build_eastmoney_url(str(company["company_code"]), str(company["anchor_date"]))))
    results: dict[str, tuple[dict[str, Any], str, dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(_fetch_json, url): (company, url) for company, url in jobs}
        for future in as_completed(futures):
            company, url = futures[future]
            payload = future.result()
            results[_window_id(company)] = (company, url, payload)
    candidates = []
    snapshots = {}
    for window_id in sorted(results):
        company, url, payload = results[window_id]
        candidates.append(build_price_candidate(company, payload, url))
        snapshots[window_id] = payload
    manifest = write_price_bundle(output_root, candidates, snapshots)
    return {
        "record_count": len(candidates),
        "full_window_count": sum(row["status"] == "WINDOW_AVAILABLE" for row in candidates),
        "partial_or_missing_count": sum(row["status"] != "WINDOW_AVAILABLE" for row in candidates),
        "manifest_file_count": len(manifest["files"]),
        "formal_ready": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("work/company_price_windows_public_vendor_v1_candidate"))
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    print(json.dumps(build_public_price_windows(root, output, args.workers), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
