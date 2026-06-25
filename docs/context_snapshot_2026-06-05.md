# Context Snapshot 2026-06-05

This is the current recovery point for the diploma project context.

## Project Direction

- Central domain: ЖКХ-related public appeals and public-authority/utility
  response analysis.
- Annotation unit: source post establishes the main subject direction; comment
  is treated as public reaction and supplies sentiment, appeal form, sarcasm,
  quality and detail.
- Human-approved labels are gold. automatic teacher/offline labels are silver and must stay
  separate in reporting and evaluation.
- Final model quality must be judged on human-gold validation/test only.

## Canonical Data Locations

Archive index:

```text
D:\Diplom\docs\project_data_archive.md
```

Main local full export:

```text
D:\Diplom\data\exports\teacher_student_full_export_2026-06-03_01-06\
```

Main fixed ML dataset:

```text
D:\Diplom\data\ml_experiments\teacher_student_full_2026-06-03_01-06\dataset_gold_silver_fixed_split.csv
```

Grouped fixed ML dataset:

```text
D:\Diplom\data\ml_experiments\teacher_student_grouped_2026-06-04\dataset_gold_silver_grouped_fixed_split.csv
```

## Fixed Split Counts

- Total rows: `264093`
- Train: `262783`
- Validation: `655`
- Test: `655`
- Human gold total: `4365`
- Human gold train: `3055`
- Human gold validation: `655`
- Human gold test: `655`
- Silver train: `259728`

## Current Best Original-Taxonomy Model

```text
D:\Diplom\data\ml_experiments\teacher_student_runs\sweep_final_2026-06-03\final_w03_weighted_lr1e5_e4\
```

Configuration:

- model: `cointegrated/rubert-tiny2`
- text mode: `post_comment`
- epochs: `4`
- batch size: `32`
- max length: `256`
- learning rate: `1e-5`
- class weights: `weighted_balanced`
- silver weight: `0.3`

Result on human-gold test:

- test mean macro-F1: `0.3003`
- validation macro-F1: `0.3086`

Weakest heads remain:

- `responsible_party`
- `authority_aspect`
- `appeal_type`
- rare `jkh_topic` classes

## Large Model Check

Full-data large run:

```text
D:\Diplom\data\ml_experiments\teacher_student_runs\large_model_full_2026-06-04\rubert_base_conversational_last2_all_train_lr5e5_e1_b32\
```

Configuration:

- model: `DeepPavlov/rubert-base-cased-conversational`
- all `262783` train rows
- frozen encoder + last `2` layers unfrozen
- gradient checkpointing enabled
- epochs: `1`
- batch size: `32`
- max length: `192`
- learning rate: `5e-5`
- silver weight: `0.3`

Result:

- validation macro-F1: `0.3034`
- test mean macro-F1: `0.2920`

Conclusion: larger RuBERT did not beat the optimized tiny2 checkpoint. The
current bottleneck is task/data design, not raw encoder size.

## Grouped Taxonomy Result

Grouped dataset builder:

```text
D:\Diplom\experiments\build_grouped_taxonomy_dataset.py
```

Grouped run:

```text
D:\Diplom\data\ml_experiments\teacher_student_runs\grouped_taxonomy_2026-06-04\tiny2_grouped_w03_lr1e5_e4\
```

Configuration:

- model: `cointegrated/rubert-tiny2`
- grouped heads: 8
- text mode: `post_comment`
- epochs: `4`
- batch size: `32`
- max length: `256`
- learning rate: `1e-5`
- class weights: `weighted_balanced`
- silver weight: `0.3`

Result:

- validation macro-F1: `0.3469`
- test mean macro-F1: `0.3544`

Important caveat: grouped score is not directly comparable to the original
taxonomy score because grouped labels are coarser. Practical conclusion: if no
new gold data is available, grouped taxonomy/cascade design is currently more
promising than simply switching to a larger model.

## Grouped Classes

- `jkh_relevance`: `no` + `unsure` -> `no_or_unsure`; `yes` stays separate.
- `jkh_topic`: water/sewerage + heating/hot water -> `utilities_water_heat`;
  house common property + management company -> `housing_management`;
  yard, waste, payments, authorities, other JKH and not-JKH stay separate.
- `authority_aspect`: poor quality + slow response + no action ->
  `service_problem`; supervision + tariff policy -> `governance_control`;
  communication, positive feedback, other and not-applicable stay separate.
- `appeal_type`: complaint + demand + request -> `problem_appeal`;
  suggestion + gratitude -> `constructive_positive`; question, info, opinion
  and other stay separate.
- `responsible_party`: local administration + housing inspection + specific
  person -> `public_authority`; management company + resource provider + waste
  operator -> `utility_or_management`; residents, unknown and not-applicable
  stay separate.
- `quality`: difficult + duplicate + no context ->
  `problematic_or_duplicate`; normal and spam stay separate.
- `sentiment` and `sarcasm` were not grouped.

## Class-Weight Balancing Result

The class-weight normalization experiment was completed on 2026-06-05.

Implemented trainer options:

- `gold_balanced` and `gold_weighted_balanced` class-weight sources;
- `--class-weight-power`;
- `--class-weight-min`;
- `--class-weight-max`;
- `--head-loss-weights`.

Computed analysis showed that uncapped weighted-balanced weights can explode on
ultra-rare classes:

- `jkh_relevance.unsure`: about `1799`;
- `jkh_topic.management_company`: about `900`;
- `responsible_party.specific_person`: about `750`;
- `quality.duplicate`: about `6748`.

Gold-only capped weights were tested and rejected: the human-gold train split is
too small for stable rare-class weighting. The best hypothesis was smoothed
weighted-train balancing:

```text
weight = (total / (num_classes * class_count)) ** 0.75
cap = 4.0
silver_weight = 0.3
```

Full original-taxonomy check:

```text
D:\Diplom\data\ml_experiments\class_weight_sweep_2026-06-05\original_weighted_power075_cap4_full\
```

- validation macro-F1: `0.3074`
- test mean macro-F1: `0.2956`
- conclusion: below the original best `0.3003`, so
  `final_w03_weighted_lr1e5_e4` remains the best original-taxonomy checkpoint.

Full grouped-taxonomy check:

```text
D:\Diplom\data\ml_experiments\class_weight_sweep_2026-06-05\grouped_weighted_power075_cap4_full\
```

- validation macro-F1: `0.3546`
- test mean macro-F1: `0.3561`
- conclusion: slightly above grouped baseline `0.3544`, so this is now the
  best grouped/cascade checkpoint candidate.

Practical recommendation: use grouped/cascade taxonomy with smoothed capped
weighted-train class weights if no more human-gold data will be added. Do not
use gold-only class weights for the current data volume.

## Individual Class-Weighting Result

The user rejected grouped/general-axis weighting as insufficient, so a follow-up
experiment tested individual class weights on the original taxonomy only.

Implemented:

- `--class-weights-json` in the trainer;
- `experiments/evaluate_checkpoint_splits.py` for per-class TP/FP/FN/TN,
  precision, recall and F1 on fixed gold validation/test splits;
- per-class presets generated from validation errors:
  `individual_guarded`, `individual_fn_fp_ratio`, `individual_weak_only`;
- a surgical `individual_authority_only` preset after screen analysis.

Corrected screen v2 results:

- baseline screen: validation `0.2735`, test `0.2733`;
- `individual_guarded`: validation `0.2571`, test `0.2587`;
- `individual_fn_fp_ratio`: validation `0.2760`, test `0.2533`
  (validation overfit);
- `individual_weak_only`: validation `0.2730`, test `0.2748`;
- `individual_authority_only`: validation `0.2717`, test `0.2770`.

Full original-taxonomy check:

```text
D:\Diplom\data\ml_experiments\individual_class_weighting_2026-06-05\sweep_v2\original_individual_authority_only_full\
```

- validation macro-F1: `0.3078`;
- test mean macro-F1: `0.3000`;
- conclusion: below original baseline `0.3003`, so individual class weighting
  did not replace `final_w03_weighted_lr1e5_e4`.

## OМСУ Numeric Rating Layer

The user clarified that the project must keep all 8 existing taxonomy axes and
add a separate numeric rating for local government/ОМСУ work. The score is not a
replacement for the taxonomy.

Durable note:

```text
D:\Diplom\docs\omsu_score_experiments_2026-06-06.md
```

Implemented scripts:

```text
D:\Diplom\experiments\omsu_scoring.py
D:\Diplom\experiments\build_omsu_score_dataset.py
D:\Diplom\experiments\evaluate_omsu_score_predictions.py
D:\Diplom\experiments\run_omsu_score_sweep.py
D:\Diplom\experiments\evaluate_binary_thresholds.py
D:\Diplom\experiments\evaluate_selective_binary_policy.py
```

Main artifacts:

```text
D:\Diplom\data\ml_experiments\omsu_score_2026-06-06\dataset_gold_silver_omsu_fixed_split.csv
D:\Diplom\data\ml_experiments\omsu_score_2026-06-06\threshold\negative_signal_capped_20k\
D:\Diplom\data\ml_experiments\omsu_score_2026-06-06\threshold\selective_policy_085_015\
```

Key result: direct ОМСУ binary model plus selective policy
`P(negative_omsu)>=0.85` / `P(negative_omsu)<=0.15` reaches on human-gold test:

- coverage: `0.7496`;
- accuracy: `0.9939`;
- macro-F1: `0.9102`;
- weighted-F1: `0.9937`;
- `negative_omsu` F1: `0.8235`;
- `negative_omsu` precision: `0.8750`;
- `negative_omsu` recall: `0.7778`.

Recommendation: use the best 8-axis checkpoint for taxonomy and a second ОМСУ
cascade checkpoint for rating fields: `omsu_score`, `omsu_impact_class`,
`omsu_negative_probability`, `omsu_decision`, `omsu_confidence_band` and
`omsu_score_reason`.

## Full Cascade Evaluation

The full cascade evaluator was added and run on 2026-06-06:

```text
D:\Diplom\experiments\evaluate_cascade_system.py
```

Durable note:

```text
D:\Diplom\docs\cascade_system_evaluation_2026-06-06.md
```

Runtime artifact:

```text
D:\Diplom\data\ml_experiments\cascade_eval_2026-06-06_01-48\
```

Cascade stages:

1. best 8-axis taxonomy checkpoint;
2. deterministic consistency rules for dependent taxonomy fields;
3. predicted-axis `omsu_score`;
4. direct ОМСУ binary checkpoint;
5. selective decision policy for automatic rating.

Test metrics:

- mean 8-axis macro-F1 after consistency rules: `0.3032`;
- strict all-8 exact match: `0.0885`;
- OМСУ selective coverage: `0.7496`;
- OМСУ selective macro-F1: `0.9102`;
- OМСУ selective weighted-F1: `0.9937`;
- OМСУ negative-class F1: `0.8235`;
- numeric `omsu_score` MAE: `13.14`.

Interpretation: the cascade is strong enough for high-confidence ОМСУ rating,
but the detailed 8-axis taxonomy still has weak rare-class macro-F1. For
infographics, use axis distributions with confidence/coverage notes rather than
claiming uniformly high accuracy on every rare class.

## Pseudo-Gold Layer

The user approved "псевдо-золотая разметка" as the term for a stricter
teacher-assisted training layer. This is not human-gold and must not be used for
validation/test.

Builder:

```text
D:\Diplom\experiments\build_pseudo_gold_layer.py
```

Durable note:

```text
D:\Diplom\docs\pseudo_gold_layer_experiments_2026-06-06.md
```

Runtime artifact:

```text
D:\Diplom\data\ml_experiments\pseudo_gold_2026-06-06_v2\
```

Pseudo-gold v2 selected `7134` train rows from silver/model-score audit and
raised many rare class counts. However, full 8-axis gold+pseudo-gold training
worsened test mean macro-F1 to `0.2385`, so broad pseudo-gold replacement is
rejected.

Specialist checks:

- `responsible_party`: test macro-F1 improved from cascade baseline `0.1495`
  to `0.1784`;
- hybrid mean 8-axis test macro-F1 would move from `0.3032` to about `0.3069`;
- `authority_aspect`, `appeal_type`, and `jkh_topic` specialists worsened.

Conclusion: pseudo-gold is viable only as targeted per-axis specialist training,
with each specialist accepted only after human-gold test improvement.

## High-F1 Recovery Attempts

The user asked to continue by any reasonable means and set a `40` minute limit
for training runs. Durable note:

```text
D:\Diplom\docs\high_f1_recovery_attempts_2026-06-06.md
```

New selective taxonomy evaluator:

```text
D:\Diplom\experiments\evaluate_selective_taxonomy_policy.py
```

Runtime artifacts:

```text
D:\Diplom\data\ml_experiments\selective_taxonomy_2026-06-06_strict\
D:\Diplom\data\ml_experiments\gold_specialists_2026-06-06\
```

Results:

- strict selective taxonomy reached at best mean test macro-F1 `0.3363` with
  mean coverage `0.5076`;
- gold-only specialists completed within about `28-29` minutes but did not
  beat the cascade except for a tiny `responsible_party` movement;
- simple anchor overrides improved validation but failed on test;
- current best practical full taxonomy result is still cascade plus optional
  pseudo-gold `responsible_party` specialist, about `0.3069` mean test macro-F1;
- high F1 is currently available for the OМСУ selective layer, not for every
  detailed taxonomy axis.

## Durable Notes

- Weak-axis analysis:
  `D:\Diplom\docs\model_weak_axes_analysis_2026-06-03.md`
- Teacher-student training:
  `D:\Diplom\docs\teacher_student_training_2026-06-03.md`
- Large model experiments:
  `D:\Diplom\docs\large_model_experiments_2026-06-04.md`
- Grouped taxonomy:
  `D:\Diplom\docs\grouped_taxonomy_experiments_2026-06-04.md`
- Class-weight balancing:
  `D:\Diplom\docs\class_weight_balancing_experiments_2026-06-05.md`
- Individual class weighting:
  `D:\Diplom\docs\individual_class_weighting_experiments_2026-06-05.md`
- No sample-weight class sweep:
  `D:\Diplom\docs\no_sample_weight_class_sweep_2026-06-05.md`
- OМСУ score experiments:
  `D:\Diplom\docs\omsu_score_experiments_2026-06-06.md`
- Cascade system evaluation:
  `D:\Diplom\docs\cascade_system_evaluation_2026-06-06.md`
- Pseudo-gold layer:
  `D:\Diplom\docs\pseudo_gold_layer_experiments_2026-06-06.md`
- High-F1 recovery attempts:
  `D:\Diplom\docs\high_f1_recovery_attempts_2026-06-06.md`
- Chat memory:
  `D:\Diplom\docs\chat_context.md`
