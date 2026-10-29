import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dataset_config_declares_all_sources_and_disjoint_event_splits():
    config = json.loads((ROOT / "configs" / "dataset.json").read_text(encoding="utf-8"))

    assert set(config["sources"]) == {"macro", "industry", "company", "qa"}
    split_sets = [set(values) for values in config["splits"].values()]
    assert set.union(*split_sets) == {f"event-{index:02d}" for index in range(1, 11)}
    assert all(
        left.isdisjoint(right)
        for index, left in enumerate(split_sets)
        for right in split_sets[index + 1 :]
    )


def test_3b_config_is_the_supported_low_memory_baseline():
    config = json.loads((ROOT / "configs" / "sft_qlora_3b.json").read_text(encoding="utf-8"))

    assert config["quantization"]["load_in_4bit"] is True
    assert config["training"]["max_seq_length"] == 2048
    assert config["training"]["per_device_train_batch_size"] == 1
    assert config["training"]["gradient_checkpointing"] is True
