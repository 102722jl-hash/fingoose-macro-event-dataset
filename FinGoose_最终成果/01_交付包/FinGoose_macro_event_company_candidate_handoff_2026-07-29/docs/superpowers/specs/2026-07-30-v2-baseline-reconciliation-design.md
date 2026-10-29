# FinGoose v2 基线协调与可复现构建设计

## 状态与目标

- 状态：APPROVED
- 目标：解释并修复 v2 manifest 哈希漂移，禁止测试改写生产候选目录，并建立可审计的新候选基线。
- 边界：不修改 v1，不改变事件、里程碑、传导图或行情业务内容，不自动提升 formal_ready。

## 根因

v2 构建测试将 output_root 指向 data/market_event_attribution_v2_candidate。构建器又使用当前 UTC 时间写入 manifest.json 与 V2_RELEASE_MANIFEST.json，因此运行测试会重写生产候选包并改变哈希。

## 设计

1. build_dataset 接受显式 generated_at 与可选 release_manifest_path。调用方不传时仍使用当前 UTC，测试必须传固定值。
2. 构建测试使用 TemporaryDirectory 作为 output_root，并把 release manifest 写入临时目录。
3. 新增只读协调器，核对当前 manifest 的每个路径、SHA-256 与记录数；输出到 work/baseline_reconciliation_v2/。
4. baseline_transition.json 同时记录冻结哈希、当前哈希、重建清单哈希、文件级校验和结论。
5. 只有清单自洽、所有记录可解析、所有文件哈希与记录数匹配时，状态才为 READY_FOR_BASELINE_APPROVAL；本次不直接覆盖生产 manifest。
6. 采用新基线是后续独立动作；本轮只产出审核材料并重新验证 FAST_CANDIDATE。

## 验收

- 运行 v2 构建测试前后，生产候选目录哈希完全不变。
- 两次使用相同 generated_at 的临时构建产生相同 manifest 哈希。
- 协调器不写 data/，能识别缺失文件、哈希差异、记录数差异和非法路径。
- 当前 manifest 自洽时生成 READY_FOR_BASELINE_APPROVAL；否则为 BLOCKED。
- FAST_CANDIDATE 继续保持 formal_ready=false。