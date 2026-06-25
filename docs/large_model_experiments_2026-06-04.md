# Large Model Experiments 2026-06-04

This note records the local larger-model checks requested after the
`cointegrated/rubert-tiny2` teacher-student sweep plateaued at about `0.3003`
mean macro-F1 on the human-gold test split.

Canonical comparison output:

```text
D:\Diplom\data\ml_experiments\teacher_student_runs\large_model_presets_2026-06-04\comparison\
```

Key files:

- `model_run_summary.md`
- `model_run_summary.csv`
- `model_run_summary.json`

The fixed evaluation policy is unchanged: validation and test are human-gold
only (`655` validation rows, `655` test rows). Silver is used only in training.

## Trainer Changes

The multitask trainer now supports memory-aware large-model modes:

- gradient accumulation via `--grad-accum-steps`;
- encoder gradient checkpointing via `--gradient-checkpointing`;
- frozen encoder training via `--freeze-encoder`;
- partial encoder fine-tuning via `--unfreeze-last-n-layers`;
- train-only subsampling via `--max-train-rows`, preserving the fixed full
  human-gold validation/test splits.

Syntax checks passed for:

```text
experiments\train_rubert_multitask.py
experiments\run_large_model_presets.py
experiments\summarize_model_runs.py
```

Hardware check:

- CUDA available: yes;
- GPU: NVIDIA GeForce RTX 3050 Ti Laptop GPU;
- VRAM: about `4.0 GB`.

## Tested Presets

Current best baseline:

| Run | Model | Train rows | Best val macro-F1 | Test mean macro-F1 |
| --- | --- | ---: | ---: | ---: |
| `final_w03_weighted_lr1e5_e4` | `cointegrated/rubert-tiny2` | `262783` | `0.3086` | `0.3003` |

Large-model checks:

| Run | Model | Train rows | Best val macro-F1 | Test mean macro-F1 |
| --- | --- | ---: | ---: | ---: |
| `rubert_base_conversational_last2_all_train_lr5e5_e1_b32` | `DeepPavlov/rubert-base-cased-conversational` | `262783` | `0.3034` | `0.2920` |
| `rubert_base_conversational_last2_30k_lr5e5` | `DeepPavlov/rubert-base-cased-conversational` | `30000` | `0.2683` | `0.2654` |
| `rubert_base_conversational_last2_smoke_lr5e5` | `DeepPavlov/rubert-base-cased-conversational` | `12000` | `0.2648` | `0.2622` |
| `rubert_base_conversational_frozen_heads_60k` | `DeepPavlov/rubert-base-cased-conversational` | `60000` | `0.2537` | `0.2553` |
| `rubert_base_conversational_frozen_heads_12k_len256` | `DeepPavlov/rubert-base-cased-conversational` | `12000` | `0.2520` | `0.2550` |
| `rubert_base_conversational_frozen_heads_smoke` | `DeepPavlov/rubert-base-cased-conversational` | `12000` | `0.2503` | `0.2537` |
| `rubert_base_frozen_heads_60k` | `DeepPavlov/rubert-base-cased` | `60000` | `0.2388` | `0.2421` |
| `rubert_base_frozen_heads_smoke` | `DeepPavlov/rubert-base-cased` | `12000` | `0.2372` | `0.2414` |
| `rubert_base_conversational_last2_smoke` | `DeepPavlov/rubert-base-cased-conversational` | `12000` | `0.2258` | `0.2292` |
| `rubert_base_last2_smoke` | `DeepPavlov/rubert-base-cased` | `12000` | `0.2183` | `0.2255` |

## Per-Head Observation

Best large preset:

```text
rubert_base_conversational_last2_30k_lr5e5
```

Compared with the current tiny2 best:

| Head | Tiny2 best macro-F1 | Best large macro-F1 | Direction |
| --- | ---: | ---: | --- |
| `jkh_relevance` | `0.4475` | `0.3797` | worse |
| `jkh_topic` | `0.3088` | `0.2130` | worse |
| `authority_aspect` | `0.1921` | `0.1266` | worse |
| `sentiment` | `0.3710` | `0.3718` | roughly tied |
| `appeal_type` | `0.2519` | `0.1918` | worse |
| `responsible_party` | `0.1482` | `0.1404` | slightly worse |
| `sarcasm` | `0.3214` | `0.3386` | better |
| `quality` | `0.3612` | `0.3616` | roughly tied |

## Interpretation

The larger RuBERT-base family did not beat the optimized `rubert-tiny2`
teacher-student checkpoint under the available local GPU constraints.

The result is not simply "the big model is bad". The useful details are:

- conversational RuBERT is better than ordinary RuBERT-base for this data;
- unfreezing the last two layers with `lr=5e-5` is better than `2e-5`;
- increasing train rows from `12000` to `30000` improves the best large preset;
- longer context (`max_length=256`) barely changes the frozen-head result;
- large models show small gains on `sarcasm` and near parity on `sentiment` and
  `quality`;
- domain taxonomy heads remain worse: `jkh_topic`, `authority_aspect`,
  `appeal_type`, and `responsible_party`.

Current conclusion: the main bottleneck is not raw encoder capacity. It is the
combination of sparse human-gold rare classes, noisy/heuristic silver labels,
and a difficult multitask taxonomy where several heads require domain-specific
judgment.

## Full-Data Large Model Check

After the short presets, the strongest large-model setup was run on the full
fixed train split:

```text
data\ml_experiments\teacher_student_runs\large_model_full_2026-06-04\rubert_base_conversational_last2_all_train_lr5e5_e1_b32\
```

Configuration:

- `DeepPavlov/rubert-base-cased-conversational`;
- all `262783` train rows;
- human-gold validation/test: `655` / `655`;
- frozen encoder with last `2` layers unfrozen;
- gradient checkpointing enabled;
- `epochs=1`, `batch_size=32`, `max_length=192`, `lr=5e-5`;
- `silver_weight=0.3`, `weighted_balanced` class weights.

Result:

- validation macro-F1: `0.3034`;
- test mean macro-F1: `0.2920`.

The full-data large model still did not beat the optimized tiny2 checkpoint
(`0.3003` test mean macro-F1).

## Grouped-Taxonomy Follow-Up

Because the large full-data result was still not strong enough, weak classes
were grouped and a new fixed-split dataset was built:

```text
data\ml_experiments\teacher_student_grouped_2026-06-04\dataset_gold_silver_grouped_fixed_split.csv
```

Grouped tiny2 run:

```text
data\ml_experiments\teacher_student_runs\grouped_taxonomy_2026-06-04\tiny2_grouped_w03_lr1e5_e4\
```

Result:

- best validation macro-F1: `0.3469`;
- test mean macro-F1: `0.3544`.

This is not an apples-to-apples replacement for the original taxonomy score
because the grouped labels are coarser. It is, however, the strongest practical
signal so far: with no new gold data, task/taxonomy design improves reliability
more than simply increasing model size.

## Recommendation

Keep the current production candidate as:

```text
D:\Diplom\data\ml_experiments\teacher_student_runs\sweep_final_2026-06-03\final_w03_weighted_lr1e5_e4\
```

Next improvements should prioritize data and task design:

1. Add targeted hard-gold examples for weak classes:
   `responsible_party`, `authority_aspect`, `appeal_type`, rare JKH topics.
2. Consider separate specialist heads or a cascade:
   first `jkh_relevance/topic`, then authority/responsible/appeal on relevant
   records only.
3. Consider the grouped taxonomy as the practical auto-labeling taxonomy when
   no additional gold data is available.
4. Use the large conversational RuBERT only for later overnight experiments if
   more GPU time is acceptable; do not replace the tiny2 checkpoint based on
   current evidence.
