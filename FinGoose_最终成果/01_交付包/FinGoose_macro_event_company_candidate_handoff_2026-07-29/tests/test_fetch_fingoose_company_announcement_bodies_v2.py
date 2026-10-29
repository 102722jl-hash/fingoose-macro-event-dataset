from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class FetchCompanyAnnouncementBodiesTests(unittest.TestCase):
    def test_build_jobs_covers_all_registered_title_candidates(self) -> None:
        from fetch_fingoose_company_announcement_bodies_v2 import (
            load_candidate_jobs,
        )

        jobs = load_candidate_jobs(ROOT)

        self.assertEqual(len(jobs), 47)
        self.assertEqual(len({job["announcement_id"] for job in jobs}), 47)
        self.assertTrue(
            all(
                job["source_url"].startswith(
                    "https://static.cninfo.com.cn/"
                )
                for job in jobs
            )
        )

    def test_failed_download_is_a_persisted_unresolved_record(self) -> None:
        from fetch_fingoose_company_announcement_bodies_v2 import (
            retrieval_failure,
        )

        job = {
            "announcement_id": "123",
            "mapping_id": "event-company-1",
            "event_id": "event-01",
            "company_id": "company-1",
            "company_code": "000001.SZ",
            "announcement_title": "公告",
            "source_url": "https://static.cninfo.com.cn/example.pdf",
            "first_public_at": "2020-03-12",
        }

        record = retrieval_failure(job, "HTTP_404")

        self.assertEqual(record["retrieval_status"], "FAILED")
        self.assertFalse(record["body_review_eligible"])
        self.assertEqual(record["failure_reason"], "HTTP_404")

    def test_non_official_download_host_is_rejected(self) -> None:
        from fetch_fingoose_company_announcement_bodies_v2 import (
            normalize_official_url,
        )

        with self.assertRaisesRegex(ValueError, "OFFICIAL_HOST_REQUIRED"):
            normalize_official_url("https://example.com/document.pdf")


if __name__ == "__main__":
    unittest.main()
