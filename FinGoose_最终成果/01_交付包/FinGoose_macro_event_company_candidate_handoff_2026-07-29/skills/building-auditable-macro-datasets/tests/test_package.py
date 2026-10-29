import re
import json

import yaml


def _frontmatter(text: str) -> dict[str, object]:
    match = re.match(r"\A---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match is not None
    return yaml.safe_load(match.group(1))


def test_skill_package_has_discoverable_metadata(skill_root):
    text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    metadata = _frontmatter(text)
    assert text.startswith("---\nname: building-auditable-macro-datasets\n")
    assert metadata["name"] == "building-auditable-macro-datasets"
    assert str(metadata["description"]).startswith("Use when ")
    assert "扩展新的宏观事件" in text
    assert "补足" in text
    assert "可复现" in text
    assert "非 `IDENTIFIED` 一律 `ABSTAIN`" in text
    assert "NEEDS_HUMAN_REVIEW" in text
    for directory in ("scripts", "references", "assets"):
        assert (skill_root / directory).is_dir()


def test_openai_yaml_mentions_the_skill_explicitly(skill_root):
    metadata = yaml.safe_load(
        (skill_root / "agents/openai.yaml").read_text(encoding="utf-8")
    )
    assert metadata["interface"]["display_name"] == "可审计宏观数据集"
    assert "$building-auditable-macro-datasets" in metadata["interface"]["default_prompt"]


def test_fingoose_profile_keeps_confirmed_defaults(skill_root):
    profile = json.loads(
        (skill_root / "assets/profiles/fingoose.json").read_text(encoding="utf-8")
    )
    assert profile["industry_min"] == 5
    assert profile["industry_max"] == 10
    assert profile["company_default"] == 3
    assert profile["qa_default"] == 4
    assert profile["market_window_keys"] == ["T_MINUS_1", "T0", "D1", "D3", "D5", "D20"]
    assert profile["audit_policy"] == "strict-claim-closure-v2"
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


def test_skill_preserves_the_confirmed_ui_as_the_only_display_baseline(skill_root):
    skill = (skill_root / "SKILL.md").read_text(encoding="utf-8")
    contract = (skill_root / "references/ui-integration-contract.md").read_text(
        encoding="utf-8"
    )
    assert "ui-integration-contract.md" in skill
    assert "现有 UI 是唯一展示基线" in contract
    assert "不得重构、删除或替换现有 UI" in contract
    assert "单事件接入" in contract
    assert "截图核对" in contract
    assert "批量接入" in contract
    assert "旧数据兼容" in contract
