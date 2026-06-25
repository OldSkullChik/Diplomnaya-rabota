# Группировка слабых классов: эксперимент 2026-06-04

Цель эксперимента: проверить, можно ли улучшить авторазметчик без новых
gold-записей, если укрупнить самые слабые и шумные классы таксономии.

Оценка остается честной: validation/test состоят только из human-gold записей.
Silver/автоматическая разметка используется только в train.

## Исходные данные

- Полный fixed split:
  `data/ml_experiments/teacher_student_full_2026-06-03_01-06/dataset_gold_silver_fixed_split.csv`
- Всего строк: `264093`
- Train: `262783`
- Validation: `655`
- Test: `655`
- Human-gold всего: `4365`
- Silver train: `259728`

## Большой RuBERT на всех данных

Перед группировкой был запущен большой RuBERT на всем train:

- модель: `DeepPavlov/rubert-base-cased-conversational`
- режим: frozen encoder + последние 2 слоя разморожены
- train rows: `262783`
- epochs: `1`
- batch size: `32`
- max length: `192`
- learning rate: `5e-5`
- silver weight: `0.3`
- validation macro-F1: `0.3034`
- test mean macro-F1: `0.2920`

Вывод: большой RuBERT на полном наборе не превзошел текущий лучший tiny2
(`0.3003` на test). Значит основной предел сейчас не в размере энкодера, а в
шуме silver-разметки, малом числе human-gold для редких классов и слишком тонкой
таксономии на слабых осях.

## Grouped Taxonomy

Скрипт:

```text
experiments/build_grouped_taxonomy_dataset.py
```

Grouped-набор:

```text
data/ml_experiments/teacher_student_grouped_2026-06-04/dataset_gold_silver_grouped_fixed_split.csv
```

Ключевая идея: сохранить смысл ЖКХ-разметки, но укрупнить классы, где текущий
gold/silver сигнал слишком разрежен.

Примеры группировки:

- `responsible_party`: администрация/ГЖИ/конкретное должностное лицо ->
  `public_authority`; УК/ресурсник/оператор ТКО -> `utility_or_management`.
- `authority_aspect`: плохое качество/медленная реакция/бездействие ->
  `service_problem`; надзор/тарифная политика -> `governance_control`.
- `appeal_type`: жалоба/требование/просьба -> `problem_appeal`;
  предложение/благодарность -> `constructive_positive`.
- `jkh_relevance`: `no` и `unsure` объединены в `no_or_unsure`, `yes` оставлен
  отдельно.

## Grouped-модель

Run:

```text
data/ml_experiments/teacher_student_runs/grouped_taxonomy_2026-06-04/tiny2_grouped_w03_lr1e5_e4/
```

Настройки:

- модель: `cointegrated/rubert-tiny2`
- target heads: 8 grouped-осей
- text mode: `post_comment`
- train rows: `262783`
- epochs: `4`
- batch size: `32`
- max length: `256`
- learning rate: `1e-5`
- class weights: `weighted_balanced`
- silver weight: `0.3`

Validation macro-F1 по эпохам:

- epoch 1: `0.3358`
- epoch 2: `0.3440`
- epoch 3: `0.3463`
- epoch 4: `0.3469`

Test mean macro-F1:

```text
0.3544
```

## Test Metrics

| Ось | Macro-F1 | Accuracy | Weighted F1 |
| --- | ---: | ---: | ---: |
| `jkh_relevance_grouped` | `0.6660` | `0.7863` | `0.8260` |
| `jkh_topic_grouped` | `0.2942` | `0.7420` | `0.8137` |
| `authority_aspect_grouped` | `0.2714` | `0.7328` | `0.7996` |
| `sentiment_grouped` | `0.3797` | `0.4733` | `0.4452` |
| `appeal_type_grouped` | `0.2934` | `0.3542` | `0.3331` |
| `responsible_party_grouped` | `0.2604` | `0.7099` | `0.7922` |
| `sarcasm_grouped` | `0.3122` | `0.5710` | `0.5672` |
| `quality_grouped` | `0.3574` | `0.8641` | `0.8249` |

## Сравнение

| Run | Таксономия | Model | Test mean macro-F1 |
| --- | --- | --- | ---: |
| `final_w03_weighted_lr1e5_e4` | исходная | `rubert-tiny2` | `0.3003` |
| `rubert_base_conversational_last2_all_train_lr5e5_e1_b32` | исходная | `rubert-base-conversational` | `0.2920` |
| `tiny2_grouped_w03_lr1e5_e4` | grouped | `rubert-tiny2` | `0.3544` |

Важно: grouped-метрика не является прямой заменой исходной метрики, потому что
таксономия стала укрупненной. Но это сильный практический сигнал: для дипломной
авторазметки укрупнение слабых классов дает более стабильное поведение, чем
простая замена tiny2 на большой RuBERT.

## Вывод

Если новых human-gold записей больше не будет, самый рациональный путь:

1. Оставить исходную полную таксономию как аналитическую/экспертную схему.
2. Для авторазметчика использовать grouped-таксономию или каскад:
   сначала уверенно определить ЖКХ/не ЖКХ и крупную тему, затем отдельно
   уточнять слабые оси.
3. Не считать большой RuBERT главным решением проблемы: на текущих данных он не
   дал прироста.

