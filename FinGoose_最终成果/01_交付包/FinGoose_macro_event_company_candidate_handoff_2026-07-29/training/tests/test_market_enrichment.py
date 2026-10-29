from copy import deepcopy

import pytest

from fingoose_training.market_enrichment import (
    MarketEnrichmentError,
    attach_industry_market_windows,
    build_industry_window_sw1_index,
    calculate_company_relative_windows,
    index_industry_windows,
    merge_existing_market_relative_windows,
    resolve_company_industry_window,
)


def _industry_window():
    return {
        "event_industry_mapping_id": "industry-1",
        "benchmark": {"benchmark_id": "SW1-801010"},
        "continuous_window": [
            {
                "actual_date": "2020-01-01",
                "industry_value": 2000.0,
                "market_value": 4000.0,
            },
            {
                "actual_date": "2020-01-02",
                "industry_value": 2060.0,
                "market_value": 4040.0,
            },
        ],
        "fixed_windows": {"D1": {"actual_date": "2020-01-02"}},
    }


def test_industry_windows_are_indexed_by_mapping_id_without_mutation():
    rows = [_industry_window()]
    before = deepcopy(rows)

    indexed = index_industry_windows(rows)

    assert indexed["industry-1"] == rows[0]
    assert indexed["industry-1"] is not rows[0]
    assert rows == before


def test_duplicate_industry_window_mapping_fails():
    with pytest.raises(MarketEnrichmentError, match="duplicate"):
        index_industry_windows([
            {"event_industry_mapping_id": "industry-1"},
            {"event_industry_mapping_id": "industry-1"},
        ])


def test_attach_industry_window_requires_exact_mapping():
    impacts = [{"event_industry_mapping_id": "industry-1", "industry_name_zh": "行业"}]
    attached = attach_industry_market_windows(impacts, [_industry_window()])
    assert attached[0]["market_window"]["event_industry_mapping_id"] == "industry-1"
    assert "market_window" not in impacts[0]

    with pytest.raises(MarketEnrichmentError, match="missing"):
        attach_industry_market_windows(
            [{"event_industry_mapping_id": "industry-missing"}],
            [_industry_window()],
        )


def test_sw1_index_and_company_resolution_use_explicit_mapping_then_sw1():
    window = _industry_window()
    by_mapping = index_industry_windows([window])
    by_sw1 = build_industry_window_sw1_index([window])
    assert set(by_sw1) == {"801010"}

    explicit = resolve_company_industry_window(
        {"binding_review": {"industry_impact_id": "industry-1"}},
        by_mapping,
        by_sw1,
    )
    fallback = resolve_company_industry_window(
        {"market_window": {"industry_id": "801010"}},
        {},
        by_sw1,
    )
    assert explicit["event_industry_mapping_id"] == "industry-1"
    assert fallback["event_industry_mapping_id"] == "industry-1"


def test_legacy_company_mapping_falls_back_to_explicit_sw1_id():
    window = _industry_window()
    resolved = resolve_company_industry_window(
        {
            "binding_review": {"industry_impact_id": "legacy-industry-id"},
            "market_window": {"industry_id": "801010"},
        },
        index_industry_windows([window]),
        build_industry_window_sw1_index([window]),
    )
    assert resolved["event_industry_mapping_id"] == "industry-1"


def test_company_relative_returns_use_company_dates_and_common_base():
    company = {
        "observations": {
            "T_MINUS_1": {"actual_date": "2020-01-01", "absolute_return": 0.0},
            "D1": {"actual_date": "2020-01-02", "absolute_return": 0.10},
        }
    }

    result = calculate_company_relative_windows(company, _industry_window())

    d1 = result["D1"]
    assert d1["formula_inputs"] == {
        "company_absolute_return": 0.10,
        "industry_base_value": 2000.0,
        "industry_value": 2060.0,
        "market_base_value": 4000.0,
        "market_value": 4040.0,
    }
    assert d1["market_relative_return"] == pytest.approx(0.09)
    assert d1["industry_relative_return"] == pytest.approx(0.07)
    assert d1["formula_version"] == "company-relative-v1"


def test_missing_benchmark_date_stays_missing_not_zero():
    result = calculate_company_relative_windows(
        {"observations": {
            "T_MINUS_1": {"actual_date": "2020-01-01", "absolute_return": 0.0},
            "D1": {"actual_date": "2020-01-03", "absolute_return": 0.10},
        }},
        _industry_window(),
    )

    assert result["D1"] == {
        "status": "DATA_MISSING",
        "missing_reason": "BENCHMARK_ACTUAL_DATE_NOT_FOUND:2020-01-03",
    }


def test_zero_benchmark_base_is_explicitly_missing():
    window = _industry_window()
    window["continuous_window"][0]["industry_value"] = 0.0
    result = calculate_company_relative_windows(
        {"observations": {
            "T_MINUS_1": {"actual_date": "2020-01-01", "absolute_return": 0.0},
            "D1": {"actual_date": "2020-01-02", "absolute_return": 0.10},
        }},
        window,
    )
    assert result["D1"]["status"] == "DATA_MISSING"
    assert result["D1"]["missing_reason"] == "BENCHMARK_BASE_ZERO:D1"


def test_existing_market_relative_window_can_fill_only_market_side():
    calculated = {
        "D1": {
            "status": "DATA_MISSING",
            "missing_reason": "BENCHMARK_BASE_DATE_NOT_FOUND:2020-01-01",
        }
    }
    existing = {
        "observations": {
            "D1": {
                "end_date": "2020-01-02",
                "company_return": 0.10,
                "market_return": 0.02,
                "market_relative_return": 0.08,
                "market_status": "AVAILABLE",
                "industry_status": "DATA_PENDING",
                "formula_inputs": {
                    "company": [100.0, 110.0],
                    "market": [4000.0, 4080.0],
                    "industry": [None, None],
                },
            }
        }
    }

    result = merge_existing_market_relative_windows(calculated, existing)

    assert result["D1"]["status"] == "PARTIAL_CALCULATED"
    assert result["D1"]["market_relative_return"] == pytest.approx(0.08)
    assert result["D1"]["industry_relative_return"] is None
    assert result["D1"]["missing_reason"] == "INDUSTRY_BENCHMARK_DATA_PENDING"
