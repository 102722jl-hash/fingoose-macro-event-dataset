# FinGoose event-01 Industry Evidence and Market Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `event-01` 的八条行业映射建设为具有七步机制、逐节点证据、驱动观测、申万/沪深300窗口、混杂反证和同页 UI 联动的高质量候选样板。

**Architecture:** 保留现有 77 条行业候选为只读基线，在 `work/event_01_industry_closure_v2_candidate/` 生成只含八条 `event-01` 记录的覆盖层。证据抓取、机制投影、行情计算和 UI 合并由相互独立的小模块完成；覆盖层通过稳定 `event_industry_mapping_id` 合并，其他 69 条记录不改变。

**Tech Stack:** Python 3.12、标准库 `urllib/html.parser/zoneinfo`、现有 JSONL I/O、可选 AKShare 1.18.x、静态 HTML/CSS/JavaScript、pytest/unittest、Playwright。

---

## 实施前约束

- 设计依据：`docs/superpowers/specs/2026-08-04-event-01-industry-evidence-market-closure-design.md`。
- 当前工作区 `.git` 目录无 `HEAD`，不是有效 Git 仓库。每个任务保留提交检查点和建议提交消息，但只有在执行时检测到 `.git/HEAD` 后才运行 `git add/commit`；否则将 `NO_VALID_GIT_METADATA` 写入实施日志，不能伪造提交成功。
- 不修改 `work/industry_impact_high_quality_v2_candidate/` 的基线 JSONL。
- 网络、证据或行情失败只产生 `EVIDENCE_PENDING`、`DATA_PENDING` 或 `OPEN`。
- 全部记录保持 `PROPOSED / NEEDS_HUMAN_REVIEW / formal_ready=false / sha_gate=DEFERRED`。
- SHA 不参与本轮完成门禁；覆盖层 manifest 只保存路径、字节数、计数和生成时间。

## 文件结构

**Create**

- `configs/industry_impact_v2/event_01_closure_profiles.json`：八行业七步机制、方向、条件、反证和驱动配置。
- `configs/industry_impact_v2/event_01_source_registry.jsonl`：官方来源、引文、定位符、用途和节点关系。
- `configs/industry_impact_v2/event_01_market_registry.json`：八个申万指数、沪深300和提供方优先级。
- `requirements-event01-industry.txt`：可选行情适配器依赖。
- `code/fingoose_industry_source_snapshot_v2.py`：来源抓取、正文标准化、引文存在性校验和快照清单。
- `code/fingoose_industry_market_v2.py`：行情提供方、共同交易日、窗口、归一化和相对收益。
- `code/fingoose_event_01_industry_closure_v2.py`：覆盖层组装、完成门禁和验证报告。
- `code/build_fingoose_event_01_industry_closure_v2.py`：命令行入口。
- `tests/test_fingoose_industry_source_snapshot_v2.py`：抓取与证据门禁测试。
- `tests/test_fingoose_industry_market_v2.py`：T0、窗口和公式测试。
- `tests/test_fingoose_event_01_industry_closure_v2.py`：八行业覆盖、56 节点和完成门禁测试。
- `tests/verify_event_01_industry_ui.mjs`：桌面与移动端浏览器验收。
- `work/event_01_industry_closure_v2_candidate/`：生成的覆盖数据、原始来源和报告。

**Modify**

- `code/fingoose_company_impact_market_v2.py`：按 `Asia/Shanghai` 转换事件时间后对齐 T0。
- `code/fingoose_company_impact_ui_v2.py`：加载覆盖层、展示逐节点证据、三序列图表和结构化混杂。
- `tests/test_fingoose_company_impact_market_v2.py`：跨时区和盘后测试。
- `tests/test_fingoose_industry_ui_v2.py`：覆盖层、八行业常驻和 UI 内容测试。

## Task 1: 锁定覆盖层和配置契约

**Files:**

- Create: `configs/industry_impact_v2/event_01_closure_profiles.json`
- Create: `configs/industry_impact_v2/event_01_market_registry.json`
- Create: `tests/test_fingoose_event_01_industry_closure_v2.py`
- Create: `code/fingoose_event_01_industry_closure_v2.py`

- [ ] **Step 1: 写覆盖层配置失败测试**

在 `tests/test_fingoose_event_01_industry_closure_v2.py` 写入：

```python
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class Event01IndustryClosureTests(unittest.TestCase):
    def test_profiles_cover_exactly_eight_event_01_mappings(self) -> None:
        from fingoose_event_01_industry_closure_v2 import load_closure_profiles

        profiles = load_closure_profiles(
            ROOT / "configs/industry_impact_v2/event_01_closure_profiles.json"
        )
        self.assertEqual(len(profiles), 8)
        self.assertEqual({row["event_id"] for row in profiles}, {"event-01"})
        self.assertEqual(
            {row["impact_tier"] for row in profiles},
            {"CORE_DIRECT", "SECOND_ORDER", "CONDITIONAL"},
        )
        self.assertEqual(len({row["event_industry_mapping_id"] for row in profiles}), 8)
        self.assertTrue(all(len(row["mechanism_steps"]) == 7 for row in profiles))
        self.assertTrue(all(row["formal_ready"] is False for row in profiles))
        self.assertTrue(all(row["sha_gate"] == "DEFERRED" for row in profiles))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认按预期失败**

Run:

```powershell
python -m pytest tests/test_fingoose_event_01_industry_closure_v2.py -q
```

Expected: `ModuleNotFoundError: No module named 'fingoose_event_01_industry_closure_v2'`。

- [ ] **Step 3: 创建配置加载器和硬门禁**

在 `code/fingoose_event_01_industry_closure_v2.py` 写入：

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EXPECTED_IDS = {
    "event-industry-event-01-801150",
    "event-industry-event-01-801170",
    "event-industry-event-01-801210",
    "event-industry-event-01-801200",
    "event-industry-event-01-801760",
    "event-industry-event-01-801020",
    "event-industry-event-01-801750",
    "event-industry-event-01-801120",
}
STATEMENT_CLASSES = {"SOURCE_FACT", "CALCULATED_FACT", "RESEARCH_INFERENCE"}


def load_closure_profiles(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = [dict(row) for row in payload["profiles"]]
    ids = {str(row["event_industry_mapping_id"]) for row in rows}
    if ids != EXPECTED_IDS:
        raise ValueError(f"EVENT_01_MAPPING_SET_MISMATCH:{sorted(ids)}")
    for row in rows:
        if row["event_id"] != "event-01" or len(row["mechanism_steps"]) != 7:
            raise ValueError(f"INVALID_EVENT_01_PROFILE:{row.get('event_industry_mapping_id')}")
        if any(step["statement_class"] not in STATEMENT_CLASSES for step in row["mechanism_steps"]):
            raise ValueError(f"INVALID_STATEMENT_CLASS:{row['event_industry_mapping_id']}")
        if row["formal_ready"] is not False or row["sha_gate"] != "DEFERRED":
            raise ValueError(f"RELEASE_BOUNDARY_VIOLATION:{row['event_industry_mapping_id']}")
    return rows
```

- [ ] **Step 4: 写入八行业机制配置**

`configs/industry_impact_v2/event_01_closure_profiles.json` 使用以下稳定映射和确切七步内容：

| ID | 层级 | 行业 | 行为变化 | 主驱动 | 经营变量 | 收入/成本变量 | 三期限 |
|---|---|---|---|---|---|---|---|
| `event-industry-event-01-801150` | `CORE_DIRECT` | 医药生物 | 全球疫情扩散推动核酸检测纳入确诊流程并加快试剂审批 | 检测试剂获批数量与检测需求 | 试剂准入、产量和检测量 | 试剂收入、常规诊疗损失和毛利率 | `MIXED/POSITIVE/MIXED` |
| `event-industry-event-01-801170` | `CORE_DIRECT` | 交通运输 | 多国旅行限制和居民主动减少出行 | 航空 RPK 与旅客运输量 | 航班量、客座率和机场吞吐量 | 客运收入、航空性收入和固定成本摊薄 | `NEGATIVE/NEGATIVE/MIXED` |
| `event-industry-event-01-801210` | `CORE_DIRECT` | 社会服务（事件日名称：休闲服务） | 跨境和本地旅游活动受限 | 国内旅游人次和旅行限制覆盖率 | 酒店入住率、预订量和景区客流 | 房费、旅游收入和经营杠杆 | `NEGATIVE/NEGATIVE/MIXED` |
| `event-industry-event-01-801200` | `SECOND_ORDER` | 商贸零售（事件日名称：商业贸易） | 线下聚集减少并向线上渠道迁移 | 社零、门店客流和网上零售 | 同店销售、客流和库存周转 | 零售收入、租金减免和库存损失 | `NEGATIVE/NEGATIVE/MIXED` |
| `event-industry-event-01-801760` | `SECOND_ORDER` | 传媒 | 电影院暂停营业、制作和宣发停滞 | 影院营业状态、观影人次和票房 | 影院营业率、排片和票房 | 票房分账收入和固定租赁成本 | `NEGATIVE/NEGATIVE/MIXED` |
| `event-industry-event-01-801020` | `SECOND_ORDER` | 采掘（石油石化细分暴露） | 旅行和工业活动预期下降叠加产油国协调破裂 | 原油需求预测、库存和 WTI | 炼厂开工、成品油需求和库存 | 实现油价、炼化价差和库存损益 | `NEGATIVE/NEGATIVE/MIXED` |
| `event-industry-event-01-801750` | `CONDITIONAL` | 计算机 | 远程办公和在线服务使用增加 | 软件业务收入、云服务或在线办公使用 | 云资源使用、在线协作席位和订单 | 订阅收入、服务器成本和获客费用 | `POSITIVE/POSITIVE/MIXED` |
| `event-industry-event-01-801120` | `CONDITIONAL` | 食品饮料 | 餐饮渠道收缩、家庭消费和必选消费增加 | 餐饮收入和食品饮料零售 | 餐饮渠道销量、家庭渠道补库和产品结构 | 分渠道收入、促销费用和毛利率 | `MIXED/NEGATIVE/MIXED` |

每条配置的七个 `step_type` 固定为：

```json
[
  "EVENT_FACT",
  "BEHAVIOR_OR_POLICY_CHANGE",
  "OBSERVABLE_DRIVER",
  "INDUSTRY_OPERATING_VARIABLE",
  "INDUSTRY_REVENUE_OR_COST_VARIABLE",
  "DIRECTION_ASSESSMENT",
  "PRICE_CONFOUNDER_AND_COUNTEREVIDENCE"
]
```

前四步在 `evidence_ids` 中引用 Task 3 的来源 ID；第五、六步使用 `RESEARCH_INFERENCE` 并填写 `premise_step_numbers`、`condition_zh` 和 `invalidation_zh`；第七步使用 `CALCULATED_FACT`，由行情模块写入。

- [ ] **Step 5: 写行情注册表**

`configs/industry_impact_v2/event_01_market_registry.json` 明确：

```json
{
  "event_id": "event-01",
  "classification_edition": "SW2014",
  "event_at": "2020-03-11T16:30:00+00:00",
  "market_timezone": "Asia/Shanghai",
  "market_close": "15:00:00",
  "market_benchmark": {"benchmark_id": "CSI300", "code": "sh000300"},
  "industry_benchmarks": [
    {"mapping_id": "event-industry-event-01-801150", "code": "801150", "name_at_event": "医药生物"},
    {"mapping_id": "event-industry-event-01-801170", "code": "801170", "name_at_event": "交通运输"},
    {"mapping_id": "event-industry-event-01-801210", "code": "801210", "name_at_event": "休闲服务"},
    {"mapping_id": "event-industry-event-01-801200", "code": "801200", "name_at_event": "商业贸易"},
    {"mapping_id": "event-industry-event-01-801760", "code": "801760", "name_at_event": "传媒"},
    {"mapping_id": "event-industry-event-01-801020", "code": "801020", "name_at_event": "采掘"},
    {"mapping_id": "event-industry-event-01-801750", "code": "801750", "name_at_event": "计算机"},
    {"mapping_id": "event-industry-event-01-801120", "code": "801120", "name_at_event": "食品饮料"}
  ],
  "provider_priority": ["LICENSED_DATABASE", "AKSHARE_SWSRESEARCH", "PRE_REGISTERED_ETF"],
  "missing_value_policy": "KEEP_NULL_NEVER_ZERO_IMPUTE",
  "formal_ready": false,
  "sha_gate": "DEFERRED"
}
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_fingoose_event_01_industry_closure_v2.py -q`

Expected: `1 passed`。

- [ ] **Step 7: 记录提交检查点**

若 `.git/HEAD` 存在，执行：

```powershell
git add configs/industry_impact_v2/event_01_closure_profiles.json configs/industry_impact_v2/event_01_market_registry.json code/fingoose_event_01_industry_closure_v2.py tests/test_fingoose_event_01_industry_closure_v2.py
git commit -m "feat: define event01 industry closure contract"
```

当前工作区预期记录：`NO_VALID_GIT_METADATA / feat: define event01 industry closure contract`。

## Task 2: 实现来源快照和引文校验

**Files:**

- Create: `configs/industry_impact_v2/event_01_source_registry.jsonl`
- Create: `code/fingoose_industry_source_snapshot_v2.py`
- Create: `tests/test_fingoose_industry_source_snapshot_v2.py`

- [ ] **Step 1: 写快照失败测试**

```python
def test_snapshot_accepts_only_body_containing_required_quote(tmp_path: Path) -> None:
    from fingoose_industry_source_snapshot_v2 import snapshot_source

    target = {
        "source_id": "source-test",
        "source_url": "https://example.invalid/source",
        "media_type": "text/html",
        "required_quote": "核酸检测",
        "published_at": "2020-02-19T00:00:00+08:00",
        "usage_boundary": "PREDICTION_VISIBLE",
    }
    accepted = snapshot_source(
        target,
        output_root=tmp_path,
        fetch_bytes=lambda _: "<html><body>核酸检测作为病原学证据</body></html>".encode(),
        accessed_at="2026-08-04T12:00:00+08:00",
    )
    self.assertEqual(accepted["fetch_status"], "RETRIEVED_QUOTE_VERIFIED")
    self.assertTrue((tmp_path / accepted["raw_snapshot_path"]).exists())

    rejected = snapshot_source(
        {**target, "source_id": "source-mismatch", "required_quote": "不存在的句子"},
        output_root=tmp_path,
        fetch_bytes=lambda _: b"<html><body>only a title</body></html>",
        accessed_at="2026-08-04T12:00:00+08:00",
    )
    self.assertEqual(rejected["fetch_status"], "CONTENT_MISMATCH")
    self.assertIsNone(rejected["verified_quote"])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_fingoose_industry_source_snapshot_v2.py -q`

Expected: module import failure。

- [ ] **Step 3: 实现抓取、文本归一化和失败日志**

`code/fingoose_industry_source_snapshot_v2.py` 提供以下接口：

```python
def html_text(payload: bytes) -> str:
    parser = VisibleTextParser()
    parser.feed(payload.decode("utf-8", errors="replace"))
    return " ".join(" ".join(parser.parts).split())


def payload_text(payload: bytes, media_type: str) -> str:
    if media_type == "application/pdf":
        from io import BytesIO
        from pypdf import PdfReader

        return " ".join(
            " ".join((page.extract_text() or "").split())
            for page in PdfReader(BytesIO(payload)).pages
        )
    return html_text(payload)


def snapshot_source(target, *, output_root, fetch_bytes, accessed_at):
    suffix = ".pdf" if target.get("media_type") == "application/pdf" else ".html"
    relative = Path("raw/evidence") / f"{target['source_id']}{suffix}"
    try:
        payload = fetch_bytes(target["source_url"])
    except Exception as exc:
        return {
            **target,
            "accessed_at": accessed_at,
            "raw_snapshot_path": None,
            "verified_quote": None,
            "fetch_status": "FETCH_FAILED",
            "failure_reason": f"{type(exc).__name__}:{exc}",
        }
    text = payload_text(payload, str(target.get("media_type") or "text/html"))
    quote = " ".join(str(target["required_quote"]).split())
    status = "RETRIEVED_QUOTE_VERIFIED" if quote in text else "CONTENT_MISMATCH"
    destination = output_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return {
        **target,
        "accessed_at": accessed_at,
        "raw_snapshot_path": relative.as_posix(),
        "verified_quote": quote if status == "RETRIEVED_QUOTE_VERIFIED" else None,
        "fetch_status": status,
        "failure_reason": None if status == "RETRIEVED_QUOTE_VERIFIED" else "REQUIRED_QUOTE_NOT_FOUND",
    }
```

同时实现 `snapshot_registry(registry_path, output_root, accessed_at)`，使用 `urllib.request.Request` 的固定 `User-Agent`，逐条写入 `industry_source_fetches.jsonl`。HTTP 失败不得终止其他来源抓取。

- [ ] **Step 4: 写 14 条确切来源注册记录**

`configs/industry_impact_v2/event_01_source_registry.jsonl` 使用以下来源。每行包含 `source_id/source_tier/publisher/title/source_url/published_at/required_quote/evidence_locator/usage_boundary/supports_mapping_ids/supports_step_types/licence_status`：

| source_id | 发布方 | URL | 用途 |
|---|---|---|---|
| `event01-who-pandemic` | WHO | `https://www.who.int/news-room/speeches/item/who-director-general-s-opening-remarks-at-the-media-briefing-on-covid-19---11-march-2020` | 事件锚点 |
| `event01-gov-diagnosis-v6` | 国务院/卫健委 | `https://www.gov.cn/zhengce/2020-02/19/content_5480958.htm` | 核酸检测进入诊疗方案 |
| `event01-nmpa-test-kits` | 国家药监局 | `https://www.nmpa.gov.cn/directory/web/nmpa/zhuanti/yqyjzxd/yqyjxd/20200330170001581.html` | 23 个检测试剂审批 |
| `event01-iata-mar-rpk` | IATA | `https://www.iata.org/en/iata-repository/publications/economic-reports/air-passenger-monthly-analysis---mar-2020` | 全球 RPK -52.9%、中国国内 RPK -65.5% |
| `event01-unwto-restrictions` | UNWTO | `https://www.unwto.org/news/covid-19-response-travel-restrictions` | 96% 目的地实施旅行限制 |
| `event01-caac-2020` | 中国民航局 | `http://www.caac.gov.cn/XWZX/MHYW/202106/t20210610_207917.html` | 2020 年旅客量、客座率与机场吞吐量 |
| `event01-mct-tourism-2020` | 文化和旅游部 | `https://zwgk.mct.gov.cn/zfxxgkml/tjxx/202102/t20210218_921658.html` | 一季度国内旅游 2.95 亿人次、同比 -83.4% |
| `event01-nbs-retail-mar` | 国家统计局 | `https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1900683.html` | 3 月社零、餐饮、食品和饮料分项 |
| `event01-film-covid-meeting` | 国家电影局 | `https://www.chinafilm.gov.cn/xwzx/tp/202004/t20200430_1254.html` | 全国影院暂停营业、制作宣发停滞 |
| `event01-film-guangdong` | 国家电影局 | `https://www.chinafilm.gov.cn/xwzx/gzdt/202005/t20200506_1216.html` | 广东影院停业和票房降幅，限定地区用途 |
| `event01-miit-software-2020` | 工业和信息化部 | `https://www.miit.gov.cn/gxsj/tjfx/rjy/art/2021/art_f6e61b9ffc494c099ea89faecb47acd2.html` | 软件业务收入，`VERIFICATION_ONLY` |
| `event01-eia-mar20-steo` | EIA | `https://www.eia.gov/outlooks/steo/archives/mar20.pdf` | 原油需求、库存、OPEC 协调破裂 |
| `event01-fed-mar03` | Federal Reserve | `https://www.federalreserve.gov/newsevents/pressreleases/monetary20200303a.htm` | 紧急降息混杂事件 |
| `event01-fed-mar15` | Federal Reserve | `https://www.federalreserve.gov/newsevents/pressreleases/monetary20200315a.htm` | 后续流动性政策混杂事件 |

证据到机制步骤的固定映射为：

| 行业 | 行为/政策事实 | 驱动事实 | 经营变量事实 | 混杂与反证 |
|---|---|---|---|---|
| 医药生物 | WHO、国务院诊疗方案 | 药监局试剂审批 | 诊疗方案和审批数量 | 国内疫情与审批早于 WHO 定性 |
| 交通运输 | WHO、UNWTO 旅行限制 | IATA RPK | IATA、民航局旅客量和客座率 | 各国和中国旅行限制提前生效 |
| 社会服务 | WHO、UNWTO 旅行限制 | 文旅部旅游人次 | 文旅部旅游人次与收入 | 国内旅游在 WHO 定性前已收缩 |
| 商贸零售 | WHO 与国内活动限制 | 国家统计局社零 | 社零、网上零售和业态分项 | 居民收入与线上迁移 |
| 传媒 | 国家电影局影院暂停 | 影院营业状态与票房 | 国家电影局停业和票房材料 | 中国影院 1 月已经停业 |
| 采掘（石油石化细分） | WHO、EIA OPEC 协调变化 | EIA 需求、库存和油价预测 | EIA 炼厂、需求与库存解释 | OPEC+ 协调破裂和价格战 |
| 计算机 | WHO 与远程活动变化 | 工信部软件业务收入 | 软件业务收入和在线服务需求 | 权益抛售与远程需求方向相反 |
| 食品饮料 | WHO 与餐饮活动变化 | 国家统计局餐饮和食品饮料分项 | 餐饮、粮油食品和饮料零售 | 餐饮下降与家庭消费增加 |

`EVENT_FACT` 统一引用 `event01-who-pandemic`。上述表中的行为、驱动和经营来源分别绑定对应 `step_type`；不允许将一个来源 ID 无差别复制到七个节点。

引文必须从下载正文逐字核对。搜索摘要只能帮助定位，不得写入 `verified_quote`。IATA、文旅部、民航局、药监局、统计局和工信部的事件后材料统一使用 `VERIFICATION_ONLY`。

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_fingoose_industry_source_snapshot_v2.py -q`

Expected: all tests pass。

- [ ] **Step 6: 记录提交检查点**

Commit message: `feat: add event01 industry evidence snapshots`；无 Git 元数据时写入实施日志。

## Task 3: 投影逐节点证据、驱动观测和混杂记录

**Files:**

- Modify: `code/fingoose_event_01_industry_closure_v2.py`
- Modify: `tests/test_fingoose_event_01_industry_closure_v2.py`

- [ ] **Step 1: 写 56 节点、事实门禁和推断门禁测试**

```python
def test_chain_projection_separates_facts_and_inferences(self) -> None:
    from fingoose_event_01_industry_closure_v2 import build_mechanism_chains, load_closure_profiles

    profiles = load_closure_profiles(
        ROOT / "configs/industry_impact_v2/event_01_closure_profiles.json"
    )
    evidence = {
        evidence_id: {"evidence_id": evidence_id, "fetch_status": "RETRIEVED_QUOTE_VERIFIED"}
        for profile in profiles
        for step in profile["mechanism_steps"]
        for evidence_id in step.get("evidence_ids", [])
    }
    chains = build_mechanism_chains(profiles, evidence)
    self.assertEqual(len(chains), 8)
    self.assertEqual(sum(len(row["nodes"]) for row in chains), 56)
    for chain in chains:
        for node in chain["nodes"]:
            if node["statement_class"] == "SOURCE_FACT":
                self.assertTrue(node["evidence_ids"])
            if node["statement_class"] == "RESEARCH_INFERENCE":
                self.assertTrue(node["premise_node_ids"])
                self.assertTrue(node["condition_zh"])
                self.assertTrue(node["invalidation_zh"])
```

- [ ] **Step 2: 运行测试并确认失败**

Expected: `ImportError: cannot import name 'build_mechanism_chains'`。

- [ ] **Step 3: 实现机制节点投影**

```python
def build_mechanism_chains(profiles, evidence_by_id):
    chains = []
    for profile in profiles:
        nodes = []
        for index, step in enumerate(profile["mechanism_steps"], 1):
            node_id = f"industry-mechanism-{profile['event_industry_mapping_id']}-{index}"
            premise_ids = [
                f"industry-mechanism-{profile['event_industry_mapping_id']}-{number}"
                for number in step.get("premise_step_numbers", [])
            ]
            evidence_ids = list(step.get("evidence_ids", []))
            missing = [
                evidence_id for evidence_id in evidence_ids
                if evidence_by_id.get(evidence_id, {}).get("fetch_status") != "RETRIEVED_QUOTE_VERIFIED"
            ]
            nodes.append({
                "node_id": node_id,
                "node_type": step["step_type"],
                "statement_class": step["statement_class"],
                "statement_zh": step["statement_zh"],
                "evidence_ids": evidence_ids,
                "premise_node_ids": premise_ids,
                "condition_zh": step.get("condition_zh"),
                "invalidation_zh": step.get("invalidation_zh"),
                "evidence_status": "AVAILABLE" if evidence_ids and not missing else (
                    "NOT_APPLICABLE_INFERENCE" if step["statement_class"] == "RESEARCH_INFERENCE" else "EVIDENCE_PENDING"
                ),
            })
        chains.append({
            "industry_chain_id": f"industry-chain-{profile['event_industry_mapping_id']}",
            "event_industry_mapping_id": profile["event_industry_mapping_id"],
            "event_id": "event-01",
            "nodes": nodes,
            "edges": [
                {"from_node_id": nodes[i]["node_id"], "to_node_id": nodes[i + 1]["node_id"]}
                for i in range(6)
            ],
            "horizon_directions": profile["horizon_directions"],
            "confounders": profile["confounders"],
            "chain_status": "PROPOSED_INDUSTRY_MECHANISM",
            "review_status": "NEEDS_HUMAN_REVIEW",
            "formal_ready": False,
            "sha_gate": "DEFERRED",
        })
    return chains
```

- [ ] **Step 4: 为八行业写结构化混杂**

配置中的 `confounders` 至少包含：

| 行业 | 等级 | 竞争解释 |
|---|---|---|
| 医药生物 | `MATERIAL` | 中国国内疫情、检测审批和常规诊疗变化早于 WHO 定性 |
| 交通运输 | `MATERIAL` | 各国旅行限制和中国国内管控已提前生效 |
| 社会服务 | `MATERIAL` | 国内旅游活动在 WHO 定性前已大幅收缩 |
| 商贸零售 | `MATERIAL` | 国内管控、居民收入预期和线上迁移共同作用 |
| 传媒 | `MATERIAL` | 中国影院在 1 月已停业，WHO 节点不是首次冲击 |
| 采掘（石油石化细分） | `DOMINANT` | 3 月 6 日 OPEC+ 协调破裂和沙特—俄罗斯价格战可能主导油价 |
| 计算机 | `MATERIAL` | 市场风险偏好下跌与远程办公需求上升方向相反 |
| 食品饮料 | `MATERIAL` | 餐饮渠道下降与家庭食品消费增加方向相反 |

每项包含 `affected_windows`、`mechanism_overlap`、`alternative_explanation_zh`、`counterevidence_zh`、`attribution_limit_zh` 和证据 ID。所有八条均设置 `challenge_set_only=true`，但这不阻止数据完整记录成为 `CANDIDATE_COMPLETE`。

- [ ] **Step 5: 投影驱动注册和观测**

实现 `build_driver_records(profiles, evidence_by_id)`，每条映射一个主驱动，最多一个次驱动。观测使用以下已核验值，并保留来源周期和单位：

- 医药生物：截至 2020-03-30 共批准 23 个检测试剂，其中核酸 15 个、抗体 8 个；
- 交通运输：2020 年 3 月全球 RPK 同比 -52.9%，中国国内 RPK 同比 -65.5%；
- 社会服务：2020 年一季度国内旅游 2.95 亿人次，同比 -83.4%；
- 商贸零售：2020 年 3 月社零 26450 亿元，同比 -15.8%；
- 传媒：全国影院暂停营业；广东 1—4 月票房同比 -89.9%，记录地区限定；
- 采掘：使用 EIA 2020 年原油需求、库存和价格预测字段；
- 计算机：使用工信部 2020 年软件业务收入及同比，标记年度频率和 `VERIFICATION_ONLY`；
- 食品饮料：2020 年 3 月餐饮收入同比 -46.8%、粮油食品 +19.2%、饮料 +6.3%。

未能从正文逐字核验的数值不写入 `value`，而写入 `null`、`DATA_PENDING` 和对应来源失败原因。

- [ ] **Step 6: 运行机制测试**

Run: `python -m pytest tests/test_fingoose_event_01_industry_closure_v2.py -q`

Expected: all tests pass。

- [ ] **Step 7: 记录提交检查点**

Commit message: `feat: project evidence-backed event01 industry chains`。

## Task 4: 实现跨时区 T0 和可复算行业窗口

**Files:**

- Create: `requirements-event01-industry.txt`
- Modify: `code/fingoose_company_impact_market_v2.py`
- Modify: `tests/test_fingoose_company_impact_market_v2.py`
- Create: `code/fingoose_industry_market_v2.py`
- Create: `tests/test_fingoose_industry_market_v2.py`

- [ ] **Step 1: 写北京时间转换失败测试**

在 `tests/test_fingoose_company_impact_market_v2.py` 添加：

```python
def test_utc_event_is_converted_to_shanghai_before_t0_alignment(self) -> None:
    from fingoose_company_impact_market_v2 import align_t0

    result = align_t0(
        "2020-03-11T16:30:00+00:00",
        ["2020-03-11", "2020-03-12", "2020-03-13"],
        market_timezone="Asia/Shanghai",
    )
    self.assertEqual(result["T0"], "2020-03-12")
    self.assertEqual(result["local_event_at"], "2020-03-12T00:30:00+08:00")
    self.assertEqual(result["alignment_reason"], "PRE_OPEN_SAME_SESSION")
```

- [ ] **Step 2: 运行该测试确认失败**

Expected: `TypeError: align_t0() got an unexpected keyword argument 'market_timezone'`。

- [ ] **Step 3: 修正共享 T0 对齐函数**

```python
from zoneinfo import ZoneInfo

MARKET_OPEN = time(9, 30)


def align_t0(event_at: str, sessions: Iterable[str], *, market_timezone: str = "Asia/Shanghai") -> dict[str, str]:
    ordered = sorted({date.fromisoformat(value) for value in sessions})
    if not ordered:
        raise ValueError("EMPTY_SESSION_CALENDAR")
    if len(event_at) == 10:
        local_date = date.fromisoformat(event_at)
        local_text = event_at
        local_clock = None
        after_close = False
    else:
        parsed = datetime.fromisoformat(event_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("EVENT_TIMEZONE_REQUIRED")
        local = parsed.astimezone(ZoneInfo(market_timezone))
        local_date = local.date()
        local_text = local.isoformat()
        local_clock = local.timetz().replace(tzinfo=None)
        after_close = local_clock > MARKET_CLOSE
    if local_date in ordered and not after_close:
        t0 = local_date
        if len(event_at) == 10:
            reason = "DATE_PRECISION_SAME_OR_NEXT_SESSION"
        elif local_clock is not None and local_clock < MARKET_OPEN:
            reason = "PRE_OPEN_SAME_SESSION"
        else:
            reason = "IN_SESSION_SAME_DAY"
    else:
        candidates = [session for session in ordered if session > local_date]
        if not candidates:
            raise ValueError("NO_SESSION_AFTER_EVENT")
        t0 = candidates[0]
        reason = "AFTER_CLOSE_NEXT_SESSION" if after_close else "NON_SESSION_NEXT_SESSION"
    return {"T0": t0.isoformat(), "alignment_reason": reason, "local_event_at": local_text}
```

运行现有市场测试，确认未破坏其他事件：

Run: `python -m pytest tests/test_fingoose_company_impact_market_v2.py -q`

Expected: all tests pass。

- [ ] **Step 4: 写行业窗口失败测试**

`tests/test_fingoose_industry_market_v2.py` 构造 2020-02-13 至 2020-06-12 的共同交易日和两组收盘价，断言：

```python
window = build_industry_market_window(
    mapping_id="event-industry-event-01-801170",
    event_at="2020-03-11T16:30:00+00:00",
    industry_rows=industry_rows,
    market_rows=market_rows,
    driver_observations=[{"period": "2020-03", "value": -52.9, "unit": "%同比"}],
)
self.assertEqual(window["t0_alignment"]["T0"], "2020-03-12")
self.assertEqual(window["fixed_windows"]["T_MINUS_1"]["actual_date"], "2020-03-11")
self.assertEqual(window["fixed_windows"]["D3"]["actual_date"], "2020-03-17")
self.assertEqual(window["fixed_windows"]["D20"]["actual_date"], "2020-04-10")
self.assertEqual(window["continuous_window"][0]["actual_date"], "2020-02-13")
self.assertEqual(window["continuous_window"][0]["industry_normalized"], 100 * industry_rows[0]["close"] / industry_t_minus_1)
self.assertAlmostEqual(
    window["fixed_windows"]["D1"]["market_relative_return"],
    (industry_d1 / industry_t_minus_1 - 1) - (market_d1 / market_t_minus_1 - 1),
)
```

- [ ] **Step 5: 实现行情标准化和窗口计算**

`code/fingoose_industry_market_v2.py` 提供：

```python
WINDOW_OFFSETS = {"T_MINUS_1": -1, "T0": 0, "D1": 1, "D3": 3, "D5": 5, "D20": 20}


def normalized(value: float, base: float) -> float:
    if base == 0:
        raise ValueError("ZERO_BASE_VALUE")
    return value / base * 100.0


def excess_return(industry_start, industry_end, market_start, market_end):
    return (industry_end / industry_start - 1) - (market_end / market_start - 1)


def common_rows(industry_rows, market_rows):
    industry = {str(row["date"]): dict(row) for row in industry_rows}
    market = {str(row["date"]): dict(row) for row in market_rows}
    return [(day, industry[day], market[day]) for day in sorted(set(industry) & set(market))]
```

`build_industry_market_window` 必须从共同交易日计算 `T-20..D20`、固定窗口和 M3；M3 使用 T0 三个自然月后当日或下一共同交易日。每个固定窗口保存绝对值、归一化值、行业收益、沪深300收益、相对收益、公式和输入值。共同日期不足时返回 `DATA_PENDING` 和精确 reason code，不做邻近日期替换。

- [ ] **Step 6: 实现可选 AKShare 抓取器并保存完整返回表**

`requirements-event01-industry.txt`：

```text
akshare>=1.18.75,<2
pypdf>=5,<6
```

提供 `fetch_market_registry(registry, raw_root)`：

```python
import akshare as ak

sw = ak.index_hist_sw(symbol=sw_code, period="day")
csi = ak.stock_zh_index_daily_tx(
    symbol="sh000300",
    start_date="20200201",
    end_date="20200630",
)
sw.to_csv(raw_root / f"sw_{sw_code}.csv", index=False, encoding="utf-8-sig")
csi.to_csv(raw_root / "csi300.csv", index=False, encoding="utf-8-sig")
```

保存提供方、函数、参数、抓取时间、原始列名、输出路径和 `licence_status=PUBLIC_REPRODUCIBLE_LICENSE_REVIEW_PENDING`。若本地许可数据库出现同代码数据，优先使用数据库并记录查询表与截止口径。AKShare 缺失、接口失败或返回空表时保留失败记录，不自动选择 ETF。

- [ ] **Step 7: 运行市场测试**

Run:

```powershell
python -m pytest tests/test_fingoose_company_impact_market_v2.py tests/test_fingoose_industry_market_v2.py -q
```

Expected: all tests pass。

- [ ] **Step 8: 记录提交检查点**

Commit message: `feat: compute event01 industry benchmark windows`。

## Task 5: 生成八行业覆盖包和真实完成矩阵

**Files:**

- Modify: `code/fingoose_event_01_industry_closure_v2.py`
- Create: `code/build_fingoose_event_01_industry_closure_v2.py`
- Modify: `tests/test_fingoose_event_01_industry_closure_v2.py`

- [ ] **Step 1: 写覆盖包失败测试**

```python
def test_builder_emits_joinable_overlay_without_promoting_release(self) -> None:
    from fingoose_event_01_industry_closure_v2 import build_event_01_closure_bundle
    from fingoose_company_impact_io_v2 import read_jsonl

    output = Path(self._temp.name) / "overlay"
    report = build_event_01_closure_bundle(
        ROOT,
        output_root=output,
        evidence_fetches=[],
        market_payloads={},
    )
    expected = {
        "event_industry_mappings.jsonl",
        "industry_mechanism_chains.jsonl",
        "industry_evidence.jsonl",
        "industry_driver_registry.jsonl",
        "industry_driver_observations.jsonl",
        "industry_market_windows.jsonl",
        "industry_completion_report.jsonl",
        "industry_source_fetches.jsonl",
    }
    self.assertTrue(expected.issubset({path.name for path in output.iterdir()}))
    mappings = read_jsonl(output / "event_industry_mappings.jsonl")
    chains = read_jsonl(output / "industry_mechanism_chains.jsonl")
    self.assertEqual(len(mappings), 8)
    self.assertEqual(sum(len(row["nodes"]) for row in chains), 56)
    self.assertFalse(report["formal_ready"])
    self.assertEqual(report["sha_gate"], "DEFERRED")
```

在测试类中增加确定性的临时目录生命周期：

```python
import tempfile


def setUp(self) -> None:
    self._temp = tempfile.TemporaryDirectory()


def tearDown(self) -> None:
    self._temp.cleanup()
```

- [ ] **Step 2: 实现证据投影**

仅将 `fetch_status=RETRIEVED_QUOTE_VERIFIED` 的来源投影为可用证据。字段固定为：

```python
{
    "evidence_id": source["source_id"],
    "evidence_kind": "INDUSTRY_MECHANISM_SOURCE",
    "source_tier": source["source_tier"],
    "publisher": source["publisher"],
    "title": source["title"],
    "source_url": source["source_url"],
    "published_at": source["published_at"],
    "first_public_at": source.get("first_public_at", source["published_at"]),
    "accessed_at": source["accessed_at"],
    "original_quote": source["verified_quote"],
    "locator": source["evidence_locator"],
    "availability_scope": source["usage_boundary"],
    "supports_mapping_ids": source["supports_mapping_ids"],
    "supports_step_types": source["supports_step_types"],
    "raw_snapshot_path": source["raw_snapshot_path"],
    "review_status": "SOURCE_TEXT_LOCATOR_VERIFIED",
    "formal_ready": False,
    "sha_gate": "DEFERRED",
}
```

- [ ] **Step 3: 实现完成门禁**

```python
def completion_for(mapping, chain, driver, window):
    fact_types = {
        node["node_type"] for node in chain["nodes"]
        if node["statement_class"] == "SOURCE_FACT" and node["evidence_status"] == "AVAILABLE"
    }
    required_facts = {
        "EVENT_FACT",
        "BEHAVIOR_OR_POLICY_CHANGE",
        "OBSERVABLE_DRIVER",
        "INDUSTRY_OPERATING_VARIABLE",
    }
    blockers = []
    if not required_facts.issubset(fact_types):
        blockers.append("FOUR_FACT_PILLARS_INCOMPLETE")
    if driver["source_status"] != "AVAILABLE":
        blockers.append("DRIVER_DATA_INCOMPLETE")
    if window["window_status"] != "AVAILABLE":
        blockers.append("INDUSTRY_WINDOW_INCOMPLETE")
    if any(value == "UNKNOWN" for value in chain["horizon_directions"].values()) and not chain.get("abstention"):
        blockers.append("UNEXPLAINED_UNKNOWN_DIRECTION")
    if not chain.get("confounders"):
        blockers.append("CONFOUNDERS_INCOMPLETE")
    return {
        "event_industry_mapping_id": mapping["event_industry_mapping_id"],
        "completion_status": "CANDIDATE_COMPLETE" if not blockers else "OPEN",
        "blockers": blockers,
        "challenge_set_only": any(
            row["severity"] in {"MATERIAL", "DOMINANT", "UNRESOLVED"}
            for row in chain["confounders"]
        ),
        "review_status": "NEEDS_HUMAN_REVIEW",
        "formal_ready": False,
        "sha_gate": "DEFERRED",
    }
```

公司样本不是行业层完成门禁；它作为 UI 联动状态单独显示。

- [ ] **Step 4: 实现确定性文件输出和验证报告**

`build_event_01_closure_bundle` 写八个 JSONL、`summary.json`、`validation_report.json` 和不含 SHA 的 `manifest.json`。验证报告至少检查：

- 映射数 8；
- 机制链数 8；
- 机制节点数 56；
- 三层级互斥；
- 所有 ID 可连接；
- 来源用途边界合法；
- 行情缺失未变为零；
- 所有记录 `formal_ready=false`；
- 未修改基线文件。

CLI `code/build_fingoose_event_01_industry_closure_v2.py`：

```python
from fingoose_event_01_industry_closure_v2 import main

if __name__ == "__main__":
    raise SystemExit(main())
```

默认输出 `work/event_01_industry_closure_v2_candidate`。

- [ ] **Step 5: 运行覆盖包测试**

Run: `python -m pytest tests/test_fingoose_event_01_industry_closure_v2.py -q`

Expected: all tests pass。

- [ ] **Step 6: 记录提交检查点**

Commit message: `feat: build event01 industry closure overlay`。

## Task 6: 在现有 UI 合并覆盖层并展示完整数据

**Files:**

- Modify: `code/fingoose_company_impact_ui_v2.py:24-124`
- Modify: `code/fingoose_company_impact_ui_v2.py:228-384`
- Modify: `tests/test_fingoose_industry_ui_v2.py`

- [ ] **Step 1: 写覆盖合并和 UI 失败测试**

```python
def test_event_01_overlay_replaces_only_matching_industry_rows(self) -> None:
    from fingoose_company_impact_ui_v2 import build_ui_bundle

    bundle = build_ui_bundle(
        ROOT,
        candidate_root=ROOT / "work/company_impact_high_quality_v2_candidate",
        industry_root=ROOT / "work/industry_impact_high_quality_v2_candidate",
        industry_overlay_root=ROOT / "work/event_01_industry_closure_v2_candidate",
    )
    event_01 = next(row for row in bundle["events"] if row["event_id"] == "event-01")
    event_02 = next(row for row in bundle["events"] if row["event_id"] == "event-02")
    self.assertEqual(len(event_01["industry_impacts"]), 8)
    self.assertTrue(all(row.get("overlay_source") == "EVENT_01_CLOSURE" for row in event_01["industry_impacts"]))
    self.assertTrue(all(row.get("overlay_source") is None for row in event_02["industry_impacts"]))


def test_industry_detail_renders_node_sources_driver_and_structured_confounders(self) -> None:
    for text in (
        "来源事实",
        "计算事实",
        "研究推断",
        "查看原文",
        "主驱动（右轴）",
        "竞争解释",
        "归因边界",
        "挑战集",
        "原始值",
        "归一化值",
    ):
        self.assertIn(text, self.html)
```

- [ ] **Step 2: 实现覆盖层合并**

扩展 `_load_industry_layer`，读取 `industry_driver_observations.jsonl` 和 `industry_source_fetches.jsonl`（文件不存在时返回空列表）。新增：

```python
def _merge_industry_layers(base, overlay):
    merged = {key: list(rows) for key, rows in base.items()}
    for key in ("mappings", "chains", "drivers", "windows", "completion"):
        by_id = {str(row["event_industry_mapping_id"]): dict(row) for row in merged[key]}
        for row in overlay[key]:
            mapping_id = str(row["event_industry_mapping_id"])
            if not mapping_id.startswith("event-industry-event-01-") or mapping_id not in by_id:
                raise ValueError(f"INVALID_INDUSTRY_OVERLAY_ID:{mapping_id}")
            by_id[mapping_id] = {**dict(row), "overlay_source": "EVENT_01_CLOSURE"}
        merged[key] = list(by_id.values())
    base_evidence = {str(row["evidence_id"]): dict(row) for row in merged["evidence"]}
    base_evidence.update({str(row["evidence_id"]): dict(row) for row in overlay["evidence"]})
    merged["evidence"] = list(base_evidence.values())
    merged["observations"] = list(overlay.get("observations", []))
    merged["fetches"] = list(overlay.get("fetches", []))
    return merged
```

`_attach_industry_layer` 不再只读取 `event_evidence_ids`。它必须汇总当前链全部节点的 `evidence_ids`，把对应证据附到 `node["evidence"]` 和 `mapping["evidence"]`；再按 `driver_series_id` 附加驱动观测。事件级 `industry_evidence` 使用八条链证据 ID 的并集，避免只有事件锚点可见。

`build_ui_bundle` 新增 `industry_overlay_root` 参数；默认路径存在时自动合并，不存在时保持原行为。

同步扩展 `write_ui(..., industry_overlay_root=None)`，并为 `code/fingoose_company_impact_ui_v2.py` 增加 `main()`：参数固定为 `--root`、`--candidate`、`--industry`、`--industry-overlay` 和 `--output`，调用 `write_ui` 后输出中文摘要。这样 Task 8 的页面重建命令是实际可执行入口。

- [ ] **Step 3: 渲染逐节点证据和技术边界**

修改 `industryMechanismDetail`：

- `SOURCE_FACT` 显示绿色“来源事实”；
- `CALCULATED_FACT` 显示蓝色“计算事实”；
- `RESEARCH_INFERENCE` 显示灰色“研究推断”；
- 每个来源事实列出引文、发布方、发布时间、定位符和带 `target="_blank" rel="noopener"` 的“查看原文”；
- 每个研究推断列出前置节点、生效条件和失效条件；
- 无可用证据时显示 `证据待核验：<reason code>`，不显示事件锚点证据替代整链证据。

- [ ] **Step 4: 渲染行业、沪深300和驱动三序列图表**

`industryChart` 输出 SVG：

- 行业和沪深300使用共同 `T-1=100` 左轴；
- 驱动变量使用原单位右轴；
- 月频或季度驱动只画离散点，不插值为日频；
- 竖线标出 T0；
- 无连续行情时用状态面板代替 `<svg>`；
- “原始值/归一化值”分段控件只切换已有字段，不在浏览器重新猜测数据。

固定窗口表增加行业绝对值、沪深300绝对值、行业收益、沪深300收益、相对收益和公式输入折叠区。

- [ ] **Step 5: 渲染结构化混杂和公司回接**

每条混杂显示事件、影响窗口、严重度、机制重叠、竞争解释、反证和归因边界。`MATERIAL/DOMINANT/UNRESOLVED` 显示“仅挑战集”。没有公司样本时显示“行业机制已建立，当前尚未配置公司样本”。

- [ ] **Step 6: 运行 UI 单元测试**

Run:

```powershell
python -m pytest tests/test_fingoose_industry_ui_v2.py tests/test_fingoose_company_impact_ui_v2.py -q
```

Expected: all tests pass，事件计数仍为 `8/8/8/8/7/7/7/7/8/9`。

- [ ] **Step 7: 记录提交检查点**

Commit message: `feat: render event01 industry evidence and market overlay`。

## Task 7: 抓取真实来源、行情和驱动数据

**Files:**

- Generate: `work/event_01_industry_closure_v2_candidate/raw/evidence/*`
- Generate: `work/event_01_industry_closure_v2_candidate/raw/market/*`
- Generate: `work/event_01_industry_closure_v2_candidate/industry_source_fetches.jsonl`

- [ ] **Step 1: 安装可选行情依赖**

Run:

```powershell
python -m pip install -r requirements-event01-industry.txt
```

Expected: AKShare imports successfully. If installation is not authorized or fails, record `AKSHARE_UNAVAILABLE` and keep market rows `DATA_PENDING`; do not bypass the gate with invented CSV data。

- [ ] **Step 2: 抓取并保存官方证据正文**

Run:

```powershell
python code/fingoose_industry_source_snapshot_v2.py --root . --registry configs/industry_impact_v2/event_01_source_registry.jsonl --output work/event_01_industry_closure_v2_candidate
```

Expected: 14 条抓取记录；每条状态为 `RETRIEVED_QUOTE_VERIFIED`、`CONTENT_MISMATCH` 或 `FETCH_FAILED`，不存在无状态记录。

- [ ] **Step 3: 抓取并保存八个申万指数和沪深300完整返回表**

Run:

```powershell
python code/fingoose_industry_market_v2.py --root . --registry configs/industry_impact_v2/event_01_market_registry.json --output work/event_01_industry_closure_v2_candidate/raw/market
```

Expected: 每个成功序列覆盖至少 `2020-02-13` 至 `2020-06-12`；失败序列在抓取清单中有精确 reason code。确认 801020 的事件日名称显示为“采掘”，不得把它伪装为纯石油石化指数。

- [ ] **Step 4: 运行覆盖层构建器**

Run:

```powershell
python code/build_fingoose_event_01_industry_closure_v2.py --root . --output work/event_01_industry_closure_v2_candidate
```

Expected: 输出 8 条映射、8 条链、56 个节点。`candidate_complete_count` 由真实门禁计算，不预设为 8；所有未完成项在 `industry_completion_report.jsonl` 中列出。

- [ ] **Step 5: 人工抽查证据和数值**

逐项打开 14 个来源中的可用快照，确认引文确实存在。对交通运输、商贸零售和采掘三个行业，手工用保存的 `T-1/T0/D3` 绝对值复算收益率与相对收益，误差容忍 `1e-10`。把抽查结果写入 `validation_report.json` 的 `manual_spot_checks`。

- [ ] **Step 6: 记录数据检查点**

Commit message: `data: add event01 industry evidence and market candidate`；无 Git 元数据时记录生成文件清单和字节数。

## Task 8: 生成 UI 并执行桌面、移动端验收

**Files:**

- Generate: `work/company_impact_high_quality_v2_candidate/ui/index.html`
- Create: `tests/verify_event_01_industry_ui.mjs`

- [ ] **Step 1: 重建同一 UI 页面**

Run:

```powershell
python code/fingoose_company_impact_ui_v2.py --root . --candidate work/company_impact_high_quality_v2_candidate --industry work/industry_impact_high_quality_v2_candidate --industry-overlay work/event_01_industry_closure_v2_candidate --output work/company_impact_high_quality_v2_candidate/ui
```

Expected: `index.html` 包含 `event-01` 八个行业、逐节点来源、三序列图表或明确缺口状态。

- [ ] **Step 2: 写 Playwright 验收脚本**

`tests/verify_event_01_industry_ui.mjs`：

```javascript
import { chromium } from 'playwright';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const html = path.resolve('work/company_impact_high_quality_v2_candidate/ui/index.html');
const browser = await chromium.launch({ headless: true });
for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on('console', message => {
    if (message.type() === 'error') errors.push(message.text());
  });
  await page.goto(pathToFileURL(html).href);
  await page.locator('[data-event="event-01"]').click();
  await page.getByText('行业板块链', { exact: true }).click();
  await page.locator('[data-industry-mapping="event-industry-event-01-801170"]').click();
  const branchCount = await page.locator('[data-industry-mapping]').count();
  if (branchCount < 8) throw new Error(`event-01 industry branches missing: ${branchCount}`);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  if (overflow) throw new Error(`page overflow at ${viewport.width}px`);
  if (errors.length) throw new Error(errors.join('\n'));
  await page.screenshot({
    path: `work/event_01_industry_closure_v2_candidate/ui-${viewport.width}.png`,
    fullPage: true,
  });
  await page.close();
}
await browser.close();
```

- [ ] **Step 3: 运行视觉验收**

Run: `node tests/verify_event_01_industry_ui.mjs`

Expected: desktop and mobile screenshots created; no console errors, no page-level horizontal overflow, eight industry branches remain visible。

- [ ] **Step 4: 人工检查截图和图表像素**

使用本地图片查看工具检查：七步链无文字遮挡；长引文可展开；图例与坐标不重叠；有行情时 SVG 具有行业线和沪深300线；无行情时显示缺口说明而非空白图。

- [ ] **Step 5: 启动局域网页面服务**

Run:

```powershell
Start-Process -WindowStyle Hidden -FilePath python -ArgumentList '-m','http.server','8000','--bind','0.0.0.0','--directory','work/company_impact_high_quality_v2_candidate/ui'
```

Expected: 本机 `http://127.0.0.1:8000/` 可访问；局域网使用当前主机 IPv4 加 `:8000`。

- [ ] **Step 6: 记录提交检查点**

Commit message: `feat: complete event01 industry research UI sample`。

## Task 9: 全量回归和交付报告

**Files:**

- Generate: `work/event_01_industry_closure_v2_candidate/HANDOFF.md`
- Update: `work/event_01_industry_closure_v2_candidate/validation_report.json`

- [ ] **Step 1: 运行专项回归**

Run:

```powershell
python -m pytest tests/test_fingoose_industry_source_snapshot_v2.py tests/test_fingoose_industry_market_v2.py tests/test_fingoose_event_01_industry_closure_v2.py tests/test_fingoose_industry_impact_v2.py tests/test_fingoose_industry_ui_v2.py tests/test_fingoose_company_impact_market_v2.py tests/test_fingoose_company_impact_ui_v2.py -q
```

Expected: all tests pass。

- [ ] **Step 2: 运行全仓相关测试**

Run:

```powershell
python -m pytest tests -q
```

Expected: no new failures. Existing unrelated failure must be记录为基线差异，不能被本任务静默修改或跳过。

- [ ] **Step 3: 检查发布边界和覆盖隔离**

Run:

```powershell
rg -n '"formal_ready"\s*:\s*true|"sha_gate"\s*:\s*"PASSED"|"review_status"\s*:\s*"CONFIRMED"' work/event_01_industry_closure_v2_candidate
```

Expected: no matches。

使用测试或一次性只读检查确认基线 77 条和覆盖后 77 条 ID 集合一致，`event-02` 至 `event-10` 的 69 条记录语义不变。

- [ ] **Step 4: 写交付报告**

`HANDOFF.md` 必须列出：

- 8 条映射、56 个节点的实际生成计数；
- 已核验与失败来源计数；
- 可用与缺失行情序列；
- `CANDIDATE_COMPLETE/OPEN` 实际分布；
- 每条 OPEN 的阻塞项；
- 八行业混杂等级和挑战集状态；
- 测试命令及实际结果；
- UI 路径和局域网 URL；
- `formal_ready=false / sha_gate=DEFERRED`；
- 工作区没有有效 Git 元数据时的明确说明。

- [ ] **Step 5: 最终提交或变更清单**

若 Git 可用：

```powershell
git add docs/superpowers/plans/2026-08-04-event-01-industry-evidence-market-closure.md configs/industry_impact_v2 code tests requirements-event01-industry.txt work/event_01_industry_closure_v2_candidate work/company_impact_high_quality_v2_candidate/ui/index.html
git commit -m "feat: deliver event01 industry evidence market closure"
```

若 Git 不可用：在 `HANDOFF.md` 列出所有新增和修改路径，并标记 `NO_VALID_GIT_METADATA`。

## 完成定义

实施完成不等于八条都必须被强行标记为 `CANDIDATE_COMPLETE`。完成定义是：八条行业链全部进入真实门禁，所有成功证据与行情均可追溯和复算，所有失败均留下明确阻塞项，UI 不再出现无说明空白内容，且没有任何候选结论越过人工审核和发布边界。




