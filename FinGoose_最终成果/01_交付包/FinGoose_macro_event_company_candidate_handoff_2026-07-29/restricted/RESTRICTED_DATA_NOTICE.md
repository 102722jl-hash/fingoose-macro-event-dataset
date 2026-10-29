# 许可供应商数据限制说明

本交接包不复制 `inputs/commodities/v0.2/inbox/wind/dce_iron_ore` 下约 1.1 GB 的许可供应商原始文件，避免在未确认授权范围时二次分发。

相关文件包括期货交易日历、合约资料、数据字典及可能的供应商行情材料。它们在原项目中的分类为：

```json
{
  "source_class": "LICENSED_VENDOR_DATA",
  "verification_status": "VENDOR_VERIFIED",
  "formal_source_status": "OFFICIAL_CROSSCHECK_REQUIRED"
}
```

`RESTRICTED_DATA_MANIFEST.csv` 记录原项目相对路径、大小和 SHA-256。接手方必须从获授权的原始位置恢复文件，并核对哈希；不得把供应商数据的存在等同于官方交叉验证完成。

`answer_evaluation.distill.jsonl` 仅用于数值提取、单位换算、负数和百分比评测，不属于 30 个公司档案或 60 条事件样本，因此也只在限制清单中登记。

