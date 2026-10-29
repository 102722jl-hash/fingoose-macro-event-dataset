from __future__ import annotations

import argparse
import json
from pathlib import Path

from fingoose_training.artifacts import write_json, write_jsonl
from fingoose_training.loaders import read_json, read_jsonl
from fingoose_training.metrics import evaluate_predictions


def _resolve(config_path: Path, value: str) -> Path:
    return (config_path.parent / value).resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate a FinGoose LoRA adapter.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--adapter", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--max-samples", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    config_path = args.config.resolve()
    config = read_json(config_path)
    samples = [
        row
        for row in read_jsonl(_resolve(config_path, config["sft_dataset"]))
        if row.get("split") == "test"
    ]
    if args.max_samples is not None:
        samples = samples[: args.max_samples]
    if args.dry_run:
        print(
            json.dumps(
                {"ready": bool(samples), "test_samples": len(samples), "model_loaded": False},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0 if samples else 1

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    quant = config["quantization"]
    compute_dtype = getattr(torch, quant.get("bnb_4bit_compute_dtype", "bfloat16"))
    bnb = BitsAndBytesConfig(
        load_in_4bit=quant["load_in_4bit"],
        bnb_4bit_quant_type=quant.get("bnb_4bit_quant_type", "nf4"),
        bnb_4bit_use_double_quant=quant.get("bnb_4bit_use_double_quant", True),
        bnb_4bit_compute_dtype=compute_dtype,
    )
    tokenizer = AutoTokenizer.from_pretrained(config["model_name_or_path"], use_fast=True)
    base = AutoModelForCausalLM.from_pretrained(
        config["model_name_or_path"], quantization_config=bnb, device_map="auto"
    )
    model = PeftModel.from_pretrained(base, args.adapter.resolve())
    predictions = []
    for sample in samples:
        prompt_messages = sample["messages"][:2]
        prompt = tokenizer.apply_chat_template(
            prompt_messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=768,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        generated = output[0][inputs["input_ids"].shape[1] :]
        predictions.append(
            {"sample_id": sample["sample_id"], "text": tokenizer.decode(generated, skip_special_tokens=True)}
        )

    output_dir = (args.output_dir or args.adapter.resolve().parent).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "predictions.jsonl", predictions)
    write_json(
        output_dir / "evaluation_metrics.json",
        evaluate_predictions(samples, predictions),
    )
    print(json.dumps({"evaluated": len(samples), "output_dir": str(output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
