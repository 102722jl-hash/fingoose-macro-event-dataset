import assert from "node:assert/strict";
import test from "node:test";

import {buildQueryFields, selectTargetReports} from "file:///D:/%E6%A1%8C%E9%9D%A2/workspace/codex1/handoff/FinGoose_macro_event_company_candidate_handoff_2026-07-29/code/fetch_cninfo_company_reports_v2.mjs";

test("buildQueryFields supports precise code and orgId lookup", () => {
  const fields = buildQueryFields("", "2020-01-01", "2022-02-24", "sse", "601233,9900019547");
  assert.equal(fields.searchkey, "");
  assert.equal(fields.stock, "601233,9900019547");
});

test("selectTargetReports accepts issuer-prefixed full reports", () => {
  const payload = {announcements: [
    {announcementId: "annual", announcementTitle: "桐昆股份2020年年度报告", announcementTime: 1617033600000, adjunctUrl: "finalpage/2021-03-30/annual.PDF", secCode: "601233", secName: "桐昆股份"},
    {announcementId: "interim", announcementTitle: "桐昆股份2021年半年度报告", announcementTime: 1630368000000, adjunctUrl: "finalpage/2021-08-31/interim.PDF", secCode: "601233", secName: "桐昆股份"},
  ]};
  const selected = selectTargetReports(payload, {code: "601233", annualYear: 2020, interimYear: 2021, cutoffDate: "2022-02-24"});
  assert.equal(selected.ANNUAL_REPORT.announcementId, "annual");
  assert.equal(selected.INTERIM_REPORT.announcementId, "interim");
});
