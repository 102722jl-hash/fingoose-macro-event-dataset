import assert from "node:assert/strict";
import test from "node:test";

import {selectTargetReports} from "../code/fetch_cninfo_company_reports_v2.mjs";

test("explicit verified announcement id admits an annual title that omits year", () => {
  const payload = {announcements: [{
    announcementId: "1212708494",
    announcementTitle: "锦江酒店年报",
    announcementTime: 1648483200000,
    adjunctUrl: "finalpage/2022-03-29/1212708494.PDF",
    secCode: "600754",
    secName: "锦江酒店",
  }]};
  const selected = selectTargetReports(payload, {
    code: "600754",
    annualYear: 2021,
    interimYear: 2022,
    cutoffDate: "2022-12-01",
    annualAnnouncementId: "1212708494",
  });
  assert.equal(selected.ANNUAL_REPORT.announcementId, "1212708494");
  assert.equal(selected.ANNUAL_REPORT.selectionBasis, "EXPLICIT_PDF_VERIFIED_ID");
});
