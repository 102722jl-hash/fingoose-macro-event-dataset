from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class BuildCompanyDossierCandidatesTests(unittest.TestCase):
    def test_industry_terms_only_extend_demand_cost_claims(self) -> None:
        from build_company_dossier_candidates_v2 import terms_for_claim

        demand_terms = terms_for_claim("601111.SH", "DEMAND_COST_EXPOSURE")
        limitation_terms = terms_for_claim(
            "601111.SH",
            "LIMITATION_OR_COUNTEREVIDENCE",
        )

        self.assertIn("航油成本", demand_terms)
        self.assertNotIn("航空运输", limitation_terms)
        self.assertIn("套期保值", limitation_terms)


if __name__ == "__main__":
    unittest.main()
