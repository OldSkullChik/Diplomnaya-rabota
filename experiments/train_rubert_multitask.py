#!/usr/bin/env python
"""Train a compact multi-head RuBERT classifier on a prepared CSV dataset."""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from torch.optim import AdamW
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer, get_linear_schedule_with_warmup


class TextMultiTaskDataset(Dataset):
    def __init__(
        self,
        rows,
        target_cols,
        label_maps,
        tokenizer,
        max_length,
        text_mode,
        cache_tokenization=False,
        tokenization_batch_size=1024,
    ):
        self.rows = rows
        self.target_cols = target_cols
        self.label_maps = label_maps
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.text_mode = text_mode
        self.cached = cache_tokenization
        self.input_ids = None
        self.attention_mask = None
        self.labels = None
        self.sample_weights = None

        if self.cached:
            self._build_cache(tokenization_batch_size)

    def __len__(self):
        return len(self.rows)

    def row_text(self, row):
        text = str(row.get("text", ""))
        if self.text_mode == "post_comment":
            post_text = str(row.get("post_text", ""))
            text = f"[POST] {post_text} [COMMENT] {text}"
        return text

    def row_weight(self, row):
        try:
            return float(row.get("sample_weight", 1.0) or 1.0)
        except ValueError:
            return 1.0

    def _build_cache(self, tokenization_batch_size):
        input_chunks = []
        mask_chunks = []
        texts = [self.row_text(row) for row in self.rows]
        for start in range(0, len(texts), tokenization_batch_size):
            encoded = self.tokenizer(
                texts[start : start + tokenization_batch_size],
                max_length=self.max_length,
                padding="max_length",
                truncation=True,
                return_tensors="pt",
            )
            input_chunks.append(encoded["input_ids"])
            mask_chunks.append(encoded["attention_mask"].to(torch.uint8))
        self.input_ids = torch.cat(input_chunks, dim=0)
        self.attention_mask = torch.cat(mask_chunks, dim=0)
        self.labels = {
            col: torch.tensor([self.label_maps[col][row[col]] for row in self.rows], dtype=torch.long)
            for col in self.target_cols
        }
        self.sample_weights = torch.tensor([self.row_weight(row) for row in self.rows], dtype=torch.float32)

    def __getitem__(self, index):
        row = self.rows[index]
        if self.cached:
            item = {
                "input_ids": self.input_ids[index],
                "attention_mask": self.attention_mask[index],
                "_sample_weight": self.sample_weights[index],
            }
            for col in self.target_cols:
                item[col] = self.labels[col][index]
            return item

        text = self.row_text(row)
        encoded = self.tokenizer(
            text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        item = {
            "input_ids": encoded["input_ids"].squeeze(0),
            "attention_mask": encoded["attention_mask"].squeeze(0),
        }
        for col in self.target_cols:
            item[col] = torch.tensor(self.label_maps[col][row[col]], dtype=torch.long)
        item["_sample_weight"] = torch.tensor(self.row_weight(row), dtype=torch.float32)
        return item


class MultiHeadRuBert(nn.Module):
    def __init__(
        self,
        model_name,
        head_sizes,
        dropout,
        gradient_checkpointing=False,
        freeze_encoder=False,
        unfreeze_last_n_layers=0,
    ):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(model_name)
        if gradient_checkpointing and hasattr(self.encoder, "gradient_checkpointing_enable"):
            self.encoder.gradient_checkpointing_enable()
        hidden_size = self.encoder.config.hidden_size
        self.dropout = nn.Dropout(dropout)
        self.heads = nn.ModuleDict(
            {
                name: nn.Sequential(
                    nn.Linear(hidden_size, hidden_size // 2),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden_size // 2, size),
                )
                for name, size in head_sizes.items()
            }
        )
        self.apply_encoder_freezing(freeze_encoder, unfreeze_last_n_layers)

    def encoder_layers(self):
        encoder = getattr(self.encoder, "encoder", None)
        layers = getattr(encoder, "layer", None)
        if layers is not None:
            return list(layers)
        transformer = getattr(self.encoder, "transformer", None)
        layers = getattr(transformer, "layer", None)
        if layers is not None:
            return list(layers)
        layers = getattr(transformer, "h", None)
        if layers is not None:
            return list(layers)
        return []

    def apply_encoder_freezing(self, freeze_encoder, unfreeze_last_n_layers):
        if not freeze_encoder and not unfreeze_last_n_layers:
            return
        for param in self.encoder.parameters():
            param.requires_grad = False
        if not freeze_encoder:
            for param in self.encoder.parameters():
                param.requires_grad = True
        layers = self.encoder_layers()
        if unfreeze_last_n_layers and layers:
            for layer in layers[-unfreeze_last_n_layers:]:
                for param in layer.parameters():
                    param.requires_grad = True
            for attr in ("pooler",):
                module = getattr(self.encoder, attr, None)
                if module is not None:
                    for param in module.parameters():
                        param.requires_grad = True

    def forward(self, input_ids, attention_mask):
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        pooled = self.dropout(outputs.last_hidden_state[:, 0, :])
        return {name: head(pooled) for name, head in self.heads.items()}


def read_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def build_label_maps(rows, target_cols):
    maps = {}
    for col in target_cols:
        values = sorted({row[col] for row in rows if row.get(col)})
        maps[col] = {value: idx for idx, value in enumerate(values)}
    return maps


def row_sample_weight(row):
    try:
        return float(row.get("sample_weight", 1.0) or 1.0)
    except ValueError:
        return 1.0


def is_gold_row(row):
    return str(row.get("label_source", "")).strip() == "gold_human"


def rows_for_class_weight_source(rows, mode):
    if mode == "none":
        return []
    if mode in {"gold_balanced", "gold_weighted_balanced"}:
        gold_rows = [row for row in rows if is_gold_row(row)]
        return gold_rows or rows
    return rows


def class_weight_counts(rows, col, mode):
    weighted_modes = {"weighted_balanced", "gold_weighted_balanced"}
    if mode in weighted_modes:
        counts = Counter()
        for row in rows:
            counts[row[col]] += row_sample_weight(row)
    else:
        counts = Counter(row[col] for row in rows)
    return counts


def normalized_balanced_weights(counts, label_map, power=1.0, min_weight=0.0, max_weight=0.0):
    total = sum(counts.values())
    if total <= 0:
        return {label: 1.0 for label in label_map}
    weights = {}
    for label in label_map:
        count = max(float(counts.get(label, 0)), 1.0)
        weight = total / (len(label_map) * count)
        if power != 1.0:
            weight = weight**power
        weights[label] = float(weight)

    weighted_mean = sum(float(counts.get(label, 0)) * weight for label, weight in weights.items()) / total
    if weighted_mean > 0:
        weights = {label: float(weight / weighted_mean) for label, weight in weights.items()}
    if min_weight > 0:
        weights = {label: max(weight, min_weight) for label, weight in weights.items()}
    if max_weight > 0:
        weights = {label: min(weight, max_weight) for label, weight in weights.items()}
    return weights


def class_weights(rows, col, label_map, device, mode, power=1.0, min_weight=0.0, max_weight=0.0):
    if mode == "none":
        return None, {}, {}
    source_rows = rows_for_class_weight_source(rows, mode)
    counts = class_weight_counts(source_rows, col, mode)
    weights_by_label = normalized_balanced_weights(
        counts,
        label_map,
        power=power,
        min_weight=min_weight,
        max_weight=max_weight,
    )
    weights = [weights_by_label[label] for label in label_map]
    return torch.tensor(weights, dtype=torch.float32, device=device), weights_by_label, dict(counts)


def load_head_loss_weights(value, target_cols):
    weights = {col: 1.0 for col in target_cols}
    if not value:
        return weights
    path = Path(value)
    try:
        path_exists = path.exists()
    except OSError:
        path_exists = False
    if path_exists:
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = json.loads(value)
    for col, weight in data.items():
        if col in weights:
            weights[col] = float(weight)
    return weights


def load_class_weight_overrides(value, target_cols):
    overrides = {col: {} for col in target_cols}
    if not value:
        return overrides
    path = Path(value)
    try:
        path_exists = path.exists()
    except OSError:
        path_exists = False
    if path_exists:
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = json.loads(value)
    for col, weights in data.items():
        if col not in overrides or not isinstance(weights, dict):
            continue
        overrides[col] = {str(label): float(weight) for label, weight in weights.items()}
    return overrides


def apply_sample_weight_overrides(rows, gold_weight, silver_weight):
    if gold_weight is None and silver_weight is None:
        return
    for row in rows:
        source = str(row.get("label_source", "")).strip()
        if silver_weight is not None and source == "silver_auto":
            row["sample_weight"] = f"{silver_weight:g}"
        elif gold_weight is not None and source == "gold_human":
            row["sample_weight"] = f"{gold_weight:g}"


def split_rows(rows, test_size, val_size, seed):
    split_values = {str(row.get("split", "")).strip().lower() for row in rows}
    if {"train", "val", "test"} <= split_values:
        train = [row for row in rows if str(row.get("split", "")).strip().lower() == "train"]
        val = [row for row in rows if str(row.get("split", "")).strip().lower() == "val"]
        test = [row for row in rows if str(row.get("split", "")).strip().lower() == "test"]
        if not train or not val or not test:
            raise ValueError("fixed split requires non-empty train, val, and test rows")
        return train, val, test

    train_val, test = train_test_split(rows, test_size=test_size, random_state=seed, shuffle=True)
    relative_val = val_size / (1.0 - test_size)
    train, val = train_test_split(train_val, test_size=relative_val, random_state=seed, shuffle=True)
    return train, val, test


def run_epoch(
    model,
    loader,
    target_cols,
    criterions,
    head_loss_weights,
    optimizer,
    scheduler,
    device,
    scaler=None,
    epoch=0,
    log_every_steps=0,
    grad_accum_steps=1,
):
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    all_true = {col: [] for col in target_cols}
    all_pred = {col: [] for col in target_cols}
    grad_accum_steps = max(int(grad_accum_steps), 1)

    if training:
        optimizer.zero_grad(set_to_none=True)

    for step, batch in enumerate(loader, start=1):
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device=device, dtype=torch.long)
        targets = {col: batch[col].to(device) for col in target_cols}
        sample_weight = batch.get("_sample_weight")
        if sample_weight is None:
            sample_weight = torch.ones(input_ids.shape[0], dtype=torch.float32)
        sample_weight = sample_weight.to(device)

        with torch.set_grad_enabled(training):
            use_amp = scaler is not None
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=use_amp):
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                weighted_losses = [
                    criterions[col](outputs[col], targets[col]) * float(head_loss_weights.get(col, 1.0))
                    for col in target_cols
                ]
                head_weight_sum = sum(float(head_loss_weights.get(col, 1.0)) for col in target_cols)
                per_sample_loss = sum(weighted_losses) / max(head_weight_sum, 1e-6)
                loss = (per_sample_loss * sample_weight).sum() / sample_weight.sum().clamp_min(1e-6)

        if training:
            backprop_loss = loss / grad_accum_steps
            should_step = step % grad_accum_steps == 0 or step == len(loader)
            if scaler is not None:
                old_scale = scaler.get_scale()
                scaler.scale(backprop_loss).backward()
                if should_step:
                    scaler.unscale_(optimizer)
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    scaler.step(optimizer)
                    scaler.update()
                    optimizer_stepped = scaler.get_scale() >= old_scale
                else:
                    optimizer_stepped = False
            else:
                backprop_loss.backward()
                if should_step:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step()
                    optimizer_stepped = True
                else:
                    optimizer_stepped = False
            if should_step:
                if optimizer_stepped:
                    scheduler.step()
                optimizer.zero_grad(set_to_none=True)

        total_loss += loss.item()
        for col in target_cols:
            preds = torch.argmax(outputs[col].detach(), dim=1)
            all_true[col].extend(targets[col].detach().cpu().tolist())
            all_pred[col].extend(preds.cpu().tolist())

        if training and log_every_steps and step % log_every_steps == 0:
            running_loss = total_loss / max(step, 1)
            print(f"epoch={epoch} step={step}/{len(loader)} train_loss_so_far={running_loss:.4f}", flush=True)

    metrics = {"loss": total_loss / max(len(loader), 1)}
    for col in target_cols:
        metrics[col] = {
            "accuracy": accuracy_score(all_true[col], all_pred[col]),
            "macro_f1": f1_score(all_true[col], all_pred[col], average="macro", zero_division=0),
            "weighted_f1": f1_score(all_true[col], all_pred[col], average="weighted", zero_division=0),
        }
    return metrics, all_true, all_pred


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--target-cols", nargs="+", required=True)
    parser.add_argument("--text-mode", choices=["comment", "post_comment"], default="post_comment")
    parser.add_argument("--base-model", default="cointegrated/rubert-tiny2")
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--test-size", type=float, default=0.15)
    parser.add_argument("--val-size", type=float, default=0.15)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--max-train-rows", type=int, default=0)
    parser.add_argument("--dropout", type=float, default=0.3)
    parser.add_argument(
        "--class-weight-mode",
        choices=["balanced", "weighted_balanced", "gold_balanced", "gold_weighted_balanced", "none"],
        default="balanced",
    )
    parser.add_argument("--class-weight-power", type=float, default=1.0)
    parser.add_argument("--class-weight-min", type=float, default=0.0)
    parser.add_argument("--class-weight-max", type=float, default=0.0)
    parser.add_argument("--class-weights-json", default="")
    parser.add_argument("--head-loss-weights", default="")
    parser.add_argument("--gold-weight-override", type=float, default=None)
    parser.add_argument("--silver-weight-override", type=float, default=None)
    parser.add_argument("--cache-tokenization", action="store_true")
    parser.add_argument("--tokenization-batch-size", type=int, default=1024)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--log-every-steps", type=int, default=0)
    parser.add_argument("--grad-accum-steps", type=int, default=1)
    parser.add_argument("--gradient-checkpointing", action="store_true")
    parser.add_argument("--freeze-encoder", action="store_true")
    parser.add_argument("--unfreeze-last-n-layers", type=int, default=0)
    parser.add_argument("--save-model", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    set_seed(args.seed)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = [row for row in read_csv(args.input_csv) if all(row.get(col) for col in args.target_cols)]
    apply_sample_weight_overrides(rows, args.gold_weight_override, args.silver_weight_override)
    if args.max_samples and len(rows) > args.max_samples:
        rows = random.sample(rows, args.max_samples)
    if len(rows) < 20:
        raise SystemExit(f"Too few usable rows: {len(rows)}")

    label_maps = build_label_maps(rows, args.target_cols)
    train_rows, val_rows, test_rows = split_rows(rows, args.test_size, args.val_size, args.seed)
    if args.max_train_rows and len(train_rows) > args.max_train_rows:
        train_rows = random.sample(train_rows, args.max_train_rows)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    datasets = {
        "train": TextMultiTaskDataset(
            train_rows,
            args.target_cols,
            label_maps,
            tokenizer,
            args.max_length,
            args.text_mode,
            cache_tokenization=args.cache_tokenization,
            tokenization_batch_size=args.tokenization_batch_size,
        ),
        "val": TextMultiTaskDataset(
            val_rows,
            args.target_cols,
            label_maps,
            tokenizer,
            args.max_length,
            args.text_mode,
            cache_tokenization=args.cache_tokenization,
            tokenization_batch_size=args.tokenization_batch_size,
        ),
        "test": TextMultiTaskDataset(
            test_rows,
            args.target_cols,
            label_maps,
            tokenizer,
            args.max_length,
            args.text_mode,
            cache_tokenization=args.cache_tokenization,
            tokenization_batch_size=args.tokenization_batch_size,
        ),
    }
    loaders = {
        name: DataLoader(
            dataset,
            batch_size=args.batch_size,
            shuffle=(name == "train"),
            num_workers=args.num_workers,
            pin_memory=(device.type == "cuda"),
        )
        for name, dataset in datasets.items()
    }

    model = MultiHeadRuBert(
        args.base_model,
        {col: len(label_maps[col]) for col in args.target_cols},
        dropout=args.dropout,
        gradient_checkpointing=args.gradient_checkpointing,
        freeze_encoder=args.freeze_encoder,
        unfreeze_last_n_layers=args.unfreeze_last_n_layers,
    ).to(device)
    trainable_parameters = sum(param.numel() for param in model.parameters() if param.requires_grad)
    total_parameters = sum(param.numel() for param in model.parameters())
    optimizer = AdamW((param for param in model.parameters() if param.requires_grad), lr=args.lr)
    total_steps = ((len(loaders["train"]) + max(args.grad_accum_steps, 1) - 1) // max(args.grad_accum_steps, 1)) * args.epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=max(total_steps // 10, 1),
        num_training_steps=total_steps,
    )
    class_weight_tensors = {}
    class_weight_values = {}
    class_weight_count_values = {}
    class_weight_overrides = load_class_weight_overrides(args.class_weights_json, args.target_cols)
    for col in args.target_cols:
        weight_tensor, weights_by_label, counts_by_label = class_weights(
            train_rows,
            col,
            label_maps[col],
            device,
            args.class_weight_mode,
            power=args.class_weight_power,
            min_weight=args.class_weight_min,
            max_weight=args.class_weight_max,
        )
        overrides = class_weight_overrides.get(col, {})
        for label, weight in overrides.items():
            if label in weights_by_label:
                weights_by_label[label] = float(weight)
        if weight_tensor is not None:
            weight_tensor = torch.tensor(
                [weights_by_label[label] for label in label_maps[col]],
                dtype=torch.float32,
                device=device,
            )
        class_weight_tensors[col] = weight_tensor
        class_weight_values[col] = weights_by_label
        class_weight_count_values[col] = counts_by_label
    criterions = {
        col: nn.CrossEntropyLoss(
            weight=class_weight_tensors[col],
            reduction="none",
        )
        for col in args.target_cols
    }
    head_loss_weights = load_head_loss_weights(args.head_loss_weights, args.target_cols)
    scaler = torch.amp.GradScaler("cuda") if device.type == "cuda" else None

    history = []
    best_val = -1.0
    best_state = None
    for epoch in range(1, args.epochs + 1):
        train_metrics, _, _ = run_epoch(
            model,
            loaders["train"],
            args.target_cols,
            criterions,
            head_loss_weights,
            optimizer,
            scheduler,
            device,
            scaler,
            epoch=epoch,
            log_every_steps=args.log_every_steps,
            grad_accum_steps=args.grad_accum_steps,
        )
        val_metrics, _, _ = run_epoch(
            model,
            loaders["val"],
            args.target_cols,
            criterions,
            head_loss_weights,
            None,
            None,
            device,
        )
        mean_val_macro = float(np.mean([val_metrics[col]["macro_f1"] for col in args.target_cols]))
        history.append({"epoch": epoch, "train": train_metrics, "val": val_metrics, "mean_val_macro_f1": mean_val_macro})
        print(f"epoch={epoch} train_loss={train_metrics['loss']:.4f} val_macro_f1={mean_val_macro:.4f}", flush=True)
        if mean_val_macro > best_val:
            best_val = mean_val_macro
            best_state = {k: v.detach().cpu() for k, v in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)
    test_metrics, y_true, y_pred = run_epoch(
        model,
        loaders["test"],
        args.target_cols,
        criterions,
        head_loss_weights,
        None,
        None,
        device,
    )

    inverse_maps = {
        col: {idx: label for label, idx in label_maps[col].items()}
        for col in args.target_cols
    }
    reports = {}
    for col in args.target_cols:
        labels = list(range(len(label_maps[col])))
        names = [inverse_maps[col][idx] for idx in labels]
        reports[col] = classification_report(
            y_true[col],
            y_pred[col],
            labels=labels,
            target_names=names,
            output_dict=True,
            zero_division=0,
        )

    result = {
        "input_csv": args.input_csv,
        "base_model": args.base_model,
        "device": str(device),
        "target_cols": args.target_cols,
        "text_mode": args.text_mode,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "grad_accum_steps": args.grad_accum_steps,
        "effective_batch_size": args.batch_size * max(args.grad_accum_steps, 1),
        "max_length": args.max_length,
        "lr": args.lr,
        "dropout": args.dropout,
        "class_weight_mode": args.class_weight_mode,
        "class_weight_power": args.class_weight_power,
        "class_weight_min": args.class_weight_min,
        "class_weight_max": args.class_weight_max,
        "class_weights_json": args.class_weights_json,
        "class_weight_overrides": class_weight_overrides,
        "head_loss_weights": head_loss_weights,
        "class_weights": class_weight_values,
        "class_weight_counts": class_weight_count_values,
        "gradient_checkpointing": args.gradient_checkpointing,
        "freeze_encoder": args.freeze_encoder,
        "unfreeze_last_n_layers": args.unfreeze_last_n_layers,
        "trainable_parameters": trainable_parameters,
        "total_parameters": total_parameters,
        "gold_weight_override": args.gold_weight_override,
        "silver_weight_override": args.silver_weight_override,
        "cache_tokenization": args.cache_tokenization,
        "uses_fixed_split": {"train", "val", "test"} <= {str(row.get("split", "")).strip().lower() for row in rows},
        "max_train_rows": args.max_train_rows,
        "sample_weight_distribution": dict(Counter(str(row.get("sample_weight", "1.0") or "1.0") for row in rows).most_common()),
        "rows": {"total": len(rows), "train": len(train_rows), "val": len(val_rows), "test": len(test_rows)},
        "label_maps": label_maps,
        "history": history,
        "test_metrics": test_metrics,
        "classification_reports": reports,
    }
    write_json(output_dir / "metrics.json", result)
    if args.save_model:
        torch.save(model.state_dict(), output_dir / "model.pt")
        tokenizer.save_pretrained(output_dir / "tokenizer")
    print(json.dumps({"device": str(device), "rows": result["rows"], "test_metrics": test_metrics}, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
