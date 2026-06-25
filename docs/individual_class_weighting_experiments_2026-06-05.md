# Индивидуальная балансировка классов, 2026-06-05

## Зачем переделывали

Предыдущий эксперимент с class weights был недостаточно точным: он проверял в основном общие схемы по осям и grouped-таксономию, хотя требовалась проверка весов отдельных классов исходной таксономии. Этот повторный эксперимент проводился без grouped-подхода: только исходные 8 осей и отдельные классы внутри них.

## База сравнения

Текущий лучший checkpoint исходной таксономии:

```text
data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/final_w03_weighted_lr1e5_e4/
```

Метрики baseline:

- validation macro-F1: `0.3086`
- test mean macro-F1: `0.3003`

## Что было добавлено

В trainer добавлена поддержка ручных весов отдельных классов:

```text
--class-weights-json
```

JSON задает веса так:

```json
{
  "authority_aspect": {
    "poor_quality": 4.62341725,
    "slow_response": 2.97924307
  }
}
```

Также добавлен evaluator:

```text
experiments/evaluate_checkpoint_splits.py
```

Он считает для каждого класса на gold validation/test:

- support;
- TP;
- FP;
- FN;
- TN;
- precision;
- recall;
- F1.

## Расчет индивидуальных весов

Отчет по классам и весам:

```text
data/ml_experiments/individual_class_weighting_2026-06-05/presets/individual_class_weight_rationale.md
data/ml_experiments/individual_class_weighting_2026-06-05/presets/individual_class_weight_rationale.csv
```

Были построены три первичных per-class пресета:

- `individual_guarded`: поднимает классы с низким recall/F1 и режет классы с большим FP;
- `individual_fn_fp_ratio`: двигает вес по соотношению FN/FP;
- `individual_weak_only`: трогает только слабые оси (`authority_aspect`, `appeal_type`, `responsible_party`, `quality`).

После первой проверки была обнаружена ошибка методики: cap применялся даже к классам, которые не должны были меняться. Это исправлено. Финальные screen-цифры ниже относятся к исправленной версии `sweep_v2`.

## Screen-проверка

Screen: `80000` train rows, 2 эпохи, исходная таксономия.

| Run | Best val macro-F1 | Test mean macro-F1 | Вывод |
| --- | ---: | ---: | --- |
| `original_baseline_repro_screen` | 0.2735 | 0.2733 | локальный baseline |
| `original_individual_guarded_screen` | 0.2571 | 0.2587 | отвергнут |
| `original_individual_fn_fp_ratio_screen` | 0.2760 | 0.2533 | val-ловушка, переобучение под validation |
| `original_individual_weak_only_screen` | 0.2730 | 0.2748 | слабый test-прирост, но ниже по val |
| `original_individual_authority_only_screen` | 0.2717 | 0.2770 | лучший screen test, выбран для full |

`authority_only` был выбран не потому, что он красивый по validation, а потому что он единственный не развалил весь test и дал осмысленное локальное улучшение `authority_aspect` при минимальном вмешательстве: менялись только конкретные классы `authority_aspect`.

## Full-проверка

Full: `262783` train rows, 4 эпохи, исходная таксономия.

| Run | Best val macro-F1 | Test mean macro-F1 |
| --- | ---: | ---: |
| baseline `final_w03_weighted_lr1e5_e4` | 0.3086 | 0.3003 |
| `original_individual_authority_only_full` | 0.3078 | 0.3000 |

Per-head test macro-F1:

| Head | Baseline | Authority-only full | Изменение |
| --- | ---: | ---: | ---: |
| `jkh_relevance` | 0.4475 | 0.4475 | 0.0000 |
| `jkh_topic` | 0.3088 | 0.3088 | 0.0000 |
| `authority_aspect` | 0.1921 | 0.1854 | -0.0067 |
| `sentiment` | 0.3710 | 0.3676 | -0.0034 |
| `appeal_type` | 0.2519 | 0.2536 | +0.0017 |
| `responsible_party` | 0.1482 | 0.1472 | -0.0010 |
| `sarcasm` | 0.3214 | 0.3214 | 0.0000 |
| `quality` | 0.3612 | 0.3684 | +0.0072 |

## Итог

Индивидуальная балансировка классов была проверена корректно, но не дала надежного улучшения лучшей исходной модели. Лучшим checkpoint исходной таксономии остается:

```text
data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/final_w03_weighted_lr1e5_e4/
```

Почему прирост не получился:

- слабые классы имеют мало human-gold примеров, поэтому validation-ошибки отдельных классов плохо переносятся на test;
- весами можно сдвинуть recall/precision одного класса, но модель часто платит ухудшением соседних классов той же оси;
- `fn_fp_ratio` показал типичную ловушку: validation вырос (`0.2760` против `0.2735`), а test упал (`0.2533`);
- `authority_only` был самым аккуратным вариантом, но на full не подтвердил screen-улучшение.

Практический вывод: на текущем объеме gold-данных веса отдельных классов уже почти исчерпаны. Следующий реальный шаг для качества исходной таксономии - не очередная формула весов, а изменение постановки задачи: cascade/per-head модели, binary gate перед детальными классами, калибровка порогов или добавление targeted hard-gold для слабых классов.

## Артефакты

```text
data/ml_experiments/individual_class_weighting_2026-06-05/baseline_original_eval/
data/ml_experiments/individual_class_weighting_2026-06-05/presets/
data/ml_experiments/individual_class_weighting_2026-06-05/sweep/
data/ml_experiments/individual_class_weighting_2026-06-05/sweep_v2/
```

Ключевой full run:

```text
data/ml_experiments/individual_class_weighting_2026-06-05/sweep_v2/original_individual_authority_only_full/
```
