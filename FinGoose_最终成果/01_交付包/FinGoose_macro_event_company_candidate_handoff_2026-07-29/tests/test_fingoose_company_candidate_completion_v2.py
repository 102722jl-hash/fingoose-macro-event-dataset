from __future__ import annotations

from contextlib import nullcontext
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class CompanyCandidateCompletionTests(unittest.TestCase):
    def test_binding_review_requires_complete_candidate_disposition(self) -> None:
        from fingoose_company_candidate_completion_v2 import build_binding_review

        mapping = {
            "mapping_id": "mapping-1",
            "event_id": "event-04",
            "anchor_id": "anchor-fast-event-04-M03",
            "candidate_binding_ids": ["binding-a", "binding-b", "binding-c"],
        }

        review = build_binding_review(
            mapping,
            primary_binding_id="binding-a",
            secondary_binding_ids=["binding-b"],
            rejected_bindings={"binding-c": "公司业务证据不支持该渠道"},
            selection_basis="事件前官方业务披露支持需求恢复渠道。",
            evidence_ids=["evidence-1"],
            counterevidence_ids=["evidence-2"],
        )

        self.assertEqual(review["primary_binding_id"], "binding-a")
        self.assertEqual(review["secondary_binding_ids"], ["binding-b"])
        self.assertEqual(
            review["rejected_bindings"],
            [{"binding_id": "binding-c", "reason": "公司业务证据不支持该渠道"}],
        )
        self.assertEqual(review["review_status"], "NEEDS_HUMAN_REVIEW")
        self.assertFalse(review["price_selection_used"])

    def test_unknown_direction_becomes_explicit_abstention(self) -> None:
        from fingoose_company_candidate_completion_v2 import build_horizon_reviews

        reviews = build_horizon_reviews(
            {"IMMEDIATE": "UNKNOWN", "SHORT_TERM": "MIXED", "MEDIUM_TERM": "UNKNOWN"},
            abstentions={
                "IMMEDIATE": {
                    "reason": "缺少事件日附近的公司特异性证据",
                    "missing_evidence": ["COMPANY_SPECIFIC_TRIGGER"],
                },
                "MEDIUM_TERM": {
                    "reason": "中期竞争机制无法排序",
                    "missing_evidence": ["COMPETING_MECHANISM_RANKING"],
                },
            },
        )

        self.assertEqual(reviews["IMMEDIATE"]["decision_status"], "ABSTAIN")
        self.assertEqual(
            reviews["SHORT_TERM"]["decision_status"], "DIRECTIONAL_CANDIDATE"
        )
        self.assertTrue(reviews["MEDIUM_TERM"]["missing_evidence"])

    def test_completion_gate_reports_every_open_blocker(self) -> None:
        from fingoose_company_candidate_completion_v2 import evaluate_completion

        result = evaluate_completion(
            mapping_id="mapping-1",
            binding_review={"primary_binding_id": "binding-a", "review_status": "NEEDS_HUMAN_REVIEW"},
            dossier={"research_categories": []},
            direction={"horizon_reviews": {}},
            market_window={"observations": {}},
            relative_window={"observations": {}},
            confounder={"company_confounder_status": "SEARCH_PENDING", "suspension_status": "UNVERIFIED"},
        )

        self.assertEqual(result["completion_status"], "OPEN")
        self.assertIn("DOSSIER_RESEARCH_INCOMPLETE", result["blockers"])
        self.assertIn("DIRECTION_HORIZONS_INCOMPLETE", result["blockers"])
        self.assertIn("INDUSTRY_WINDOW_INCOMPLETE", result["blockers"])
        self.assertIn("CONFOUNDER_REVIEW_INCOMPLETE", result["blockers"])
        self.assertIn("SUSPENSION_REVIEW_INCOMPLETE", result["blockers"])

    def test_horizon_review_carries_conditions_and_evidence(self) -> None:
        from fingoose_company_candidate_completion_v2 import build_horizon_reviews

        reviews = build_horizon_reviews(
            {"IMMEDIATE": "POSITIVE", "SHORT_TERM": "MIXED", "MEDIUM_TERM": "UNKNOWN"},
            abstentions={
                "MEDIUM_TERM": {
                    "reason": "??????????",
                    "missing_evidence": ["COMPETING_MECHANISM_RANKING"],
                }
            },
            conditions=["?????????????"],
            invalidation_conditions=["???????????"],
            evidence_ids=["evidence-1"],
            counterevidence_ids=["evidence-2"],
        )

        self.assertEqual(reviews["IMMEDIATE"]["conditions"], ["?????????????"])
        self.assertEqual(reviews["SHORT_TERM"]["evidence_ids"], ["evidence-1"])
        self.assertEqual(reviews["MEDIUM_TERM"]["counterevidence_ids"], ["evidence-2"])

    def test_candidate_builder_writes_full_coverage_and_keeps_open_gates_honest(self) -> None:
        from build_fingoose_company_candidate_completion_v2 import build

        with nullcontext(ROOT / ".test-tmp") as temp_dir:
            output = Path(temp_dir)
            report = build(ROOT, output)

            self.assertEqual(report["mapping_count"], 30)
            self.assertEqual(report["binding_review_count"], 30)
            self.assertEqual(report["direction_horizon_review_count"], 30)
            self.assertEqual(report["completion_report_count"], 30)
            self.assertEqual(report["mechanism_chain_count"], 30)
            self.assertEqual(report["mechanism_chain_node_count"], 210)
            self.assertEqual(report["mechanism_chain_edge_count"], 180)
            self.assertTrue((output / "event_company_mechanism_chains.jsonl").exists())
            self.assertFalse(report["formal_ready"])
            self.assertEqual(report["sha_gate"], "DEFERRED")

            binding_reviews = _read_jsonl(output / "event_company_binding_reviews.jsonl")
            event_04 = [row for row in binding_reviews if row["event_id"] == "event-04"]
            self.assertEqual(len(event_04), 3)
            self.assertTrue(
                all(row["primary_binding_id"] == "binding-event-04-168114977cc5" for row in event_04)
            )
            self.assertTrue(all(len(row["rejected_bindings"]) == 4 for row in event_04))

            dossiers = _read_jsonl(output / "company_master_dossiers.jsonl")
            self.assertTrue(all(len(row["research_categories"]) == 5 for row in dossiers))
            search_audits = _read_jsonl(output / "company_dossier_search_audits.jsonl")
            self.assertTrue(search_audits)
            self.assertTrue(
                all(row["result"] == "NOT_DISCLOSED_AFTER_SEARCH" for row in search_audits)
            )

            directions = _read_jsonl(output / "direction_assessments.jsonl")
            for row in directions:
                self.assertEqual(set(row["horizon_reviews"]), {"IMMEDIATE", "SHORT_TERM", "MEDIUM_TERM"})
                for horizon in row["horizon_reviews"].values():
                    if horizon["direction"] == "UNKNOWN":
                        self.assertEqual(horizon["decision_status"], "ABSTAIN")
                        self.assertTrue(horizon["abstention_reason"])

            completion = _read_jsonl(output / "candidate_completion_report.jsonl")
            self.assertEqual(
                {row["mapping_id"] for row in completion},
                {row["mapping_id"] for row in binding_reviews},
            )
            self.assertTrue(all(row["completion_status"] == "OPEN" for row in completion))
            self.assertTrue(
                all("INDUSTRY_WINDOW_INCOMPLETE" in row["blockers"] for row in completion)
            )
            chains = _read_jsonl(output / "event_company_mechanism_chains.jsonl")
            self.assertEqual(
                {row["mapping_id"] for row in chains},
                {row["mapping_id"] for row in completion},
            )
            self.assertTrue(
                all("MECHANISM_CHAIN_INCOMPLETE" not in row["blockers"] for row in completion)
            )


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    import json

    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


if __name__ == "__main__":
    unittest.main()
