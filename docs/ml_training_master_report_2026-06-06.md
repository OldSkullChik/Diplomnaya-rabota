# Единый отчет по данным, тестам, обучению и итогам ML-контура

Дата фиксации: `2026-06-06`.

Проект: дипломная работа по сбору, разметке и автоматической аналитике обращений/комментариев в сфере ЖКХ и оценки работы ОМСУ.

Этот файл объединяет основные данные, ход экспериментов, результаты тестов, финальные выводы и ссылки на артефакты. Тяжелые CSV, модели, картинки, матрицы и checkpoint-и не хранятся в git, но их локальные пути указаны здесь.

## Главный вывод

Финальная архитектура должна состоять из двух контуров:

1. **8-осевая таксономия** для подробной аналитики:
   `jkh_relevance`, `jkh_topic`, `authority_aspect`, `sentiment`, `appeal_type`, `responsible_party`, `sarcasm`, `quality`.

2. **Отдельная числовая оценка ОМСУ**:
   `omsu_score`, `omsu_negative_probability`, `omsu_decision`, `omsu_confidence_band`, `omsu_score_reason`.

Высокого F1 по всем классам полной 8-осевой таксономии достичь не удалось. Честный потолок текущих данных по original taxonomy находится примерно в зоне `0.29-0.33` mean macro-F1, в зависимости от способа оценки и confidence coverage. Причина не в длительности обучения и не только в размере модели, а в малом количестве human-gold для редких и неоднозначных классов.

Сильный production-like результат получен для отдельного слоя оценки ОМСУ:

| Метрика OMSU selective layer | Значение |
| --- | ---: |
| Coverage | `0.7496` |
| Accuracy | `0.9939` |
| Macro-F1 | `0.9102` |
| Weighted-F1 | `0.9937` |
| Negative F1 | `0.8235` |
| Negative precision | `0.8750` |
| Negative recall | `0.7778` |

Итоговое решение: обучение по текущей полной таксономии закрыто. Дальнейший существенный рост возможен только при новой human-gold разметке, упрощении/группировке таксономии или изменении постановки задачи.

## Где хранится все важное

### Главные документы

| Файл | Содержание |
| --- | --- |
| `docs/chat_context.md` | Живая память проекта и решений |
| `docs/final_training_summary_2026-06-06.md` | Финальное закрытие обучения |
| `docs/ml_training_master_report_2026-06-06.md` | Этот единый отчет |
| `docs/project_data_archive.md` | Индекс расположения данных |
| `docs/teacher_student_training_2026-06-03.md` | Teacher-student export/training |
| `docs/large_model_experiments_2026-06-04.md` | Большие модели |
| `docs/grouped_taxonomy_experiments_2026-06-04.md` | Укрупненная таксономия |
| `docs/class_weight_balancing_experiments_2026-06-05.md` | Балансировка весов классов |
| `docs/individual_class_weighting_experiments_2026-06-05.md` | Индивидуальные веса классов |
| `docs/no_sample_weight_class_sweep_2026-06-05.md` | Тест без весов выборки |
| `docs/omsu_score_experiments_2026-06-06.md` | Оценка ОМСУ |
| `docs/cascade_system_evaluation_2026-06-06.md` | Общий каскад |
| `docs/pseudo_gold_layer_experiments_2026-06-06.md` | Псевдо-золотая разметка |
| `docs/high_f1_recovery_attempts_2026-06-06.md` | Попытки поднять F1 после pseudo-gold |
| `docs/model_weak_axes_analysis_2026-06-03.md` | Анализ слабых осей |

### Главные локальные артефакты

| Папка | Содержание |
| --- | --- |
| `data/ml_experiments/teacher_student_full_2026-06-03_01-06/` | Fixed gold/silver datasets |
| `data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/final_w03_weighted_lr1e5_e4/` | Лучший original 8-axis checkpoint |
| `data/ml_experiments/omsu_score_2026-06-06/threshold/negative_signal_capped_20k/` | Лучший OMSU checkpoint |
| `data/ml_experiments/cascade_eval_2026-06-06_01-48/` | Общий каскад + OMSU evaluator |
| `data/ml_experiments/pseudo_gold_2026-06-06_v2/` | Targeted pseudo-gold v2 |
| `data/ml_experiments/selective_taxonomy_2026-06-06_strict/` | Strict selective taxonomy |
| `data/ml_experiments/gold_specialists_2026-06-06/` | Gold-only specialists |
| `data/ml_experiments/final_taxonomy_ensemble_2026-06-06/` | Финальный ensemble selector, отклонен |
| `data/ml_experiments/jkh_internal_specialist_2026-06-06/` | ЖКХ-internal specialist, отклонен |
| `data/exports/full_corpus_confusions_2026-06-03/` | Предсказания по `265181` строкам |
| `data/exports/full_corpus_confusion_counts_matplotlib_2026-06-03/` | Absolute-count confusion matrices |
| `data/exports/full_corpus_binary_agreement_matrices_2026-06-03/` | Binary agreement matrices |
| `data/exports/full_corpus_one_vs_rest_label_matrices_2026-06-03/` | One-vs-rest matrices по каждому классу |

## Данные и разметка

### Производственная разметка после финальной проверки

| Показатель | Значение |
| --- | ---: |
| Всего отправленных разметок | `6219` |
| Проверено | `6219` |
| Ожидает проверки | `0` |
| Принято в датасет | `4704` |
| Подтвержденные удаленные посты | `749` |
| Отклонено всего | `766` |
| Net points | `3491` |

Удаленные посты считаются отдельно: они важны для аудита, но не входят как обычные обучающие labels.

### Общий корпус

| Показатель | Значение |
| --- | ---: |
| Всего `SourceRecord` после импорта | `265181` |
| Записей с контекстом поста | `265131` |
| Gold-only fixed dataset | `4365` |
| Gold train | `3055` |
| Gold validation | `655` |
| Gold test | `655` |
| Gold+silver fixed dataset | `264093` |
| Train в gold+silver fixed dataset | `262783` |
| Silver train rows | `259728` |
| Silver sample weight в основной схеме | `0.3` |

### Teacher-student source export

Локальная папка:

```text
data/exports/teacher_student_full_export_2026-06-03_01-06/
```

Производственный архив:

```text
/home/oldskull/apps/Diplomnaya-rabota/data/exports/teacher_student_full_export_2026-06-03_01-06.tar.gz
```

Состав:

- `01_gold_approved_annotations.csv`: `5953` raw approved annotations;
- `02_gold_all_annotations_audit.csv`: `6719` total annotations;
- `03_gold_statistics/`: статистика production export;
- `silver_batches/`: `259228` unresolved records в `26` CSV batches.

Silver labeling:

| Показатель | Значение |
| --- | ---: |
| Silver rows | `259228` |
| Generated by rules | `244852` |
| Audited overrides | `14376` |
| Duplicate records | `0` |
| Validation errors | `0` |

Основное распределение silver:

| Label | Count |
| --- | ---: |
| `jkh_relevance=no` | `183557` |
| `jkh_relevance=yes` | `75671` |
| `not_jkh` | `183557` |
| `waste_cleaning` | `26637` |
| `yard_area` | `23354` |
| `house_common_property` | `5254` |
| `cold_water_sewerage` | `5043` |
| `public_authorities` | `4938` |
| `heating_hot_water` | `4695` |
| `payments_tariffs` | `4679` |
| `other_jkh` | `1071` |

## Методологические решения

### Пост важнее комментария для темы ЖКХ

В процессе отбора было принято принципиальное решение:

- пост задает тему и основной контекст;
- комментарий является реакцией общественности;
- релевантность ЖКХ и тема ЖКХ определяются преимущественно по посту;
- тональность, тип обращения, сарказм и детали реакции учитываются по связке `post + comment`.

Это решение привело к strict post-only кампании приоритизации.

### ЖКХ-enrichment campaign

Итоговый production dry-run и activation:

| Показатель | Значение |
| --- | ---: |
| Unresolved records | `259788` |
| Likely ЖКХ candidates | `14954` |
| Random controls | `150` |
| Paused general records | `244684` |

Пул был активирован на сервере. После restart `diplom-gunicorn` публичный `/healthz/` вернул:

```json
{"status": "ok", "database": "ok", "maintenance": false}
```

## Таксономия

Финальная original taxonomy состоит из 8 осей:

| Ось | Смысл |
| --- | --- |
| `jkh_relevance` | относится ли запись к ЖКХ |
| `jkh_topic` | тема ЖКХ |
| `authority_aspect` | аспект работы власти/ОМСУ |
| `sentiment` | тональность реакции |
| `appeal_type` | тип обращения/реакции |
| `responsible_party` | кто воспринимается ответственным |
| `sarcasm` | наличие сарказма |
| `quality` | качество/пригодность комментария |

Отдельно введены поля оценки ОМСУ:

| Поле | Смысл |
| --- | --- |
| `omsu_score` | числовая оценка влияния на восприятие работы ОМСУ |
| `omsu_negative_probability` | вероятность негативного сигнала |
| `omsu_decision` | решение: negative / not_negative / low_confidence |
| `omsu_confidence_band` | зона уверенности |
| `omsu_score_reason` | объяснение оценки |

## Политика оценки

Для всех ML-экспериментов главным правилом было:

- train может использовать gold + silver / pseudo-gold;
- validation и test должны оставаться human-gold;
- silver/pseudo-gold нельзя переносить в validation/test;
- выбор модели делается по validation, но финальное решение подтверждается на test;
- macro-F1 важнее accuracy, потому что классы сильно несбалансированы.

Почему accuracy не годится как главный показатель:

- `not_jkh`, `not_applicable`, `normal`, `opinion` доминируют;
- модель может давать высокую accuracy, просто угадывая частые классы;
- редкие классы важны для аналитики, но именно они чаще всего проседают;
- поэтому основной индикатор качества - macro-F1.

## Хронология основных этапов

| Дата | Этап | Итог |
| --- | --- | --- |
| 2026-05-21 | Первые benchmark-и old/new | Старый корпус лучше из-за объема и простой таксономии |
| 2026-05-25 | Большая проверка разметок | Подготовлены и применены решения review |
| 2026-05-26 | ЖКХ-priority campaign | Активирован strict post-only пул |
| 2026-06-02 | Финальная проверка pending | `6219` checked, `4704` accepted dataset |
| 2026-06-03 | Teacher-student export | Gold/silver fixed dataset `264093` rows |
| 2026-06-03 | Diamond / full corpus matrices | Полные матрицы по `265181` строкам |
| 2026-06-04 | Large models / grouped taxonomy | Large хуже tiny2; grouped лучше, но другая таксономия |
| 2026-06-05 | Class/sample weights | Original taxonomy не улучшилась |
| 2026-06-06 | OMSU rating | Selective macro-F1 `0.9102` |
| 2026-06-06 | Pseudo-gold / specialists | Полезен только `responsible_party`, и слабо |
| 2026-06-06 | Финальное закрытие | Обучение закрыто, принята cascade + OMSU architecture |

## Benchmark с reference-проектом `Normalizaciya`

Ранний benchmark сравнивал старый проект и новый ЖКХ-проект.

Старый полный корпус:

| Ось | Accuracy / Macro-F1 |
| --- | ---: |
| `sentiment` macro-F1 | `0.790` |
| `appeal_type` macro-F1 | `0.761` |
| `common_addressee` macro-F1 | `0.898` |

Вывод: старый корпус давал сильные метрики, потому что он гораздо больше (`138680` старых records) и использует более простую таксономию. Новый ЖКХ-проект сложнее: больше осей, больше редких классов, больше контекстной неоднозначности.

## Teacher-student обучение

### Gold-only baseline

Gold-only контроль был нужен как нижний ориентир. Он показал, что человеческой голды без silver недостаточно.

Пример результата:

| Метрика | Значение |
| --- | ---: |
| `jkh_relevance` accuracy | `0.9191` |
| `jkh_relevance` macro-F1 | `0.4459` |
| `jkh_relevance` weighted-F1 | `0.8973` |

Интерпретация: высокая accuracy объясняется перекосом классов, а не надежностью по всей таксономии.

### Первый gold+silver teacher-student run

Конфигурация:

- model: `cointegrated/rubert-tiny2`;
- heads: все 8 taxonomy heads;
- text mode: `post_comment`;
- epochs: `2`;
- batch size: `32`;
- max length: `256`;
- device: CUDA.

Training:

| Epoch | Train loss | Val macro-F1 |
| ---: | ---: | ---: |
| 1 | `2.5903` | `0.3024` |
| 2 | `2.9005` | `0.3046` |

Human-gold test:

| Ось | Accuracy | Macro-F1 | Weighted-F1 |
| --- | ---: | ---: | ---: |
| `jkh_relevance` | `0.7863` | `0.4456` | `0.8256` |
| `jkh_topic` | `0.7313` | `0.3022` | `0.8036` |
| `authority_aspect` | `0.6718` | `0.1809` | `0.7633` |
| `sentiment` | `0.4519` | `0.3646` | `0.4264` |
| `appeal_type` | `0.3267` | `0.2478` | `0.3206` |
| `responsible_party` | `0.7008` | `0.1477` | `0.7863` |
| `sarcasm` | `0.5771` | `0.3179` | `0.5727` |
| `quality` | `0.8595` | `0.3622` | `0.8237` |

Mean macro-F1:

| Run | Mean macro-F1 |
| --- | ---: |
| Gold-only | `0.2249` |
| Gold+silver | `0.2961` |
| Delta | `+0.0712` |

Вывод: teacher-student подход полезен, но не решает rare-class проблему полностью.

### Sweep teacher-student

Quick sweep:

| Run | Best val macro-F1 | Test mean macro-F1 | Silver weight | Class weights | LR |
| --- | ---: | ---: | ---: | --- | ---: |
| `quick_w03_weighted` | `0.2951` | `0.3000` | `0.3` | `weighted_balanced` | `2e-5` |
| `quick_w04_weighted` | `0.2937` | `0.2999` | `0.4` | `weighted_balanced` | `2e-5` |
| `quick_w02_weighted` | `0.2925` | `0.2997` | `0.2` | `weighted_balanced` | `2e-5` |
| `quick_w05_weighted` | `0.2921` | `0.3000` | `0.5` | `weighted_balanced` | `2e-5` |
| `quick_w03_no_class_weights` | `0.2740` | `0.2661` | `0.3` | `none` | `2e-5` |

Финальный лучший original checkpoint:

```text
data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/final_w03_weighted_lr1e5_e4/
```

Headline:

| Показатель | Значение |
| --- | ---: |
| Best validation macro-F1 | `0.3086` |
| Test mean macro-F1 | `0.3003` |

## Diamond data

Diamond layer был попыткой получить более надежную teacher-assisted разметку.

Архив:

```text
data/exports/diamond_labeled_data_2026-06-03.tar.gz
```

Ключевые файлы:

- `01_diamond_import_ready_labels.csv`;
- `02_diamond_train_ml.csv`;
- `03_dataset_gold_diamond_fixed_split.csv`;
- `04_dataset_gold_diamond_silver_weighted_fixed_split.csv`;
- `05_silver_remainder_low_weight.csv`;
- `06_silver_model_scores_audit.csv`;
- `07_diamond_rejected_borderline_sample.csv`;
- `08_diamond_summary.*`;
- `09_diamond_manifest.*`.

Результаты:

| Run | Train data | Test mean macro-F1 |
| --- | --- | ---: |
| `diamond_full_2026-06-03` | gold + diamond + low-weight silver | `0.2972` |
| `diamond_clean_2026-06-03` | gold + diamond only | `0.2768` |
| Current baseline | optimized gold+silver | `0.3003` |

Вывод: diamond data сохраняется как сильный labeled-data asset, но не заменяет лучший checkpoint.

## Full-corpus matrices and analytics

Пользователь запросил матрицы по всем `265000+` комментариям. Был обработан полный корпус:

| Группа | Строк |
| --- | ---: |
| All | `265181` |
| Gold raw | `5953` |
| Silver auto | `259228` |

### Absolute-count confusion matrices

Артефакты:

```text
data/exports/full_corpus_confusions_2026-06-03/
data/exports/full_corpus_confusion_counts_matplotlib_2026-06-03/
```

Создано:

- `24` PNG;
- `24` SVG;
- `24` matrix CSV;
- full predictions CSV на `265181` строк.

### Binary agreement matrices

Артефакты:

```text
data/exports/full_corpus_binary_agreement_matrices_2026-06-03/
```

Headline full-corpus agreement:

| Ось | Matched / Total |
| --- | ---: |
| `jkh_relevance` | `257334 / 265181` |
| `jkh_topic` | `247805 / 265181` |
| `authority_aspect` | `201039 / 265181` |
| `sentiment` | `197115 / 265181` |
| `appeal_type` | `190577 / 265181` |
| `responsible_party` | `244887 / 265181` |
| `sarcasm` | `198082 / 265181` |
| `quality` | `259004 / 265181` |
| Strict all-heads | `122091 / 265181` |

Важно: эти матрицы по all/silver сравнивают модель с automatic silver labels, а не с чистой human truth.

### One-vs-rest label matrices

Артефакты:

```text
data/exports/full_corpus_one_vs_rest_label_matrices_2026-06-03/
```

Создано:

- `52` classes per group;
- `156` class matrices across all/gold_raw/silver_auto;
- `156` PNG;
- `156` SVG;
- `157` CSV;
- `4` HTML;
- `1` JSON.

Примеры full-corpus class metrics:

| Класс | Support | TP | FN | FP | TN | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Администрация | `19869` | `17220` | `2649` | `3221` | `242091` | `~0.854` |
| Жилищная инспекция | `3961` | `3676` | `285` | `1367` | `259853` | не зафиксировано в summary |
| Оператор ТКО | `1878` | `1693` | `185` | `1783` | `261520` | не зафиксировано в summary |
| Плохое качество работы | `7009` | `1959` | `5050` | `8954` | `249218` | не зафиксировано в summary |

## Большие модели

Аппаратная база:

- GPU: `NVIDIA GeForce RTX 3050 Ti Laptop GPU`;
- VRAM: `4.0 GB`;
- CUDA доступна.

Текущий tiny2 baseline:

| Run | Model | Train rows | Best val macro-F1 | Test mean macro-F1 |
| --- | --- | ---: | ---: | ---: |
| `final_w03_weighted_lr1e5_e4` | `cointegrated/rubert-tiny2` | `262783` | `0.3086` | `0.3003` |

Large model checks:

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

Вывод: большая модель не решила проблему. Она слегка помогала сарказму/тональности, но проигрывала на доменных осях.

## Grouped taxonomy

Из-за слабых rare classes была проверена укрупненная таксономия.

Grouped baseline:

| Run | Best val macro-F1 | Test mean macro-F1 |
| --- | ---: | ---: |
| `tiny2_grouped_w03_lr1e5_e4` | `0.3469` | `0.3544` |

Grouped with new capped weights:

| Run | Best val macro-F1 | Test mean macro-F1 |
| --- | ---: | ---: |
| `grouped_weighted_power075_cap4_full` | `0.3546` | `0.3561` |

Per-head for grouped weighted:

| Head | Macro-F1 |
| --- | ---: |
| `jkh_relevance_grouped` | `0.6646` |
| `jkh_topic_grouped` | `0.2849` |
| `authority_aspect_grouped` | `0.2805` |
| `sentiment_grouped` | `0.3664` |
| `appeal_type_grouped` | `0.2993` |
| `responsible_party_grouped` | `0.2674` |
| `sarcasm_grouped` | `0.3251` |
| `quality_grouped` | `0.3605` |

Вывод: grouped taxonomy сильнее original taxonomy, но это уже другая, более грубая постановка задачи. Для диплома ее можно использовать как исследовательский вариант, но нельзя напрямую сравнивать с original taxonomy.

## Class weight balancing

Проверялись:

- aggressive weighted balancing;
- gold-only weights;
- smoothed weighted train weights;
- capped weights;
- grouped + capped weights.

Проблема старой схемы: веса редких классов могли быть экстремальными.

Примеры расчетных весов:

| Класс | Примерный вес |
| --- | ---: |
| `jkh_relevance.unsure` | `1799` |
| `jkh_topic.management_company` | `900` |
| `authority_aspect.other` | `310` |
| `responsible_party.specific_person` | `750` |
| `quality.duplicate` | `6748` |

Главная проверенная формула:

```text
weight = (total / (num_classes * class_count)) ** 0.75
```

Затем веса нормировались и ограничивались сверху `4.0`.

Результаты:

| Схема | Таксономия | Train rows | Best val macro-F1 | Test mean macro-F1 | Вывод |
| --- | --- | ---: | ---: | ---: | --- |
| `original_gold_cap3_screen` | original | `80000` | `0.2349` | `0.2267` | плохо |
| `original_gold_cap5_screen` | original | `80000` | `0.2081` | `0.2041` | плохо |
| `original_gold_power075_cap4_screen` | original | `80000` | `0.2437` | `0.2275` | плохо |
| `original_current_weighted_screen` | original | `80000` | `0.2729` | `0.2750` | baseline screen |
| `original_weighted_power075_cap4_screen` | original | `80000` | `0.2796` | `0.2682` | val лучше, test хуже |
| `grouped_current_weighted_screen` | grouped | `80000` | `0.3346` | `0.3357` | grouped baseline |
| `grouped_weighted_power075_cap4_screen` | grouped | `80000` | `0.3472` | `0.3464` | лучший screen |
| `original_weighted_power075_cap4_full` | original | `262783` | `0.3074` | `0.2956` | не победил baseline |
| `grouped_weighted_power075_cap4_full` | grouped | `262783` | `0.3546` | `0.3561` | лучший grouped |

Вывод: для original taxonomy новая схема весов не стала лучше baseline.

## Individual class weights

Проверялись индивидуальные веса по конкретным слабым классам.

Screen v2:

| Run | Val macro-F1 | Test mean macro-F1 |
| --- | ---: | ---: |
| baseline | `0.2735` | `0.2733` |
| `guarded` | `0.2571` | `0.2587` |
| `fn_fp_ratio` | `0.2760` | `0.2533` |
| `weak_only` | `0.2730` | `0.2748` |
| `authority_only` | `0.2717` | `0.2770` |

Full `authority_only`:

| Run | Val macro-F1 | Test mean macro-F1 |
| --- | ---: | ---: |
| `authority_only_full` | `0.3078` | `0.3000` |
| Current original baseline | `0.3086` | `0.3003` |

Вывод: индивидуальные веса классов не дали надежного прироста.

## No-sample-weight class sweep

Пользователь уточнил, что нужно убрать веса выборки, а не веса классов. Все runs принудительно ставили:

```text
gold_weight_override=1.0
silver_weight_override=1.0
```

Результаты:

| Run | Train rows | Epochs | Class weights | Best val macro-F1 | Test mean macro-F1 |
| --- | ---: | ---: | --- | ---: | ---: |
| `no_sample_balanced_full` | `262783` | `4` | balanced | `0.3077` | `0.2962` |
| `no_sample_balanced_power075_cap4_screen` | `80000` | `2` | balanced power 0.75 cap 4 | `0.2804` | `0.2688` |
| `no_sample_balanced_screen` | `80000` | `2` | balanced | `0.2730` | `0.2730` |
| `no_sample_balanced_power05_cap6_screen` | `80000` | `2` | balanced power 0.5 cap 6 | `0.2586` | `0.2532` |
| `no_sample_gold_power075_cap4_screen` | `80000` | `2` | gold balanced | `0.2436` | `0.2261` |
| `no_sample_gold_power05_cap6_screen` | `80000` | `2` | gold balanced | `0.2363` | `0.2296` |
| `no_sample_none_screen` | `80000` | `2` | none | `0.2146` | `0.2087` |

Вывод: полностью убирать sample weights не нужно. Silver без понижения веса начинает слишком сильно шуметь.

## Pseudo-gold

Pseudo-gold v2:

```text
data/ml_experiments/pseudo_gold_2026-06-06_v2/
```

Состав:

| Показатель | Значение |
| --- | ---: |
| Gold train rows | `3055` |
| Pseudo-gold train rows | `7134` |
| Gold val/test rows | `1310` |
| Dataset rows | `11499` |
| Pseudo weight | `0.85` |

Увеличение редких train counts:

| Класс | Было | Стало |
| --- | ---: | ---: |
| `responsible_party.housing_inspection` | `9` | `696` |
| `responsible_party.specific_person` | `12` | `120` |
| `jkh_topic.management_company` | `9` | `249` |
| `authority_aspect.tariff_policy` | `8` | `683` |
| `appeal_type.demand` | `34` | `298` |

Результаты:

| Модель | Test macro-F1 / mean |
| --- | ---: |
| Full 8-axis gold+pseudo-gold | `0.2385` |
| `responsible_party` pseudo-gold specialist | `0.1784` |
| Cascade `responsible_party` baseline | `0.1495` |
| Hybrid cascade + responsible specialist | около `0.3069` mean |
| `authority_aspect` specialist | `0.1293`, хуже baseline `0.2128` |
| `appeal_type` specialist | `0.1326`, хуже baseline `0.2519` |
| `jkh_topic` specialist | `0.2450`, хуже baseline `0.3106` |

Вывод: pseudo-gold нельзя широко смешивать с gold как будто это настоящая истина. Он полезен только точечно и только после проверки на human-gold test.

## Selective taxonomy

Strict selective taxonomy:

```text
data/ml_experiments/selective_taxonomy_2026-06-06_strict/
```

| Min coverage | Mean test macro-F1 | Mean test coverage |
| ---: | ---: | ---: |
| `0.8` | `0.3083` | `0.8706` |
| `0.6` | `0.3126` | `0.7689` |
| `0.5` | `0.3220` | `0.7141` |
| `0.4` | `0.3261` | `0.6926` |
| `0.3` | `0.3284` | `0.6668` |
| `0.2` | `0.3284` | `0.6668` |
| `0.1` | `0.3363` | `0.5076` |

Вывод: можно получить более качественный уверенный срез, но ценой coverage. Это полезно для аналитических витрин, но не решает полную автоматическую разметку.

## Gold-only specialists

Gold-only specialists обучались в лимите около `28-29` минут.

| Axis | Specialist test macro-F1 | Cascade baseline |
| --- | ---: | ---: |
| `responsible_party` | `0.1546` | `0.1495` |
| `authority_aspect` | `0.1058` | `0.2128` |
| `appeal_type` | `0.0917` | `0.2519` |
| `jkh_topic` | `0.2030` | `0.3106` |

Вывод: чистой gold train слишком мало. Specialists не решают задачу.

## Rule-based anchor overrides

Проверялись anchor overrides для `responsible_party` и `authority_aspect`.

| Axis | Best validation macro-F1 | Test after rules | Baseline test |
| --- | ---: | ---: | ---: |
| `responsible_party` | `0.2678` | `0.1481` | `0.1495` |
| `authority_aspect` | `0.2255` | `0.2041` | `0.2128` |

Вывод: правила переобучаются на validation и не подтверждаются на test.

## OMSU scoring layer

Датасет:

```text
data/ml_experiments/omsu_score_2026-06-06/dataset_gold_silver_omsu_fixed_split.csv
```

| Показатель | Значение |
| --- | ---: |
| Rows | `264093` |
| Mean `omsu_score` | `-5.94` |
| `negative_omsu` | `23856` |
| `not_negative_omsu` | `240237` |

Сначала score выводился из 8-axis predictions:

| Метод | Test macro-F1 | Weighted-F1 |
| --- | ---: | ---: |
| Derived from current best 8-axis predictions | `0.6371` | `0.8502` |

Затем обучена direct binary OMSU model:

```text
data/ml_experiments/omsu_score_2026-06-06/threshold/negative_signal_capped_20k/
```

| Метод | Test macro-F1 | Weighted-F1 | Negative F1 |
| --- | ---: | ---: | ---: |
| Argmax | `0.7321` | не указано | не указано |
| Threshold `0.69` | `0.7635` | `0.9302` | `0.5690` |
| Selective `>=0.85` / `<=0.15` | `0.9102` | `0.9937` | `0.8235` |

Selective policy:

- если `P(negative_omsu) >= 0.85`: `negative_omsu`;
- если `P(negative_omsu) <= 0.15`: `not_negative_omsu`;
- иначе: `low_confidence`.

Итоговый practical result:

| Метрика | Значение |
| --- | ---: |
| Coverage | `0.7496` |
| Accuracy | `0.9939` |
| Macro-F1 | `0.9102` |
| Weighted-F1 | `0.9937` |
| Negative F1 | `0.8235` |
| Negative precision | `0.8750` |
| Negative recall | `0.7778` |

Вывод: это главный сильный ML-результат проекта.

## Full cascade

Скрипт:

```text
experiments/evaluate_cascade_system.py
```

Артефакт:

```text
data/ml_experiments/cascade_eval_2026-06-06_01-48/
```

Компоненты:

- лучший 8-axis checkpoint;
- deterministic taxonomy consistency rules;
- direct OMSU checkpoint;
- selective OMSU decision.

Consistency rule:

```text
if jkh_relevance == no:
    jkh_topic = not_jkh
    authority_aspect = not_applicable
    responsible_party = not_applicable
```

Финальная строгая перепроверка all-label macro-F1:

| Split | Mean macro-F1 | Exact all-8 |
| --- | ---: | ---: |
| validation | `0.2969` | `0.0733` |
| test | `0.2920` | `0.0885` |

OMSU selective внутри каскада:

| Метрика | Значение |
| --- | ---: |
| Coverage | `0.7496` |
| Accuracy | `0.9939` |
| Macro-F1 | `0.9102` |
| Weighted-F1 | `0.9937` |
| Negative F1 | `0.8235` |

Вывод: каскад пригоден для приложения, если не выдавать подробную 8-axis taxonomy за высокоточную по всем классам.

## Финальные проверки 2026-06-06

### Final taxonomy ensemble

Скрипт:

```text
experiments/evaluate_final_taxonomy_ensemble.py
```

Артефакт:

```text
data/ml_experiments/final_taxonomy_ensemble_2026-06-06/
```

Он выбрал лучший источник по каждой оси на validation.

Выбранные источники:

| Axis | Selected source |
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

Вывод: validation-selected ensemble не принимается, потому что не дает надежного test-прироста.

### ЖКХ-internal specialist

Скрипты:

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
| Train gold внутри ЖКХ | `271` |
| Train silver внутри ЖКХ | `40136` |
| Gold val/test внутри ЖКХ | `110` |
| Dataset total | `40517` |

Обучение:

- `cointegrated/rubert-tiny2`;
- target cols: `jkh_topic`, `authority_aspect`, `responsible_party`;
- epochs: `3`;
- batch size: `32`;
- max length: `256`;
- class weight mode: `weighted_balanced`;
- class weight power: `0.75`;
- cap: `4.0`;
- runtime: около `21.5` минут, внутри лимита `40` минут.

Internal test:

| Axis | Macro-F1 |
| --- | ---: |
| `jkh_topic` | `0.4915` |
| `authority_aspect` | `0.1170` |
| `responsible_party` | `0.2233` |

Full routed evaluation:

| Split | Mean macro-F1 | Exact all-8 |
| --- | ---: | ---: |
| validation | `0.2943` | `0.0733` |
| test | `0.2864` | `0.0885` |

Test per axis:

| Axis | Macro-F1 |
| --- | ---: |
| `jkh_relevance` | `0.4475` |
| `jkh_topic` | `0.2983` |
| `authority_aspect` | `0.1538` |
| `sentiment` | `0.3710` |
| `appeal_type` | `0.2519` |
| `responsible_party` | `0.1762` |
| `sarcasm` | `0.3214` |
| `quality` | `0.2709` |

Вывод: specialist интересен исследовательски, но в full routed-сценарии ухудшает итог. В финал не принимается.

## Принято / отклонено

### Принято

| Компонент | Решение |
| --- | --- |
| Best original 8-axis checkpoint | Оставить как базу taxonomy |
| Consistency rules | Оставить |
| OMSU direct selective checkpoint | Оставить как главный production-like ML результат |
| Selective taxonomy | Использовать только как confidence/coverage analytic slice |
| Full corpus matrices | Использовать в аналитике/визуализации с caveat про silver |
| Grouped taxonomy | Упоминать как исследовательский вариант и возможное направление упрощения |

### Отклонено

| Компонент | Почему |
| --- | --- |
| Broad pseudo-gold full 8-axis | ухудшил test до `0.2385` |
| Gold-only specialists | слишком мало gold, слабые test results |
| Pseudo-gold specialists кроме `responsible_party` | ухудшили test |
| Rule-based anchor overrides | validation overfit |
| Large RuBERT variants | не обогнали tiny2 baseline |
| No-sample-weight full run | `0.2962`, ниже baseline |
| Individual class weighting | нет надежного test-прироста |
| Validation-selected ensemble | `0.2970`, не победил baseline |
| ЖКХ-internal routed specialist | `0.2864`, ухудшил full routed |

## Почему не получилось получить 85% F1 по всем осям

Причины:

1. Human-gold мало для редких классов.
2. Классы пересекаются семантически.
3. `authority_aspect` и `appeal_type` требуют понимания намерения, а не только ключевых слов.
4. `responsible_party` часто не названа прямо.
5. В полном корпусе доминируют `not_jkh` и `not_applicable`.
6. Silver увеличивает объем, но добавляет шум.
7. Pseudo-gold увеличивает rare classes, но не гарантирует правильных границ.
8. Validation/test по `655` строк малы для стабильной настройки десятков весов, порогов и правил.
9. Большая модель на 4 GB VRAM ограничена по режимам обучения и не решает проблему слабого обучающего сигнала.
10. Группировка классов помогает, но меняет задачу.

## Финальная архитектура приложения

Рекомендуемая схема:

```text
Вход: post_text + comment_text
        |
        v
8-axis taxonomy model
        |
        v
consistency rules
        |
        +--> taxonomy outputs for analytics
        |
        v
OMSU scoring model / OMSU probability layer
        |
        +--> omsu_score
        +--> omsu_negative_probability
        +--> omsu_decision
        +--> omsu_confidence_band
        +--> omsu_score_reason
```

Для API:

- подробные оси отдавать с confidence и/или пометкой о надежности;
- OMSU score отдавать отдельно;
- `low_confidence` не превращать в уверенное решение;
- для статистики показывать coverage рядом с качеством;
- не скрывать, что детальная taxonomy является аналитическим слоем, а не идеальным автосудьей.

## Формулировка для диплома

Можно использовать такую формулировку:

> В рамках работы разработана система сбора, разметки и автоматической аналитики общественных реакций на материалы, связанные с ЖКХ и работой ОМСУ. Для подробного анализа используется многоосевая таксономия, включающая релевантность ЖКХ, тему, аспект работы власти, тональность, тип обращения, ответственную сторону, сарказм и качество текста. Отдельно реализован числовой слой оценки работы ОМСУ, который формирует интегральную оценку и уровень уверенности. Эксперименты показали, что подробная 8-осевая таксономия требует большего объема доверенной ручной разметки для редких классов, однако отдельный слой оценки негативного сигнала ОМСУ достигает высокого качества на доверенном тестовом срезе.

## Итоговое решение

Финально принимаются:

```text
data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/final_w03_weighted_lr1e5_e4/
data/ml_experiments/cascade_eval_2026-06-06_01-48/
data/ml_experiments/omsu_score_2026-06-06/threshold/negative_signal_capped_20k/
```

Финально документируются как исследовательские, но не production-final:

```text
data/ml_experiments/pseudo_gold_2026-06-06_v2/
data/ml_experiments/selective_taxonomy_2026-06-06_strict/
data/ml_experiments/gold_specialists_2026-06-06/
data/ml_experiments/final_taxonomy_ensemble_2026-06-06/
data/ml_experiments/jkh_internal_specialist_2026-06-06/
data/ml_experiments/class_weight_sweep_2026-06-05/
data/ml_experiments/individual_class_weighting_2026-06-05/
data/ml_experiments/no_sample_weight_class_sweep_2026-06-05/
```

Обучение текущего ML-контура считается завершенным.
