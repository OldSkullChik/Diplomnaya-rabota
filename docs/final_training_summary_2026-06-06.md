# Финальный отчет по обучению и аналитике, 2026-06-06

## Человеческое резюме последних 5 дней

За последние дни проект прошел путь от обычной платформы ручной разметки к полноценному исследовательскому контуру для диплома. Сначала были выгружены и проверены человеческие разметки: логичные ответы принимались, ошибочные отклонялись, удаленные посты фиксировались отдельно. После большой проверки в производственной базе остались точные итоги: `6219` проверенных разметок, `4704` принятых в датасет, `749` подтвержденных удаленных постов, `766` отклоненных ответов и `0` ожидающих проверки.

Потом стало ясно, что обычный поток данных слишком беден на ЖКХ. Поэтому была создана приоритетная кампания отбора: вместо случайных комментариев пользователям стали выдаваться записи из вероятного ЖКХ-пула. Важное методическое решение: направление темы определяется в первую очередь постом, а комментарий является реакцией общественности. После нескольких сухих прогонов был активирован строгий post-only вариант: `14954` вероятных ЖКХ-кандидата, `150` контрольных не-ЖКХ записей, `244684` общих записей временно исключены из выдачи.

Далее была собрана большая обучающая база. На сервере выгружены gold и silver данные: human-gold как доверенная разметка, silver как сырье для псевдо-золотой и teacher-student разметки. Локально получен полный экспорт `teacher_student_full_export_2026-06-03_01-06`: `01_gold_approved_annotations.csv`, `02_gold_all_annotations_audit.csv`, статистика и `26` silver-batches. Общий размер распакованного пакета составил около `298295002` байт.

После этого началась ML-часть. Были обучены и проверены RuBERT-модели по 8 осям: `jkh_relevance`, `jkh_topic`, `authority_aspect`, `sentiment`, `appeal_type`, `responsible_party`, `sarcasm`, `quality`. Проверялись маленький RuBERT, большие RuBERT-пресеты, веса классов, индивидуальные веса классов, режим без весов выборки, grouped taxonomy, diamond-data, pseudo-gold и отдельные специалисты по слабым осям. Главный вывод: полная 8-осевая таксономия не выходит на высокий macro-F1 с текущей человеческой голдой. Проблема не в длительности обучения, а в структуре данных: редкие классы, спорные границы, мало надежных примеров и сильный перекос в `not_jkh`/`not_applicable`.

Отдельно была добавлена числовая оценка работы ОМСУ. Она не заменяет 8 осей, а работает рядом с ними. Именно этот слой дал сильный результат: direct OMSU-модель с selective-policy показала test macro-F1 `0.9102` при coverage `0.7496`. Поэтому финальная архитектура делится на две части: подробная таксономия для аналитики и статистики с обязательной уверенностью/ограничениями, и отдельный более надежный контур оценки ОМСУ.

## Ключевые данные проекта

### Производственная разметка

| Показатель | Значение |
| --- | ---: |
| Всего отправленных разметок | `6219` |
| Проверено | `6219` |
| Ожидает проверки | `0` |
| Принято в датасет | `4704` |
| Подтвержденные удаленные посты | `749` |
| Отклонено всего | `766` |
| Итоговые баллы | `3491` |

### Полный корпус и обучающие файлы

| Сущность | Значение |
| --- | ---: |
| Всего `SourceRecord` после импорта | `265181` |
| Записей с контекстом поста | `265131` |
| Gold rows в fixed split | `4365` |
| Gold train | `3055` |
| Gold validation | `655` |
| Gold test | `655` |
| Gold+silver fixed dataset | `264093` |
| Train в gold+silver fixed dataset | `262783` |
| Silver train rows | `259728` |
| Silver sample weight в основной схеме | `0.3` |

Основные локальные источники:

- `data/ml_experiments/teacher_student_full_2026-06-03_01-06/dataset_gold_silver_fixed_split.csv`
- `data/ml_experiments/teacher_student_full_2026-06-03_01-06/dataset_gold_only_fixed_split.csv`
- `data/ml_experiments/diamond_dataset_2026-06-03/`
- `data/exports/full_corpus_confusions_2026-06-03/`
- `data/exports/full_corpus_binary_agreement_matrices_2026-06-03/`
- `data/exports/full_corpus_one_vs_rest_label_matrices_2026-06-03/`

## Что проверялось по моделям

### Лучший исходный 8-осевой checkpoint

Путь:

```text
data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/final_w03_weighted_lr1e5_e4/
```

Исторический headline для original taxonomy: test mean macro-F1 около `0.3003`.

### Каскад с правилами согласованности

Путь:

```text
data/ml_experiments/cascade_eval_2026-06-06_01-48/
```

Правило: если `jkh_relevance=no`, то принудительно ставятся `jkh_topic=not_jkh`, `authority_aspect=not_applicable`, `responsible_party=not_applicable`.

Ранее в сводках фигурировал headline около `0.3032`. Финальная строгая перепроверка all-label macro-F1 дала:

| Split | Strict mean macro-F1 | Strict all-8 exact match |
| --- | ---: | ---: |
| validation | `0.2969` | `0.0733` |
| test | `0.2920` | `0.0885` |

По осям на test:

| Ось | Strict test macro-F1 |
| --- | ---: |
| `jkh_relevance` | `0.4475` |
| `jkh_topic` | `0.3106` |
| `authority_aspect` | `0.2128` |
| `sentiment` | `0.3710` |
| `appeal_type` | `0.2519` |
| `responsible_party` | `0.1495` |
| `sarcasm` | `0.3214` |
| `quality` | `0.2709` |

### Большие модели

Большие RuBERT-пресеты на RTX 3050 Ti 4 GB не дали прироста. Лучший крупный smoke/full follow-up оставался ниже tiny2 baseline: крупные модели частично помогали `sarcasm`/`sentiment`, но теряли на доменных осях.

Сводные документы:

- `docs/large_model_experiments_2026-06-04.md`
- `docs/grouped_taxonomy_experiments_2026-06-04.md`

### Весовые эксперименты

Проверялись:

- обычные class weights;
- capped/smoothed class weights;
- индивидуальные веса по конкретным классам;
- режим без весов выборки, где gold и silver имеют одинаковый вес;
- grouped taxonomy.

Итог:

- grouped taxonomy поднялась до test mean macro-F1 около `0.3561`, но это уже другая, укрупненная таксономия;
- original taxonomy после весов не обогнала лучший исходный checkpoint;
- полный no-sample-weight run дал `0.2962`, ниже baseline;
- individual authority-only full дал около `0.3000`, то есть почти baseline, но без надежного прироста.

Сводные документы:

- `docs/class_weight_balancing_experiments_2026-06-05.md`
- `docs/individual_class_weighting_experiments_2026-06-05.md`
- `docs/no_sample_weight_class_sweep_2026-06-05.md`

### Pseudo-gold

Путь:

```text
data/ml_experiments/pseudo_gold_2026-06-06_v2/
```

Было добавлено `7134` pseudo-gold train rows. Они заметно увеличили редкие train-классы, например:

- `responsible_party.housing_inspection`: `9 -> 696`
- `responsible_party.specific_person`: `12 -> 120`
- `jkh_topic.management_company`: `9 -> 249`
- `authority_aspect.tariff_policy`: `8 -> 683`
- `appeal_type.demand`: `34 -> 298`

Но широкий full 8-axis pseudo-gold ухудшил test mean macro-F1 до `0.2385`. Из специалистов полезным оказался только `responsible_party`: test macro-F1 `0.1784` против cascade baseline `0.1495`. Остальные специалисты ухудшили test.

Документ:

- `docs/pseudo_gold_layer_experiments_2026-06-06.md`

### Selective taxonomy

Путь:

```text
data/ml_experiments/selective_taxonomy_2026-06-06_strict/
```

Лучший строгий selective-срез:

| Min coverage | Mean test macro-F1 | Mean test coverage |
| ---: | ---: | ---: |
| `0.8` | `0.3083` | `0.8706` |
| `0.6` | `0.3126` | `0.7689` |
| `0.5` | `0.3220` | `0.7141` |
| `0.4` | `0.3261` | `0.6926` |
| `0.3` | `0.3284` | `0.6668` |
| `0.2` | `0.3284` | `0.6668` |
| `0.1` | `0.3363` | `0.5076` |

Вывод: confidence filtering улучшает уверенный срез, но не превращает всю 8-осевую таксономию в высокоточную модель.

Документ:

- `docs/high_f1_recovery_attempts_2026-06-06.md`

### OMSU rating layer

Путь:

```text
data/ml_experiments/omsu_score_2026-06-06/threshold/negative_signal_capped_20k/
```

Лучший практический слой:

| Метрика | Значение |
| --- | ---: |
| Argmax test macro-F1 | `0.7321` |
| Threshold `0.69` test macro-F1 | `0.7635` |
| Selective coverage | `0.7496` |
| Selective accuracy | `0.9939` |
| Selective macro-F1 | `0.9102` |
| Selective weighted-F1 | `0.9937` |
| Negative F1 | `0.8235` |
| Negative precision | `0.8750` |
| Negative recall | `0.7778` |

Это самый сильный производственный результат. Его нужно использовать для числовой оценки работы ОМСУ, но не выдавать за качество всех 8 осей.

Документ:

- `docs/omsu_score_experiments_2026-06-06.md`

## Финальные проверки 2026-06-06

### Ensemble selector

Новый скрипт:

```text
experiments/evaluate_final_taxonomy_ensemble.py
```

Артефакты:

```text
data/ml_experiments/final_taxonomy_ensemble_2026-06-06/
```

Он сравнил доступные checkpoint-ы по каждой оси на human-gold validation и собрал hybrid. Выбранные источники:

| Ось | Источник по validation |
| --- | --- |
| `jkh_relevance` | `no_sample_balanced_full` |
| `jkh_topic` | `cascade_consistency` |
| `authority_aspect` | `cascade_consistency` |
| `sentiment` | `no_sample_balanced_full` |
| `appeal_type` | `cascade_consistency` |
| `responsible_party` | `pseudo_gold_responsible_specialist` |
| `sarcasm` | `cascade_consistency` |
| `quality` | `cascade_consistency` |

Результат:

| Variant | Split | Mean macro-F1 | Strict exact match |
| --- | --- | ---: | ---: |
| raw | validation | `0.3054` | `0.0702` |
| raw | test | `0.2943` | `0.0763` |
| with consistency rules | validation | `0.3093` | `0.0733` |
| with consistency rules | test | `0.2970` | `0.0855` |

Вывод: автоматический выбор по validation немного переобучился и не обогнал baseline на test. В производство этот ensemble не принимается.

### ЖКХ-внутренний specialist

Новые скрипты:

```text
experiments/build_jkh_internal_dataset.py
experiments/evaluate_jkh_routed_specialist.py
```

Артефакты:

```text
data/ml_experiments/jkh_internal_specialist_2026-06-06/
```

Датасет:

| Показатель | Значение |
| --- | ---: |
| Gold train внутри ЖКХ | `271` |
| Silver train внутри ЖКХ | `40136` |
| Gold val/test внутри ЖКХ | `110` |
| Всего строк | `40517` |

Обучение:

- модель: `cointegrated/rubert-tiny2`;
- target cols: `jkh_topic`, `authority_aspect`, `responsible_party`;
- epochs: `3`;
- batch size: `32`;
- max length: `256`;
- class weights: `weighted_balanced`, power `0.75`, cap `4.0`;
- длительность: около `21.5` минут, внутри лимита `40` минут.

Внутренний test specialist:

| Ось | Macro-F1 |
| --- | ---: |
| `jkh_topic` | `0.4915` |
| `authority_aspect` | `0.1170` |
| `responsible_party` | `0.2233` |

Полная routed-проверка на всех human-gold test:

| Split | Mean macro-F1 | Strict all-8 exact match |
| --- | ---: | ---: |
| validation | `0.2943` | `0.0733` |
| test | `0.2864` | `0.0885` |

По test:

| Ось | Macro-F1 |
| --- | ---: |
| `jkh_relevance` | `0.4475` |
| `jkh_topic` | `0.2983` |
| `authority_aspect` | `0.1538` |
| `sentiment` | `0.3710` |
| `appeal_type` | `0.2519` |
| `responsible_party` | `0.1762` |
| `sarcasm` | `0.3214` |
| `quality` | `0.2709` |

Вывод: внутренний specialist полезен как исследовательский факт, но в полном routed-сценарии ухудшает среднюю метрику. В финальную модель не принимается.

## Финальное решение по обучению

1. Для полной 8-осевой original taxonomy оставляем текущий каскад на базе:

```text
data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/final_w03_weighted_lr1e5_e4/
```

и deterministic consistency rules из:

```text
data/ml_experiments/cascade_eval_2026-06-06_01-48/
```

2. Для числовой оценки ОМСУ оставляем отдельный selective layer:

```text
data/ml_experiments/omsu_score_2026-06-06/threshold/negative_signal_capped_20k/
```

3. В приложении и API нужно разделять:

- подробные 8 осей: аналитическая таксономия с confidence/coverage;
- `omsu_score`, `omsu_negative_probability`, `omsu_decision`, `omsu_confidence_band`, `omsu_score_reason`: отдельный слой оценки работы ОМСУ.

4. Не принимаются как финальные:

- broad pseudo-gold full 8-axis model;
- gold-only specialists;
- automatic validation-selected ensemble;
- routed ЖКХ-internal specialist;
- large RuBERT variants;
- no-sample-weight full run;
- individual class-weight variants.

## Почему F1 не удалось поднять до 85% по всем 8 осям

Основная причина не в слабой видеокарте и не в недостатке эпох. Причина в обучающем сигнале:

- human-gold слишком мало для редких классов;
- многие классы семантически пересекаются;
- `authority_aspect` и `appeal_type` требуют понимания намерения, а не только слов;
- часть классов почти отсутствует в test/train;
- silver и pseudo-gold помогают по объему, но добавляют шум;
- validation/test по `655` строк малы для стабильного подбора десятков правил и весов;
- общий корпус доминируется `not_jkh` и `not_applicable`.

Поэтому честный высокий результат сейчас есть только у OMSU selective layer. Для полной 8-осевой таксономии текущий честный потолок находится в районе `0.29-0.33` strict mean macro-F1 в зависимости от способа оценки и confidence coverage.

## Практическая рекомендация для диплома

В дипломе не нужно делать вид, что 8-осевая таксономия стала production-grade на всех классах. Сильная и честная формулировка:

> Разработана система сбора и многоосевой разметки обращений в сфере ЖКХ. Для подробной таксономии используется каскадная модель с оценкой уверенности; для итоговой оценки работы ОМСУ введен отдельный числовой слой, который показал высокий результат на доверенном тестовом срезе.

Это честно, технически защищаемо и не разрушает идею приложения.
