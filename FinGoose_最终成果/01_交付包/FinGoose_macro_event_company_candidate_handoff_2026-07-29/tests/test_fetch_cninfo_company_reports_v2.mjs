import assert from "node:assert/strict";
import test from "node:test";

import {
  buildQueryFields,
  selectTargetReports,
} from "../code/fetch_cninfo_company_reports_v2.mjs";


test("buildQueryFields uses periodic report categories", () => {
  const fields = buildQueryFields("上海机场", "2018-01-01", "2020-03-11");
  assert.equal(fields.searchkey, "上海机场");
  assert.equal(fields.pageSize, "100");
  assert.equal(fields.category, "category_ndbg_szsh;category_bndbg_szsh");
});


test("selectTargetReports rejects summaries and code mismatches", () => {
  const base = {
    announcementTime: 1553270400000,
    adjunctUrl: "finalpage/2019-03-23/report.PDF",
    secName: "上海机场",
  };
  const payload = {
    announcements: [
      {...base, announcementId: "summary", announcementTitle: "2018年年度报告摘要", secCode: "600009"},
      {...base, announcementId: "wrong", announcementTitle: "2018年年度报告", secCode: "900009"},
      {...base, announcementId: "full", announcementTitle: "2018年年度报告", secCode: "600009"},
    ],
  };

  const selected = selectTargetReports(payload, {
    code: "600009",
    annualYear: 2018,
    interimYear: 2019,
    cutoffDate: "2020-03-11",
  });

  assert.equal(selected.ANNUAL_REPORT.announcementId, "full");
});
