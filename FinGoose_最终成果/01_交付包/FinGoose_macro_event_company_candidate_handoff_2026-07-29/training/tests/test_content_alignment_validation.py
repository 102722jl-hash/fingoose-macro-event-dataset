from copy import deepcopy

from fingoose_training.answer_renderer import PLACEHOLDER_TOKENS
from fingoose_training.validation_impl_006 import _check


def test_content_alignment_forbidden_tokens_are_stable():
    assert "待补充陈述" in PLACEHOLDER_TOKENS
    assert "omitted_count" in PLACEHOLDER_TOKENS


def _company_sample():
    return {
        "sample_id": "company-test",
        "task_type": "COMPANY_IMPACT",
        "messages": [{"content": ""}, {"content": ""}, {"content": "因果边界"}],
        "metadata": {
            "research_content_version": "research-content-v1",
            "related_company_codes": ["000001.SZ"],
            "research_content": {
                "company_code": "000001.SZ",
                "horizon_directions": {
                    "IMMEDIATE": "MIXED",
                    "SHORT_TERM": "MIXED",
                    "MEDIUM_TERM": "MIXED",
                },
                "causal_identification": {
                    "status": "NOT_IDENTIFIED",
                    "causal_attribution_allowed": False,
                    "causal_conclusion": "ABSTAIN",
                    "gate_results": {"comparison_group_defined": False},
                },
                "relative_market_windows": {
                    "D1": {
                        "status": "CALCULATED",
                        "formula_inputs": {
                            "company_absolute_return": 0.10,
                            "industry_base_value": 100.0,
                            "industry_value": 102.0,
                            "market_base_value": 100.0,
                            "market_value": 101.0,
                        },
                        "industry_relative_return": 0.08,
                        "market_relative_return": 0.09,
                    }
                },
            },
        },
    }


def test_validation_rejects_nonidentified_causal_attribution():
    broken = _company_sample()
    causal = broken["metadata"]["research_content"]["causal_identification"]
    causal["causal_attribution_allowed"] = True

    assert "CAUSAL_GATE_CONTRADICTION" in {row["code"] for row in _check(broken)}


def test_validation_rejects_unreproducible_relative_return():
    broken = deepcopy(_company_sample())
    window = broken["metadata"]["research_content"]["relative_market_windows"]["D1"]
    window["market_relative_return"] += 0.01

    assert "MARKET_CALCULATION_MISMATCH" in {row["code"] for row in _check(broken)}


def test_validation_accepts_reproducible_partial_source_window():
    sample = _company_sample()
    sample["metadata"]["research_content"]["relative_market_windows"] = {
        "D5": {
            "status": "PARTIAL_CALCULATED",
            "formula_version": "company-relative-source-v1",
            "formula_inputs": {
                "company": [23.46, 19.13],
                "industry": [None, None],
                "market": [4623.05, 4551.63],
            },
            "company_absolute_return": -0.18456947996589945,
            "market_return": -0.015448675657844912,
            "market_relative_return": -0.16912080430805454,
            "industry_return": None,
            "industry_relative_return": None,
            "missing_reason": "INDUSTRY_BENCHMARK_DATA_PENDING",
        }
    }

    assert "MARKET_CALCULATION_MISMATCH" not in {
        row["code"] for row in _check(sample)
    }
