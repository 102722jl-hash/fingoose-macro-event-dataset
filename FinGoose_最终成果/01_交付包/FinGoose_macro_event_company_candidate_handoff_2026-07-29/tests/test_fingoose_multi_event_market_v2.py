from __future__ import annotations

import shutil
import sys
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class _Frame:
    empty = False
    columns = ["date", "close"]

    def to_csv(self, path: Path, **_: object) -> None:
        path.write_text("date,close\n2022-01-04,100\n", encoding="utf-8")


def test_market_fetch_uses_registry_csi300_date_range(monkeypatch) -> None:
    from fingoose_industry_market_v2 import fetch_market_registry

    calls: list[dict[str, str]] = []

    class AkModule:
        @staticmethod
        def index_hist_sw(*, symbol: str, period: str) -> _Frame:
            return _Frame()

        @staticmethod
        def stock_zh_index_daily_tx(**kwargs: str) -> _Frame:
            calls.append(dict(kwargs))
            return _Frame()

    monkeypatch.setitem(sys.modules, "akshare", AkModule())
    output = ROOT / "work/_test_multi_event_market_fetch"
    if output.exists():
        shutil.rmtree(output)
    try:
        records = fetch_market_registry(
            {
                "date_range": {"start_date": "20220101", "end_date": "20250801"},
                "industry_benchmarks": [
                    {"mapping_id": "event-industry-event-02-801010", "code": "801010"}
                ],
                "market_benchmark": {"benchmark_id": "CSI300", "code": "sh000300"},
            },
            output,
        )
        assert calls == [
            {
                "symbol": "sh000300",
                "start_date": "20220101",
                "end_date": "20250801",
            }
        ]
        csi = next(row for row in records if row["series_id"] == "CSI300")
        assert csi["provider_parameters"] == calls[0]
    finally:
        if output.exists():
            shutil.rmtree(output)


def _sessions() -> list[str]:
    current = date(2021, 11, 1)
    end = date(2025, 8, 1)
    rows: list[str] = []
    while current <= end:
        if current.weekday() < 5:
            rows.append(current.isoformat())
        current += timedelta(days=1)
    return rows


def test_all_69_windows_use_first_public_t0_and_keep_frozen_mapping_pool() -> None:
    from fingoose_industry_market_v2 import build_market_windows_for_mappings
    from fingoose_multi_event_industry_closure_v2 import load_closure_profiles

    profiles = load_closure_profiles(ROOT)
    sessions = _sessions()
    market_rows = [
        {"date": day, "close": 4000.0 + index}
        for index, day in enumerate(sessions)
    ]
    codes = {str(profile["sw1_id"]) for profile in profiles}
    industry_rows_by_code = {
        code: [
            {"date": day, "close": 1000.0 + code_index * 10 + index}
            for index, day in enumerate(sessions)
        ]
        for code_index, code in enumerate(sorted(codes))
    }

    windows = build_market_windows_for_mappings(
        mappings=profiles,
        industry_rows_by_code=industry_rows_by_code,
        market_rows=market_rows,
        market_timezone="Asia/Shanghai",
    )

    assert len(windows) == 69
    assert {row["event_industry_mapping_id"] for row in windows} == {
        row["event_industry_mapping_id"] for row in profiles
    }
    assert all(row["window_status"] == "AVAILABLE" for row in windows)
    assert all(len(row["continuous_window"]) == 41 for row in windows)
    assert all(
        set(row["fixed_windows"])
        == {"T_MINUS_1", "T0", "D1", "D3", "D5", "D20", "M3"}
        for row in windows
    )
    event_09 = next(row for row in windows if row["event_id"] == "event-09")
    assert event_09["event_at_basis"] == "ANCHOR_FIRST_PUBLIC_AT"
    assert event_09["event_at"] == "2024-09-24T16:07:00+08:00"
    assert event_09["t0_alignment"]["T0"] == "2024-09-25"
    assert all(
        point["industry_value"] != 0 and point["market_value"] != 0
        for row in windows
        for point in row["continuous_window"]
    )


def test_load_market_windows_from_raw_reads_registered_csv_files(request) -> None:
    from fingoose_industry_market_v2 import load_market_windows_from_raw

    sessions = _sessions()
    output = ROOT / "work/_test_multi_event_market_loader"
    if output.exists():
        shutil.rmtree(output)
    request.addfinalizer(lambda: shutil.rmtree(output, ignore_errors=True))
    raw_root = output / "raw/market"
    raw_root.mkdir(parents=True)
    (raw_root / "csi300.csv").write_text(
        "date,close\n"
        + "".join(
            f"{day},{4000.0 + index}\n" for index, day in enumerate(sessions)
        ),
        encoding="utf-8",
    )
    (raw_root / "sw_801010.csv").write_text(
        "date,close\n"
        + "".join(
            f"{day},{1000.0 + index}\n"
            for index, day in enumerate(sessions)
        ),
        encoding="utf-8-sig",
    )
    mapping = {
        "event_industry_mapping_id": "event-industry-event-02-801010",
        "event_id": "event-02",
        "anchor_first_public_at": "2022-02-24T05:00:00+00:00",
        "classification_edition": "SW2021",
        "sw1_id": "801010",
    }
    observation = {
        "event_industry_mapping_id": mapping["event_industry_mapping_id"],
        "value": 1.0,
    }

    windows = load_market_windows_from_raw(
        mappings=[mapping],
        registry={
            "market_timezone": "Asia/Shanghai",
            "industry_benchmarks": [{"code": "801010"}],
        },
        raw_root=raw_root,
        driver_observations_by_mapping={
            mapping["event_industry_mapping_id"]: [observation]
        },
    )

    assert len(windows) == 1
    assert windows[0]["window_status"] == "AVAILABLE"
    assert windows[0]["t0_alignment"]["T0"] == "2022-02-24"
    assert windows[0]["driver_observations"] == [observation]


def test_closure_builder_loads_raw_market_when_payloads_are_not_explicit(
    monkeypatch,
) -> None:
    from fingoose_company_impact_io_v2 import read_jsonl
    import fingoose_industry_market_v2 as market_module
    from fingoose_multi_event_industry_closure_v2 import build_closure_bundle

    calls: list[tuple[int, Path]] = []

    def fake_loader(*, mappings, registry, raw_root, driver_observations_by_mapping=None):
        rows = list(mappings)
        calls.append((len(rows), raw_root))
        return [
            {
                "event_industry_mapping_id": row["event_industry_mapping_id"],
                "event_id": row["event_id"],
                "event_at": row["anchor_first_public_at"],
                "event_at_basis": "ANCHOR_FIRST_PUBLIC_AT",
                "continuous_window": [{"industry_value": 1.0, "market_value": 1.0}],
                "fixed_windows": {"T0": {"industry_value": 1.0, "market_value": 1.0}},
                "window_status": "AVAILABLE",
                "pending_reason": None,
                "review_status": "NEEDS_HUMAN_REVIEW",
                "formal_ready": False,
                "sha_gate": "DEFERRED",
            }
            for row in rows
        ]

    monkeypatch.setattr(market_module, "load_market_windows_from_raw", fake_loader)
    output = ROOT / "work/_test_multi_event_market_bundle"
    if output.exists():
        shutil.rmtree(output)
    try:
        report = build_closure_bundle(
            ROOT,
            output_root=output,
            evidence_fetches=[],
            driver_payloads={},
            market_payloads=None,
        )
        windows = read_jsonl(output / "industry_market_windows.jsonl")
        assert calls == [(69, output / "raw/market")]
        assert len(windows) == 69
        assert all(row["window_status"] == "AVAILABLE" for row in windows)
        assert report["available_market_window_count"] == 69
    finally:
        if output.exists():
            shutil.rmtree(output)
