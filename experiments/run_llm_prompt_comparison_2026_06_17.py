#!/usr/bin/env python
"""Evaluate HF LLMs as prompt-only classifiers for the diploma tasks."""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

import torch
from sklearn.metrics import accuracy_score, f1_score
from transformers import AutoModelForCausalLM, AutoTokenizer


TAXONOMY_INPUT = "data/ml_experiments/teacher_student_full_2026-06-03_01-06/dataset_gold_silver_fixed_split.csv"
OMSU_INPUT = "data/ml_experiments/omsu_score_2026-06-06/dataset_gold_silver_omsu_fixed_split.csv"

TASKS = {
    "taxonomy": {
        "input_csv": TAXONOMY_INPUT,
        "targets": [
            "jkh_relevance",
            "jkh_topic",
            "authority_aspect",
            "sentiment",
            "appeal_type",
            "responsible_party",
            "sarcasm",
            "quality",
        ],
    },
    "omsu": {
        "input_csv": OMSU_INPUT,
        "targets": ["omsu_negative_signal"],
    },
}


AXIS_HINTS = {
    "jkh_relevance": "относится ли запись к ЖКХ",
    "jkh_topic": "конкретная тема ЖКХ",
    "authority_aspect": "аспект работы власти или публичного управления",
    "sentiment": "тональность обращения",
    "appeal_type": "тип обращения",
    "responsible_party": "ответственная сторона",
    "sarcasm": "есть ли сарказм",
    "quality": "качество/пригодность сообщения",
    "omsu_negative_signal": "есть ли негативный сигнал для оценки ОМСУ",
}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def text_for_row(row: dict[str, str], max_chars: int) -> str:
    post_text = (row.get("post_text") or "").strip()
    comment_text = (row.get("text") or "").strip()
    text = f"[POST]\n{post_text}\n\n[COMMENT]\n{comment_text}".strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...[truncated]"
    return text


def label_sets(rows: list[dict[str, str]], targets: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for target in targets:
        counts = Counter(row.get(target, "") for row in rows if row.get(target))
        out[target] = [label for label, _ in counts.most_common()]
    return out


def build_prompt(
    row: dict[str, str],
    targets: list[str],
    labels: dict[str, list[str]],
    max_chars: int,
    no_think: bool = False,
) -> str:
    label_block = []
    for target in targets:
        allowed = ", ".join(labels[target])
        hint = AXIS_HINTS.get(target, target)
        label_block.append(f"- {target}: {hint}. Allowed values: {allowed}")

    control = ""
    if no_think:
        control = "Do not use thinking/reasoning mode. Do not output <think>. Return the JSON object immediately.\n"

    return (
        control +
        "Классифицируй обращение гражданина по заданным полям.\n"
        "Верни только валидный JSON-объект без markdown, пояснений и дополнительного текста.\n"
        "Значения должны быть строго из allowed values.\n\n"
        "Поля:\n"
        + "\n".join(label_block)
        + "\n\nТекст:\n"
        + text_for_row(row, max_chars)
    )


def apply_chat_template(tokenizer: Any, prompt: str, no_think: bool = False) -> str:
    if no_think:
        prompt = prompt.rstrip() + "\n/no_think"
    messages = [
        {
            "role": "system",
            "content": "Ты строгий классификатор обращений по ЖКХ и оценке ОМСУ. Отвечай только JSON.",
        },
        {"role": "user", "content": prompt},
    ]
    if getattr(tokenizer, "chat_template", None):
        try:
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=not no_think,
            )
        except TypeError:
            return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    return messages[0]["content"] + "\n\n" + messages[1]["content"] + "\n\nJSON:"


def parse_json_object(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*?\}", text, flags=re.S)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def choose_device(value: str) -> str:
    if value != "auto":
        return value
    return "cuda" if torch.cuda.is_available() else "cpu"


def model_ref(model_id: str, local_model_root: str, prefer_local: bool) -> str:
    if not prefer_local:
        return model_id
    candidate = Path(local_model_root) / model_id.replace("/", "__")
    return str(candidate) if candidate.exists() else model_id


def load_llm(args: argparse.Namespace) -> tuple[Any, Any, str]:
    ref = model_ref(args.model, args.local_model_root, args.prefer_local)
    device = choose_device(args.device)
    tokenizer = AutoTokenizer.from_pretrained(ref, trust_remote_code=args.trust_remote_code)
    dtype = torch.float16 if device == "cuda" else torch.float32
    model_kwargs: dict[str, Any] = {"torch_dtype": dtype, "trust_remote_code": args.trust_remote_code}
    if args.attn_implementation:
        model_kwargs["attn_implementation"] = args.attn_implementation
    model = AutoModelForCausalLM.from_pretrained(ref, **model_kwargs)
    model.to(device)
    model.eval()
    if tokenizer.pad_token_id is None and tokenizer.eos_token_id is not None:
        tokenizer.pad_token = tokenizer.eos_token
    return tokenizer, model, device


def generate_one(tokenizer: Any, model: Any, device: str, prompt: str, args: argparse.Namespace) -> str:
    input_text = apply_chat_template(tokenizer, prompt, no_think=args.no_think)
    encoded = tokenizer(input_text, return_tensors="pt", truncation=True, max_length=args.max_input_tokens)
    encoded = {key: value.to(device) for key, value in encoded.items()}
    input_len = int(encoded["input_ids"].shape[1])
    generate_kwargs: dict[str, Any] = {
        **encoded,
        "do_sample": False,
        "max_new_tokens": args.max_new_tokens,
        "pad_token_id": tokenizer.pad_token_id or tokenizer.eos_token_id,
        "eos_token_id": tokenizer.eos_token_id,
    }
    if args.no_use_cache:
        generate_kwargs["use_cache"] = False
    with torch.inference_mode():
        output = model.generate(**generate_kwargs)
    generated = output[0][input_len:]
    return tokenizer.decode(generated, skip_special_tokens=True).strip()


def compute_metrics(records: list[dict[str, Any]], targets: list[str], labels: dict[str, list[str]]) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "rows": len(records),
        "parse_rate": sum(1 for row in records if row["parsed"]) / max(len(records), 1),
        "invalid_rate": sum(1 for row in records if row["invalid"]) / max(len(records), 1),
        "targets": {},
    }
    parsed_valid = [row for row in records if row["parsed"] and not row["invalid"]]
    for target in targets:
        y_true = [row["true"][target] for row in parsed_valid]
        y_pred = [row["pred"][target] for row in parsed_valid]
        if not y_true:
            metrics["targets"][target] = {"accuracy": 0.0, "macro_f1": 0.0, "weighted_f1": 0.0, "evaluated": 0}
            continue
        metrics["targets"][target] = {
            "accuracy": accuracy_score(y_true, y_pred),
            "macro_f1": f1_score(y_true, y_pred, labels=labels[target], average="macro", zero_division=0),
            "weighted_f1": f1_score(y_true, y_pred, labels=labels[target], average="weighted", zero_division=0),
            "evaluated": len(y_true),
        }
    macro_values = [payload["macro_f1"] for payload in metrics["targets"].values()]
    metrics["mean_macro_f1"] = sum(macro_values) / max(len(macro_values), 1)
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--task", choices=sorted(TASKS), default="omsu")
    parser.add_argument("--input-csv", default="")
    parser.add_argument("--output-dir", default="data/ml_experiments/llm_prompt_comparison_2026-06-17")
    parser.add_argument("--local-model-root", default="data/hf_models")
    parser.add_argument("--prefer-local", action="store_true")
    parser.add_argument("--split", default="test")
    parser.add_argument("--max-samples", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--trust-remote-code", action="store_true")
    parser.add_argument("--attn-implementation", default="")
    parser.add_argument("--no-think", action="store_true")
    parser.add_argument("--no-use-cache", action="store_true")
    parser.add_argument("--max-input-chars", type=int, default=2400)
    parser.add_argument("--max-input-tokens", type=int, default=2048)
    parser.add_argument("--max-new-tokens", type=int, default=160)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if "qwen3" in args.model.lower():
        args.no_think = True
    task = TASKS[args.task]
    targets = task["targets"]
    input_csv = Path(args.input_csv or task["input_csv"])
    all_rows = [row for row in read_csv_rows(input_csv) if all(row.get(target) for target in targets)]
    rows = [row for row in all_rows if (row.get("split") or "").strip().lower() == args.split.lower()]
    if not rows:
        raise SystemExit(f"No rows found for split={args.split!r} in {input_csv}")

    random.Random(args.seed).shuffle(rows)
    rows = rows[: args.max_samples]
    labels = label_sets(all_rows, targets)

    tokenizer, model, device = load_llm(args)
    started = time.time()
    records: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, 1):
        prompt = build_prompt(row, targets, labels, args.max_input_chars, no_think=args.no_think)
        raw = generate_one(tokenizer, model, device, prompt, args)
        parsed = parse_json_object(raw)
        pred: dict[str, str] = {}
        invalid = parsed is None
        if parsed is not None:
            for target in targets:
                value = str(parsed.get(target, "")).strip()
                pred[target] = value
                if value not in labels[target]:
                    invalid = True

        records.append(
            {
                "record_id": row.get("record_id", ""),
                "true": {target: row.get(target, "") for target in targets},
                "pred": pred,
                "parsed": parsed is not None,
                "invalid": invalid,
                "raw": raw,
            }
        )
        print(f"{idx}/{len(rows)} parsed={parsed is not None} invalid={invalid}", flush=True)

    metrics = compute_metrics(records, targets, labels)
    metrics.update(
        {
            "model": args.model,
            "task": args.task,
            "input_csv": str(input_csv),
            "split": args.split,
            "device": device,
            "elapsed_seconds": time.time() - started,
            "seconds_per_row": (time.time() - started) / max(len(rows), 1),
            "max_samples": args.max_samples,
            "labels": labels,
        }
    )

    slug = args.model.replace("/", "__")
    output_dir = Path(args.output_dir) / args.task / slug
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "metrics.json", metrics)
    write_json(output_dir / "predictions.json", records)
    print(json.dumps(metrics, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
