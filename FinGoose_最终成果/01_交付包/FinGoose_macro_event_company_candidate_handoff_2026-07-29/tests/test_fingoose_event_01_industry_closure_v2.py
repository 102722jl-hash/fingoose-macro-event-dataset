from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class Event01IndustryClosureTests(unittest.TestCase):
    def test_profiles_cover_exactly_eight_event_01_mappings(self) -> None:
        from fingoose_event_01_industry_closure_v2 import load_closure_profiles

        profiles = load_closure_profiles(
            ROOT / "configs/industry_impact_v2/event_01_closure_profiles.json"
        )
        self.assertEqual(len(profiles), 8)
        self.assertEqual({row["event_id"] for row in profiles}, {"event-01"})
        self.assertEqual(
            {row["impact_tier"] for row in profiles},
            {"CORE_DIRECT", "SECOND_ORDER", "CONDITIONAL"},
        )
        self.assertEqual(
            len({row["event_industry_mapping_id"] for row in profiles}), 8
        )
        self.assertTrue(all(len(row["mechanism_steps"]) == 7 for row in profiles))
        self.assertTrue(all(row["formal_ready"] is False for row in profiles))
        self.assertTrue(all(row["sha_gate"] == "DEFERRED" for row in profiles))


    def test_chain_projection_separates_facts_and_inferences(self) -> None:
        from fingoose_event_01_industry_closure_v2 import (
            build_mechanism_chains,
            load_closure_profiles,
        )

        profiles = load_closure_profiles(
            ROOT / "configs/industry_impact_v2/event_01_closure_profiles.json"
        )
        evidence = {
            evidence_id: {
                "evidence_id": evidence_id,
                "fetch_status": "RETRIEVED_QUOTE_VERIFIED",
            }
            for profile in profiles
            for step in profile["mechanism_steps"]
            for evidence_id in step.get("evidence_ids", [])
        }
        chains = build_mechanism_chains(profiles, evidence)
        self.assertEqual(len(chains), 8)
        self.assertEqual(sum(len(row["nodes"]) for row in chains), 56)
        for chain in chains:
            for node in chain["nodes"]:
                if node["statement_class"] == "SOURCE_FACT":
                    self.assertTrue(node["evidence_ids"])
                if node["statement_class"] == "RESEARCH_INFERENCE":
                    self.assertTrue(node["premise_node_ids"])
                    self.assertTrue(node["condition_zh"])
                    self.assertTrue(node["invalidation_zh"])


    def test_driver_and_confounder_projection_covers_all_eight_mappings(self) -> None:
        from fingoose_event_01_industry_closure_v2 import (
            build_driver_records,
            build_mechanism_chains,
            load_closure_profiles,
        )

        profiles = load_closure_profiles(
            ROOT / "configs/industry_impact_v2/event_01_closure_profiles.json"
        )
        evidence = {
            evidence_id: {
                "evidence_id": evidence_id,
                "fetch_status": "RETRIEVED_QUOTE_VERIFIED",
            }
            for profile in profiles
            for step in profile["mechanism_steps"]
            for evidence_id in step.get("evidence_ids", [])
        }
        chains = build_mechanism_chains(profiles, evidence)
        drivers, observations = build_driver_records(profiles, evidence)
        self.assertEqual(len(drivers), 8)
        self.assertEqual(
            {row["event_industry_mapping_id"] for row in drivers},
            {row["event_industry_mapping_id"] for row in profiles},
        )
        self.assertTrue(all(row["confounders"] for row in chains))
        self.assertTrue(all(row["challenge_set_only"] for row in chains))
        self.assertTrue(all(row["source_status"] == "AVAILABLE" for row in drivers))
        self.assertGreaterEqual(len(observations), 8)


    def test_builder_emits_joinable_overlay_without_promoting_release(self) -> None:
        from fingoose_company_impact_io_v2 import read_jsonl
        from fingoose_event_01_industry_closure_v2 import (
            build_event_01_closure_bundle,
        )

        output = ROOT / "work/_test_event01_closure_bundle"
        report = build_event_01_closure_bundle(
            ROOT,
            output_root=output,
            evidence_fetches=[],
            market_payloads={},
        )
        expected = {
            "event_industry_mappings.jsonl",
            "industry_mechanism_chains.jsonl",
            "industry_evidence.jsonl",
            "industry_driver_registry.jsonl",
            "industry_driver_observations.jsonl",
            "industry_market_windows.jsonl",
            "industry_completion_report.jsonl",
            "industry_source_fetches.jsonl",
        }
        self.assertTrue(expected.issubset({path.name for path in output.iterdir()}))
        mappings = read_jsonl(output / "event_industry_mappings.jsonl")
        chains = read_jsonl(output / "industry_mechanism_chains.jsonl")
        completion = read_jsonl(output / "industry_completion_report.jsonl")
        self.assertEqual(len(mappings), 8)
        self.assertEqual(sum(len(row["nodes"]) for row in chains), 56)
        self.assertTrue(all(row["completion_status"] == "OPEN" for row in completion))
        self.assertFalse(report["formal_ready"])
        self.assertEqual(report["sha_gate"], "DEFERRED")


if __name__ == "__main__":
    unittest.main()
