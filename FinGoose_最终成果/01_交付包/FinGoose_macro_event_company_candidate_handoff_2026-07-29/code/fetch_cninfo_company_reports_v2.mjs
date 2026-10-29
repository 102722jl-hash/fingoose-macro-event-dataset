import {createHash} from "node:crypto";
import {mkdir, readFile, writeFile} from "node:fs/promises";
import path from "node:path";
import {fileURLToPath, pathToFileURL} from "node:url";


const QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query";
const STATIC_BASE = "https://static.cninfo.com.cn/";


export function buildQueryFields(companyName, startDate, endDate, column = "sse", stock = "") {
  return {
    pageNum: "1",
    pageSize: "100",
    column,
    tabName: "fulltext",
    plate: "",
    stock,
    searchkey: companyName,
    secid: "",
    category: "category_ndbg_szsh;category_bndbg_szsh",
    trade: "",
    seDate: `${startDate}~${endDate}`,
    sortName: "",
    sortType: "",
    isHLtitle: "true",
  };
}


function normalizeTitle(value) {
  return String(value || "")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, "")
    .replace(/\s+/g, "");
}


function chinaDate(milliseconds) {
  return new Date(Number(milliseconds) + 8 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);
}


export function selectTargetReports(payload, target) {
  const matchers = {
    ANNUAL_REPORT: new RegExp(`${target.annualYear}(?:年年度报告|年度报告|年报)(?:（[^）]+）)?$`),
    INTERIM_REPORT: new RegExp(`${target.interimYear}年(?:半年度报告|半年报|中期报告)(?:全文)?(?:（[^）]+）)?$`),
  };
  const selected = {};
  for (const raw of payload.announcements || []) {
    if (String(raw.secCode || "") !== target.code) continue;
    const title = normalizeTitle(raw.announcementTitle);
    if (title.includes("摘要")) continue;
    if (/英文版|H股公告|港股公告/.test(title)) continue;
    const explicitAnnual = target.annualAnnouncementId
      && String(raw.announcementId) === String(target.annualAnnouncementId);
    const sourceClass = explicitAnnual
      ? "ANNUAL_REPORT"
      : Object.entries(matchers).find(([, matcher]) => matcher.test(title))?.[0];
    if (!sourceClass) continue;
    const publishedAt = chinaDate(raw.announcementTime);
    if (publishedAt >= target.cutoffDate) continue;
    selected[sourceClass] ??= {
      ...raw,
      documentTitle: title,
      publishedAt,
      sourceClass,
      selectionBasis: explicitAnnual ? "EXPLICIT_PDF_VERIFIED_ID" : "TITLE_AND_PERIOD",
      sourceUrl: String(raw.adjunctUrl || "").startsWith("http")
        ? raw.adjunctUrl
        : STATIC_BASE + String(raw.adjunctUrl || "").replace(/^\//, ""),
    };
  }
  return selected;
}


function readJsonl(text) {
  return text.split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
}


async function fetchWithRetry(url, options, attempts = 3) {
  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const response = await fetch(url, options);
      if (!response.ok) throw new Error(`HTTP_${response.status}`);
      return response;
    } catch (error) {
      lastError = error;
      if (attempt < attempts) {
        await new Promise((resolve) => setTimeout(resolve, attempt * 500));
      }
    }
  }
  throw lastError;
}


export async function collectOfficialReports(root) {
  const configDir = path.join(root, "configs", "company_impact_high_quality_v2");
  const outputDir = path.join(root, "work", "company_impact_high_quality_v2_candidate");
  const rawDir = path.join(outputDir, "source_intake");
  const sourceDir = path.join(outputDir, "sources");
  await mkdir(rawDir, {recursive: true});
  await mkdir(sourceDir, {recursive: true});

  const [companiesText, mappingsText, targetsText] = await Promise.all([
    readFile(path.join(configDir, "company_registry.jsonl"), "utf8"),
    readFile(path.join(configDir, "event_company_map.jsonl"), "utf8"),
    readFile(path.join(configDir, "official_report_targets.jsonl"), "utf8"),
  ]);
  const companies = readJsonl(companiesText);
  const mappings = readJsonl(mappingsText);
  const targets = readJsonl(targetsText);
  const companyByCode = new Map(companies.map((row) => [row.company_code, row]));
  const cutoffByCompany = new Map();
  for (const row of mappings) {
    const current = cutoffByCompany.get(row.company_code);
    if (!current || row.selection_cutoff_at < current) {
      cutoffByCompany.set(row.company_code, row.selection_cutoff_at);
    }
  }

  const manifest = [];
  const gaps = [];
  for (const spec of targets) {
    const company = companyByCode.get(spec.company_code);
    const cutoffAt = cutoffByCompany.get(spec.company_code);
    if (!company || !cutoffAt) {
      gaps.push({...spec, gap_reason: "MISSING_COMPANY_OR_CUTOFF"});
      continue;
    }
    const cutoffDate = cutoffAt.slice(0, 10);
    const code = spec.company_code.slice(0, 6);
    const column = spec.company_code.endsWith(".SZ") ? "szse" : "sse";
    const startDate = `${spec.annual_year}-01-01`;
    const fields = buildQueryFields(
      company.company_name,
      startDate,
      cutoffDate,
      column,
    );
    let payload;
    try {
      const response = await fetchWithRetry(QUERY_URL, {
        method: "POST",
        headers: {
          "content-type": "application/x-www-form-urlencoded",
          referer: "https://www.cninfo.com.cn/",
          "user-agent": "Mozilla/5.0",
        },
        body: new URLSearchParams(fields),
      });
      payload = await response.json();
      const orgId = (payload.announcements || [])
        .find((row) => String(row.secCode || "") === code)?.orgId;
      if (orgId) {
        const preciseResponse = await fetchWithRetry(QUERY_URL, {
          method: "POST",
          headers: {
            "content-type": "application/x-www-form-urlencoded",
            referer: "https://www.cninfo.com.cn/",
            "user-agent": "Mozilla/5.0",
          },
          body: new URLSearchParams(buildQueryFields(
            "",
            startDate,
            cutoffDate,
            column,
            `${code},${orgId}`,
          )),
        });
        const precisePayload = await preciseResponse.json();
        const merged = [...(precisePayload.announcements || []), ...(payload.announcements || [])];
        payload.announcements = [...new Map(merged.map((row) => [String(row.announcementId), row])).values()];
        payload.totalAnnouncement = payload.announcements.length;
      }
      await writeFile(
        path.join(rawDir, `${spec.company_code}.json`),
        JSON.stringify(payload, null, 2),
        "utf8",
      );
    } catch (error) {
      gaps.push({...spec, gap_reason: `QUERY_FAILED:${error.message}`});
      continue;
    }

    const selected = selectTargetReports(payload, {
      code,
      annualYear: spec.annual_year,
      interimYear: spec.interim_year,
      cutoffDate,
      annualAnnouncementId: spec.annual_announcement_id,
    });
    for (const sourceClass of ["ANNUAL_REPORT", "INTERIM_REPORT"]) {
      const report = selected[sourceClass];
      if (!report) {
        gaps.push({
          company_code: spec.company_code,
          source_class: sourceClass,
          target_year: sourceClass === "ANNUAL_REPORT" ? spec.annual_year : spec.interim_year,
          gap_reason: "TARGET_REPORT_NOT_FOUND_BEFORE_CUTOFF",
        });
        continue;
      }
      const reportingPeriod = sourceClass === "ANNUAL_REPORT"
        ? String(spec.annual_year)
        : `${spec.interim_year}-H1`;
      const fileName = `${spec.company_code}__${reportingPeriod}__${sourceClass.toLowerCase()}.pdf`;
      const snapshotPath = path.join(sourceDir, fileName);
      let downloadStatus = "DOWNLOADED";
      let byteLength = null;
      try {
        const response = await fetchWithRetry(report.sourceUrl, {
          headers: {referer: "https://www.cninfo.com.cn/", "user-agent": "Mozilla/5.0"},
        });
        const bytes = Buffer.from(await response.arrayBuffer());
        await writeFile(snapshotPath, bytes);
        byteLength = bytes.length;
      } catch (error) {
        downloadStatus = `DOWNLOAD_FAILED:${error.message}`;
      }
      const sourceId = `company-source-${createHash("sha256")
        .update(`${company.company_id}|${report.announcementId}`)
        .digest("hex")
        .slice(0, 16)}`;
      manifest.push({
        source_id: sourceId,
        document_id: String(report.announcementId),
        company_id: company.company_id,
        company_code: spec.company_code,
        source_class: sourceClass,
        selection_basis: report.selectionBasis,
        source_url: report.sourceUrl,
        document_title: report.documentTitle,
        issuer: company.company_name,
        published_at: report.publishedAt,
        published_at_precision: "DATE",
        reporting_period: reportingPeriod,
        snapshot_path: downloadStatus === "DOWNLOADED" ? `sources/${fileName}` : null,
        byte_length: byteLength,
        download_status: downloadStatus,
        selection_cutoff_at: cutoffAt,
        availability_scope: "PREDICTION_VISIBLE",
        sha_gate: "DEFERRED",
        formal_ready: false,
      });
    }
  }

  manifest.sort((a, b) => a.company_code.localeCompare(b.company_code) || a.source_class.localeCompare(b.source_class));
  await writeFile(
    path.join(outputDir, "source_manifest_seed.jsonl"),
    manifest.map((row) => JSON.stringify(row)).join("\n") + (manifest.length ? "\n" : ""),
    "utf8",
  );
  await writeFile(
    path.join(outputDir, "official_report_gap_report.json"),
    JSON.stringify({gaps}, null, 2),
    "utf8",
  );
  const summary = {
    company_count: targets.length,
    requested_report_count: targets.length * 2,
    selected_report_count: manifest.length,
    downloaded_report_count: manifest.filter((row) => row.download_status === "DOWNLOADED").length,
    gap_count: gaps.length,
    sha_gate: "DEFERRED",
    formal_ready: false,
  };
  await writeFile(
    path.join(outputDir, "official_report_intake_summary.json"),
    JSON.stringify(summary, null, 2),
    "utf8",
  );
  return summary;
}


const invokedPath = process.argv[1] ? pathToFileURL(path.resolve(process.argv[1])).href : null;
if (invokedPath === import.meta.url) {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
  collectOfficialReports(root)
    .then((summary) => console.log(JSON.stringify(summary, null, 2)))
    .catch((error) => {
      console.error(error);
      process.exitCode = 1;
    });
}
