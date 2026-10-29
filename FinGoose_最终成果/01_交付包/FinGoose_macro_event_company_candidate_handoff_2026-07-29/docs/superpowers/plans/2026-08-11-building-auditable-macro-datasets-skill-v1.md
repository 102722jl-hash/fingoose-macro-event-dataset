# Building Auditable Macro Datasets Skill v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建可自主发现宏观事件、联网补足候选证据、扩展事件/行业/公司/QA、执行行情与因果门禁并从冻结输入确定性复现 FinGoose 候选训练数据的项目型 Skill。

**Architecture:** 在项目内维护 `building-auditable-macro-datasets` Skill 源码。Codex 负责使用可用搜索与浏览工具进行受控发现和研究判断，Skill 中的 Python 脚本负责稳定运行账本、结构化证据、候选隔离、FinGoose 命令编排和离线 SHA 复现；所有联网结果先冻结为审计产物，离线构建不依赖实时网络。

**Tech Stack:** Python 3.12 标准库、pytest、JSON/JSONL、SHA256、现有 FinGoose Python 构建与验证脚本、Codex Skill `SKILL.md` 和 `agents/openai.yaml`。

**Repository note:** 当前项目目录不是 Git 仓库。每个任务使用定向测试、全量测试和文件 SHA256 作为检查点，不执行虚构 `git commit`。Skill 源码先放在项目的 `skills/` 目录；验证通过后再由用户决定是否安装到个人 Skill 目录。

---

## 文件结构

- Create `skills/building-auditable-macro-datasets/SKILL.md`：触发条件、阶段路由、门禁和停止条件。
- Create `skills/building-auditable-macro-datasets/agents/openai.yaml`：Skill UI 元数据。
- Create `skills/building-auditable-macro-datasets/scripts/macro_dataset_pipeline.py`：统一 CLI、运行状态和 FinGoose 编排。
- Create `skills/building-auditable-macro-datasets/scripts/source_extractors.py`：搜索结果登记、HTML/PDF/文本证据规范化、快照字节保存和快照元数据。
- Create `skills/building-auditable-macro-datasets/scripts/audit_outputs.py`：规范 JSON、稳定 ID、SHA、缺口审计、隔离和复现比较。
- Create `skills/building-auditable-macro-datasets/references/data-contracts.md`：运行产物和四层内容契约。
- Create `skills/building-auditable-macro-datasets/references/source-policy.md`：来源等级、联网边界和受控快照。
- Create `skills/building-auditable-macro-datasets/references/temporal-policy.md`：双时钟和截止时间门禁。
- Create `skills/building-auditable-macro-datasets/references/evidence-gates.md`：证据合并、冲突和隔离原因。
- Create `skills/building-auditable-macro-datasets/references/market-formulas.md`：固定窗口、公式和缺口状态。
- Create `skills/building-auditable-macro-datasets/references/causal-gates.md`：四级因果状态和 ABSTAIN 规则。
- Create `skills/building-auditable-macro-datasets/assets/profiles/fingoose.json`：FinGoose 路径、默认规模和命令适配。
- Create `skills/building-auditable-macro-datasets/tests/conftest.py`：Skill 测试加载帮助函数。
- Create `skills/building-auditable-macro-datasets/tests/test_package.py`：Skill 包与元数据合约。
- Create `skills/building-auditable-macro-datasets/tests/test_run_ledger.py`：运行目录、规范写入和 SHA。
- Create `skills/building-auditable-macro-datasets/tests/test_discovery_and_gaps.py`：事件发现与缺口清单。
- Create `skills/building-auditable-macro-datasets/tests/test_source_extraction.py`：搜索审计和证据规范化。
- Create `skills/building-auditable-macro-datasets/tests/test_gates.py`：来源、时间、证据、行情和因果门禁。
- Create `skills/building-auditable-macro-datasets/tests/test_pipeline.py`：构建、隔离、验证和离线复现。
- Create `skills/building-auditable-macro-datasets/tests/scenarios.json`：无上下文前向测试请求与成功标准。

---

### Task 1: 初始化 Skill 包并锁定发现元数据

**Files:**
- Create: `skills/building-auditable-macro-datasets/SKILL.md`
- Create: `skills/building-auditable-macro-datasets/agents/openai.yaml`
- Create: `skills/building-auditable-macro-datasets/tests/conftest.py`
- Create: `skills/building-auditable-macro-datasets/tests/test_package.py`

- [ ] **Step 1: 写 Skill 包 RED 测试**

```python
from pathlib import Path
import re


SKILL_ROOT = Path(__file__).resolve().parents[1]


def test_skill_package_has_discoverable_metadata():
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\nname: building-auditable-macro-datasets\n")
    assert re.search(r"description: Use when .+", text)
    assert "扩展新的宏观事件" in text
    assert "补足" in text
    assert "可复现" in text


def test_openai_yaml_mentions_the_skill_explicitly():
    text = (SKILL_ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
    assert 'display_name: "可审计宏观数据集"' in text
    assert "$building-auditable-macro-datasets" in text
```

- [ ] **Step 2: 运行 RED 测试**

Run:

```powershell
python -m pytest skills/building-auditable-macro-datasets/tests/test_package.py -q
```

Expected: FAIL，因为 Skill 目录尚不存在。

- [ ] **Step 3: 使用官方初始化器创建 Skill 骨架**

Run:

```powershell
python C:\Users\LL\.codex\skills\.system\skill-creator\scripts\init_skill.py building-auditable-macro-datasets `
  --path skills `
  --resources scripts,references,assets `
  --interface 'display_name=可审计宏观数据集' `
  --interface 'short_description=发现、补全并复现宏观事件训练数据' `
  --interface 'default_prompt=使用 $building-auditable-macro-datasets 扩展一个宏观事件并生成可审计候选数据。'
```

然后将 `SKILL.md` 收缩为以下最小可发现骨架，后续任务再补充完整流程：

```markdown
---
name: building-auditable-macro-datasets
description: Use when expanding macro events, filling missing evidence or market data, building event-linked industry/company/QA records, or verifying reproducible macro research datasets.
---

# Building Auditable Macro Datasets

为宏观事件研究生成可审计候选数据。保持证据、时间、行情、因果和人工审核边界。

## Core Boundaries

- 只使用公开可复核来源支持来源事实。
- 将事前推理与事后验证分开。
- 无法闭环的记录进入隔离区。
- 非 `IDENTIFIED` 一律 `ABSTAIN`。
- 不自动解除 `NEEDS_HUMAN_REVIEW`。

## Supported Requests

- 扩展新的宏观事件。
- 补足现有事件、行业、公司、QA、证据或行情缺口。
- 从冻结输入构建并验证可复现候选数据。
```

- [ ] **Step 4: 运行 GREEN 和官方格式校验**

Run:

```powershell
python -m pytest skills/building-auditable-macro-datasets/tests/test_package.py -q
python C:\Users\LL\.codex\skills\.system\skill-creator\scripts\quick_validate.py skills/building-auditable-macro-datasets
```

Expected: 包测试全部 PASS；`Skill is valid!`。

- [ ] **Step 5: 保存检查点**

Run:

```powershell
Get-FileHash -Algorithm SHA256 `
  skills/building-auditable-macro-datasets/SKILL.md, `
  skills/building-auditable-macro-datasets/agents/openai.yaml
```

记录两个 SHA 到执行报告草稿。

---

### Task 2: 实现规范 JSON、运行账本和 FinGoose Profile

**Files:**
- Create: `skills/building-auditable-macro-datasets/scripts/audit_outputs.py`
- Create: `skills/building-auditable-macro-datasets/assets/profiles/fingoose.json`
- Create: `skills/building-auditable-macro-datasets/tests/test_run_ledger.py`

- [ ] **Step 1: 写运行账本和规范输出 RED 测试**

```python
import json

from audit_outputs import canonical_json, init_run, sha256_path


def test_canonical_json_is_stable():
    left = canonical_json({"b": [2, 1], "a": "中文"})
    right = canonical_json({"a": "中文", "b": [2, 1]})
    assert left == right == '{"a":"中文","b":[2,1]}\n'


def test_init_run_creates_immutable_audit_contract(tmp_path):
    run_dir = init_run(
        tmp_path,
        run_id="run-test-001",
        request={"mode": "audit", "profile": "fingoose"},
    )
    assert json.loads((run_dir / "request.json").read_text(encoding="utf-8")) == {
        "mode": "audit",
        "profile": "fingoose",
        "run_id": "run-test-001",
    }
    assert sha256_path(run_dir / "request.json")
    assert (run_dir / "base_unified_events.jsonl").exists()
    assert (run_dir / "content_candidates.jsonl").exists()
    assert (run_dir / "accepted_content.jsonl").exists()


def test_init_run_refuses_to_overwrite(tmp_path):
    init_run(tmp_path, run_id="run-test-001", request={"mode": "audit"})
    try:
        init_run(tmp_path, run_id="run-test-001", request={"mode": "audit"})
    except FileExistsError:
        pass
    else:
        raise AssertionError("existing run must not be overwritten")
```

- [ ] **Step 2: 运行 RED 测试**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'skills/building-auditable-macro-datasets/scripts').Path
python -m pytest skills/building-auditable-macro-datasets/tests/test_run_ledger.py -q
```

Expected: FAIL，`audit_outputs` 尚不存在。

- [ ] **Step 3: 实现最小规范写入和运行初始化**

```python
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping


RUN_FILES = (
    "base_unified_events.jsonl",
    "discovery_candidates.jsonl",
    "gap_manifest.jsonl",
    "search_plan.jsonl",
    "search_audit.jsonl",
    "evidence_candidates.jsonl",
    "accepted_evidence.jsonl",
    "rejected_evidence.jsonl",
    "content_candidates.jsonl",
    "accepted_content.jsonl",
    "quarantine.jsonl",
)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ) + "\n"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def sha256_path(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def init_run(root: Path, *, run_id: str, request: Mapping[str, Any]) -> Path:
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "snapshots").mkdir()
    write_json(run_dir / "request.json", {**dict(request), "run_id": run_id})
    for name in RUN_FILES:
        (run_dir / name).write_text("", encoding="utf-8", newline="\n")
    return run_dir
```

创建 `fingoose.json`，使用明确值而非环境猜测：

```json
{
  "profile_version": "macro-dataset-profile-v1",
  "project_root": "../../..",
  "dataset_config": "training/configs/dataset.json",
  "training_config": "training/configs/sft_qlora_3b.json",
  "base_unified_events": "training/data/unified_events.jsonl",
  "candidate_work_dir": "work/skill_candidate_runs",
  "research_runs_dir": "work/skill_research_runs",
  "industry_min": 5,
  "industry_max": 10,
  "company_default": 3,
  "qa_default": 4,
  "market_window_keys": ["T0", "D1", "D3", "D5", "D20"],
  "split_policy": {
    "method": "sha256_mod_100",
    "version": "split-v1",
    "train_max": 79,
    "validation_max": 89
  },
  "candidate_build_commands": [
    ["python", "training/scripts/build_sft_dataset.py", "--config", "{run_config}"]
  ],
  "validation_commands": [
    ["python", "training/scripts/validate_dataset.py", "--config", "{run_config}"],
    ["python", "training/scripts/train_sft.py", "--config", "{run_training_config}", "--dry-run"]
  ]
}
```

- [ ] **Step 4: 运行 GREEN 测试**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'skills/building-auditable-macro-datasets/scripts').Path
python -m pytest skills/building-auditable-macro-datasets/tests/test_run_ledger.py -q
```

Expected: 全部 PASS。

- [ ] **Step 5: 保存检查点**

Run:

```powershell
Get-FileHash -Algorithm SHA256 `
  skills/building-auditable-macro-datasets/scripts/audit_outputs.py, `
  skills/building-auditable-macro-datasets/assets/profiles/fingoose.json
```

---

### Task 3: 实现事件发现清单和现有缺口审计

**Files:**
- Create: `skills/building-auditable-macro-datasets/scripts/macro_dataset_pipeline.py`
- Create: `skills/building-auditable-macro-datasets/tests/test_discovery_and_gaps.py`

- [ ] **Step 1: 写发现去重和缺口分类 RED 测试**

```python
from macro_dataset_pipeline import deduplicate_candidates, scan_record_gaps


def test_discovery_candidates_are_deduplicated_by_anchor_and_official_url():
    rows = [
        {"title_zh": "事件 A", "anchor_at": "2026-01-01", "official_seed_urls": ["https://a.test/x"]},
        {"title_zh": "事件 A 重复", "anchor_at": "2026-01-01", "official_seed_urls": ["https://a.test/x"]},
    ]
    result = deduplicate_candidates(rows)
    assert len(result) == 1
    assert result[0]["candidate_event_id"].startswith("candidate-event-")


def test_gap_scan_emits_stable_codes_without_fabricating_values():
    gaps = scan_record_gaps({
        "event_id": "event-x",
        "evidence_registry": [{"evidence_id": "e1", "original_quote": "事实"}],
        "industries": [],
        "companies": [],
        "qa": [],
    })
    assert {row["gap_code"] for row in gaps} == {
        "EVIDENCE_LOCATOR_MISSING",
        "EVIDENCE_URL_MISSING",
        "SUPPORTED_INDUSTRIES_MISSING",
        "SUPPORTED_COMPANIES_MISSING",
        "EVENT_QA_MISSING",
    }
    assert all(row["event_id"] == "event-x" for row in gaps)
```

- [ ] **Step 2: 运行 RED 测试**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'skills/building-auditable-macro-datasets/scripts').Path
python -m pytest skills/building-auditable-macro-datasets/tests/test_discovery_and_gaps.py -q
```

Expected: FAIL，因为发现和审计函数尚不存在。

- [ ] **Step 3: 实现稳定候选 ID、去重和缺口清单**

在 `macro_dataset_pipeline.py` 中实现：

```python
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


def _stable_id(prefix: str, payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}-{sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def deduplicate_candidates(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        urls = sorted(str(value) for value in row.get("official_seed_urls") or [] if value)
        fingerprint = {"anchor_at": str(row.get("anchor_at") or ""), "official_seed_urls": urls}
        key = _stable_id("candidate-event", fingerprint)
        unique.setdefault(key, {**dict(row), "candidate_event_id": key, "deduplication_fingerprint": key})
    return [unique[key] for key in sorted(unique)]


def scan_record_gaps(record: Mapping[str, Any]) -> list[dict[str, str]]:
    event_id = str(record.get("event_id") or "")
    codes: set[str] = set()
    for evidence in record.get("evidence_registry") or []:
        if not evidence.get("original_quote"):
            codes.add("EVIDENCE_QUOTE_MISSING")
        if not evidence.get("locator"):
            codes.add("EVIDENCE_LOCATOR_MISSING")
        if not evidence.get("source_url"):
            codes.add("EVIDENCE_URL_MISSING")
    if not record.get("industries"):
        codes.add("SUPPORTED_INDUSTRIES_MISSING")
    if not record.get("companies"):
        codes.add("SUPPORTED_COMPANIES_MISSING")
    if not record.get("qa"):
        codes.add("EVENT_QA_MISSING")
    return [{"event_id": event_id, "gap_code": code} for code in sorted(codes)]
```

CLI 的 `discover` 读取由 Codex 搜索工具写入的候选 JSONL，调用 `deduplicate_candidates()` 后写 `discovery_candidates.jsonl`；`audit` 读取 profile 指定的统一事件文件，写 `gap_manifest.jsonl`。脚本不得自行臆造搜索结果。

- [ ] **Step 4: 运行 GREEN 测试和 CLI help**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'skills/building-auditable-macro-datasets/scripts').Path
python -m pytest skills/building-auditable-macro-datasets/tests/test_discovery_and_gaps.py -q
python skills/building-auditable-macro-datasets/scripts/macro_dataset_pipeline.py --help
```

Expected: 测试 PASS；help 列出 `discover/audit/enrich/build/validate/reproduce`。

- [ ] **Step 5: 保存检查点**

Run:

```powershell
Get-FileHash -Algorithm SHA256 skills/building-auditable-macro-datasets/scripts/macro_dataset_pipeline.py
```

---

### Task 4: 实现搜索审计、正文提取和受控快照

**Files:**
- Create: `skills/building-auditable-macro-datasets/scripts/source_extractors.py`
- Create: `skills/building-auditable-macro-datasets/tests/test_source_extraction.py`
- Create: `skills/building-auditable-macro-datasets/references/source-policy.md`

- [ ] **Step 1: 写搜索登记和证据提取 RED 测试**

```python
from source_extractors import normalize_search_hit, normalize_evidence_candidate, store_snapshot


def test_search_hit_keeps_query_rank_and_adapter():
    hit = normalize_search_hit(
        query="site:who.int pandemic declaration",
        adapter="fixture-search",
        rank=1,
        url="https://www.who.int/example",
        title="WHO statement",
    )
    assert hit["query"] == "site:who.int pandemic declaration"
    assert hit["adapter"] == "fixture-search"
    assert hit["rank"] == 1
    assert hit["candidate_url"] == "https://www.who.int/example"


def test_evidence_candidate_requires_quote_locator_and_url():
    result = normalize_evidence_candidate({
        "source_url": "https://example.test/official",
        "publisher": "Official publisher",
        "published_at": "2026-01-01T00:00:00Z",
        "original_quote": "Official text",
        "locator": {"type": "html_text", "value": "Official text"},
        "retrieved_at": "2026-01-02T00:00:00Z",
        "snapshot_sha256": "a" * 64,
    })
    assert result["evidence_id"].startswith("evidence-")
    assert result["acceptance_status"] == "CANDIDATE"


def test_search_snippet_cannot_become_source_fact():
    result = normalize_evidence_candidate({
        "source_url": "https://example.test/official",
        "search_snippet": "snippet only",
    })
    assert result["acceptance_status"] == "REJECTED"
    assert result["acceptance_reason"] == "ORIGINAL_QUOTE_MISSING"


def test_store_snapshot_writes_exact_bytes_and_stable_relative_path(tmp_path):
    payload = b"official body"
    result = store_snapshot(
        tmp_path,
        source_url="https://example.test/official",
        content_bytes=payload,
        content_type="text/html",
        retrieved_at="2026-01-02T00:00:00Z",
        allow_raw_storage=True,
    )
    stored = tmp_path / result["snapshot_path"]
    assert stored.read_bytes() == payload
    assert stored.name == f'{result["snapshot_sha256"]}.html'
    assert result["raw_storage_status"] == "STORED"


def test_store_snapshot_honors_raw_storage_policy(tmp_path):
    result = store_snapshot(
        tmp_path,
        source_url="https://example.test/restricted",
        content_bytes=b"licensed body",
        content_type="application/pdf",
        retrieved_at="2026-01-02T00:00:00Z",
        allow_raw_storage=False,
    )
    assert result["snapshot_path"] is None
    assert result["snapshot_sha256"]
    assert result["raw_storage_status"] == "NOT_STORED_BY_POLICY"
    assert not (tmp_path / "snapshots").exists()
```

- [ ] **Step 2: 运行 RED 测试**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'skills/building-auditable-macro-datasets/scripts').Path
python -m pytest skills/building-auditable-macro-datasets/tests/test_source_extraction.py -q
```

Expected: FAIL，`source_extractors` 尚不存在。

- [ ] **Step 3: 实现结构化登记，不在脚本中绑定具体搜索服务**

```python
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping


def _id(prefix: str, value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}-{sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def normalize_search_hit(*, query: str, adapter: str, rank: int, url: str, title: str) -> dict[str, Any]:
    return {
        "search_hit_id": _id("search-hit", {"query": query, "url": url}),
        "query": query,
        "adapter": adapter,
        "rank": int(rank),
        "candidate_url": url,
        "title": title,
    }


def normalize_evidence_candidate(record: Mapping[str, Any]) -> dict[str, Any]:
    clean = dict(record)
    clean["evidence_id"] = clean.get("evidence_id") or _id(
        "evidence",
        {"source_url": clean.get("source_url"), "locator": clean.get("locator")},
    )
    missing = next(
        (code for field, code in (
            ("original_quote", "ORIGINAL_QUOTE_MISSING"),
            ("locator", "LOCATOR_MISSING"),
            ("source_url", "SOURCE_URL_MISSING"),
        ) if not clean.get(field)),
        None,
    )
    clean["acceptance_status"] = "REJECTED" if missing else "CANDIDATE"
    clean["acceptance_reason"] = missing or "PENDING_GATES"
    return clean


def store_snapshot(
    root: Path,
    *,
    source_url: str,
    content_bytes: bytes,
    content_type: str,
    retrieved_at: str,
    allow_raw_storage: bool = True,
) -> dict[str, Any]:
    digest = sha256(content_bytes).hexdigest()
    suffix = {
        "text/html": ".html",
        "application/pdf": ".pdf",
        "application/json": ".json",
        "text/plain": ".txt",
    }.get(content_type.split(";", 1)[0].strip().lower(), ".bin")
    relative_path = None
    status = "NOT_STORED_BY_POLICY"
    if allow_raw_storage:
        snapshot_dir = root / "snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        target = snapshot_dir / f"{digest}{suffix}"
        if target.exists() and target.read_bytes() != content_bytes:
            raise ValueError("snapshot hash collision")
        if not target.exists():
            target.write_bytes(content_bytes)
        relative_path = target.relative_to(root).as_posix()
        status = "STORED"
    return {
        "source_url": source_url,
        "retrieved_at": retrieved_at,
        "content_type": content_type,
        "snapshot_path": relative_path,
        "snapshot_sha256": digest,
        "raw_storage_status": status,
    }
```

`source-policy.md` 必须明确 T1-T4 等级、搜索摘要禁用、访问控制、快照许可、抓取元数据和浏览器回退规则。允许保存原文时，正文提取器必须先把实际响应字节交给 `store_snapshot()`，再从该快照生成结构化证据；不允许保存原文时，保留允许的摘录、定位、URL、抓取时间和内容 SHA，并令 `snapshot_path=null`。

- [ ] **Step 4: 运行 GREEN 测试**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'skills/building-auditable-macro-datasets/scripts').Path
python -m pytest skills/building-auditable-macro-datasets/tests/test_source_extraction.py -q
```

Expected: 全部 PASS。

- [ ] **Step 5: 保存检查点**

Run:

```powershell
Get-FileHash -Algorithm SHA256 `
  skills/building-auditable-macro-datasets/scripts/source_extractors.py, `
  skills/building-auditable-macro-datasets/references/source-policy.md
```

---

### Task 5: 实现来源、双时钟、证据和因果门禁

**Files:**
- Modify: `skills/building-auditable-macro-datasets/scripts/audit_outputs.py`
- Create: `skills/building-auditable-macro-datasets/tests/test_gates.py`
- Create: `skills/building-auditable-macro-datasets/references/temporal-policy.md`
- Create: `skills/building-auditable-macro-datasets/references/evidence-gates.md`
- Create: `skills/building-auditable-macro-datasets/references/causal-gates.md`

- [ ] **Step 1: 写门禁 RED 测试**

```python
from audit_outputs import classify_temporal_role, evaluate_candidate_evidence, validate_causal_gate


def test_post_event_material_is_validation_only():
    assert classify_temporal_role(
        published_at="2026-01-03T00:00:00Z",
        anchor_at="2026-01-01T00:00:00Z",
        declared_role="POST_EVENT_VALIDATION",
    ) == "POST_EVENT_VALIDATION"


def test_post_event_material_cannot_claim_as_of_role():
    assert classify_temporal_role(
        published_at="2026-01-03T00:00:00Z",
        anchor_at="2026-01-01T00:00:00Z",
        declared_role="AS_OF_EVIDENCE",
    ) == "CUTOFF_BLOCKED"


def test_media_source_cannot_support_source_fact():
    result = evaluate_candidate_evidence({
        "source_tier": "T3",
        "statement_class": "SOURCE_FACT",
        "original_quote": "报道转述",
        "locator": "paragraph 2",
        "source_url": "https://media.test/story",
        "temporal_role": "AS_OF_EVIDENCE",
    })
    assert result == {"accepted": False, "reason": "SOURCE_TIER_NOT_ELIGIBLE"}


def test_nonidentified_must_abstain():
    errors = validate_causal_gate({
        "status": "NOT_IDENTIFIED",
        "causal_attribution_allowed": True,
        "causal_conclusion": "CAUSED",
        "gate_results": {},
    })
    assert errors == ["CAUSAL_GATE_CONTRADICTION"]
```

- [ ] **Step 2: 运行 RED 测试**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'skills/building-auditable-macro-datasets/scripts').Path
python -m pytest skills/building-auditable-macro-datasets/tests/test_gates.py -q
```

Expected: FAIL，门禁函数尚不存在。

- [ ] **Step 3: 实现严格门禁**

```python
from datetime import datetime


CAUSAL_STATUSES = {
    "NOT_IDENTIFIED",
    "DESCRIPTIVE_EVENT_STUDY",
    "QUASI_EXPERIMENTAL_CANDIDATE",
    "IDENTIFIED",
}


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def classify_temporal_role(*, published_at: str, anchor_at: str, declared_role: str) -> str:
    if declared_role == "POST_EVENT_VALIDATION":
        return "POST_EVENT_VALIDATION"
    if _time(published_at) > _time(anchor_at):
        return "CUTOFF_BLOCKED"
    return "AS_OF_EVIDENCE"


def evaluate_candidate_evidence(record):
    if record.get("statement_class") == "SOURCE_FACT" and record.get("source_tier") not in {"T1", "T2"}:
        return {"accepted": False, "reason": "SOURCE_TIER_NOT_ELIGIBLE"}
    if record.get("temporal_role") == "CUTOFF_BLOCKED":
        return {"accepted": False, "reason": "CUTOFF_BLOCKED"}
    if not all(record.get(field) for field in ("original_quote", "locator", "source_url")):
        return {"accepted": False, "reason": "SOURCE_EVIDENCE_INCOMPLETE"}
    return {"accepted": True, "reason": "GATES_PASSED"}


def validate_causal_gate(causal):
    status = str(causal.get("status") or "")
    allowed = causal.get("causal_attribution_allowed") is True
    conclusion = causal.get("causal_conclusion")
    gates = causal.get("gate_results") or {}
    contradiction = (
        status not in CAUSAL_STATUSES
        or (status != "IDENTIFIED" and (allowed or conclusion != "ABSTAIN"))
        or (status == "IDENTIFIED" and (not allowed or not gates or not all(value is True for value in gates.values())))
    )
    return ["CAUSAL_GATE_CONTRADICTION"] if contradiction else []
```

References 必须逐字段记录允许的来源等级、三种时间角色、完整证据字段、冲突处理以及全部因果门禁。

- [ ] **Step 4: 运行 GREEN 测试**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'skills/building-auditable-macro-datasets/scripts').Path
python -m pytest skills/building-auditable-macro-datasets/tests/test_gates.py -q
```

Expected: 全部 PASS。

- [ ] **Step 5: 保存检查点**

Run:

```powershell
Get-FileHash -Algorithm SHA256 `
  skills/building-auditable-macro-datasets/references/temporal-policy.md, `
  skills/building-auditable-macro-datasets/references/evidence-gates.md, `
  skills/building-auditable-macro-datasets/references/causal-gates.md
```

---

### Task 6: 固化事件、行业、公司、QA 和行情内容契约

**Files:**
- Create: `skills/building-auditable-macro-datasets/references/data-contracts.md`
- Create: `skills/building-auditable-macro-datasets/references/market-formulas.md`
- Modify: `skills/building-auditable-macro-datasets/assets/profiles/fingoose.json`
- Modify: `skills/building-auditable-macro-datasets/tests/test_package.py`

- [ ] **Step 1: 写 reference 和 profile 合约 RED 测试**

```python
import json


def test_fingoose_profile_keeps_confirmed_defaults(skill_root):
    profile = json.loads(
        (skill_root / "assets/profiles/fingoose.json").read_text(encoding="utf-8")
    )
    assert profile["industry_min"] == 5
    assert profile["industry_max"] == 10
    assert profile["company_default"] == 3
    assert profile["qa_default"] == 4
    assert profile["market_window_keys"] == ["T0", "D1", "D3", "D5", "D20"]
    assert profile["split_policy"] == {
        "method": "sha256_mod_100",
        "version": "split-v1",
        "train_max": 79,
        "validation_max": 89,
    }


def test_references_preserve_event_linked_qa_and_three_distinct_horizons(skill_root):
    contract = (skill_root / "references/data-contracts.md").read_text(encoding="utf-8")
    assert "QA 必须保留所属事件 ID" in contract
    assert "即时" in contract and "短期" in contract and "中期" in contract
    assert "三个阶段不得复用同一陈述" in contract


def test_market_reference_forbids_zero_fill(skill_root):
    text = (skill_root / "references/market-formulas.md").read_text(encoding="utf-8")
    assert "PARTIAL_CALCULATED" in text
    assert "DATA_MISSING" in text
    assert "禁止以零替代缺失值" in text


def test_content_contract_freezes_prose_before_offline_replay(skill_root):
    contract = (skill_root / "references/data-contracts.md").read_text(encoding="utf-8")
    assert "content_candidates.jsonl" in contract
    assert "accepted_content.jsonl" in contract
    assert "offline-replay 不得重新生成或改写研究文字" in contract
```

- [ ] **Step 2: 运行 RED 测试**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'skills/building-auditable-macro-datasets/scripts').Path
python -m pytest skills/building-auditable-macro-datasets/tests/test_package.py -q
```

Expected: FAIL，因为两个 reference 尚不存在。

- [ ] **Step 3: 编写精确内容契约**

`data-contracts.md` 必须包含：

```text
事件层：来源事实、时间线、里程碑、机制、三个不重复阶段、行情、失效条件
行业层：5-10 个证据支持行业、七步机制、经营/财务变量、三个阶段、行情、反证
公司层：默认 3 家、事前业务暴露选样、经营路径、三个阶段、相对收益、混杂和反证
QA 层：证据查询、机制阶段、行情验证、行业公司四类；QA 必须保留所属事件 ID

content_candidates.jsonl：机器门禁前的研究内容候选
accepted_content.jsonl：每行包含 event_id、operation=UPSERT、完整 unified_event、evidence_ids、content_sha256 和可选 split_assignment
accepted_content 的 unified_event 必须包含事件、行业、公司和事件关联 QA 的完整候选内容，不保存依赖隐式会话状态的增量自然语言指令
online-acquire 冻结 accepted_content；offline-replay 不得重新生成或改写研究文字
```

`market-formulas.md` 必须给出以下公式和状态：

```text
company_absolute_return = company_value / company_T_MINUS_1 - 1
market_return = market_value / market_T_MINUS_1 - 1
industry_return = industry_value / industry_T_MINUS_1 - 1
market_relative_return = company_absolute_return - market_return
industry_relative_return = company_absolute_return - industry_return

CALCULATED：三类输入齐全
PARTIAL_CALCULATED：公司与市场齐全、行业缺失并有原因码
DATA_MISSING：关键输入不足并有原因码
禁止以零替代缺失值
```

- [ ] **Step 4: 运行 GREEN 测试**

Run:

```powershell
python -m pytest skills/building-auditable-macro-datasets/tests/test_package.py -q
```

Expected: 全部 PASS。

- [ ] **Step 5: 保存检查点**

Run:

```powershell
Get-FileHash -Algorithm SHA256 `
  skills/building-auditable-macro-datasets/references/data-contracts.md, `
  skills/building-auditable-macro-datasets/references/market-formulas.md
```

---

### Task 7: 实现候选构建、隔离和验证编排

**Files:**
- Modify: `skills/building-auditable-macro-datasets/scripts/macro_dataset_pipeline.py`
- Modify: `skills/building-auditable-macro-datasets/scripts/audit_outputs.py`
- Create: `skills/building-auditable-macro-datasets/tests/test_pipeline.py`

- [ ] **Step 1: 写隔离继续和候选资格 RED 测试**

```python
import json

from audit_outputs import (
    assemble_candidate_master,
    build_event_splits,
    canonical_sha256,
    candidate_eligibility,
    partition_candidates,
)
from macro_dataset_pipeline import write_run_configs


def test_failed_event_is_quarantined_without_blocking_closed_event():
    eligible, quarantine = partition_candidates([
        {"event_id": "event-ok", "closure_status": "CLOSED", "errors": [], "warnings": []},
        {"event_id": "event-bad", "closure_status": "OPEN", "errors": ["SOURCE_EVIDENCE_INCOMPLETE"], "warnings": []},
    ])
    assert [row["event_id"] for row in eligible] == ["event-ok"]
    assert quarantine == [{
        "event_id": "event-bad",
        "quarantine_reasons": ["OPEN", "SOURCE_EVIDENCE_INCOMPLETE"],
    }]


def test_candidate_sft_requires_zero_errors_and_warnings():
    assert candidate_eligibility({"closure_status": "CLOSED", "errors": [], "warnings": []}) is True
    assert candidate_eligibility({"closure_status": "CLOSED", "errors": [], "warnings": ["x"]}) is False


def test_accepted_content_replaces_existing_event_and_adds_new_event():
    base = [
        {"event_id": "event-01", "title_zh": "旧标题"},
        {"event_id": "event-02", "title_zh": "保留事件"},
    ]
    updated = {"event_id": "event-01", "title_zh": "更新标题"}
    added = {"event_id": "event-11", "title_zh": "新增事件"}
    accepted = [
        {
            "event_id": "event-01",
            "operation": "UPSERT",
            "unified_event": updated,
            "evidence_ids": ["evidence-01"],
            "content_sha256": canonical_sha256(updated),
        },
        {
            "event_id": "event-11",
            "operation": "UPSERT",
            "unified_event": added,
            "evidence_ids": ["evidence-11"],
            "content_sha256": canonical_sha256(added),
        },
    ]
    result = assemble_candidate_master(base, accepted)
    assert [row["event_id"] for row in result] == ["event-01", "event-02", "event-11"]
    assert result[0]["title_zh"] == "更新标题"


def test_split_preserves_existing_allows_override_and_hashes_new_events():
    base_splits = {
        "train": ["event-01"],
        "validation": ["event-09"],
        "test": ["event-10"],
    }
    policy = {
        "method": "sha256_mod_100",
        "version": "split-v1",
        "train_max": 79,
        "validation_max": 89,
    }
    accepted = [
        {"event_id": "event-01", "split_assignment": "test"},
        {"event_id": "event-11", "split_assignment": "validation"},
        {"event_id": "event-12"},
    ]
    left = build_event_splits(
        ["event-01", "event-09", "event-10", "event-11", "event-12"],
        base_splits,
        accepted,
        policy,
    )
    right = build_event_splits(
        ["event-01", "event-09", "event-10", "event-11", "event-12"],
        base_splits,
        accepted,
        policy,
    )
    assert "event-01" in left["train"]
    assert "event-11" in left["validation"]
    assert left == right
    assert sum("event-12" in ids for ids in left.values()) == 1


def test_run_configs_point_only_to_run_local_candidate_outputs(tmp_path):
    run_dir = tmp_path / "run-test-001"
    run_dir.mkdir()
    dataset_path, training_path = write_run_configs(
        run_dir,
        {"dataset_version": "v1", "sources": {}, "outputs": {}, "splits": {}},
        {"config_version": "train-v1"},
        {"train": ["event-01"], "validation": [], "test": []},
    )
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    training = json.loads(training_path.read_text(encoding="utf-8"))
    assert dataset["outputs"]["unified_events"] == "candidate_master_data.jsonl"
    assert dataset["outputs"]["sft_dataset"] == "candidate_sft_dataset.jsonl"
    assert dataset["project_root"] == str(run_dir.resolve())
    assert sorted(dataset["sources"]["frozen"]["files"]) == [
        "accepted_content",
        "accepted_evidence",
        "base_dataset_config",
        "base_training_config",
        "base_unified_events",
        "profile",
    ]
    assert training["dataset_config"] == "dataset.run.json"
    assert training["sft_dataset"] == "candidate_sft_dataset.jsonl"
```

- [ ] **Step 2: 运行 RED 测试**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'skills/building-auditable-macro-datasets/scripts').Path
python -m pytest skills/building-auditable-macro-datasets/tests/test_pipeline.py -q
```

Expected: FAIL，候选分层函数尚不存在。

- [ ] **Step 3: 实现候选分层和安全命令编排**

```python
def canonical_sha256(value):
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def candidate_eligibility(record):
    return (
        record.get("closure_status") == "CLOSED"
        and not record.get("errors")
        and not record.get("warnings")
    )


def partition_candidates(records):
    eligible, quarantine = [], []
    for record in sorted(records, key=lambda row: str(row.get("event_id"))):
        if candidate_eligibility(record):
            eligible.append(dict(record))
            continue
        reasons = []
        if record.get("closure_status") != "CLOSED":
            reasons.append(str(record.get("closure_status") or "UNKNOWN_CLOSURE"))
        reasons.extend(str(value) for value in record.get("errors") or [])
        reasons.extend(str(value) for value in record.get("warnings") or [])
        quarantine.append({
            "event_id": str(record.get("event_id") or ""),
            "quarantine_reasons": sorted(set(reasons)),
        })
    return eligible, quarantine


def assemble_candidate_master(base_events, accepted_content):
    by_id = {}
    for event in base_events:
        event_id = str(event.get("event_id") or "")
        if not event_id or event_id in by_id:
            raise ValueError("base events require unique non-empty event_id")
        by_id[event_id] = dict(event)

    accepted_ids = set()
    for record in sorted(accepted_content, key=lambda row: str(row.get("event_id") or "")):
        event_id = str(record.get("event_id") or "")
        unified_event = record.get("unified_event")
        if record.get("operation") != "UPSERT":
            raise ValueError(f"unsupported content operation for {event_id}")
        if event_id in accepted_ids:
            raise ValueError(f"duplicate accepted content for {event_id}")
        if not isinstance(unified_event, dict) or unified_event.get("event_id") != event_id:
            raise ValueError(f"unified event mismatch for {event_id}")
        if not record.get("evidence_ids"):
            raise ValueError(f"accepted content lacks evidence_ids for {event_id}")
        if record.get("content_sha256") != canonical_sha256(unified_event):
            raise ValueError(f"content SHA mismatch for {event_id}")
        accepted_ids.add(event_id)
        by_id[event_id] = dict(unified_event)
    return [by_id[event_id] for event_id in sorted(by_id)]


def _existing_split_index(splits):
    result = {}
    for split_name in ("train", "validation", "test"):
        for event_id in splits.get(split_name, []):
            if event_id in result:
                raise ValueError(f"event appears in multiple splits: {event_id}")
            result[event_id] = split_name
    return result


def _stable_split(event_id, policy):
    if policy.get("method") != "sha256_mod_100":
        raise ValueError("unsupported split method")
    raw = f'{policy["version"]}:{event_id}'.encode("utf-8")
    bucket = int(sha256(raw).hexdigest()[:8], 16) % 100
    if bucket <= int(policy["train_max"]):
        return "train"
    if bucket <= int(policy["validation_max"]):
        return "validation"
    return "test"


def build_event_splits(event_ids, base_splits, accepted_content, policy):
    existing = _existing_split_index(base_splits)
    overrides = {
        str(row["event_id"]): row.get("split_assignment")
        for row in accepted_content
        if row.get("split_assignment") is not None
    }
    output = {"train": [], "validation": [], "test": []}
    for event_id in sorted(event_ids):
        split_name = existing.get(event_id)
        if split_name is None:
            split_name = overrides.get(event_id) or _stable_split(event_id, policy)
        if split_name not in output:
            raise ValueError(f"invalid split for {event_id}: {split_name}")
        output[split_name].append(event_id)
    return output
```

`online-acquire` 完成机器门禁后，把完整统一事件候选写入 `accepted_content.jsonl`，并把当次使用的 profile、基础 dataset 配置、基础 training 配置和基线统一事件分别规范写入 `profile.json`、`base_dataset_config.json`、`base_training_config.json` 和 `base_unified_events.jsonl`。`build` 只调用 `assemble_candidate_master(base_unified_events, accepted_content)`，按 `event_id` 稳定写入 `candidate_master_data.jsonl`；它不得重新联网、调用模型或从自然语言补丁重新生成内容。

在 `macro_dataset_pipeline.py` 中实现 `write_run_configs(run_dir, base_dataset_config, base_training_config, splits)`：

```python
from audit_outputs import write_json


def write_run_configs(run_dir, base_dataset_config, base_training_config, splits):
    dataset = dict(base_dataset_config)
    dataset["project_root"] = str(run_dir.resolve())
    dataset["sources"] = {
        "frozen": {
            "base_dir": ".",
            "files": {
                "profile": "profile.json",
                "base_dataset_config": "base_dataset_config.json",
                "base_training_config": "base_training_config.json",
                "base_unified_events": "base_unified_events.jsonl",
                "accepted_evidence": "accepted_evidence.jsonl",
                "accepted_content": "accepted_content.jsonl",
            },
        },
    }
    dataset.pop("content_alignment", None)
    dataset["outputs"] = {
        "unified_events": "candidate_master_data.jsonl",
        "sft_dataset": "candidate_sft_dataset.jsonl",
        "split_manifest": "split_manifest.json",
        "manifest": "manifest.json",
        "validation_report": "validation_report.json",
    }
    dataset["splits"] = splits
    run_config = run_dir / "dataset.run.json"
    write_json(run_config, dataset)

    training = dict(base_training_config)
    training["dataset_config"] = "dataset.run.json"
    training["sft_dataset"] = "candidate_sft_dataset.jsonl"
    training["dataset_manifest"] = "manifest.json"
    training["validation_report"] = "validation_report.json"
    training["runs_dir"] = "training-dry-runs"
    run_training_config = run_dir / "sft.run.json"
    write_json(run_training_config, training)
    return run_config, run_training_config
```

使用 `subprocess.run(command, cwd=project_root, check=False, shell=False)` 执行 profile 中的参数数组，并仅替换显式的 `{run_config}` 与 `{run_training_config}` 参数。不得拼接 shell 字符串。候选构建只运行 `build_sft_dataset.py`，因为 `candidate_master_data.jsonl` 已经是统一事件输入；不得再次运行 `build_unified_dataset.py` 覆盖它。运行配置和所有候选输出均写入具体目录 `work/skill_research_runs/run-test-001/`，不得覆盖 `training/data`。

`validate` 只有在所有 profile validation commands 返回 0，且 validation report 为 `0 errors / 0 warnings` 时才把 run 标记为 `CANDIDATE_SFT_ELIGIBLE`。所有记录继续保留 `NEEDS_HUMAN_REVIEW` 和 `formal_ready=false`。

- [ ] **Step 4: 运行 GREEN 测试和现有 FinGoose 回归**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'skills/building-auditable-macro-datasets/scripts').Path
python -m pytest skills/building-auditable-macro-datasets/tests/test_pipeline.py -q
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests -q
```

Expected: Skill 测试 PASS；现有 FinGoose 全量测试 PASS。

- [ ] **Step 5: 保存检查点**

Run:

```powershell
Get-FileHash -Algorithm SHA256 `
  skills/building-auditable-macro-datasets/scripts/macro_dataset_pipeline.py, `
  skills/building-auditable-macro-datasets/scripts/audit_outputs.py
```

---

### Task 8: 实现 offline-replay 和双轮 SHA

**Files:**
- Modify: `skills/building-auditable-macro-datasets/scripts/macro_dataset_pipeline.py`
- Modify: `skills/building-auditable-macro-datasets/scripts/audit_outputs.py`
- Modify: `skills/building-auditable-macro-datasets/tests/test_pipeline.py`

- [ ] **Step 1: 写复现 RED 测试**

```python
from pathlib import Path

from audit_outputs import compare_artifact_sets, validate_replay_inputs


def test_replay_artifact_sets_must_have_identical_hashes(tmp_path):
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir()
    right.mkdir()
    for root in (left, right):
        (root / "candidate_master_data.jsonl").write_text('{"event_id":"event-1"}\n', encoding="utf-8")
        (root / "candidate_sft_dataset.jsonl").write_text('{"sample_id":"sample-1"}\n', encoding="utf-8")
        (root / "validation_report.json").write_text('{"valid":true}\n', encoding="utf-8")
    report = compare_artifact_sets(left, right, (
        "candidate_master_data.jsonl", "candidate_sft_dataset.jsonl", "validation_report.json"
    ))
    assert report["stable"] is True
    assert all(row["matches"] for row in report["artifacts"])


def test_replay_detects_changed_artifact(tmp_path):
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "x.json").write_text('{"x":1}\n', encoding="utf-8")
    (right / "x.json").write_text('{"x":2}\n', encoding="utf-8")
    assert compare_artifact_sets(left, right, ("x.json",))["stable"] is False


def test_replay_requires_frozen_evidence_content_baseline_and_configs(tmp_path):
    (tmp_path / "snapshots").mkdir()
    for name in (
        "profile.json",
        "base_dataset_config.json",
        "base_training_config.json",
        "base_unified_events.jsonl",
        "accepted_evidence.jsonl",
    ):
        (tmp_path / name).write_text("{}\n", encoding="utf-8")
    assert validate_replay_inputs(tmp_path) == ["ACCEPTED_CONTENT_MISSING"]
    (tmp_path / "accepted_content.jsonl").write_text("{}\n", encoding="utf-8")
    assert validate_replay_inputs(tmp_path) == []
```

- [ ] **Step 2: 运行 RED 测试**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'skills/building-auditable-macro-datasets/scripts').Path
python -m pytest skills/building-auditable-macro-datasets/tests/test_pipeline.py -q
```

Expected: FAIL，`compare_artifact_sets` 尚不存在。

- [ ] **Step 3: 实现双轮比较和离线约束**

```python
class OfflineNetworkAccessError(RuntimeError):
    pass


class OfflineGenerationAccessError(RuntimeError):
    pass


def compare_artifact_sets(left, right, names):
    artifacts = []
    for name in names:
        left_hash = sha256_path(left / name)
        right_hash = sha256_path(right / name)
        artifacts.append({
            "name": name,
            "left_sha256": left_hash,
            "right_sha256": right_hash,
            "matches": left_hash == right_hash,
        })
    return {"stable": all(row["matches"] for row in artifacts), "artifacts": artifacts}


def validate_replay_inputs(run_dir):
    required = {
        "profile.json": "PROFILE_MISSING",
        "base_dataset_config.json": "BASE_DATASET_CONFIG_MISSING",
        "base_training_config.json": "BASE_TRAINING_CONFIG_MISSING",
        "base_unified_events.jsonl": "BASE_UNIFIED_EVENTS_MISSING",
        "accepted_evidence.jsonl": "ACCEPTED_EVIDENCE_MISSING",
        "accepted_content.jsonl": "ACCEPTED_CONTENT_MISSING",
    }
    errors = [code for name, code in required.items() if not (run_dir / name).is_file()]
    if not (run_dir / "snapshots").is_dir():
        errors.append("SNAPSHOT_DIRECTORY_MISSING")
    return sorted(errors)
```

`reproduce` 必须：

1. 使用 `validate_replay_inputs()` 确认 profile、基础 dataset/training 配置、`base_unified_events.jsonl`、`accepted_evidence.jsonl`、`accepted_content.jsonl` 和快照目录已冻结；
2. 设置 `MACRO_DATASET_OFFLINE=1`；
3. 从冻结的 `base_unified_events.jsonl` 和 `accepted_content.jsonl` 分别装配 `replay-1` 与 `replay-2`，不调用搜索、正文提取、浏览器、模型或任何 prose 生成步骤；
4. 使用冻结配置和 profile 分别生成两个 run-local dataset/training config，再执行 SFT 投影与 validate；
5. 比较 `candidate_master_data.jsonl`、`candidate_sft_dataset.jsonl`、`split_manifest.json` 和 `validation_report.json`；
6. 写 `reproducibility_report.json`；
7. 任一 SHA 不同则返回非零退出码。

离线模式中调用任何搜索、HTTP、浏览器或研究文字生成适配器必须抛出 `OfflineNetworkAccessError` 或 `OfflineGenerationAccessError`。`reproduce` 的调用图只能进入冻结输入加载、`assemble_candidate_master()`、`build_event_splits()`、现有 SFT projector 和验证器。

- [ ] **Step 4: 运行 GREEN 和真实离线复现**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'skills/building-auditable-macro-datasets/scripts').Path
python -m pytest skills/building-auditable-macro-datasets/tests/test_pipeline.py -q
python skills/building-auditable-macro-datasets/scripts/macro_dataset_pipeline.py reproduce `
  --profile skills/building-auditable-macro-datasets/assets/profiles/fingoose.json `
  --run-id run-fingoose-golden-001
```

Expected: 测试 PASS；命令输出 `stable=true`，四个 SHA 全部相同。

- [ ] **Step 5: 保存检查点**

Run:

```powershell
Get-FileHash -Algorithm SHA256 `
  work/skill_research_runs/run-fingoose-golden-001/reproducibility_report.json
```

---

### Task 9: 完成 SKILL.md、前向场景和交付验证

**Files:**
- Modify: `skills/building-auditable-macro-datasets/SKILL.md`
- Modify: `skills/building-auditable-macro-datasets/agents/openai.yaml`
- Create: `skills/building-auditable-macro-datasets/tests/scenarios.json`

- [ ] **Step 1: 写 Skill 工作流缺失 RED 测试**

在 `test_package.py` 增加：

```python
def test_skill_routes_all_confirmed_workflows(skill_root):
    text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    required = (
        "discover", "audit", "enrich", "build", "validate", "reproduce",
        "online-acquire", "offline-replay", "NEEDS_HUMAN_REVIEW",
        "PARTIAL_CALCULATED", "ABSTAIN", "quarantine",
    )
    assert all(value in text for value in required)


def test_skill_routes_references_without_embedding_large_contracts(skill_root):
    text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    for name in (
        "data-contracts.md", "source-policy.md", "temporal-policy.md",
        "evidence-gates.md", "market-formulas.md", "causal-gates.md",
    ):
        assert name in text
    assert len(text.splitlines()) < 500
```

- [ ] **Step 2: 运行 RED 测试**

Run:

```powershell
python -m pytest skills/building-auditable-macro-datasets/tests/test_package.py -q
```

Expected: FAIL，因为最小骨架还没有完整阶段路由。

- [ ] **Step 3: 完成精简 Skill 工作流和场景清单**

`SKILL.md` 必须使用命令式表达并包含：

```text
1. 判断指定事件、受控发现或缺口审计
2. online-acquire：搜索、正文提取、快照、来源分级、双时钟
3. enrich：只写候选工作区
4. build：事件/行业/公司/事件关联 QA
5. validate：证据、行情、因果、编码、关联
6. quarantine：失败事件隔离并继续
7. offline-replay：只读取冻结的 accepted evidence/content、基线和配置进行双轮构建与 SHA，不重新生成研究文字
8. 停止条件：来源冲突、无法定位、映射歧义、行情不可回算
9. 永久边界：NEEDS_HUMAN_REVIEW、formal_ready=false、非 IDENTIFIED 必须 ABSTAIN
```

`scenarios.json` 写入三个不泄漏答案的前向场景：

```json
[
  {
    "scenario_id": "specified-event",
    "prompt": "使用 $building-auditable-macro-datasets 扩展一个给定锚点和官方种子 URL 的宏观事件，生成候选审计目录。",
    "success": ["candidate_master_data", "candidate_sft_or_quarantine", "search_audit", "validation_report"]
  },
  {
    "scenario_id": "controlled-discovery",
    "prompt": "使用 $building-auditable-macro-datasets 搜索给定季度的重要宏观事件，只先生成候选清单。",
    "success": ["discovery_candidates", "no_unselected_event_build"]
  },
  {
    "scenario_id": "offline-replay",
    "prompt": "使用 $building-auditable-macro-datasets 从冻结证据、冻结研究内容、基线和配置离线重建两次并比较 SHA。",
    "success": ["no_network", "no_prose_regeneration", "stable_hashes", "ready_true", "model_loaded_false"]
  }
]
```

- [ ] **Step 4: 运行完整自动验证**

Run:

```powershell
$env:PYTHONPATH=(Resolve-Path 'skills/building-auditable-macro-datasets/scripts').Path
python -m pytest skills/building-auditable-macro-datasets/tests -q
python C:\Users\LL\.codex\skills\.system\skill-creator\scripts\quick_validate.py `
  skills/building-auditable-macro-datasets
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests -q
python -m compileall -q `
  skills/building-auditable-macro-datasets/scripts `
  training/fingoose_training `
  training/scripts
python training/scripts/validate_dataset.py --config training/configs/dataset.json
python training/scripts/train_sft.py --config training/configs/sft_qlora_3b.json --dry-run
```

Expected: Skill 与 FinGoose 测试全部 PASS；Skill 格式有效；compileall 无输出；数据验证 `0 errors / 0 warnings`；dry-run 为 `ready=true`、`model_loaded=false`。

- [ ] **Step 5: 执行前向测试**

在允许创建独立执行上下文的主会话中，分别使用 `scenarios.json` 的三个 prompt 调用未继承本次会话结论的执行者。只提供 Skill 路径、场景 prompt、冻结测试输入和临时输出目录。

每个场景必须满足自己的 `success` 列表；若失败，记录实际输出和失败原因，最小修改 `SKILL.md` 或对应脚本后重新执行。不要把预期答案、已知问题或本次设计结论泄漏给前向测试执行者。

- [ ] **Step 6: 写执行报告和最终 SHA**

Create:

`docs/superpowers/plans/2026-08-11-building-auditable-macro-datasets-skill-v1-execution-report.md`

报告必须记录：

- Skill tests 数量和结果；
- FinGoose tests 数量和结果；
- quick validation、compileall、dataset validation 和 dry-run；
- 三个前向场景结果；
- 黄金样本四个 SHA；
- 尚未执行人工审核、个人目录安装和真实 GPU 训练的边界。

Run:

```powershell
Get-FileHash -Algorithm SHA256 `
  skills/building-auditable-macro-datasets/SKILL.md, `
  skills/building-auditable-macro-datasets/agents/openai.yaml, `
  skills/building-auditable-macro-datasets/scripts/*.py, `
  skills/building-auditable-macro-datasets/assets/profiles/fingoose.json
```

- [ ] **Step 7: 安装决策门禁**

项目内 Skill 验证完成后，向用户展示执行报告和项目内 Skill 路径。只有用户明确要求安装时，才调用 skill-installer 或经批准复制到个人 Skill 目录；未获授权不得修改 `C:\Users\LL\.codex\skills`。
