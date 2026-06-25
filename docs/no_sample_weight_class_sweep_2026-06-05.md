# No Sample-Weight Class Sweep, 2026-06-05

## Задача

Проверить гипотезу пользователя: повторить эксперименты с развесовкой классов,
но отключить веса разметки. То есть human-gold и automatic teacher-silver строки должны
участвовать в loss с одинаковым весом, а улучшение должно идти только через
class weights. Главная метрика отбора - macro-F1, а не accuracy.

## Данные

Dataset:

```text
D:\Diplom\data\ml_experiments\teacher_student_full_2026-06-03_01-06\dataset_gold_silver_fixed_split.csv
```

Фиксированный split:

- train: `262783`;
- validation: `655` human-gold;
- test: `655` human-gold;
- gold train: `3055`;
- silver train: `259728`.

Во всех запусках принудительно выставлено:

```text
--gold-weight-override 1.0
--silver-weight-override 1.0
```

То есть sample weights отключены как механизм доверия к разметке.

## Артефакты

Основная папка:

```text
D:\Diplom\data\ml_experiments\no_sample_weight_class_sweep_2026-06-05\
```

Сводка:

```text
D:\Diplom\data\ml_experiments\no_sample_weight_class_sweep_2026-06-05\no_sample_weight_class_sweep_summary.md
```

Сравнение с текущей лучшей моделью:

```text
D:\Diplom\data\ml_experiments\no_sample_weight_class_sweep_2026-06-05\comparison_vs_best\model_run_summary.md
```

Новый runner:

```text
D:\Diplom\experiments\run_no_sample_weight_class_sweep.py
```

## Screen Results

Screen-прогоны использовали `80000` train rows, `2` эпохи, RuBERT tiny2,
`post_comment`, batch size `32`, max length `256`, lr `1e-5`.

| Run | Class weights | Best val macro-F1 | Test mean macro-F1 |
| --- | --- | ---: | ---: |
| `no_sample_none_screen` | none | `0.2146` | `0.2087` |
| `no_sample_balanced_screen` | balanced, power `1.0`, no cap | `0.2730` | `0.2730` |
| `no_sample_balanced_power075_cap4_screen` | balanced, power `0.75`, cap `4.0` | `0.2804` | `0.2688` |
| `no_sample_balanced_power05_cap6_screen` | balanced, power `0.5`, cap `6.0` | `0.2586` | `0.2532` |
| `no_sample_gold_power075_cap4_screen` | gold-balanced, power `0.75`, cap `4.0` | `0.2436` | `0.2261` |
| `no_sample_gold_power05_cap6_screen` | gold-balanced, power `0.5`, cap `6.0` | `0.2363` | `0.2296` |

Screen вывод: class weights нужны, потому что без них F1 падает до `0.2087`.
Но отключение sample weights само по себе не дает прорыва. Лучший screen test
остался около `0.2730`.

## Full Run

Полностью был прогнан лучший практический вариант:

```text
D:\Diplom\data\ml_experiments\no_sample_weight_class_sweep_2026-06-05\no_sample_balanced_full\
```

Конфигурация:

- model: `cointegrated/rubert-tiny2`;
- target heads: все 8 осей текущей таксономии;
- epochs: `4`;
- train rows: `262783`;
- text mode: `post_comment`;
- class weights: `balanced`, power `1.0`, без cap;
- sample weights: отключены через `gold=1.0`, `silver=1.0`.

Результат:

- best validation macro-F1: `0.3077`;
- held-out test mean macro-F1: `0.2962`.

Per-head test macro-F1:

| Head | Macro-F1 |
| --- | ---: |
| `jkh_relevance` | `0.4475` |
| `jkh_topic` | `0.3038` |
| `authority_aspect` | `0.1882` |
| `sentiment` | `0.3611` |
| `appeal_type` | `0.2514` |
| `responsible_party` | `0.1483` |
| `sarcasm` | `0.3157` |
| `quality` | `0.3536` |

Второй full-кандидат `no_sample_balanced_power075_cap4_full` был остановлен
после начала второй эпохи. Причина: первая эпоха дала только `val_macro_f1=0.2913`,
хуже `no_sample_balanced_full` на той же стадии; run шел заметно медленнее,
держал GPU около `85 C` и память около `3.8/4.0 GB`. Screen у этого варианта
тоже имел хуже test (`0.2688`), поэтому продолжать несколько часов было
необоснованно.

## Comparison With Current Best

Current best original-taxonomy checkpoint:

```text
D:\Diplom\data\ml_experiments\teacher_student_runs\sweep_final_2026-06-03\final_w03_weighted_lr1e5_e4\
```

| Run | Best val macro-F1 | Test mean macro-F1 |
| --- | ---: | ---: |
| current best, `silver_weight=0.3`, weighted-balanced class weights | `0.3086` | `0.3003` |
| no sample weights, balanced class weights | `0.3077` | `0.2962` |

Per-head comparison:

| Head | Current best | No sample weights |
| --- | ---: | ---: |
| `jkh_relevance` | `0.4475` | `0.4475` |
| `jkh_topic` | `0.3088` | `0.3038` |
| `authority_aspect` | `0.1921` | `0.1882` |
| `sentiment` | `0.3710` | `0.3611` |
| `appeal_type` | `0.2519` | `0.2514` |
| `responsible_party` | `0.1482` | `0.1483` |
| `sarcasm` | `0.3214` | `0.3157` |
| `quality` | `0.3612` | `0.3536` |

## Вывод

Гипотеза проверена: отключение весов разметки не улучшило F1. Оно почти догнало
старый validation, но проиграло на held-out human-gold test:

```text
0.2962 < 0.3003
```

Классовые веса действительно нужны, но sample weights тоже полезны: они
приглушают шумный silver и оставляют human-gold более заметным в обучении.
Полное доверие silver-данным делает модель чуть хуже почти по всем головам,
особенно по `jkh_topic`, `sentiment`, `sarcasm` и `quality`.

Текущая лучшая original-taxonomy модель не меняется:

```text
D:\Diplom\data\ml_experiments\teacher_student_runs\sweep_final_2026-06-03\final_w03_weighted_lr1e5_e4\
```
