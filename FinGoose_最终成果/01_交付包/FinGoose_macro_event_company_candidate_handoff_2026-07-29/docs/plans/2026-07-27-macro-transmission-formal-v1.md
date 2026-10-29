# FinGoose 宏观传导链正式集 v1 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 将 10 个公司宏观案例组、20 条研究候选升级为可验证的宏观传导链正式训练子集，并发布到 `outputs/fingoose-formal-v1.0-macro`。

**架构：** 新建正式宏观模块，不修改现有 `fingoose_macro_candidate_v0_3.py` 或其研究候选输出。正式模块读取统一官方证据、可见公司事实、H1 隐藏结果和窗口后隐藏官方行业统计，构建可解析传导链；独立验证器按标签产出 `correct`、`incorrect` 或 `inconclusive`；独立发布器沿用公司分组五折与 Canonical 门槛。

**技术栈：** Python 3.12、标准库、`jsonschema`、现有官方来源快照/哈希策略、现有 `parse_timestamp()` 与 SourcePolicy。

---

## 文件结构

- Create: `schemas/fingoose_macro_transmission_formal_v1.schema.json`
  - 正式宏观传导链记录 Schema。
- Create: `schemas/fingoose_macro_transmission_verification_v1.schema.json`
  - 三标签隐藏验证 Schema。
- Create: `configs/fingoose_macro_transmission_templates_v1.json`
  - 10 家公司的行业传导模板及可接受的官方后验行业统计类别。
- Create: `configs/fingoose_macro_hidden_industry_sources_v1.json`
  - 窗口后官方行业统计目录；每条必须带官方 URL、发布时间、行业类别、快照和哈希字段。
- Create: `fingoose_macro_transmission_formal_v1.py`
  - 传导链选择、记录验证、标签推导和可见性校验。
- Create: `fingoose_macro_transmission_verifier_v1.py`
  - H1 公司结果和隐藏行业统计结果的标签验证。
- Create: `fingoose_macro_transmission_release_v1.py`
  - 20 条宏观样本的来源、去重、五折、Canonical 和发布验收。
- Create: `build_fingoose_macro_transmission_formal_v1.py`
  - 构建候选、隐藏验证和正式发布的 CLI。
- Create: `tests/test_fingoose_macro_transmission_formal_v1.py`
  - 传导链、隐藏隔离和标签验证测试。
- Create: `tests/test_fingoose_macro_transmission_release_v1.py`
  - 宏观正式发布与五折切分测试。

## 正式记录契约

每条正式候选有两个来源于同一公司的预测类型 `industry_transmission` 与 `company_event`，但都含三项标签。核心字段为：

```json
{
  "record_id": "macro-formal-v1-000002-sz-industry-transmission",
  "company": {"company_code": "000002.SZ"},
  "macro_cutoff_at": "2025-04-30T23:59:59+08:00",
  "forecast_window": {"start_date": "2025-05-01", "end_date": "2025-06-30"},
  "transmission_chain": [{
    "indicator_evidence_id": "...",
    "indicator_period": "2025-01_to_2025-03",
    "indicator_direction": "DOWN",
    "transmission_category": "demand",
    "industry_effect": "WEAKENING",
    "company_fact_id": "..."
  }],
  "supporting_indicator_evidence_ids": ["...", "..."],
  "counterevidence_ids": ["..."],
  "alternative_explanation": "...",
  "prediction": {
    "revenue_direction": "DOWN",
    "profit_state": "LOSS_WIDENS",
    "industry_condition": "WEAKENING"
  }
}
```

每条候选至少有 6 条可见官方证据、3 个来源族、2 项支持指标、1 条反证、1 项替代解释和本公司可见年报/Q1 事实。传导节点是公开、简短的领域摘要，不储存 CoT。

### 任务 1：定义正式 Schema 与可见传导链验证

**文件：**
- Create: `schemas/fingoose_macro_transmission_formal_v1.schema.json`
- Create: `tests/test_fingoose_macro_transmission_formal_v1.py`
- Create: `fingoose_macro_transmission_formal_v1.py`

- [ ] **步骤 1：先写失败测试**

```python
def test_validate_formal_macro_record_requires_two_supporting_indicators_and_alternative_explanation(self):
    from fingoose_macro_transmission_formal_v1 import validate_formal_macro_record

    record = self._valid_record()
    record['supporting_indicator_evidence_ids'] = record['supporting_indicator_evidence_ids'][:1]
    record.pop('alternative_explanation')

    errors = validate_formal_macro_record(record, self._visible_evidence())

    self.assertIn('SUPPORTING_INDICATORS_INSUFFICIENT', errors)
    self.assertIn('ALTERNATIVE_EXPLANATION_REQUIRED', errors)
```

- [ ] **步骤 2：运行并确认红灯**

```powershell
& 'C:\Users\LL\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_fingoose_macro_transmission_formal_v1.FormalMacroTransmissionTests.test_validate_formal_macro_record_requires_two_supporting_indicators_and_alternative_explanation -v
```

预期：因模块不存在而失败。

- [ ] **步骤 3：实现最小 Schema 和验证器**

实现 `validate_formal_macro_record(record, visible_evidence)`，执行以下确定性检查：

```python
if len(record['supporting_indicator_evidence_ids']) < 2:
    errors.append('SUPPORTING_INDICATORS_INSUFFICIENT')
if not str(record.get('alternative_explanation', '')).strip():
    errors.append('ALTERNATIVE_EXPLANATION_REQUIRED')
if any(not _is_visible_before_cutoff(evidence[id], record['macro_cutoff_at']) for id in all_input_ids):
    errors.append('VISIBLE_EVIDENCE_INVALID')
```

同时拒绝 H1、窗口后统计、供应商域名、未解析哈希、少于 6 条证据、少于 3 个来源族、缺失公司事实、传导节点引用未知指标或公司事实、以及未引用的反证。

- [ ] **步骤 4：运行该测试并确认绿灯**

运行步骤 2 的命令。预期通过。

### 任务 2：建立行业模板与窗口后官方隐藏统计快照

**文件：**
- Create: `configs/fingoose_macro_transmission_templates_v1.json`
- Create: `configs/fingoose_macro_hidden_industry_sources_v1.json`
- Modify: `fingoose_macro_transmission_formal_v1.py`
- Modify: `tests/test_fingoose_macro_transmission_formal_v1.py`

- [ ] **步骤 1：先写失败测试**

```python
def test_hidden_industry_source_requires_official_snapshot_hash_and_post_window_time(self):
    from fingoose_macro_transmission_formal_v1 import validate_hidden_industry_source

    source = self._hidden_industry_source()
    source['published_at'] = '2025-04-30T23:59:59+08:00'
    source.pop('content_sha256')

    errors = validate_hidden_industry_source(source)

    self.assertIn('HIDDEN_INDUSTRY_SOURCE_NOT_POST_WINDOW', errors)
    self.assertIn('HIDDEN_INDUSTRY_SOURCE_HASH_MISSING', errors)
```

- [ ] **步骤 2：运行并确认红灯**

```powershell
& 'C:\Users\LL\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_fingoose_macro_transmission_formal_v1.FormalMacroTransmissionTests.test_hidden_industry_source_requires_official_snapshot_hash_and_post_window_time -v
```

预期：验证函数缺失而失败。

- [ ] **步骤 3：建立 10 个行业映射和官方后验来源目录**

模板将 10 家公司映射到 `real_estate`、`battery`、`steel`、`petrochemical`、`photovoltaic`、`polyester`、`oil_gas` 或 `semiconductor_equipment`，并为每项记录允许的传导类别。隐藏统计目录每条必须包括：`source_id`、`industry_category`、`source_url`、`published_at`、`media_type`、`local_snapshot_path`、`content_sha256`、`source_policy: public_official_only`、`model_visible: false`。

使用现有官方下载、快照与 SHA-256 验证器获取窗口后发布的 NBS、MIIT、海关总署或国家能源局原始页面/PDF。任何不能证明官方域名、发布时间、快照哈希和行业口径的条目不得写入目录。

- [ ] **步骤 4：实现来源验证并确认绿灯**

`validate_hidden_industry_source()` 必须要求发布时间严格晚于 `2025-06-30T23:59:59+08:00`，官方 URL 通过 SourcePolicy、快照文件存在且 SHA-256 匹配、行业类别是已映射模板类别。运行步骤 2 命令，预期通过。

### 任务 3：生成三标签预测与隐藏验证

**文件：**
- Create: `schemas/fingoose_macro_transmission_verification_v1.schema.json`
- Create: `fingoose_macro_transmission_verifier_v1.py`
- Modify: `fingoose_macro_transmission_formal_v1.py`
- Modify: `tests/test_fingoose_macro_transmission_formal_v1.py`

- [ ] **步骤 1：先写失败测试**

```python
def test_hidden_verification_rejects_post_window_industry_source_in_training_projection(self):
    from fingoose_macro_transmission_verifier_v1 import build_macro_training_projection

    projection = build_macro_training_projection(
        [self._valid_record()], [self._decisive_hidden_verification()],
    )

    self.assertEqual(len(projection), 1)
    serialized = json.dumps(projection[0], ensure_ascii=True, sort_keys=True)
    self.assertNotIn('h1_2025', serialized)
    self.assertNotIn('hidden_industry', serialized)
```

- [ ] **步骤 2：运行并确认红灯**

```powershell
& 'C:\Users\LL\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_fingoose_macro_transmission_formal_v1.FormalMacroTransmissionTests.test_hidden_verification_rejects_post_window_industry_source_in_training_projection -v
```

预期：模块不存在而失败。

- [ ] **步骤 3：实现三标签验证与投影**

每条隐藏验证保存三个标签结果：H1 公司报告只产生 `revenue_direction` 和 `profit_state` 的实际值；窗口后官方行业统计只产生 `industry_condition` 的实际值。`build_macro_training_projection()` 仅在三个状态均属于 `{'correct', 'incorrect'}` 时投影可见输入，且只复制候选的公开字段与验证状态，不复制隐藏证据、实际值、页码、数值或来源 ID。

- [ ] **步骤 4：运行测试并确认绿灯**

运行步骤 2 命令。预期通过；将任一状态改为 `inconclusive` 时投影必须为空。

### 任务 4：发布 20 条宏观正式训练子集

**文件：**
- Create: `fingoose_macro_transmission_release_v1.py`
- Create: `tests/test_fingoose_macro_transmission_release_v1.py`
- Create: `build_fingoose_macro_transmission_formal_v1.py`

- [ ] **步骤 1：先写失败发布测试**

```python
def test_publish_macro_release_requires_twenty_records_and_company_group_folds(self):
    from fingoose_macro_transmission_release_v1 import build_macro_release

    with tempfile.TemporaryDirectory() as directory:
        report = build_macro_release(self._formal_root(), self._research_root(), CANONICAL_PATH, Path(directory))

    self.assertTrue(report['formal_ready'])
    self.assertEqual(report['sample_count'], 20)
    self.assertEqual(report['fold_shape'], {'fold_1': {'train': 16, 'held_out': 4}, 'fold_2': {'train': 16, 'held_out': 4}, 'fold_3': {'train': 16, 'held_out': 4}, 'fold_4': {'train': 16, 'held_out': 4}, 'fold_5': {'train': 16, 'held_out': 4}})
```

- [ ] **步骤 2：运行并确认红灯**

```powershell
& 'C:\Users\LL\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_fingoose_macro_transmission_release_v1.FormalMacroReleaseTests.test_publish_macro_release_requires_twenty_records_and_company_group_folds -v
```

预期：模块不存在而失败。

- [ ] **步骤 3：实现独立发布器和 CLI**

`build_macro_release()` 必须校验 20 条投影、每个公司恰 2 条记录、10 家公司、传导链指纹不重复、来源许可、Canonical SHA-256 和所有三标签验证状态。按公司映射五折：每折留出 2 家公司即 4 条记录，训练 8 家公司即 16 条记录。仅在无记录拒绝和无全局失败时写入：

```text
outputs/fingoose-formal-v1.0-macro/samples.jsonl
outputs/fingoose-formal-v1.0-macro/fold_assignments.jsonl
outputs/fingoose-formal-v1.0-macro/validation_report.json
outputs/fingoose-formal-v1.0-macro/rejected.jsonl
outputs/fingoose-formal-v1.0-macro/release_manifest.json
```

CLI 默认读取正式宏观中间产物并返回 `0` 仅当 `formal_ready` 为真。

- [ ] **步骤 4：运行端到端回归并生成发布集**

```powershell
& 'C:\Users\LL\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest tests.test_fingoose_macro_candidate_v0_3 tests.test_fingoose_forecast_verifier_v0_3 tests.test_fingoose_macro_transmission_formal_v1 tests.test_fingoose_macro_transmission_release_v1 -v
& 'C:\Users\LL\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' build_fingoose_macro_transmission_formal_v1.py
```

预期：20 条样本、零泄漏、零拒绝、五折每折 16 条训练和 4 条留出、Canonical 哈希不变。

## 计划自检

- 规格覆盖：任务 1 覆盖可见传导链与反证；任务 2 覆盖官方窗口后隐藏行业统计；任务 3 覆盖三标签隐藏验证与隔离；任务 4 覆盖 20 条发布、去重、五折与 Canonical。
- 一致性：正式候选使用 `fingoose_macro_transmission_formal_v1`，验证器使用 `fingoose_macro_transmission_verifier_v1`，发布器使用 `fingoose_macro_transmission_release_v1`；所有输出均是 JSON/JSONL。
- 范围：公司业绩正式集与 v0.2 Canonical 不在本计划的修改范围内。
