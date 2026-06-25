# Балансировка весов классов, 2026-06-05

## Цель

Проверить, можно ли улучшить текущий RuBERT-разметчик за счет более аккуратной балансировки весов классов. Основная проблема: часть осей (`responsible_party`, `authority_aspect`, `appeal_type`, частично `quality`) проседает из-за редких классов и сильного перекоса в сторону `not_applicable`, `not_jkh`, `opinion`, `normal`.

## Данные

- Полный teacher-student датасет: `data/ml_experiments/teacher_student_full_2026-06-03_01-06/dataset_gold_silver_fixed_split.csv`
- Строк всего: `264093`
- Train: `262783`
- Gold train: `3055`
- Silver train: `259728`
- Validation/Test: `655` / `655`, только human-gold
- Silver weight для основных прогонов: `0.3`

## Расчетные предположения

1. Старый `weighted_balanced` слишком агрессивен для ультраредких классов.

   По вычислениям текущая схема могла давать огромные веса:

   - `jkh_relevance.unsure`: около `1799`
   - `jkh_topic.management_company`: около `900`
   - `authority_aspect.other`: около `310`
   - `responsible_party.specific_person`: около `750`
   - `quality.duplicate`: около `6748`

   Это опасно: модель начинает переучиваться на единичные или шумные примеры.

2. Gold-only веса казались логичными, но оказались вредными.

   Идея была считать веса только по human-gold train и ограничивать редкие классы потолком `3`, `5` или сглаженным потолком `4`. Короткий sweep показал, что такие схемы системно ухудшают результат: редкие классы получают формально честный вес, но gold-выборка слишком мала и не покрывает все реальные формулировки.

3. Самая разумная схема: сглаженные веса по weighted train.

   Формула:

   ```text
   weight = (total / (num_classes * class_count)) ** 0.75
   ```

   Затем веса нормируются и ограничиваются сверху `4.0`.

   Смысл: редкие классы усиливаются, но без экстремальных коэффициентов. Silver остается полезным как широкий языковой фон, а human-gold validation/test сохраняют честную проверку качества.

## Проверенные схемы

Короткий sweep запускался на `80000` train rows, 2 эпохи. Финальная проверка запускалась на полном train, 4 эпохи.

| Схема | Таксономия | Train rows | Best val macro-F1 | Test mean macro-F1 | Вывод |
| --- | --- | ---: | ---: | ---: | --- |
| `original_gold_cap3_screen` | исходная | 80000 | 0.2349 | 0.2267 | плохо |
| `original_gold_cap5_screen` | исходная | 80000 | 0.2081 | 0.2041 | плохо |
| `original_gold_power075_cap4_screen` | исходная | 80000 | 0.2437 | 0.2275 | плохо |
| `original_current_weighted_screen` | исходная | 80000 | 0.2729 | 0.2750 | базовый короткий ориентир |
| `original_weighted_power075_cap4_screen` | исходная | 80000 | 0.2796 | 0.2682 | val лучше, test хуже |
| `grouped_current_weighted_screen` | grouped | 80000 | 0.3346 | 0.3357 | базовый grouped-ориентир |
| `grouped_weighted_power075_cap4_screen` | grouped | 80000 | 0.3472 | 0.3464 | лучший короткий кандидат |
| `original_weighted_power075_cap4_full` | исходная | 262783 | 0.3074 | 0.2956 | не победил baseline |
| `grouped_weighted_power075_cap4_full` | grouped | 262783 | 0.3546 | 0.3561 | лучший grouped-вариант |

## Сравнение с лучшими моделями

| Модель | Таксономия | Best val macro-F1 | Test mean macro-F1 |
| --- | --- | ---: | ---: |
| `final_w03_weighted_lr1e5_e4` | исходная | 0.3086 | 0.3003 |
| `rubert_base_conversational_last2_all_train_lr5e5_e1_b32` | исходная, large | 0.3034 | 0.2920 |
| `original_weighted_power075_cap4_full` | исходная, новые веса | 0.3074 | 0.2956 |
| `tiny2_grouped_w03_lr1e5_e4` | grouped baseline | 0.3469 | 0.3544 |
| `grouped_weighted_power075_cap4_full` | grouped, новые веса | 0.3546 | 0.3561 |

## Per-head результат финального grouped-прогона

`grouped_weighted_power075_cap4_full`:

- `jkh_relevance_grouped`: `0.6646`
- `jkh_topic_grouped`: `0.2849`
- `authority_aspect_grouped`: `0.2805`
- `sentiment_grouped`: `0.3664`
- `appeal_type_grouped`: `0.2993`
- `responsible_party_grouped`: `0.2674`
- `sarcasm_grouped`: `0.3251`
- `quality_grouped`: `0.3605`

Относительно grouped baseline:

- улучшилось: `authority_aspect_grouped`, `appeal_type_grouped`, `responsible_party_grouped`, `sarcasm_grouped`, `quality_grouped`;
- ухудшилось: `jkh_relevance_grouped`, `jkh_topic_grouped`, `sentiment_grouped`;
- общий test mean macro-F1 вырос с `0.3544` до `0.3561`.

## Итог

Для исходной полной таксономии новая схема весов не стала лучшей: `0.2956` против текущего baseline `0.3003`. Значит лучшей исходной моделью остается:

`data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/final_w03_weighted_lr1e5_e4/`

Для сгруппированной таксономии новая схема дала небольшой, но честный прирост на полном train:

`data/ml_experiments/class_weight_sweep_2026-06-05/grouped_weighted_power075_cap4_full/`

Практический вывод: при отсутствии новых human-gold записей лучший путь не в агрессивном усилении редких исходных классов, а в grouped/cascade-подходе с мягкими capped-весами. Gold-only веса использовать не стоит: они ухудшили качество почти во всех проверках.

## Артефакты

- Анализ весов: `data/ml_experiments/class_weight_analysis_2026-06-05/original_taxonomy/`
- Sweep результатов: `data/ml_experiments/class_weight_sweep_2026-06-05/`
- Summary: `data/ml_experiments/class_weight_sweep_2026-06-05/class_weight_sweep_summary.md`
- Новый лучший grouped checkpoint: `data/ml_experiments/class_weight_sweep_2026-06-05/grouped_weighted_power075_cap4_full/`
