from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


def announcement(
    title: str,
    *,
    sec_code: str = "600009",
    announcement_id: str = "1205929979",
    adjunct_url: str = "finalpage/2019-03-23/1205929979.PDF",
    published_ms: int = 1553270400000,
) -> dict[str, object]:
    return {
        "announcementId": announcement_id,
        "announcementTitle": title,
        "announcementTime": published_ms,
        "adjunctUrl": adjunct_url,
        "secCode": sec_code,
        "secName": "上海机场",
        "orgId": "gssh0600009",
    }


class CompanyOfficialIntakeTests(unittest.TestCase):
    def test_parse_cninfo_payload_builds_official_pdf_url(self) -> None:
        from fingoose_company_official_intake_v2 import parse_cninfo_payload

        rows = parse_cninfo_payload(
            {"announcements": [announcement("2018年年度报告")]}
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["company_code"], "600009")
        self.assertEqual(rows[0]["published_at"], "2019-03-23")
        self.assertEqual(
            rows[0]["source_url"],
            "https://static.cninfo.com.cn/finalpage/2019-03-23/1205929979.PDF",
        )

    def test_select_reports_requires_exact_security_code(self) -> None:
        from fingoose_company_official_intake_v2 import select_target_reports

        rows = [
            announcement("2018年年度报告", sec_code="600009"),
            announcement(
                "2018年年度报告",
                sec_code="900009",
                announcement_id="wrong-code",
            ),
        ]

        selected = select_target_reports(
            parse_payload={"announcements": rows},
            company_code="600009",
            annual_year=2018,
            interim_year=2019,
            cutoff_at="2020-03-11T16:30:00Z",
        )

        self.assertEqual(selected["ANNUAL_REPORT"]["announcement_id"], "1205929979")

    def test_select_reports_excludes_summaries_and_uses_full_report(self) -> None:
        from fingoose_company_official_intake_v2 import select_target_reports

        rows = [
            announcement("2018年年度报告摘要", announcement_id="summary"),
            announcement("2018年年度报告", announcement_id="full"),
            announcement(
                "2019年半年度报告",
                announcement_id="interim",
                adjunct_url="finalpage/2019-08-28/interim.PDF",
                published_ms=1566950400000,
            ),
        ]

        selected = select_target_reports(
            parse_payload={"announcements": rows},
            company_code="600009",
            annual_year=2018,
            interim_year=2019,
            cutoff_at="2020-03-11T16:30:00Z",
        )

        self.assertEqual(selected["ANNUAL_REPORT"]["announcement_id"], "full")
        self.assertEqual(selected["INTERIM_REPORT"]["announcement_id"], "interim")

    def test_report_on_cutoff_date_is_not_prediction_visible(self) -> None:
        from fingoose_company_official_intake_v2 import select_target_reports

        rows = [
            announcement(
                "2018年年度报告",
                published_ms=1583884800000,
            )
        ]

        selected = select_target_reports(
            parse_payload={"announcements": rows},
            company_code="600009",
            annual_year=2018,
            interim_year=2019,
            cutoff_at="2020-03-11T16:30:00Z",
        )

        self.assertNotIn("ANNUAL_REPORT", selected)


if __name__ == "__main__":
    unittest.main()
