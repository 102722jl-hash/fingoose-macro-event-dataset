# FinGoose v2 图投影与 Data-CI 主任务执行交接

## 1. 交接状态

- 配套设计：`2026-07-30-v2-graph-projection-data-ci-design.md`
- 当前状态：`FUTURE_INFRASTRUCTURE_DESIGN / NOT_IMPLEMENTED`
- 目标：让主任务按“证据时间线 -> 节点传导假设 -> 市场验证 -> 公司暴露 -> KPI 观测 -> 审核”实施十事件扩展

## 2. 预期、T0、窗口与混杂

预期基准分三类：预定发布保存公开共识来源、共识值、实际值和意外值公式；突发冲击没有可靠共识时为 `UNKNOWN`；持续演化使用前一可见状态、公开基准情景或概率分布，并注明依据。

每个资产按自身时区、交易日历、首次公开时间、盘前/盘中/盘后和数据提供方截止时间独立确定 T0。同日多个节点若日频无法区分，标记 `SAME_DAY_UNRESOLVED`，不得强行归属于某一节点。

每个序列保存 `T-60 / T-20 / T-1 / D1 / D3 / D5 / D20 / M3` 的实际日期、绝对值和数据状态，并输出原始变化、标准化变化、相对变化和历史安慰剂分位数。结果必须有公式、输入观测 ID、来源哈希和复算状态；缺失保持 `UNKNOWN` 或 `null`，不能写为 0。

混杂等级为 `CLEAN / MINOR / MATERIAL / DOMINANT / UNRESOLVED`。`MATERIAL` 和 `DOMINANT` 只进入挑战集；`UNRESOLVED` 不强制归因；同一重叠窗口不能重复形成多个干净样本。

## 3. Neo4j 派生投影

投影只读取通过验证的 JSONL，使用稳定业务键和参数化 `MERGE`。每个节点和关系携带来源记录 ID、哈希和投影批次。隐藏标签进入独立受限数据库或完全不投影。staging 验证通过后原子切换别名，不能在 push 到 `main` 后直接覆盖活动库。

以下 Cypher 是未来实现规格，不表示已经执行：

```cypher
CREATE CONSTRAINT event_id_unique IF NOT EXISTS
FOR (n:Event) REQUIRE n.event_id IS UNIQUE;
CREATE CONSTRAINT milestone_id_unique IF NOT EXISTS
FOR (n:Milestone) REQUIRE n.milestone_id IS UNIQUE;
CREATE CONSTRAINT hypothesis_id_unique IF NOT EXISTS
FOR (n:TransmissionHypothesis) REQUIRE n.hypothesis_id IS UNIQUE;
CREATE CONSTRAINT company_id_unique IF NOT EXISTS
FOR (n:Company) REQUIRE n.company_id IS UNIQUE;
CREATE CONSTRAINT exposure_id_unique IF NOT EXISTS
FOR (n:CompanyExposure) REQUIRE n.exposure_id IS UNIQUE;
CREATE CONSTRAINT observation_id_unique IF NOT EXISTS
FOR (n:KPIObservation) REQUIRE n.observation_id IS UNIQUE;
```

参数化导入示例：

```cypher
UNWIND $records AS row
MERGE (e:Event {event_id: row.event_id})
SET e.dataset_version = row.dataset_version,
    e.release_tier = row.release_tier,
    e.projection_run_id = $projection_run_id
MERGE (m:Milestone {milestone_id: row.milestone_id})
SET m.occurred_at = datetime(row.occurred_at),
    m.first_public_at = datetime(row.first_public_at),
    m.fact = row.fact,
    m.visibility = row.visibility,
    m.source_record_sha256 = row.source_record_sha256,
    m.projection_run_id = $projection_run_id
MERGE (e)-[:HAS_MILESTONE]->(m);
```

查询事件节点到公司的候选链：

```cypher
MATCH (e:Event {event_id: $event_id})-[:HAS_MILESTONE]->(m:Milestone)
      -[:ANCHORS]->(h:TransmissionHypothesis)
      -[:AFFECTS_VARIABLE]->(v:IntermediateVariable)
      -[:CREATES_EXPOSURE]->(x:CompanyExposure)
      -[:FOR_COMPANY]->(c:Company)
OPTIONAL MATCH (x)-[:MEASURED_BY]->(k:KPI)-[:HAS_OBSERVATION]->(o:KPIObservation)
RETURN m, h, v, x, c, collect(DISTINCT {kpi: k, observation: o}) AS operating_evidence
ORDER BY m.first_public_at;
```

查询只有行情支持、尚无经营支持的候选链：

```cypher
MATCH (m:Milestone)-[:ANCHORS]->(h:TransmissionHypothesis)
      -[:AFFECTS_VARIABLE]->(:IntermediateVariable)
      -[:CREATES_EXPOSURE]->(x:CompanyExposure)
      -[:FOR_COMPANY]->(c:Company)
WHERE x.market_support_status = 'SUPPORTED'
  AND x.operating_support_status IN ['UNKNOWN', 'CONTRADICTED']
RETURN m.milestone_id, h.hypothesis_id, c.company_id,
       x.market_support_status, x.operating_support_status;
```

## 4. PostgreSQL 审计投影

PostgreSQL 保存：

- `projection_runs`：批次、版本、清单哈希、起止时间和状态；
- `projection_records`：来源记录、哈希、目标类型和导入结果；
- `validation_failures`：规则、记录、严重度和错误详情；
- `review_state_history`：假设和公司暴露的状态历史；
- `market_window_recalculations`：输入、公式版本、结果和差异；
- `release_aliases`：活动公开批次与活动受限批次；
- `audit_access_log`：受限投影访问记录。

PostgreSQL 与 Neo4j 用稳定 ID 和 `projection_run_id` 对齐。任一计数、哈希或关键引用不一致时，批次不得激活。

## 5. Data-CI 流水线

1. `lint`：JSON/JSONL、UTF-8、重复 ID 和枚举。
2. `schema`：逐文件 JSON Schema。
3. `source-integrity`：快照、SHA-256、清单和定位。
4. `timeline`：双时间、阶段、锚点、时区和公开/隐藏边界。
5. `graph-rules`：路径、方向、时滞、条件、失效条件、证据、反证、循环和孤立。
6. `market-recalculation`：复算绝对值、变化率、标准化值、相对值和分位数。
7. `confounder`：重叠窗口、等级和挑战集路由。
8. `leakage`：扫描 D3 后数据、隐藏标签、审核身份和事后结果。
9. `benchmark-isolation`：三个公开示例与七个隐藏/挑战事件级隔离。
10. `manifest`：重新生成并比对记录数、版本和文件哈希。
11. `projection-dry-run`：生成投影包和差异报告，不连接活动库。
12. `staging-sync`：只在受保护分支和授权环境同步 staging。
13. `staging-verify`：路径、计数、哈希、查询契约和回滚演练。
14. `manual-approval`：人工批准发布报告。
15. `activate`：原子切换活动别名；失败时保留上一批次。

硬失败条件：

- Schema、来源或哈希失败；
- 伪造来源、共识值或不可解析引用；
- 截止日后证据或隐藏结果进入公开预测；
- 传导假设缺锚点、证据、方向路径或失效条件；
- 禁止循环、孤立节点或跨事件误连；
- 市场窗口不可复算，或缺失观测却给出数值；
- 重叠窗口重复形成干净归因样本；
- 两种数据库投影计数或哈希不一致；
- `manifest.json` 与产物不一致。

普通 PR 只运行到 dry-run；staging 使用环境级密钥；活动切换需要人工批准；隐藏文件不作为普通 CI artifact；公共页面任务无权读取隐藏凭证；回滚通过恢复上一活动别名完成。

用户原 YAML 的 `python-python-version` 应改为 `python-version`。原“push 到 main 后直连数据库”应改为 dry-run、staging、验证、人工批准和原子激活。

## 6. 十事件实施顺序

第一阶段使用 `event-02 / event-03 / event-04` 三个完整公开示例。每个事件完成来源盘点、高颗粒度双时间线、里程碑和阶段、主次锚点、动态传导假设、预定资产角色、三家公司节点级暴露、行情支持、经营支持、反证、混杂和审核。

三事件只有在人工审核与复算通过后才能作为模板。其余七个事件沿用相同 Schema 和审核规则，但节点数、阶段和资产集合由证据决定，不为模板补造节点，不依据事后走势选择资产。

十事件全部完成后再评估 v2 是否正式发布。三赛道保持独立：时间线还原、传导图构建、方向判断与拒答；不生成综合总分。

主任务执行步骤：

1. 冻结当前 v2 候选包并记录 `manifest.json` 哈希。
2. 新增事件—公司图投影 Schema，不破坏当前市场四层图 Schema。
3. 扩充三个试点事件的里程碑和阶段证据。
4. 生成节点级假设，全部保持 `PROPOSED`。
5. 将 30 家公司映射为 `CompanyExposure`，缺证据保持 `UNKNOWN/PENDING_EVIDENCE`。
6. 分离市场序列、公司 KPI 和 KPI 观测值。
7. 实现规则校验、行情复算和泄漏扫描。
8. 实现幂等 Neo4j/PostgreSQL 导出器和 dry-run 报告。
9. 在 staging 验证计数、哈希、查询和回滚。
10. 人工审核后再决定是否激活内部查询投影。
11. 更新只读中文页面，实现时间线节点与分支、行情、公司暴露、KPI、证据、反证和混杂联动。
12. 三事件验收后扩展其余七个事件。

## 7. 验收标准

- 十个事件 ID 唯一，每个事件至少一个可追溯里程碑。
- 双时间、阶段、引用和来源哈希有效。
- 每条假设均有完整路径、三段方向、时滞、条件、失效条件、证据和反证数组。
- `CONFIRMED/REJECTED` 必须有审核；无禁止循环、孤立节点和误连。
- 同一公司可保留多条不同方向暴露。
- 覆盖盘前、盘中、盘后、跨时区、节假日和缺失观测。
- 日频无法区分同日节点时为 `SAME_DAY_UNRESOLVED`。
- 突发事件无共识时为 `UNKNOWN`。
- 行情支持与经营支持分别计算，SCFI 等行业序列不进入公司 KPI。
- `MATERIAL/DOMINANT` 不进入干净主分数。
- 公开区不含截止日后来源、D5/D20/M3、隐藏标签和事后审核结论。
- 三个公开示例与七个隐藏/挑战事件无事件级交叉泄漏。
- dry-run 不改变活动数据库；staging 失败时活动批次不变；别名切换可回滚。
- 页面选择节点后只显示该节点启动或改变的分支，并展示行情、经营、绝对值、日期、公式、证据、反证和混杂。
- `UNKNOWN` 不显示为 0；桌面和移动端无文本遮挡、溢出或缺失数据误导。

## 8. 最终交付物

- 事件—公司图投影 JSON Schema；
- 当前 v2 到图投影的确定性适配器；
- Neo4j 约束、参数化导入和查询脚本；
- PostgreSQL 审计表与批次同步脚本；
- Data-CI 配置和本地等价验证命令；
- 三事件试点投影与审计报告；
- 十事件扩展后的计数、哈希和泄漏报告；
- 只读中文节点联动页面；
- 回滚说明和发布运行手册。

## 9. 准确状态表述

在实际部署和验收前，不得声称“数据库框架已完全实现”“已可直接部署生产”“传导关系已验证”“30 家公司均完成审计”“Data-CI 已持续运行”“Neo4j/PostgreSQL 已同步”或“v2 已正式发布”。

当前准确表述：

> 已完成节点级动态传导图、派生数据库投影和 Data-CI 的架构设计，可由主任务据此编写实施计划；现有 v2 仍为 `CANDIDATE`，所有传导边保持 `PROPOSED`，数据库与流水线状态为 `NOT_IMPLEMENTED`。
