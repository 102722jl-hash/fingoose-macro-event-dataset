import assert from "node:assert/strict";
import test from "node:test";

import {selectTargetReports} from "../code/fetch_cninfo_company_reports_v2.mjs";

test("selector rejects English and H-share variants when selecting A-share dossiers", () => {
  const base = {announcementTime: 1711584000000, secCode: "000333", secName: "美的集团"};
  const midea = selectTargetReports({announcements: [
    {...base, announcementId: "english", announcementTitle: "2023年年度报告（英文版）", adjunctUrl: "english.PDF"},
    {...base, announcementId: "chinese", announcementTitle: "2023年年度报告", adjunctUrl: "chinese.PDF"},
  ]}, {code: "000333", annualYear: 2023, interimYear: 2024, cutoffDate: "2025-01-01"});
  assert.equal(midea.ANNUAL_REPORT.announcementId, "chinese");

  const bankBase = {announcementTime: 1680192000000, secCode: "601988", secName: "中国银行"};
  const bank = selectTargetReports({announcements: [
    {...bankBase, announcementId: "h-share", announcementTitle: "H股公告-2022年年度报告", adjunctUrl: "h.PDF"},
    {...bankBase, announcementId: "a-share", announcementTitle: "中国银行股份有限公司2022年年度报告", adjunctUrl: "a.PDF"},
  ]}, {code: "601988", annualYear: 2022, interimYear: 2023, cutoffDate: "2024-01-01"});
  assert.equal(bank.ANNUAL_REPORT.announcementId, "a-share");
});
