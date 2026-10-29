# Event-02 Inline Citations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 event-02 的时间线节点和动态传导路径中直接显示可点击的事实与机制来源链接。

**Architecture:** 保持现有 `sources.json` 为唯一来源注册表，在生成的只读页面中建立 `sourceById` 索引，并通过一个行内引用渲染函数解析节点和路径已有的 source ID。缺失、待补证和事后机制来源分别显示明确状态，不改动底层时间线、传导路径或生产 v2 数据。

**Tech Stack:** Python 3.12、标准库 `unittest`、静态 HTML/CSS/JavaScript、Microsoft Edge 无头截图。

---

## File Structure

- Modify: `tests/test_build_fingoose_event_02_rapid_candidate_v2.py`：增加行内引用数据完整性和 HTML 渲染合同测试。
- Modify: `code/build_fingoose_event_02_rapid_candidate_v2.py`：增加引用样式、来源索引和时间线/传导链引用渲染。
- Regenerate: `work/event_02_rapid_candidate_v2/index.html`：生成带行内引用的只读成果页。
- Regenerate: `work/event_02_rapid_candidate_v2/*.json*`：由同一生成器重建，确认业务数据不漂移。

当前目录不是 Git 仓库，因此计划中的完成检查以测试和生成物验证代替提交；不执行初始化仓库、提交或推送。

### Task 1: Define Inline Citation Contract

**Files:**
- Modify: `tests/test_build_fingoose_event_02_rapid_candidate_v2.py`
- Test: `tests/test_build_fingoose_event_02_rapid_candidate_v2.py`

- [ ] **Step 1: Write the failing test**

在 `Event02RapidCandidateTests` 中新增：

```python
def test_timeline_and_paths_render_resolvable_inline_citations(self) -> None:
    self.build()
    timeline = json.loads((self.output / "timeline.json").read_text(encoding="utf-8"))
    paths = json.loads(
        (self.output / "core_transmission_paths.json").read_text(encoding="utf-8")
    )["paths"]
    sources = {
        row["source_id"]: row
        for row in json.loads((self.output / "sources.json").read_text(encoding="utf-8"))
    }
    page = (self.output / "index.html").read_text(encoding="utf-8")

    for node in timeline["nodes"]:
        if node["evidence_status"] == "VERIFIED_EXISTING":
            self.assertTrue(node["source_ids"])
            self.assertTrue(all(sources[source_id]["url"] for source_id in node["source_ids"]))
    self.assertEqual(timeline["nodes"][0]["source_ids"], [])

    for path in paths:
        refs = path["event_fact_evidence"] + [
            ref["source_id"] for ref in path["mechanism_evidence"]
        ]
        self.assertTrue(all(sources[source_id]["url"] for source_id in refs))

    for token in (
        "citationLinks", "事实来源", "事件事实依据", "机制依据",
        "事后机制验证", "暂无已验证引用", 'target="_blank"',
        'rel="noopener noreferrer"',
    ):
        self.assertIn(token, page)
```

- [ ] **Step 2: Run the test and confirm the missing renderer causes failure**

Run:

```powershell
python -m unittest tests.test_build_fingoose_event_02_rapid_candidate_v2.Event02RapidCandidateTests.test_timeline_and_paths_render_resolvable_inline_citations -v
```

Expected: FAIL because `index.html` does not contain `citationLinks` or inline citation labels.

### Task 2: Render Inline Citation Tags

**Files:**
- Modify: `code/build_fingoose_event_02_rapid_candidate_v2.py`
- Test: `tests/test_build_fingoose_event_02_rapid_candidate_v2.py`

- [ ] **Step 1: Add compact, wrapping citation styles**

Add styles inside `_html()`:

```css
.citations{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-top:10px}
.citation-label{font-size:12px;font-weight:700;color:#45535d}
.citation-link{font-size:12px;border:1px solid #aab4bb;padding:5px 7px;text-decoration:none;background:#fff}
.citation-link.mechanism{border-color:#c19a5b;background:#fff9ed;color:#775015}
.citation-empty{font-size:12px;color:#8a5d13}
```

- [ ] **Step 2: Add a single source resolver and citation renderer**

Immediately after page data initialization, add:

```javascript
const sourceById = Object.fromEntries(D.sources.map(s => [s.source_id, s]));
function citationLinks(refs, role) {
  const ids = refs.map(ref => typeof ref === 'string' ? ref : ref.source_id);
  if (!ids.length) return '<span class="citation-empty">暂无已验证引用</span>';
  return ids.map(id => {
    const source = sourceById[id];
    if (!source || !source.url) return '<span class="citation-empty">UNKNOWN · ' + esc(id) + '</span>';
    const postEvent = source.visibility === 'HIDDEN_FROM_PRIMARY_PREDICTION';
    const roleLabel = postEvent ? '事后机制验证' : (role === 'mechanism' ? '机制' : '事实与时间');
    return '<a class="citation-link ' + (role === 'mechanism' ? 'mechanism' : 'fact')
      + '" href="' + esc(source.url) + '" target="_blank" rel="noopener noreferrer">↗ '
      + esc(source.publisher) + ' · ' + roleLabel + '</a>';
  }).join('');
}
```

- [ ] **Step 3: Attach fact links to every timeline node**

Change the timeline node template so the fact and impact summary are followed by:

```javascript
<div class="citations"><span class="citation-label">事实来源</span>${citationLinks(n.source_ids || [], 'fact')}</div>
```

`M01` has an empty `source_ids` list, so it renders “暂无已验证引用” without an `<a>`.

- [ ] **Step 4: Attach separate fact and mechanism links to every path**

Change the path template so the counterevidence is followed by:

```javascript
<div class="citations"><span class="citation-label">事件事实依据</span>${citationLinks(p.event_fact_evidence || [], 'fact')}</div>
<div class="citations"><span class="citation-label">机制依据</span>${citationLinks(p.mechanism_evidence || [], 'mechanism')}</div>
```

- [ ] **Step 5: Run the focused test**

Run the Task 1 command again.

Expected: PASS.

### Task 3: Rebuild And Verify

**Files:**
- Regenerate: `work/event_02_rapid_candidate_v2/`
- Test: `tests/test_build_fingoose_event_02_rapid_candidate_v2.py`

- [ ] **Step 1: Run the complete event-02 test module**

```powershell
python -m unittest tests.test_build_fingoose_event_02_rapid_candidate_v2 -v
```

Expected: 6 tests pass.

- [ ] **Step 2: Rebuild the independent candidate**

```powershell
python code/build_fingoose_event_02_rapid_candidate_v2.py
```

Expected: `hard_failures=[]`, `formal_ready=false`, `production_dataset_modified=false`.

- [ ] **Step 3: Run event-02 and v2 regression tests**

```powershell
python -m unittest tests.test_build_fingoose_event_02_rapid_candidate_v2 tests.test_build_fingoose_24_anchor_transmission_graphs tests.test_build_fingoose_macro_event_attribution_v2 -v
```

Expected: 16 tests pass.

- [ ] **Step 4: Render desktop and mobile screenshots**

Use Edge headless mode to render `index.html` at `1440x1000` and `390x844` into the existing QA image paths.

Expected: both PNG files are non-empty; timeline labels wrap within the node, and path labels remain inside the panel on mobile.

- [ ] **Step 5: Verify the built page contains resolvable links**

Parse `sources.json`, confirm all verified node and path references resolve to non-empty URLs, and scan `index.html` for the four labels, `_blank`, and `noopener noreferrer`.

Expected: zero unresolved verified references and zero validation hard failures.
