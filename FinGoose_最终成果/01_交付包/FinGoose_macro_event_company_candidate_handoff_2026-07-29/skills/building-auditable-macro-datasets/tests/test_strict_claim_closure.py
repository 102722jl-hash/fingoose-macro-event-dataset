from copy import deepcopy

from audit_outputs import (
    STRICT_POLICY,
    candidate_eligibility,
    strict_claim_closure_gaps,
    validate_atomic_batch,
)


def market_window():
    endpoints = {}
    for index, label in enumerate(("T_MINUS_1", "T0", "D1", "D3", "D5", "D20")):
        raw_value = 100.0 + index
        market_raw_value = 200.0 + index
        industry_raw_value = 300.0 + index
        own_return = raw_value / 100.0 - 1
        market_return = market_raw_value / 200.0 - 1
        industry_return = industry_raw_value / 300.0 - 1
        endpoints[label] = {
            "date": f"2026-01-{index + 1:02d}",
            "raw_value": raw_value,
            "market_raw_value": market_raw_value,
            "industry_raw_value": industry_raw_value,
            "return": own_return,
            "market_return": market_return,
            "industry_return": industry_return,
            "market_relative_return": own_return - market_return,
            "industry_relative_return": own_return - industry_return,
        }
    return {
        "status": "CALCULATED",
        "data_source": "official exchange endpoints",
        "formula": "value / T_MINUS_1 - 1",
        "continuous_trading_verified": True,
        "endpoints": endpoints,
    }


def valid_record():
    event_id = "event-11"
    evidence_registry = []
    industries = []
    companies = []
    for industry_index in range(5):
        industry_id = f"industry-{industry_index}"
        nodes = []
        for node_index in range(7):
            node_id = f"{event_id}-{industry_id}-node-{node_index}"
            evidence_id = f"evidence-{industry_index}-{node_index}"
            support_type = "CALCULATED_LINEAGE" if node_index == 5 else "PREMISE_SUPPORT"
            if node_index == 6:
                support_type = "NEGATIVE_SEARCH_AUDIT"
            evidence_ids = [] if node_index in {5, 6} else [evidence_id]
            nodes.append({
                "node_id": node_id,
                "statement_zh": f"行业{industry_index}节点{node_index}的专属传导主张与可观测边界。",
                "support_type": support_type,
                "evidence_ids": evidence_ids,
                "support_rationale_zh": "原文直接支持该推理前提。",
                "evidence_locator": f"paragraph {node_index}",
                "negative_search_audit": {
                    "query": "counterevidence query",
                    "window_start": "2025-12-01",
                    "window_end": "2026-01-31",
                    "result_count": 0,
                    "documents_reviewed": 2,
                },
            })
            if evidence_ids:
                evidence_registry.append({
                    "evidence_id": evidence_id,
                    "publisher": "Official Agency",
                    "published_at": "2026-01-01T00:00:00Z",
                    "retrieved_at": "2026-01-02T00:00:00Z",
                    "original_quote": f"Official quote {industry_index}-{node_index}",
                    "locator": f"paragraph {node_index}",
                    "source_url": f"https://official.test/{evidence_id}",
                    "snapshot_sha256": "a" * 64,
                    "source_tier": "T1",
                    "supports_node_ids": [node_id],
                })
        industries.append({
            "event_id": event_id,
            "industry_id": industry_id,
            "mechanism_nodes": nodes,
            "horizon_analysis": {
                "IMMEDIATE": f"行业{industry_index}在首个交易日重估政策暴露。",
                "SHORT_TERM": f"行业{industry_index}在二十日内调整订单和库存。",
                "MEDIUM_TERM": f"行业{industry_index}在四个季度内由财报验证兑现。",
            },
            "market_window": market_window(),
        })
        for company_index in range(3):
            mapping_id = f"company-map-{industry_index}-{company_index}"
            disclosures = []
            for disclosure_index in range(2):
                evidence_id = f"company-evidence-{industry_index}-{company_index}-{disclosure_index}"
                disclosures.append({
                    "evidence_id": evidence_id,
                    "source_tier": "T2",
                    "temporal_role": "AS_OF_EVIDENCE",
                    "published_at": "2025-12-01T00:00:00Z",
                    "original_quote": "The filing describes the company's pre-event business exposure.",
                    "locator": f"page {disclosure_index + 1}",
                    "source_url": f"https://exchange.test/{evidence_id}.pdf",
                })
            companies.append({
                "event_id": event_id,
                "industry_id": industry_id,
                "mapping_id": mapping_id,
                "business_exposure_zh": f"公司{company_index}在事件前已披露行业{industry_index}收入暴露。",
                "company_evidence": disclosures,
                "horizon_analysis": {
                    "IMMEDIATE": "首日估值先反映暴露方向。",
                    "SHORT_TERM": "二十日内订单与成本开始调整。",
                    "MEDIUM_TERM": "季度财报检验收入和利润兑现。",
                },
                "confounders": ["同期市场风险偏好"],
                "counterevidence": ["同业走势不一致会削弱解释"],
                "market_window": market_window(),
            })
    qa = [
        {
            "event_id": event_id,
            "qa_type": "EVIDENCE_QUERY",
            "direct_answer_zh": "官方文件直接确认事件事实。",
            "reference_ids": ["evidence-0-0"],
            "evidence_ids": ["evidence-0-0"],
        },
        {
            "event_id": event_id,
            "qa_type": "MECHANISM_STAGE",
            "direct_answer_zh": "首个机制节点说明政策如何进入经营变量。",
            "reference_ids": ["event-11-industry-0-node-0"],
            "evidence_ids": ["evidence-0-0"],
        },
        {
            "event_id": event_id,
            "qa_type": "MARKET_VALIDATION",
            "direct_answer_zh": "窗口收益只验证表现一致性，不证明因果。",
            "reference_ids": ["industry-0"],
            "evidence_ids": ["evidence-0-0"],
        },
        {
            "event_id": event_id,
            "qa_type": "INDUSTRY_COMPANY",
            "direct_answer_zh": "公司按事件前披露的业务暴露纳入。",
            "reference_ids": ["company-map-0-0"],
            "evidence_ids": ["company-evidence-0-0-0"],
        },
    ]
    unified = {
        "event_id": event_id,
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "causal_assessment": {
            "status": "DESCRIPTIVE_EVENT_STUDY",
            "causal_attribution_allowed": False,
            "causal_conclusion": "ABSTAIN",
            "gate_results": {},
        },
        "evidence_registry": evidence_registry,
        "industries": industries,
        "companies": companies,
        "qa": qa,
    }
    return {"event_id": event_id, "closure_status": "OPEN", "unified_event": unified}


def test_strict_complete_record_passes():
    record = valid_record()
    assert strict_claim_closure_gaps(record) == []
    assert candidate_eligibility(record, policy=STRICT_POLICY) is True


def test_nonempty_shell_arrays_fail_closed():
    record = valid_record()
    record["unified_event"]["industries"] = [{}]
    assert "INDUSTRY_MECHANISM_NOT_SEVEN_STEPS" in strict_claim_closure_gaps(record)


def test_generic_industry_templates_are_rejected():
    record = valid_record()
    duplicate = deepcopy(record["unified_event"]["industries"][0]["mechanism_nodes"])
    record["unified_event"]["industries"][1]["mechanism_nodes"] = duplicate
    assert "GENERIC_INDUSTRY_TEMPLATE_REUSED" in strict_claim_closure_gaps(record)


def test_node_without_evidence_is_rejected():
    record = valid_record()
    record["unified_event"]["industries"][0]["mechanism_nodes"][0]["evidence_ids"] = []
    assert "MECHANISM_NODE_EVIDENCE_MISSING" in strict_claim_closure_gaps(record)


def test_company_with_less_than_two_disclosures_is_rejected():
    record = valid_record()
    record["unified_event"]["companies"][0]["company_evidence"] = record["unified_event"]["companies"][0]["company_evidence"][:1]
    assert "COMPANY_PRE_EVENT_DISCLOSURES_LT_TWO" in strict_claim_closure_gaps(record)


def test_dangling_qa_reference_is_rejected():
    record = valid_record()
    record["unified_event"]["qa"][0]["reference_ids"] = ["does-not-exist"]
    assert "QA_DANGLING_REFERENCE" in strict_claim_closure_gaps(record)


def test_non_recomputable_market_window_is_rejected():
    record = valid_record()
    del record["unified_event"]["companies"][0]["market_window"]["endpoints"]["D20"]["raw_value"]
    assert "COMPANY_MARKET_RAW_VALUE_MISSING" in strict_claim_closure_gaps(record)


def test_false_closed_status_is_rejected():
    record = valid_record()
    record["closure_status"] = "CLOSED"
    record["unified_event"]["companies"][0]["company_evidence"] = []
    gaps = strict_claim_closure_gaps(record)
    assert "COMPANY_PRE_EVENT_DISCLOSURES_LT_TWO" in gaps
    assert "FALSE_CLOSED_STATUS" in gaps


def test_market_formula_mismatch_is_rejected():
    record = valid_record()
    record["unified_event"]["companies"][0]["market_window"]["endpoints"]["D20"]["return"] = 9.0
    assert "COMPANY_MARKET_FORMULA_MISMATCH" in strict_claim_closure_gaps(record)


def test_atomic_batch_requires_exact_event_set():
    accepted = [{"event_id": "event-11"}, {"event_id": "event-12"}]
    assert validate_atomic_batch(accepted, ["event-11", "event-12"]) == []
    assert validate_atomic_batch(accepted, ["event-11", "event-12", "event-13"]) == [
        "ATOMIC_BATCH_EVENT_SET_INCOMPLETE"
    ]
