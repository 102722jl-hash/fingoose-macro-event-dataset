import json

from scripts.build_sft_dataset import main as build_sft_main
from scripts.build_unified_dataset import main as build_unified_main
from scripts.train_sft import main as train_main
from scripts.validate_dataset import main as validate_main
from test_build_cli import _make_config


def test_training_dry_run_validates_data_without_loading_model(scratch_path, capsys):
    root = scratch_path / "training_cli_project"
    root.mkdir(exist_ok=True)
    dataset_config = _make_config(root)
    assert build_unified_main(["--config", str(dataset_config)]) == 0
    assert build_sft_main(["--config", str(dataset_config)]) == 0
    assert validate_main(["--config", str(dataset_config)]) == 0

    train_config = {
        "config_version": "test",
        "experimental": False,
        "model_name_or_path": "not-downloaded/test-model",
        "sft_dataset": "../out/sft_dataset.jsonl",
        "dataset_manifest": "../out/manifest.json",
        "validation_report": "../out/validation_report.json",
        "runs_dir": "../runs",
        "quantization": {"load_in_4bit": True},
        "lora": {"r": 8, "lora_alpha": 16, "target_modules": ["q_proj"]},
        "training": {
            "max_seq_length": 512,
            "per_device_train_batch_size": 1,
            "gradient_accumulation_steps": 1,
            "gradient_checkpointing": True,
        },
    }
    train_config_path = root / "configs" / "train.json"
    train_config_path.write_text(json.dumps(train_config), encoding="utf-8")

    assert train_main(["--config", str(train_config_path), "--dry-run"]) == 0
    output = capsys.readouterr().out
    readiness = json.loads(output.strip().splitlines()[-1])
    assert readiness["ready"] is True
    assert readiness["model_loaded"] is False
    assert readiness["sample_counts"] == {"train": 4, "validation": 0, "test": 0}


def test_training_dry_run_rejects_stale_validation_report(scratch_path, capsys):
    root = scratch_path / "stale_validation_project"
    root.mkdir(exist_ok=True)
    dataset_config = _make_config(root)
    assert build_unified_main(["--config", str(dataset_config)]) == 0
    assert build_sft_main(["--config", str(dataset_config)]) == 0
    assert validate_main(["--config", str(dataset_config)]) == 0

    report_path = root / "out" / "validation_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["validated_artifacts"]["sft_dataset"]["sha256"] = "0" * 64
    report_path.write_text(json.dumps(report), encoding="utf-8")

    train_config = {
        "config_version": "test",
        "experimental": False,
        "model_name_or_path": "not-downloaded/test-model",
        "sft_dataset": "../out/sft_dataset.jsonl",
        "dataset_manifest": "../out/manifest.json",
        "validation_report": "../out/validation_report.json",
        "runs_dir": "../runs",
        "quantization": {"load_in_4bit": True},
        "lora": {"r": 8, "lora_alpha": 16, "target_modules": ["q_proj"]},
        "training": {
            "max_seq_length": 512,
            "per_device_train_batch_size": 1,
            "gradient_accumulation_steps": 1,
            "gradient_checkpointing": True,
        },
    }
    train_config_path = root / "configs" / "train.json"
    train_config_path.write_text(json.dumps(train_config), encoding="utf-8")

    assert train_main(["--config", str(train_config_path), "--dry-run"]) == 1
    readiness = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert readiness["ready"] is False
    assert "validation report does not match sft_dataset.jsonl" in readiness["errors"]
