from __future__ import annotations

import hashlib
import sys
import shutil
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MultiEventIndustryClosureTests(unittest.TestCase):
    def test_contract_projects_exactly_the_69_non_event_01_profiles(self) -> None:
        from fingoose_industry_impact_v2 import load_industry_profiles
        from fingoose_multi_event_industry_closure_v2 import (
            industry_overlay_roots,
            load_closure_profiles,
        )

        frozen = load_industry_profiles(
            ROOT / "configs/industry_impact_v2/event_industry_profiles.json"
        )
        profiles = load_closure_profiles(ROOT)

        expected_ids = {
            row["event_industry_mapping_id"]
            for row in frozen
            if row["event_id"] != "event-01"
        }
        self.assertEqual(len(profiles), 69)
        self.assertEqual(
            {row["event_industry_mapping_id"] for row in profiles}, expected_ids
        )
        self.assertEqual(
            Counter(row["event_id"] for row in profiles),
            {
                "event-02": 8,
                "event-03": 8,
                "event-04": 8,
                "event-05": 7,
                "event-06": 7,
                "event-07": 7,
                "event-08": 7,
                "event-09": 8,
                "event-10": 9,
            },
        )
        for profile in profiles:
            self.assertEqual(len(profile["mechanism_steps"]), 7)
            self.assertEqual(
                [step["step_type"] for step in profile["mechanism_steps"]],
                [
                    "EVENT_FACT",
                    "BEHAVIOR_OR_POLICY_CHANGE",
                    "OBSERVABLE_DRIVER",
                    "INDUSTRY_OPERATING_VARIABLE",
                    "INDUSTRY_REVENUE_OR_COST_VARIABLE",
                    "DIRECTION_ASSESSMENT",
                    "PRICE_CONFOUNDER_AND_COUNTEREVIDENCE",
                ],
            )
            self.assertTrue(all(step["statement_zh"] for step in profile["mechanism_steps"]))
            self.assertTrue(profile["condition_zh"])
            self.assertTrue(profile["invalidation_condition_zh"])
            self.assertTrue(profile["counterevidence_zh"])
            self.assertEqual(profile["status"], "PROPOSED")
            self.assertEqual(profile["review_status"], "NEEDS_HUMAN_REVIEW")
            self.assertIs(profile["formal_ready"], False)
            self.assertEqual(profile["sha_gate"], "DEFERRED")
        self.assertEqual(
            [path.name for path in industry_overlay_roots(ROOT)],
            [
                "event_01_industry_closure_v2_candidate",
                "ten_event_industry_closure_v2_candidate",
            ],
        )

    def test_steps_embed_real_anchor_fact_time_and_industry_transmission(self) -> None:
        from fingoose_company_impact_io_v2 import read_jsonl
        from fingoose_multi_event_industry_closure_v2 import load_closure_profiles

        baseline = read_jsonl(
            ROOT
            / "work/industry_impact_high_quality_v2_candidate/event_industry_mappings.jsonl"
        )
        anchors = {}
        for row in baseline:
            anchors.setdefault(row["event_id"], row)

        profiles = load_closure_profiles(ROOT)
        for profile in profiles:
            anchor = anchors[profile["event_id"]]
            event_fact = profile["mechanism_steps"][0]["statement_zh"]
            behavior = profile["mechanism_steps"][1]["statement_zh"]
            self.assertIn(anchor["anchor_occurred_at"], event_fact)
            self.assertIn(profile["anchor_fact_zh"], event_fact)
            self.assertRegex(profile["anchor_fact_zh"], r"[一-鿿]")
            self.assertNotIn("?????????", event_fact)
            self.assertIn(profile["display_name_zh"], behavior)
            self.assertIn(profile["observable_driver_zh"], behavior)
            self.assertIn(profile["industry_operating_variable_zh"], behavior)

        event_04 = next(row for row in profiles if row["event_id"] == "event-04")
        event_04_fact = event_04["mechanism_steps"][0]["statement_zh"]
        self.assertIn("2022-12-07T07:00:00+08:00", event_04_fact)
        self.assertIn("provisional", event_04_fact)
        self.assertIn(anchors["event-04"]["anchor_gap_reason"], event_04_fact)

    def test_empty_inputs_emit_joinable_open_overlay_without_touching_baseline(self) -> None:
        from fingoose_company_impact_io_v2 import read_jsonl
        from fingoose_multi_event_industry_closure_v2 import build_closure_bundle

        baseline = ROOT / "work/industry_impact_high_quality_v2_candidate"
        baseline_files = sorted(baseline.glob("*.jsonl"))
        before = {path.name: _sha256(path) for path in baseline_files}

        output = ROOT / "work/_test_multi_event_industry_overlay"
        if output.exists():
            shutil.rmtree(output)
        self.addCleanup(shutil.rmtree, output, True)
        with self.subTest(output=output):
            report = build_closure_bundle(
                ROOT,
                output_root=output,
                evidence_fetches=[],
                driver_payloads={},
                market_payloads={},
            )
            mappings = read_jsonl(output / "event_industry_mappings.jsonl")
            chains = read_jsonl(output / "industry_mechanism_chains.jsonl")
            drivers = read_jsonl(output / "industry_driver_registry.jsonl")
            windows = read_jsonl(output / "industry_market_windows.jsonl")
            completion = read_jsonl(output / "industry_completion_report.jsonl")

            ids = {row["event_industry_mapping_id"] for row in mappings}
            self.assertEqual(len(mappings), 69)
            self.assertEqual(len(chains), 69)
            self.assertEqual(sum(len(row["nodes"]) for row in chains), 483)
            self.assertEqual(ids, {row["event_industry_mapping_id"] for row in chains})
            self.assertEqual(ids, {row["event_industry_mapping_id"] for row in drivers})
            self.assertEqual(ids, {row["event_industry_mapping_id"] for row in windows})
            self.assertEqual(ids, {row["event_industry_mapping_id"] for row in completion})
            self.assertTrue(all(row["completion_status"] == "OPEN" for row in completion))
            for row in completion:
                self.assertEqual(
                    row["blockers"],
                    [
                        "FOUR_FACT_PILLARS_INCOMPLETE",
                        "DRIVER_DATA_INCOMPLETE",
                        "INDUSTRY_WINDOW_INCOMPLETE",
                    ],
                )
                self.assertEqual(row["review_status"], "NEEDS_HUMAN_REVIEW")
                self.assertIs(row["formal_ready"], False)
                self.assertEqual(row["sha_gate"], "DEFERRED")
            self.assertEqual(report["mapping_count"], 69)
            self.assertEqual(report["mechanism_node_count"], 483)
            self.assertEqual(report["open_count"], 69)
            self.assertEqual(report["candidate_complete_count"], 0)
            self.assertIs(report["formal_ready"], False)
            self.assertEqual(report["sha_gate"], "DEFERRED")
            registry = __import__("json").loads(
                (output / "overlay_registry.json").read_text(encoding="utf-8")
            )
            self.assertEqual(registry["expected_unique_mapping_count"], 77)
            self.assertEqual(
                [row["event_scope"] for row in registry["overlays"]],
                [["event-01"], [f"event-{number:02d}" for number in range(2, 11)]],
            )

        after = {path.name: _sha256(path) for path in baseline_files}
        self.assertEqual(after, before)

    def test_available_market_updates_calculated_fact_and_completion_gates(self) -> None:
        from fingoose_company_impact_io_v2 import read_jsonl
        from fingoose_multi_event_industry_closure_v2 import build_closure_bundle

        source_root = ROOT / "work/ten_event_industry_closure_v2_candidate"
        output = ROOT / "work/_test_multi_event_available_market"
        if output.exists():
            shutil.rmtree(output)
        self.addCleanup(shutil.rmtree, output, True)
        market_payloads = {
            row["event_industry_mapping_id"]: row
            for row in read_jsonl(source_root / "industry_market_windows.jsonl")
        }
        build_closure_bundle(
            ROOT,
            output_root=output,
            evidence_fetches=read_jsonl(source_root / "industry_source_fetches.jsonl"),
            market_payloads=market_payloads,
        )

        mappings = {
            row["event_industry_mapping_id"]: row
            for row in read_jsonl(output / "event_industry_mappings.jsonl")
        }
        chains = read_jsonl(output / "industry_mechanism_chains.jsonl")
        completion = read_jsonl(output / "industry_completion_report.jsonl")
        for chain in chains:
            for confounder in chain["confounders"]:
                self.assertEqual(
                    confounder["statement_class"],
                    "RESEARCH_INFERENCE",
                )
                self.assertGreaterEqual(len(confounder["analysis_zh"]), 120)
                self.assertTrue(confounder["distinguishing_tests_zh"])
                self.assertIn(
                    confounder["evidence_status"],
                    {"AVAILABLE", "EVIDENCE_PENDING"},
                )
                if confounder["evidence_status"] == "EVIDENCE_PENDING":
                    self.assertEqual(
                        confounder["missing_evidence_reason"],
                        "CONFOUNDER_SOURCE_NOT_VERIFIED",
                    )
            calculation = chain["nodes"][6]
            self.assertEqual(
                calculation["evidence_status"],
                "MARKET_CALCULATION_AVAILABLE",
            )
            self.assertIsNone(calculation["missing_evidence_reason"])
            self.assertTrue(calculation["calculation_reference"])

        for row in completion:
            mapping = mappings[row["event_industry_mapping_id"]]
            self.assertEqual(row["event_id"], mapping["event_id"])
            self.assertEqual(
                set(row["gate_statuses"]),
                {
                    "mechanism_evidence",
                    "driver_data",
                    "market_window",
                    "company_sample",
                },
            )
            self.assertEqual(
                row["gate_statuses"]["company_sample"],
                "AVAILABLE" if mapping["company_count"] else "DATA_PENDING",
            )
            self.assertEqual(row["evidence_coverage"]["required_node_count"], 4)
            self.assertEqual(
                row["evidence_coverage"]["evidenced_node_count"],
                sum(
                    node["statement_class"] == "SOURCE_FACT"
                    and node["evidence_status"] == "AVAILABLE"
                    for node in next(
                        chain
                        for chain in chains
                        if chain["event_industry_mapping_id"]
                        == row["event_industry_mapping_id"]
                    )["nodes"]
                ),
            )

    def test_verified_evidence_is_bound_only_to_declared_mapping_and_step(self) -> None:
        from fingoose_multi_event_industry_closure_v2 import (
            build_mechanism_chains,
            load_closure_profiles,
        )

        profiles = load_closure_profiles(ROOT)
        target = profiles[0]
        source = {
            "source_id": "source-test-event-fact",
            "fetch_status": "RETRIEVED_QUOTE_VERIFIED",
            "supports_mapping_ids": [target["event_industry_mapping_id"]],
            "supports_step_types": ["EVENT_FACT"],
        }
        chains = build_mechanism_chains(profiles, [source])
        target_chain = next(
            row
            for row in chains
            if row["event_industry_mapping_id"]
            == target["event_industry_mapping_id"]
        )
        self.assertEqual(target_chain["nodes"][0]["evidence_status"], "AVAILABLE")
        self.assertEqual(
            target_chain["nodes"][0]["evidence_ids"],
            ["source-test-event-fact"],
        )
        self.assertTrue(
            all(
                node["evidence_status"] != "AVAILABLE"
                for chain in chains
                for node in chain["nodes"]
                if node["node_id"] != target_chain["nodes"][0]["node_id"]
            )
        )


    def test_default_driver_payloads_require_verified_sources(self) -> None:
        from fingoose_company_impact_io_v2 import read_jsonl
        from fingoose_multi_event_industry_closure_v2 import (
            _driver_records,
            build_closure_bundle,
            load_closure_profiles,
        )

        output = ROOT / "work/_test_multi_event_driver_payloads"
        if output.exists():
            shutil.rmtree(output)
        self.addCleanup(shutil.rmtree, output, True)
        fetches = read_jsonl(
            ROOT
            / "work/ten_event_industry_closure_v2_candidate/industry_source_fetches.jsonl"
        )
        report = build_closure_bundle(
            ROOT,
            output_root=output,
            evidence_fetches=fetches,
            driver_payloads=None,
            market_payloads={},
        )
        drivers = read_jsonl(output / "industry_driver_registry.jsonl")
        observations = read_jsonl(output / "industry_driver_observations.jsonl")
        verified_ids = {
            row["source_id"]
            for row in fetches
            if row["fetch_status"] == "RETRIEVED_QUOTE_VERIFIED"
        }

        self.assertEqual(report["available_driver_count"], 39)
        self.assertEqual(
            sum(row["source_status"] == "AVAILABLE" for row in drivers),
            39,
        )
        self.assertEqual(len(observations), 39)
        self.assertTrue(
            all(
                row["source_id"] in verified_ids
                for row in drivers
                if row["source_status"] == "AVAILABLE"
            )
        )

        first = load_closure_profiles(ROOT)[0]
        pending, pending_observations = _driver_records(
            [first],
            {
                first["event_industry_mapping_id"]: {
                    "source_id": "unverified-source",
                    "source_status": "AVAILABLE",
                    "frequency": "EVENT_OBSERVATION",
                    "observations": [
                        {
                            "observed_at": "2022-02-24",
                            "metric_code": "UNVERIFIED",
                            "value": 1,
                            "unit": "test",
                        }
                    ],
                }
            },
            verified_source_ids=set(),
        )
        self.assertEqual(pending[0]["source_status"], "DATA_PENDING")
        self.assertIsNone(pending_observations[0]["value"])

if __name__ == "__main__":
    unittest.main()
