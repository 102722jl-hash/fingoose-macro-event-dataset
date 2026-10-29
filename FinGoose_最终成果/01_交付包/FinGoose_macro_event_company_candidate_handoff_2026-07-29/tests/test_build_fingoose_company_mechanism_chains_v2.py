from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class BuildCompanyMechanismChainsTests(unittest.TestCase):
    def test_builds_one_evidence_scoped_chain_per_frozen_mapping(self) -> None:
        from build_fingoose_company_mechanism_chains_v2 import build

        output = ROOT / "work/company_impact_high_quality_v2_candidate"
        report = build(ROOT, output=output)
        chains = _read_jsonl(output / "event_company_mechanism_chains.jsonl")
        mappings = _read_jsonl(
            ROOT / "configs/company_impact_high_quality_v2/event_company_map.jsonl"
        )

        self.assertEqual(
            report,
            {
                "mapping_count": 30,
                "chain_count": 30,
                "node_count": 210,
                "edge_count": 180,
                "formal_ready": False,
                "sha_gate": "DEFERRED",
            },
        )
        self.assertEqual(len(chains), 30)
        self.assertEqual(
            {chain["mapping_id"] for chain in chains},
            {mapping["mapping_id"] for mapping in mappings},
        )
        self.assertEqual(len({chain["mapping_id"] for chain in chains}), 30)
        self.assertTrue(all(len(chain["nodes"]) == 7 for chain in chains))
        self.assertTrue(all(len(chain["edges"]) == 6 for chain in chains))
        self.assertTrue(
            all(chain["chain_status"] == "PROPOSED_COMPANY_MECHANISM" for chain in chains)
        )
        self.assertTrue(all(chain["review_status"] == "NEEDS_HUMAN_REVIEW" for chain in chains))
        self.assertTrue(all(chain["formal_ready"] is False for chain in chains))
        self.assertTrue(all(chain["sha_gate"] == "DEFERRED" for chain in chains))
        self.assertTrue(all(chain["price_selection_used"] is False for chain in chains))

        for chain in chains:
            self.assertEqual(
                set(chain["horizon_directions"]),
                {"IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM"},
            )
            self.assertTrue(chain["conditions"])
            self.assertTrue(chain["invalidation_conditions"])
            self.assertTrue(chain["operating_metrics"])
            self.assertTrue(
                all(metric["name"] and metric["unit"] for metric in chain["operating_metrics"])
            )
            nodes = {node["node_type"]: node for node in chain["nodes"]}
            self.assertTrue(
                set(nodes["EVENT_FACT"]["evidence_ids"]).isdisjoint(
                    nodes["COMPANY_BUSINESS_EXPOSURE"]["evidence_ids"]
                )
            )
            self.assertEqual(
                len(nodes["PRICE_AND_CONFOUNDER_VERIFICATION"]["evidence_ids"]),
                3,
            )
            text = " ".join(node["statement"] for node in chain["nodes"])
            for forbidden in ("DCOILWTICO", "DCOILBRENTEU", "SP500", "DEXCHUS", "VIXCLS"):
                self.assertNotIn(forbidden, text)

        event_05 = [chain for chain in chains if chain["event_id"] == "event-05"]
        self.assertEqual(len(event_05), 3)
        for chain in event_05:
            direction = next(
                node for node in chain["nodes"] if node["node_type"] == "DIRECTION_ASSESSMENT"
            )
            self.assertEqual(direction["direction"], "UNKNOWN")
            self.assertEqual(direction["decision_status"], "ABSTAIN")

    def test_profiles_are_mapping_specific_and_name_operating_variables(self) -> None:
        profiles = _read_jsonl(
            ROOT / "configs/company_impact_high_quality_v2/company_mechanism_profiles.jsonl"
        )

        self.assertEqual(len(profiles), 30)
        self.assertEqual(len({profile["mapping_id"] for profile in profiles}), 30)
        for profile in profiles:
            self.assertEqual(
                set(profile["horizon_directions"]),
                {"IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM"},
            )
            self.assertTrue(profile["conditions"])
            self.assertTrue(profile["invalidation_conditions"])
            self.assertTrue(profile["operating_metrics"])
            self.assertTrue(profile["company_evidence_ids"])
            self.assertTrue(
                all(metric["name"] and metric["unit"] for metric in profile["operating_metrics"])
            )
        variables = {
            (profile["event_id"], profile["company_code"]): profile["observable_operating_variable"]
            for profile in profiles
        }
        expected_terms = {
            ("event-01", "002030.SZ"): ("核酸检测需求", "试剂准入"),
            ("event-01", "600009.SH"): ("旅客吞吐量", "航空性收入"),
            ("event-01", "601111.SH"): ("客流", "客座率", "客运收入"),
            ("event-02", "600346.SH"): ("原油采购成本", "炼化价差"),
            ("event-02", "601233.SH"): ("PTA-MEG成本", "长丝价差"),
            ("event-02", "601857.SH"): ("油气售价", "产量"),
            ("event-03", "600036.SH"): ("净息差", "贷款需求"),
            ("event-03", "601012.SH"): ("融资成本", "光伏订单"),
            ("event-03", "601318.SH"): ("投资收益", "负债成本"),
            ("event-04", "600009.SH"): ("旅客吞吐量",),
            ("event-04", "600754.SH"): ("入住率", "RevPAR"),
            ("event-04", "601111.SH"): ("客流", "客座率"),
            ("event-05", "002432.SZ"): ("融资可得性",),
            ("event-05", "300482.SZ"): ("现金管理",),
            ("event-05", "688235.SH"): ("回款风险",),
            ("event-06", "000301.SZ"): ("PTA", "长丝价差"),
            ("event-06", "600028.SH"): ("原油成本", "炼化价差"),
            ("event-06", "601857.SH"): ("油气售价", "产量"),
            ("event-07", "601021.SH"): ("航油成本",),
            ("event-07", "601857.SH"): ("能源风险溢价", "油气售价"),
            ("event-07", "601919.SH"): ("绕航天数", "集运运价"),
            ("event-08", "601021.SH"): ("日本航线", "日元成本"),
            ("event-08", "601211.SH"): ("跨境头寸", "交易收入"),
            ("event-08", "601988.SH"): ("外币净息差",),
            ("event-09", "300059.SZ"): ("成交额", "经纪收入"),
            ("event-09", "600036.SH"): ("信贷投放", "净息差"),
            ("event-09", "600048.SH"): ("销售回款",),
            ("event-10", "000333.SZ"): ("出口订单", "关税成本"),
            ("event-10", "002475.SZ"): ("出口订单", "产能转移"),
            ("event-10", "601012.SH"): ("出口订单", "关税成本"),
        }
        self.assertEqual(set(variables), set(expected_terms))
        for key, terms in expected_terms.items():
            with self.subTest(key=key):
                for term in terms:
                    self.assertIn(term, variables[key])


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


if __name__ == "__main__":
    unittest.main()
