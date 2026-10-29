# Unified Reasoning Chain Metadata v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将完整、可审计的证据链统一编译到 FinGoose 主数据，并投影到全部 157 条四类 SFT 样本的 metadata，同时让 messages 保留可训练的精简推导。

**Architecture:** 在 `unified_builder.py` 与候选数据之间增加独立的 `reasoning_chain.py` 编译层，生成事件、行业、公司和问答四类规范链。`sft_projector.py` 只读取规范链，生成自包含 metadata 和带关键证据 ID 的消息摘要；`validation.py` 增加图结构、节点状态、证据双向映射和任务特定门禁。原有扁平 metadata 字段继续保留以兼容现有加载器。

**Tech Stack:** Python 3.12、标准库 `json`/`dataclasses`/`typing`、pytest、现有 JSONL 构建和验证脚本。

---

## 文件边界

- Create: `training/fingoose_training/reasoning_chain.py`：证据登记、节点状态传播、四类任务链编译和主路径摘要。
- Modify: `training/fingoose_training/unified_builder.py`：把规范链写入统一事件、行业、公司和问答对象。
- Modify: `training/fingoose_training/sft_projector.py`：复制规范链到 metadata，并生成消息层主路径摘要。
- Modify: `training/fingoose_training/validation.py`：验证新 schema、DAG、证据映射和任务门禁。
- Create: `training/tests/test_reasoning_chain_v1.py`：编译器和状态传播单元测试。
- Create: `training/tests/test_sft_reasoning_chain_v1.py`：真实四类 SFT 投影测试。
- Create: `training/tests/test_validation_reasoning_chain_v1.py`：验证器失败场景测试。
- Modify: `training/tests/test_unified_builder.py`：统一主数据链路断言。
- Modify: `training/tests/test_sft_projector.py`：消息摘要和 metadata 兼容断言。
- Modify: `training/README.md`：记录新 metadata schema 和重建命令。
- Generated: `training/data/unified_events.jsonl`、`training/data/sft_dataset.jsonl`、`training/data/manifest.json`、`training/data/validation_report.json`、`training/data/split_manifest.json`。

项目目录不是有效 Git 仓库，计划中的 commit 步骤改为记录构建产物 SHA 和测试输出，不执行虚假的提交操作。

### Task 1: 编写失败测试和固定 schema

**Files:**
- Create: `training/tests/test_reasoning_chain_v1.py`
- Create: `training/tests/test_sft_reasoning_chain_v1.py`
- Create: `training/tests/test_validation_reasoning_chain_v1.py`

- [ ] **Step 1: 写编译器失败测试**

加入以下测试形态，先导入不存在的 `compile_reasoning_chain` 和 `validate_reasoning_chain`，确保测试先失败：

```python
def test_industry_chain_has_seven_nodes_and_bidirectional_evidence():
    chain = compile_reasoning_chain(
        "INDUSTRY_IMPACT",
        scope=INDUSTRY_FIXTURE,
        evidence_registry=INDUSTRY_EVIDENCE_FIXTURE,
    )
    assert len(chain["nodes"]) == 7
    assert chain["nodes"][0]["status"] == "VERIFIED_SOURCE"
    assert chain["nodes"][1]["status"] == "EVIDENCE_MISSING"
    for evidence in chain["evidence_registry"]:
        for node_id in evidence["supports_node_ids"]:
            assert node_id in {node["node_id"] for node in chain["nodes"]}
```

- [ ] **Step 2: 写状态传播失败测试**

覆盖以下规则：来源事实缺原文时为 `EVIDENCE_MISSING`；其下游推断不能成为 `SUPPORTED_INFERENCE`；行情节点只能是 `CALCULATED_ONLY`；截止日后节点为 `CUTOFF_BLOCKED`。

```python
def test_missing_premise_blocks_supported_inference():
    chain = compile_reasoning_chain("INDUSTRY_IMPACT", scope=BLOCKED_FIXTURE, evidence_registry=[])
    status_by_id = {node["node_id"]: node["status"] for node in chain["nodes"]}
    assert status_by_id["node-2"] == "EVIDENCE_MISSING"
    assert status_by_id["node-5"] == "INFERENCE_ONLY"
```

- [ ] **Step 3: 写真实 SFT 结构失败测试**

构建临时样本后断言四类任务均有 `reasoning_chain_version`、`evidence_registry`、`nodes`、`edges`、`conclusion_lineage`，并断言 messages 的 assistant 包含主路径证据 ID和“证据边界”。

- [ ] **Step 4: 写验证器失败测试**

分别构造重复节点 ID、未知边终点、环、无法到达最终节点、证据反向索引不一致和行业少于七节点的样本，断言验证器抛出稳定错误码。

- [ ] **Step 5: 运行 RED 测试**

运行：

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests/test_reasoning_chain_v1.py training/tests/test_sft_reasoning_chain_v1.py training/tests/test_validation_reasoning_chain_v1.py -q
```

预期：失败，原因是 `reasoning_chain.py` 尚未创建或新字段尚未生成。

### Task 2: 实现规范证据链编译器

**Files:**
- Create: `training/fingoose_training/reasoning_chain.py`
- Test: `training/tests/test_reasoning_chain_v1.py`

- [ ] **Step 1: 定义公开接口和状态常量**

实现以下接口，统一返回普通 `dict`，不返回不可序列化对象：

```python
def compile_reasoning_chain(
    task_type: str,
    *,
    scope: Mapping[str, Any],
    evidence_registry: Sequence[Mapping[str, Any]],
    parent_chain_refs: Sequence[str] = (),
) -> dict[str, Any]: ...

def compile_evidence_registry(
    records: Sequence[Mapping[str, Any]],
    nodes: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]: ...

def propagate_node_status(
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]: ...

def validate_chain_graph(chain: Mapping[str, Any]) -> list[str]: ...

def render_chain_summary(chain: Mapping[str, Any]) -> str: ...
```

- [ ] **Step 2: 编译证据登记表**

为每个 `evidence_id` 合并原文、定位、URL、SHA、发布时间和 `supports_node_ids`。缺证 ID 保留为记录，设置 `missing=true`，不填充伪造字段。节点 `evidence_ids` 与 registry 的 `supports_node_ids` 必须互相登记。

- [ ] **Step 3: 实现节点状态传播**

按以下优先级实现：

```text
可核对原文 + 定位 + 来源       -> VERIFIED_SOURCE
缺原文但登记 evidence_id       -> EVIDENCE_MISSING
关键前提齐全且未阻断           -> SUPPORTED_INFERENCE
推断无直接前提或关键前提缺证   -> INFERENCE_ONLY
公式/行情节点                  -> CALCULATED_ONLY
超过 prediction_cutoff_at      -> CUTOFF_BLOCKED
```

状态传播必须递归检查 `premise_node_ids`，不能仅凭“填写了前提 ID”就判定为支持。

- [ ] **Step 4: 实现四类任务节点编译**

从现有候选数据生成：

- 事件链：里程碑、传导图、市场窗口和混杂。
- 行业链：完整七步机制链，不裁剪节点。
- 公司链：公司业务暴露、经营变量、方向、行情、公告混杂和反证。
- QA 链：根据 `task_type` 提取当前问题所需节点，并写入 `parent_chain_refs`。

- [ ] **Step 5: 实现 DAG、主路径和边界**

为每个链生成 `main_path_node_ids`、`side_branch_node_ids`、`final_node_id` 和 `closure_gate`。用拓扑排序检测环；无法形成完整主路径时保留失败原因，不强行生成闭环。

- [ ] **Step 6: 生成精简消息摘要**

`render_chain_summary()`只渲染主路径的关键节点、证据 ID、三阶段方向和边界，不包含完整原文，保证与现有消息长度门禁兼容。

- [ ] **Step 7: 运行编译器测试**

运行：

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests/test_reasoning_chain_v1.py -q
```

预期：Task 1 的编译器和状态传播测试全部通过。

### Task 3: 将规范链写入统一主数据

**Files:**
- Modify: `training/fingoose_training/unified_builder.py`
- Test: `training/tests/test_unified_builder.py`

- [ ] **Step 1: 在统一 builder 中接入编译器**

在现有事件、行业、公司和 QA 对象完成 join 后调用 `compile_reasoning_chain()`，将结果写入对应对象的 `reasoning_chain`，同时保留原有 `mechanism_chain`、`event_evidence_ids` 和其他兼容字段。

- [ ] **Step 2: 保证 QA 链只引用相关范围**

QA 样本按问题类型裁剪主路径；引用上游链时记录 `parent_chain_refs`，但将当前问题所需节点和 evidence registry 复制到 QA 链中，保证单条 SFT metadata 可独立审计。

- [ ] **Step 3: 增加统一主数据测试**

断言构建结果包含10个事件；每个行业对象包含七步链；每个公司对象包含公司链；每条 QA 记录有问题特定链；原有外键数量和事件级 split 输入不变。

- [ ] **Step 4: 运行 builder 测试**

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests/test_unified_builder.py -q
```

预期：原有测试和新链路断言通过。

### Task 4: 升级 SFT 投影器

**Files:**
- Modify: `training/fingoose_training/sft_projector.py`
- Test: `training/tests/test_sft_projector.py`

- [ ] **Step 1: 扩展 `_sample()` metadata**

保留原字段并增加：

```python
metadata.update(
    {
        "reasoning_chain_version": chain["reasoning_chain_version"],
        "evidence_registry": chain["evidence_registry"],
        "reasoning_chain": chain["reasoning_chain"],
        "conclusion_lineage": chain["conclusion_lineage"],
    }
)
```

- [ ] **Step 2: 修改四类投影函数**

`_event_sample()`、`_industry_sample()`、`_company_sample()` 和 QA 投影函数都从统一主数据读取规范链，不再从原始对象递归搜集后扁平化证据。

- [ ] **Step 3: 保留消息主路径摘要**

在 assistant 内容中加入 `render_chain_summary(chain)`；行业任务必须出现七步状态摘要，QA 任务必须出现当前问题对应的证据 ID和边界。完整节点和原文仍只放 metadata。

- [ ] **Step 4: 增加兼容测试**

断言旧字段仍存在；新字段可 JSON 序列化；消息不含完整原文大段重复；消息总字符不超过2000；assistant 中引用的证据 ID存在于 registry。

- [ ] **Step 5: 运行投影测试**

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests/test_sft_projector.py training/tests/test_sft_reasoning_chain_v1.py -q
```

预期：新旧投影测试全部通过。

### Task 5: 增加发布验证门禁

**Files:**
- Modify: `training/fingoose_training/validation.py`
- Test: `training/tests/test_validation_reasoning_chain_v1.py`

- [ ] **Step 1: 验证 schema 版本和字段类型**

拒绝缺失 `reasoning_chain_version`、非字符串 ID、非法节点状态和非法边关系。

- [ ] **Step 2: 验证图结构**

检查节点唯一、边引用存在、无环、最终节点存在且主路径可达。错误使用稳定代码：`REASONING_NODE_DUPLICATE`、`REASONING_EDGE_UNKNOWN_NODE`、`REASONING_GRAPH_CYCLE`、`REASONING_FINAL_UNREACHABLE`。

- [ ] **Step 3: 验证证据双向关系**

检查节点到 registry 和 registry 到节点完全一致；缺证记录只能标记缺口，不能出现伪造 URL 或原文。

- [ ] **Step 4: 验证任务约束**

行业样本必须七步；公司链必须包含业务暴露节点；行情节点不得成为经营事实的唯一直接前提；截止日阻断节点不得进入主路径。

- [ ] **Step 5: 保留既有发布门禁**

继续验证事件 split、四类任务覆盖、消息角色、2000字符限制、无隐藏字段、metadata 外键和 SHA 绑定。

- [ ] **Step 6: 运行验证测试**

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests/test_validation.py training/tests/test_validation_reasoning_chain_v1.py -q
```

预期：旧验证测试和新增错误场景全部通过。

### Task 6: 更新文档并重建真实产物

**Files:**
- Modify: `training/README.md`
- Generated: `training/data/unified_events.jsonl`
- Generated: `training/data/sft_dataset.jsonl`
- Generated: `training/data/manifest.json`
- Generated: `training/data/split_manifest.json`
- Generated: `training/data/validation_report.json`

- [ ] **Step 1: 更新 README**

记录 metadata schema、四类链路映射、消息与 metadata 的职责差异、缺证状态和验证命令。

- [ ] **Step 2: 重建统一主数据**

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
$env:PYTHONUTF8='1'
python training/scripts/build_unified_dataset.py --config training/configs/dataset.json
```

预期输出：`wrote 10 unified events`，并且每个事件、行业、公司和 QA 对象均有规范链。

- [ ] **Step 3: 重建 SFT 数据**

```powershell
python training/scripts/build_sft_dataset.py --config training/configs/dataset.json
```

预期输出：`wrote 157 SFT samples`。样本总数和四类任务数量不变，只增加 metadata 和消息摘要。

- [ ] **Step 4: 验证并运行回归**

```powershell
python training/scripts/validate_dataset.py --config training/configs/dataset.json
python -m pytest training/tests -q
python -m compileall -q training/fingoose_training training/scripts
```

预期：`validation passed: 0 errors, 0 warnings`，现有测试与新增测试全部通过。

- [ ] **Step 5: 运行训练 dry-run**

```powershell
python training/scripts/train_sft.py --config training/configs/sft_qlora_3b.json --dry-run
```

预期：`ready: true`。该结果只表示数据和配置可用，不代表已执行 GPU 训练。

### Task 7: 做确定性和链路审计

**Files:**
- Test: `training/tests/test_sft_real_dataset.py`
- Generated: `training/data/validation_report.json`

- [ ] **Step 1: 审计样本总量和任务分布**

确认总样本仍为157，四类任务仍为10/77/30/40，事件仍为10个且没有跨 split。

- [ ] **Step 2: 审计链完整性**

统计四类任务的链节点数量、缺证节点数量、主路径长度、证据登记数量和无法闭环数量，写入验证报告的公开统计字段，不写入 evaluator-only 字段。

- [ ] **Step 3: 连续重建并比较 SHA**

连续执行两次 Task 6 的构建流程，比较 `unified_events.jsonl`、`sft_dataset.jsonl`、`split_manifest.json` 和 `validation_report.json` 的 SHA-256；任何差异都作为失败处理。

- [ ] **Step 4: 完成最终验收**

```powershell
$env:PYTHONPATH=(Resolve-Path 'training').Path
python -m pytest training/tests -q
python training/scripts/validate_dataset.py --config training/configs/dataset.json
python training/scripts/train_sft.py --config training/configs/sft_qlora_3b.json --dry-run
```

最终交付只报告数据链、验证结果和 dry-run 状态，不宣称已完成人工审核或真实模型训练。
