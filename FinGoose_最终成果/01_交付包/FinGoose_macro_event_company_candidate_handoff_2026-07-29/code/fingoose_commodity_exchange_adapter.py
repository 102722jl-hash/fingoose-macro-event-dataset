"""Build the locked FinGoose v0.2 ten-day commodity snapshot."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from fingoose_commodity_market import (
    COMMODITY_SPECS,
    MarketDataError,
    TradingCalendar,
    build_continuous_series,
    build_contract_daily_record,
)
from fingoose_commodity_sources import (
    ADAPTER_VERSION,
    SOURCE_CONFIG,
    AdapterError,
    ParsedContract,
    SnapshotStore,
    bundle_provenance,
    detected_table_content_type,
    download,
    load_dce_metadata,
    merge_contract_revisions,
    merge_source_manifest_revisions,
    parse_dce_table,
    parse_json_bytes,
    parse_shfe_like,
    parse_trade_data_js,
    read_table_bytes,
    trade_date_from_filename,
)


TARGET_DATES = (
    "2026-07-09",
    "2026-07-10",
    "2026-07-13",
    "2026-07-14",
    "2026-07-15",
    "2026-07-16",
    "2026-07-17",
    "2026-07-20",
    "2026-07-21",
    "2026-07-22",
)
DEFAULT_SNAPSHOT_DIR = Path("inputs/commodities/v0.2/snapshots")
DEFAULT_DCE_DAILY_DIR = Path("inputs/commodities/v0.2/inbox/dce/daily")
DEFAULT_DCE_METADATA = Path(
    "inputs/commodities/v0.2/inbox/dce/contract_metadata.csv"
)
DEFAULT_OUTPUT_DIR = Path("outputs/fingoose_commodity_market/v0.2")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise AdapterError(f"invalid JSONL at {path}:{line_number}") from exc
    return records


def write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(
                json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            )
    temporary.replace(path)


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def schema_validator() -> Draft202012Validator:
    schema_path = (
        Path(__file__).resolve().parent
        / "schemas"
        / "fingoose_commodity_market_v0.2.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def collect_official_source(
    *,
    exchange: str,
    dates: Sequence[str],
    store: SnapshotStore,
    manifests: list[dict[str, Any]],
) -> tuple[
    dict[str, list[ParsedContract]],
    TradingCalendar | None,
    list[dict[str, Any]],
]:
    config = SOURCE_CONFIG[exchange]
    by_commodity = {code: [] for code in config["commodities"]}
    rejected: list[dict[str, Any]] = []
    calendar = None
    base_url = config["base_url"]

    calendar_url = base_url + "/data/config/js/trade-data.js"
    calendar_manifest = None
    try:
        content, content_type, status = download(calendar_url)
        calendar_manifest = store.store(
            source_id=f"{exchange.lower()}_trade_data",
            provider=config["provider"],
            source_url=calendar_url,
            requested_date=dates[-1],
            content=content,
            original_name="trade-data.js",
            content_type=content_type,
            http_status=status,
        )
        calendar_year = int(dates[-1][:4])
        calendar = parse_trade_data_js(
            content,
            exchange=exchange,
            year=calendar_year,
            coverage_end=f"{calendar_year}-12-31",
        )
        calendar_manifest["parse_status"] = "parsed"
        calendar_manifest["record_count"] = len(calendar.trading_dates)
    except Exception as exc:
        rejected.append(
            {"exchange": exchange, "source": "calendar", "reason": str(exc)}
        )
        if calendar_manifest is not None:
            calendar_manifest["parse_status"] = "rejected"
            calendar_manifest["errors"] = [str(exc)]
    if calendar_manifest is not None:
        manifests.append(calendar_manifest)

    for trade_date in dates:
        compact = trade_date.replace("-", "")
        daily_url = (
            base_url + f"/data/tradedata/future/dailydata/kx{compact}.dat"
        )
        metadata_url = (
            base_url
            + "/data/busiparamdata/future/"
            + f"ContractBaseInfo{compact}.dat"
        )
        day_manifests: list[dict[str, Any]] = []
        try:
            daily_bytes, daily_type, daily_status = download(daily_url)
            daily_manifest = store.store(
                source_id=f"{exchange.lower()}_daily_kx",
                provider=config["provider"],
                source_url=daily_url,
                requested_date=trade_date,
                content=daily_bytes,
                original_name=f"kx{compact}.dat",
                content_type=daily_type,
                http_status=daily_status,
            )
            day_manifests.append(daily_manifest)
            metadata_bytes, metadata_type, metadata_status = download(metadata_url)
            metadata_manifest = store.store(
                source_id=f"{exchange.lower()}_contract_base",
                provider=config["provider"],
                source_url=metadata_url,
                requested_date=trade_date,
                content=metadata_bytes,
                original_name=f"ContractBaseInfo{compact}.dat",
                content_type=metadata_type,
                http_status=metadata_status,
            )
            day_manifests.append(metadata_manifest)
            daily_payload = parse_json_bytes(daily_bytes, daily_url)
            contract_payload = parse_json_bytes(metadata_bytes, metadata_url)
            parsed_count = 0
            for commodity_code in config["commodities"]:
                result = parse_shfe_like(
                    daily_payload,
                    contract_payload,
                    exchange=exchange,
                    commodity_code=commodity_code,
                    trade_date=trade_date,
                )
                by_commodity[commodity_code].extend(result.records)
                rejected.extend(
                    {
                        **item,
                        "exchange": exchange,
                        "commodity_code": commodity_code,
                        "trade_date": trade_date,
                    }
                    for item in result.rejected
                )
                parsed_count += len(result.records)
            for manifest in day_manifests:
                manifest["parse_status"] = "parsed"
                manifest["record_count"] = parsed_count
        except Exception as exc:
            rejected.append(
                {
                    "exchange": exchange,
                    "trade_date": trade_date,
                    "reason": str(exc),
                }
            )
            for manifest in day_manifests:
                manifest["parse_status"] = "rejected"
                manifest["errors"] = [str(exc)]
        manifests.extend(day_manifests)
    return by_commodity, calendar, rejected


def collect_dce_source(
    *,
    dates: Sequence[str],
    daily_dir: Path,
    metadata_path: Path,
    store: SnapshotStore,
    manifests: list[dict[str, Any]],
) -> tuple[list[ParsedContract], TradingCalendar | None, list[dict[str, Any]]]:
    if not daily_dir.exists() or not metadata_path.exists():
        return [], None, [
            {
                "exchange": "DCE",
                "reason": "DCE manual daily files or contract_metadata.csv are missing",
            }
        ]

    metadata = load_dce_metadata(metadata_path)
    metadata_bytes = metadata_path.read_bytes()
    metadata_manifest = store.store(
        source_id="dce_contract_metadata_manual",
        provider=SOURCE_CONFIG["DCE"]["provider"],
        source_url=SOURCE_CONFIG["DCE"]["landing_url"],
        requested_date=dates[-1],
        content=metadata_bytes,
        original_name=metadata_path.name,
        content_type="text/csv",
        http_status=None,
    )
    metadata_manifest["parse_status"] = "parsed"
    metadata_manifest["record_count"] = len(metadata)
    manifests.append(metadata_manifest)

    records: list[ParsedContract] = []
    rejected: list[dict[str, Any]] = []
    seen_dates: set[str] = set()
    target_dates = set(dates)
    for path in sorted(item for item in daily_dir.iterdir() if item.is_file()):
        try:
            trade_date = trade_date_from_filename(path)
        except AdapterError:
            continue
        if trade_date not in target_dates:
            continue
        if trade_date in seen_dates:
            raise AdapterError(f"multiple DCE files for {trade_date}")
        seen_dates.add(trade_date)
        content = path.read_bytes()
        manifest = store.store(
            source_id="dce_daily_manual",
            provider=SOURCE_CONFIG["DCE"]["provider"],
            source_url=SOURCE_CONFIG["DCE"]["landing_url"],
            requested_date=trade_date,
            content=content,
            original_name=path.name,
            content_type=detected_table_content_type(content),
            http_status=None,
        )
        try:
            result = parse_dce_table(
                read_table_bytes(content, path.name),
                trade_date=trade_date,
                metadata=metadata,
            )
            records.extend(result.records)
            rejected.extend(
                {
                    **item,
                    "exchange": "DCE",
                    "commodity_code": "I",
                    "trade_date": trade_date,
                }
                for item in result.rejected
            )
            manifest["parse_status"] = "parsed"
            manifest["record_count"] = len(result.records)
        except Exception as exc:
            manifest["parse_status"] = "rejected"
            manifest["errors"] = [str(exc)]
            rejected.append(
                {
                    "exchange": "DCE",
                    "trade_date": trade_date,
                    "reason": str(exc),
                }
            )
        manifests.append(manifest)

    missing_dates = sorted(target_dates - seen_dates)
    if missing_dates:
        rejected.append(
            {
                "exchange": "DCE",
                "reason": "missing DCE dates",
                "dates": missing_dates,
            }
        )
    calendar = None
    if seen_dates:
        calendar = TradingCalendar.from_values(
            "DCE",
            sorted(seen_dates),
            coverage_start=dates[0],
            coverage_end=dates[-1],
            verified=False,
        )
    return records, calendar, rejected


def validate_records(
    records: Sequence[Mapping[str, Any]],
) -> list[str]:
    validator = schema_validator()
    errors = []
    for record in records:
        for error in sorted(
            validator.iter_errors(record), key=lambda item: list(item.path)
        ):
            errors.append(
                f"{record.get('record_id', '<missing>')}: {error.message}"
            )
    return errors


def build_snapshot(
    *,
    dates: Sequence[str] = TARGET_DATES,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    dce_daily_dir: Path = DEFAULT_DCE_DAILY_DIR,
    dce_metadata: Path = DEFAULT_DCE_METADATA,
) -> dict[str, Any]:
    if tuple(dates) != TARGET_DATES:
        raise AdapterError(
            "v0.2 minimum snapshot dates must match the locked 10-day window"
        )

    store = SnapshotStore(snapshot_dir)
    manifests: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    normalized: dict[str, list[ParsedContract]] = {
        "CU": [],
        "AU": [],
        "SC": [],
        "I": [],
    }
    calendars: dict[str, TradingCalendar | None] = {
        "SHFE": None,
        "INE": None,
        "DCE": None,
    }

    for exchange in ("SHFE", "INE"):
        source_rows, calendar, source_rejected = collect_official_source(
            exchange=exchange,
            dates=dates,
            store=store,
            manifests=manifests,
        )
        for code, rows in source_rows.items():
            normalized[code].extend(rows)
        calendars[exchange] = calendar
        rejected.extend(source_rejected)

    dce_rows, dce_calendar, dce_rejected = collect_dce_source(
        dates=dates,
        daily_dir=dce_daily_dir,
        metadata_path=dce_metadata,
        store=store,
        manifests=manifests,
    )
    normalized["I"].extend(dce_rows)
    calendars["DCE"] = dce_calendar
    rejected.extend(dce_rejected)

    candidates: list[dict[str, Any]] = []
    continuous_records: list[dict[str, Any]] = []
    roll_records: list[dict[str, Any]] = []
    per_commodity: dict[str, dict[str, Any]] = {}

    for commodity_code in ("CU", "AU", "SC", "I"):
        exchange = COMMODITY_SPECS[commodity_code]["exchange"]
        source_manifests = [
            item
            for item in manifests
            if str(item["source_id"]).startswith(exchange.lower())
            and item["parse_status"] == "parsed"
        ]
        items = normalized[commodity_code]
        dates_covered = sorted({item.row["trade_date"] for item in items})
        contracts_per_day = {
            day: sum(item.row["trade_date"] == day for item in items)
            for day in dates_covered
        }
        complete = (
            dates_covered == list(dates)
            and all(count >= 2 for count in contracts_per_day.values())
        )
        per_commodity[commodity_code] = {
            "exchange": exchange,
            "date_count": len(dates_covered),
            "dates": dates_covered,
            "contract_record_count": len(items),
            "minimum_two_contracts_each_day": (
                bool(contracts_per_day)
                and all(count >= 2 for count in contracts_per_day.values())
            ),
            "complete": complete,
        }
        if not items or not source_manifests:
            continue
        provenance = bundle_provenance(
            source_manifests, commodity_code=commodity_code
        )
        candidates.extend(
            build_contract_daily_record(
                item.row,
                provenance=provenance,
                quality_flags=item.quality_flags,
            )
            for item in items
        )
        if complete:
            continuous, events = build_continuous_series(
                [item.row for item in items],
                provenance=provenance,
                trading_calendar=calendars[exchange],
            )
            continuous_records.extend(continuous)
            roll_records.extend(events)

    manifest_path = output_dir / "source_manifest.jsonl"
    merged_manifests = merge_source_manifest_revisions(
        read_jsonl(manifest_path), manifests
    )
    contract_path = output_dir / "commodity_contract_daily.jsonl"
    merged_contracts = merge_contract_revisions(
        read_jsonl(contract_path), candidates
    )
    all_records = [
        *merged_contracts,
        *continuous_records,
        *roll_records,
    ]
    validation_errors = validate_records(all_records)
    latest_contracts = [
        record for record in merged_contracts if record.get("is_latest")
    ]
    complete_commodities = [
        code for code, state in per_commodity.items() if state["complete"]
    ]

    acceptance_errors = list(validation_errors)
    if len(latest_contracts) < 80:
        acceptance_errors.append("fewer than 80 latest contract records")
    if len(continuous_records) != 10 * len(complete_commodities):
        acceptance_errors.append(
            "continuous record count does not match complete commodities"
        )
    if len(roll_records) < len(complete_commodities):
        acceptance_errors.append(
            "fewer initialization events than complete commodities"
        )
    if len(complete_commodities) < 4:
        acceptance_errors.append("not all four commodities are complete")

    status = (
        "research_candidate"
        if not acceptance_errors and len(complete_commodities) == 4
        else "blocked"
    )
    summary = {
        "dataset_version": "fingoose-commodity-real-snapshot-v0.2",
        "adapter_version": ADAPTER_VERSION,
        "dates": list(dates),
        "status": status,
        "p0_status": "blocked",
        "forecast_labels_generated": False,
        "license_scope": "unknown",
        "display_allowed": False,
        "redistribution_allowed": False,
        "manifest_count": len(manifests),
        "latest_manifest_count": sum(
            bool(item.get("is_latest")) for item in merged_manifests
        ),
        "manifest_history_count": len(merged_manifests),
        "latest_contract_record_count": len(latest_contracts),
        "all_revision_record_count": len(merged_contracts),
        "continuous_record_count": len(continuous_records),
        "roll_event_count": len(roll_records),
        "complete_commodities": complete_commodities,
        "per_commodity": per_commodity,
        "rejected": rejected,
        "validation_errors": validation_errors,
        "acceptance_errors": acceptance_errors,
        "constraints": {
            "minimum_contracts_per_commodity_day": 2,
            "minimum_total_latest_contract_records": 80,
            "formal_forecast_minimum_history_days": 60,
            "snapshot_is_research_only": True,
        },
    }

    write_jsonl(manifest_path, merged_manifests)
    write_jsonl(contract_path, merged_contracts)
    write_jsonl(
        output_dir / "commodity_roll_events.jsonl",
        sorted(
            roll_records,
            key=lambda item: (
                item["commodity"]["commodity_code"],
                item["effective_date"],
                item["record_id"],
            ),
        ),
    )
    write_jsonl(
        output_dir / "commodity_continuous_daily.jsonl",
        sorted(
            continuous_records,
            key=lambda item: (
                item["commodity"]["commodity_code"],
                item["trade_date"],
            ),
        ),
    )
    write_json(output_dir / "summary.json", summary)
    return summary


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect the locked FinGoose v0.2 ten-day commodity snapshot."
    )
    parser.add_argument(
        "--snapshot-dir", type=Path, default=DEFAULT_SNAPSHOT_DIR
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--dce-daily-dir", type=Path, default=DEFAULT_DCE_DAILY_DIR
    )
    parser.add_argument(
        "--dce-contract-metadata", type=Path, default=DEFAULT_DCE_METADATA
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    args.dce_daily_dir.mkdir(parents=True, exist_ok=True)
    args.dce_contract_metadata.parent.mkdir(parents=True, exist_ok=True)
    try:
        summary = build_snapshot(
            snapshot_dir=args.snapshot_dir,
            output_dir=args.output_dir,
            dce_daily_dir=args.dce_daily_dir,
            dce_metadata=args.dce_contract_metadata,
        )
    except (
        AdapterError,
        MarketDataError,
        OSError,
        urllib.error.URLError,
    ) as exc:
        print(f"commodity snapshot failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
