from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = ROOT / "experiments"
if str(EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(EXPERIMENTS_DIR))


DEFAULT_TAXONOMY_CHECKPOINT = (
    "data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/"
    "final_w03_weighted_lr1e5_e4"
)
DEFAULT_OMSU_CHECKPOINT = (
    "data/ml_experiments/omsu_score_2026-06-06/threshold/"
    "negative_signal_capped_20k"
)


def resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(settings.BASE_DIR) / path


def row_text(row: dict[str, str], text_mode: str) -> str:
    text = str(row.get("text", ""))
    if text_mode == "post_comment":
        return f"[POST] {row.get('post_text', '')} [COMMENT] {text}"
    return text


def apply_taxonomy_consistency_rules(pred_taxonomy_row: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    adjusted = dict(pred_taxonomy_row)
    rules: list[str] = []
    if adjusted.get("jkh_relevance") == "no":
        if adjusted.get("jkh_topic") != "not_jkh":
            adjusted["jkh_topic"] = "not_jkh"
            rules.append("jkh_relevance=no -> jkh_topic=not_jkh")
        if adjusted.get("authority_aspect") != "not_applicable":
            adjusted["authority_aspect"] = "not_applicable"
            rules.append("jkh_relevance=no -> authority_aspect=not_applicable")
        if adjusted.get("responsible_party") != "not_applicable":
            adjusted["responsible_party"] = "not_applicable"
            rules.append("jkh_relevance=no -> responsible_party=not_applicable")
    return adjusted, rules


def omsu_decision(
    probability: float,
    negative_threshold: float,
    nonnegative_threshold: float,
    *,
    score: int | None = None,
    strong_score_negative_threshold: int = -60,
    strong_score_probability_threshold: float = 0.65,
) -> tuple[str, str, float]:
    if probability >= negative_threshold:
        return "negative_omsu", "high_negative", 1.0
    if (
        score is not None
        and score <= strong_score_negative_threshold
        and probability >= strong_score_probability_threshold
    ):
        return "negative_omsu", "strong_score_negative", 0.75
    if score is not None and score <= strong_score_negative_threshold and probability <= nonnegative_threshold:
        return "low_confidence", "conflicting_strong_score", 0.0
    if probability <= nonnegative_threshold:
        return "not_negative_omsu", "high_not_negative", 1.0
    return "low_confidence", "low_confidence", 0.0


class CascadeAnalyzer:
    def __init__(
        self,
        *,
        taxonomy_checkpoint: str = DEFAULT_TAXONOMY_CHECKPOINT,
        omsu_checkpoint: str = DEFAULT_OMSU_CHECKPOINT,
        negative_threshold: float = 0.85,
        nonnegative_threshold: float = 0.15,
        strong_score_negative_threshold: int = -60,
        strong_score_probability_threshold: float = 0.65,
        device: str = "auto",
    ):
        try:
            import torch
            from transformers import AutoTokenizer
            from train_rubert_multitask import MultiHeadRuBert
            from omsu_scoring import calculate_omsu_score
        except ImportError as exc:
            raise RuntimeError(
                "ML dependencies are missing. Install the monitoring/ML environment "
                "before running analysis, or pass --skip-analysis."
            ) from exc

        self.torch = torch
        self.AutoTokenizer = AutoTokenizer
        self.MultiHeadRuBert = MultiHeadRuBert
        self.calculate_omsu_score = calculate_omsu_score
        self.taxonomy_checkpoint = resolve_path(taxonomy_checkpoint)
        self.omsu_checkpoint = resolve_path(omsu_checkpoint)
        self.negative_threshold = negative_threshold
        self.nonnegative_threshold = nonnegative_threshold
        self.strong_score_negative_threshold = strong_score_negative_threshold
        self.strong_score_probability_threshold = strong_score_probability_threshold
        self.device = self._choose_device(device)
        self.taxonomy = self._load_checkpoint(self.taxonomy_checkpoint)
        self.omsu = self._load_checkpoint(self.omsu_checkpoint)

    def _choose_device(self, value: str):
        if value != "auto":
            return self.torch.device(value)
        return self.torch.device("cuda" if self.torch.cuda.is_available() else "cpu")

    def _load_checkpoint(self, checkpoint_dir: Path) -> dict[str, Any]:
        metrics_path = checkpoint_dir / "metrics.json"
        model_path = checkpoint_dir / "model.pt"
        if not metrics_path.exists() or not model_path.exists():
            raise FileNotFoundError(f"Checkpoint is incomplete: {checkpoint_dir}")
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        tokenizer_path = checkpoint_dir / "tokenizer"
        tokenizer = self.AutoTokenizer.from_pretrained(
            str(tokenizer_path) if tokenizer_path.exists() else metrics["base_model"]
        )
        target_cols = metrics["target_cols"]
        model = self.MultiHeadRuBert(
            metrics["base_model"],
            {col: len(metrics["label_maps"][col]) for col in target_cols},
            dropout=float(metrics.get("dropout", 0.3)),
        ).to(self.device)
        model.load_state_dict(self.torch.load(model_path, map_location=self.device))
        model.eval()
        inverse_maps = {
            col: {idx: label for label, idx in label_map.items()}
            for col, label_map in metrics["label_maps"].items()
        }
        return {
            "metrics": metrics,
            "tokenizer": tokenizer,
            "model": model,
            "target_cols": target_cols,
            "inverse_maps": inverse_maps,
        }

    def analyze_items(self, items, batch_size: int = 32) -> int:
        item_list = list(items)
        if not item_list:
            return 0
        rows = [
            {
                "text": item.text,
                "post_text": item.post_text,
            }
            for item in item_list
        ]
        taxonomy_predictions = self._predict_heads(rows, self.taxonomy, batch_size)
        omsu_predictions = self._predict_omsu(rows, self.omsu, batch_size)
        now = timezone.now()

        for item, taxonomy_pred, omsu_pred in zip(item_list, taxonomy_predictions, omsu_predictions):
            raw_taxonomy = {col: taxonomy_pred["labels"][col] for col in self.taxonomy["target_cols"]}
            final_taxonomy, rules = apply_taxonomy_consistency_rules(raw_taxonomy)
            score = self.calculate_omsu_score(final_taxonomy)
            probability = float(omsu_pred["positive_probability"])
            decision, band, rating_weight = omsu_decision(
                probability,
                self.negative_threshold,
                self.nonnegative_threshold,
                score=score.score,
                strong_score_negative_threshold=self.strong_score_negative_threshold,
                strong_score_probability_threshold=self.strong_score_probability_threshold,
            )
            item.taxonomy = {
                **final_taxonomy,
                "_raw": raw_taxonomy,
                "_postprocess_rules": rules,
                "_rating_weight": rating_weight,
            }
            item.taxonomy_confidence = taxonomy_pred["confidence"]
            item.omsu_score = score.score
            item.omsu_impact_class = score.impact_class
            item.omsu_negative_probability = probability
            item.omsu_decision = decision
            item.omsu_confidence_band = band
            item.omsu_score_reason = score.reason
            item.analyzed_at = now

        for item in item_list:
            item.save(
                update_fields=[
                    "taxonomy",
                    "taxonomy_confidence",
                    "omsu_score",
                    "omsu_impact_class",
                    "omsu_negative_probability",
                    "omsu_decision",
                    "omsu_confidence_band",
                    "omsu_score_reason",
                    "analyzed_at",
                ]
            )
        return len(item_list)

    def _predict_heads(self, rows: list[dict[str, str]], checkpoint: dict[str, Any], batch_size: int):
        metrics = checkpoint["metrics"]
        tokenizer = checkpoint["tokenizer"]
        model = checkpoint["model"]
        inverse_maps = checkpoint["inverse_maps"]
        target_cols = checkpoint["target_cols"]
        predictions = [
            {"labels": {}, "confidence": {}}
            for _row in rows
        ]

        with self.torch.no_grad():
            for start in range(0, len(rows), batch_size):
                batch = rows[start : start + batch_size]
                encoded = tokenizer(
                    [row_text(row, metrics["text_mode"]) for row in batch],
                    max_length=int(metrics["max_length"]),
                    padding="max_length",
                    truncation=True,
                    return_tensors="pt",
                )
                input_ids = encoded["input_ids"].to(self.device)
                attention_mask = encoded["attention_mask"].to(device=self.device, dtype=self.torch.long)
                outputs = model(input_ids=input_ids, attention_mask=attention_mask)
                for col in target_cols:
                    probabilities = self.torch.softmax(outputs[col], dim=1).detach().cpu()
                    for offset, probs in enumerate(probabilities):
                        pred_idx = int(self.torch.argmax(probs).item())
                        predictions[start + offset]["labels"][col] = inverse_maps[col][pred_idx]
                        predictions[start + offset]["confidence"][col] = float(probs[pred_idx].item())
        return predictions

    def _predict_omsu(self, rows: list[dict[str, str]], checkpoint: dict[str, Any], batch_size: int):
        metrics = checkpoint["metrics"]
        tokenizer = checkpoint["tokenizer"]
        model = checkpoint["model"]
        target_col = "omsu_negative_signal"
        label_map = metrics["label_maps"][target_col]
        inverse_map = {idx: label for label, idx in label_map.items()}
        positive_idx = label_map["negative_omsu"]
        predictions = [
            {"argmax_pred": "", "positive_probability": 0.0}
            for _row in rows
        ]

        with self.torch.no_grad():
            for start in range(0, len(rows), batch_size):
                batch = rows[start : start + batch_size]
                encoded = tokenizer(
                    [row_text(row, metrics["text_mode"]) for row in batch],
                    max_length=int(metrics["max_length"]),
                    padding="max_length",
                    truncation=True,
                    return_tensors="pt",
                )
                input_ids = encoded["input_ids"].to(self.device)
                attention_mask = encoded["attention_mask"].to(device=self.device, dtype=self.torch.long)
                probabilities = self.torch.softmax(
                    model(input_ids=input_ids, attention_mask=attention_mask)[target_col],
                    dim=1,
                ).detach().cpu()
                for offset, probs in enumerate(probabilities):
                    pred_idx = int(self.torch.argmax(probs).item())
                    predictions[start + offset]["argmax_pred"] = inverse_map[pred_idx]
                    predictions[start + offset]["positive_probability"] = float(probs[positive_idx].item())
        return predictions
