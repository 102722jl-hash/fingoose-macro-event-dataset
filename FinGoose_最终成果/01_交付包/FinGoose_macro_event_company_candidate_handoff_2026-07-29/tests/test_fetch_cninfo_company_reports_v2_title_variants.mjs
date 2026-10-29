import assert from "node:assert/strict";
import test from "node:test";

import {selectTargetReports} from "../code/fetch_cninfo_company_reports_v2.mjs";

test("selectTargetReports accepts annual report title without duplicated year character", () => {
  const payload = {announcements: [{
    announcementId: "annual",
    announcementTitle: "招商银行股份有限公司2020年度报告",
    announcementTime: 1616169600000,
    adjunctUrl: "finalpage/2021-03-20/annual.PDF",
    secCode: "600036",
    secName: "招商银行",
  }]};
  const selected = selectTargetReports(payload, {
    code: "600036",
    annualYear: 2020,
    interimYear: 2021,
    cutoffDate: "2022-03-16",
  });
  assert.equal(selected.ANNUAL_REPORT.announcementId, "annual");
});
