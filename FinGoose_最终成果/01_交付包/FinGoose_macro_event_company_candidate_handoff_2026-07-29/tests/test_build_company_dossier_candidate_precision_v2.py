from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class DossierCandidatePrecisionTests(unittest.TestCase):
    def test_geography_terms_require_revenue_or_region_context(self) -> None:
        from build_company_dossier_candidates_v2 import terms_for_claim

        terms = terms_for_claim("002030.SZ", "GEOGRAPHIC_EXPOSURE")

        self.assertIn("分地区", terms)
        self.assertNotIn("境内", terms)
        self.assertNotIn("国外", terms)

    def test_neutral_product_terms_do_not_count_as_demand_drivers(self) -> None:
        from build_company_dossier_candidates_v2 import terms_for_claim

        terms = terms_for_claim("002030.SZ", "DEMAND_COST_EXPOSURE")

        self.assertIn("市场需求", terms)
        self.assertNotIn("体外诊断", terms)


if __name__ == "__main__":
    unittest.main()
