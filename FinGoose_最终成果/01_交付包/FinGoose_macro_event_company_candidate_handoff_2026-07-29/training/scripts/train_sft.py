from __future__ import annotations

import argparse
import inspect
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fingoose_training.artifacts import sha256_file, write_json
from fingoose_training.loaders import read_json, read_jsonl


def _resolve(config_path: Path, value: str) -> Path:
    return (config_path.parent / value).resolve()


def build_readiness(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    dataset_path = _resolve(config_path, config["sft_dataset"])
    manifest_path = _resolve(config_path, config["dataset_manifest"])
    validation_path = _resolve(config_path, config["validation_report"])
    samples = read_jsonl(dataset_path, unique_key="sample_id")
    manifest = read_json(manifest_path)
    validation = read_json(validation_path)
    errors: list[str] = []

    if not validation.get("valid"):
        errors.append("validation_report.json is not valid")
    recorded = manifest.get("artifacts", {}).get("sft_dataset", {}).get("sha256")
    actual = sha256_file(dataset_path)
    if recorded != actual:
        errors.append("sft_dataset.jsonl hash does not match manifest")
    validated = (
        validation.get("validated_artifacts", {})
        .get("sft_dataset", {})
        .get("sha256")
    )
    if validated != actual:
        errors.append("validation report does not match sft_dataset.jsonl")
    for sample in samples:
        roles = [message.get("role") for message in sample.get("messages", [])]
        if roles != ["system", "user", "assistant"]:
            errors.append(f"{sample.get('sample_id')}: invalid messages")
            break
    counts = Counter(row.get("split") for row in samples)
    if counts.get("train", 0) == 0:
        errors.append("training split is empty")

    return {
        "ready": not errors,
        "errors": errors,
        "model_loaded": False,
        "model_name_or_path": config.get("model_name_or_path"),
        "experimental": bool(config.get("experimental")),
        "four_bit": bool(config.get("quantization", {}).get("load_in_4bit")),
        "sample_counts": {
            "train": counts.get("train", 0),
            "validation": counts.get("validation", 0),
            "test": counts.get("test", 0),
        },
        "sft_dataset_sha256": actual,
    }


def _run_training(config_path: Path, config: dict[str, Any]) -> Path:
    import torch
    from datasets import Dataset
    from peft import LoraConfig, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    dataset_path = _resolve(config_path, config["sft_dataset"])
    rows = read_jsonl(dataset_path, unique_key="sample_id")
    train_rows = [{"messages": row["messages"]} for row in rows if row["split"] == "train"]
    eval_rows = [
        {"messages": row["messages"]} for row in rows if row["split"] == "validation"
    ]
    quant = config["quantization"]
    compute_dtype = getattr(torch, quant.get("bnb_4bit_compute_dtype", "bfloat16"))
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=quant["load_in_4bit"],
        bnb_4bit_quant_type=quant.get("bnb_4bit_quant_type", "nf4"),
        bnb_4bit_use_double_quant=quant.get("bnb_4bit_use_double_quant", True),
        bnb_4bit_compute_dtype=compute_dtype,
    )
    model_name = config["model_name_or_path"]
    tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=quantization_config,
        device_map="auto",
        torch_dtype=compute_dtype,
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=config["training"].get("gradient_checkpointing", True)
    )
    lora = config["lora"]
    peft_config = LoraConfig(
        r=lora["r"],
        lora_alpha=lora["lora_alpha"],
        lora_dropout=lora.get("lora_dropout", 0.05),
        bias=lora.get("bias", "none"),
        task_type=lora.get("task_type", "CAUSAL_LM"),
        target_modules=lora["target_modules"],
    )

    runs_dir = _resolve(config_path, config["runs_dir"])
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-sft-qlora"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    training = config["training"]
    sft_kwargs: dict[str, Any] = {
        "output_dir": str(run_dir / "checkpoints"),
        "per_device_train_batch_size": training["per_device_train_batch_size"],
        "per_device_eval_batch_size": training.get("per_device_eval_batch_size", 1),
        "gradient_accumulation_steps": training["gradient_accumulation_steps"],
        "gradient_checkpointing": training.get("gradient_checkpointing", True),
        "learning_rate": training.get("learning_rate", 2e-4),
        "num_train_epochs": training.get("num_train_epochs", 3),
        "warmup_ratio": training.get("warmup_ratio", 0.05),
        "logging_steps": training.get("logging_steps", 5),
        "save_strategy": training.get("save_strategy", "epoch"),
        "eval_strategy": training.get("eval_strategy", "epoch") if eval_rows else "no",
        "bf16": training.get("bf16", True),
        "fp16": training.get("fp16", False),
        "seed": training.get("seed", 20260806),
        "report_to": "none",
        "remove_unused_columns": False,
    }
    parameters = inspect.signature(SFTConfig).parameters
    length_key = "max_length" if "max_length" in parameters else "max_seq_length"
    sft_kwargs[length_key] = training["max_seq_length"]
    sft_config = SFTConfig(**sft_kwargs)
    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=Dataset.from_list(train_rows),
        eval_dataset=Dataset.from_list(eval_rows) if eval_rows else None,
        processing_class=tokenizer,
        peft_config=peft_config,
    )
    result = trainer.train()
    adapter_dir = run_dir / "adapter_model"
    trainer.save_model(str(adapter_dir))
    tokenizer.save_pretrained(adapter_dir)
    write_json(run_dir / "training_config.json", config)
    write_json(
        run_dir / "dataset_manifest.json",
        read_json(_resolve(config_path, config["dataset_manifest"])),
    )
    write_json(run_dir / "train_metrics.json", dict(result.metrics))
    return run_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train FinGoose with 4-bit QLoRA SFT.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    config_path = args.config.resolve()
    config = read_json(config_path)
    readiness = build_readiness(config_path, config)
    if args.dry_run:
        print(json.dumps(readiness, ensure_ascii=False, sort_keys=True))
        return 0 if readiness["ready"] else 1
    if not readiness["ready"]:
        print(json.dumps(readiness, ensure_ascii=False, sort_keys=True))
        return 1
    run_dir = _run_training(config_path, config)
    print(json.dumps({"run_dir": str(run_dir), "trained": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
