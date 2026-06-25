# Единый аналитический свод метрик и данных проекта

Дата фиксации: `2026-06-06`.

Основные источники:

- `docs/ml_training_master_report_2026-06-06.md`;
- `docs/final_training_summary_2026-06-06.md`;
- `docs/omsu_score_experiments_2026-06-06.md`;
- `docs/cascade_system_evaluation_2026-06-06.md`;
- `docs/pseudo_gold_layer_experiments_2026-06-06.md`;
- `docs/high_f1_recovery_attempts_2026-06-06.md`;
- `docs/large_model_experiments_2026-06-04.md`;
- `docs/grouped_taxonomy_experiments_2026-06-04.md`;
- `docs/class_weight_balancing_experiments_2026-06-05.md`;
- `docs/individual_class_weighting_experiments_2026-06-05.md`;
- `docs/no_sample_weight_class_sweep_2026-06-05.md`;
- `docs/project_data_archive.md`;
- `docs/context_snapshot_2026-06-05.md`;
- `docs/chat_context.md`.

## 1. Назначение файла

Этот файл объединяет производственные данные, структуру корпуса, состояние ручной и автоматизированной разметки, ML-эксперименты, метрики моделей, итоговые выводы и ограничения ML-части дипломного проекта.

Файл предназначен для трех задач:

- использовать как основу аналитической главы ВКР;
- брать из него компактные таблицы для презентации и защиты;
- быстро восстанавливать, какие данные, модели и артефакты считаются финальными.

Важное правило интерпретации: `human-gold` является единственным доверенным источником для validation/test. `silver` и `pseudo-gold` допускаются только как обучающие слои и не являются экспертной истиной.

## 2. Краткий итог для диплома

1. Общий корпус после импорта содержит `265181` записей `SourceRecord`.
2. Записей с контекстом поста: `265131`.
3. Чистый human-gold fixed dataset содержит `4365` записей.
4. Human-gold split: train `3055`, validation `655`, test `655`.
5. Gold+silver fixed ML dataset содержит `264093` строки.
6. Train в gold+silver fixed dataset: `262783` строки.
7. Silver train rows: `259728`.
8. Производственная разметка на момент полного teacher-student export: `6719` отправленных и проверенных разметок, `5204` принято в обучающий датасет, `749` подтвержденных удаленных постов, `766` отклонено, `0` ожидает проверки.
9. Основной teacher-student export: `teacher_student_full_export_2026-06-03_01-06`, внутри `5953` raw approved annotations, `6719` total annotations и `26` silver batches.
10. Лучший original taxonomy checkpoint: `data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/final_w03_weighted_lr1e5_e4/`.
11. Честный потолок original 8-axis taxonomy на текущих данных: около `0.29-0.33` mean macro-F1 в зависимости от способа оценки и confidence coverage. Высокого F1 по всем классам полной таксономии не достигнуто.
12. Macro-F1 важнее accuracy, потому что классы резко несбалансированы: доминирующие `not_jkh`, `not_applicable` и `normal` могут давать высокую accuracy/weighted-F1 даже при провале редких классов.
13. Большой RuBERT-base не превзошел оптимизированный `rubert-tiny2`: лучший full-data large run дал test mean macro-F1 `0.2920` против baseline `0.3003`.
14. Grouped taxonomy полезнее без новой ручной разметки: grouped baseline дал `0.3544`, а grouped weighted capped result дал `0.3561`, но это укрупненная таксономия и ее нельзя напрямую сравнивать с original.
15. OMSU selective layer дал сильный production-like результат: coverage `0.7496`, accuracy `0.9939`, macro-F1 `0.9102`, weighted-F1 `0.9937`, negative F1 `0.8235`.
16. OMSU selective layer не заменяет 8-осевую таксономию. Он работает поверх нее как отдельный рейтинговый/оценочный слой для числовой оценки работы ОМСУ.
17. Финальная архитектура: 8-axis taxonomy model -> consistency rules -> отдельная OMSU binary model -> расчет `omsu_score`, вероятности, решения, confidence band и объяснения.

## Расхождения и уточнения

| Метрика / место | Значение 1 | Значение 2 | Вероятная причина |
| --- | ---: | ---: | --- |
| Original taxonomy headline | `0.3003` test mean macro-F1 | `0.3032` after cascade rules | `0.3003` относится к лучшему checkpoint до логической постобработки; `0.3032` относится к каскадной постобработке зависимых полей. |
| Cascade final strict check | `0.3032` headline macro-F1 | `0.2920` strict all-label test mean macro-F1 | В строгой перепроверке учитываются все label-слоты, включая отсутствующие/нулевые классы. Это жестче и честнее для редких классов. |
| `quality` macro-F1 в cascade | `0.3612` | `0.2709` strict all-label | Обычный macro-F1 может не учитывать классы с нулевой поддержкой, а strict all-label macro-F1 учитывает все классы, включая `duplicate` с нулевой поддержкой в test. |
| Silver weight | `0.4` в ранней fixed-dataset политике | `0.3` в финальном лучшем checkpoint | Dataset строился с общей политикой gold/silver, но финальные training runs использовали override `silver_weight=0.3`, который оказался лучше. |
| Production accepted | `5953` raw approved annotations | `5204` approved dataset labels | `5953 = 5204` обучающих approved labels + `749` подтвержденных удаленных постов. Удаленные посты важны для аудита, но не являются обычными обучающими метками. |
| Full-corpus matrices | `265181` rows | `264093` fixed ML dataset rows | Full-corpus matrices считались по полному корпусу `gold_raw + silver_auto`; fixed ML dataset является очищенным train/val/test набором для обучения. |

## 3. Производственная разметка

Фиксация production export: `2026-06-03T04:06:32+03:00`.

| Показатель | Значение |
| --- | ---: |
| Всего отправленных разметок | `6719` |
| Проверено | `6719` |
| Принято в датасет | `5204` |
| Подтвержденные удаленные посты | `749` |
| Отклонено | `766` |
| Ожидает проверки | `0` |
| Net points / итоговые баллы | `3991` |
| Raw approved annotations | `5953` |
| Дата фиксации | `2026-06-03T04:06:32+03:00` |

Удаленные посты являются важной частью аудита качества корпуса: они показывают, что студент или проверяющий обнаружил отсутствие исходного контекста. Однако такие записи не являются обычными обучающими labels по 8 осям, потому что текстовая задача для них фактически отсутствует.

## 4. Корпус данных

### Общий корпус и fixed splits

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
| Silver sample weight в лучшем original checkpoint | `0.3` |

### Teacher-student export

| Показатель | Значение |
| --- | --- |
| Основной export | `data/exports/teacher_student_full_export_2026-06-03_01-06/` |
| Серверный архив | `/home/oldskull/apps/Diplomnaya-rabota/data/exports/teacher_student_full_export_2026-06-03_01-06.tar.gz` |
| `01_gold_approved_annotations.csv` | `5953` raw approved annotations |
| `02_gold_all_annotations_audit.csv` | `6719` total annotations |
| `silver_batches/` | `259228` unresolved records |
| Количество silver batches | `26` |
| Silver rows generated by rules | `244852` |
| Silver audited overrides | `14376` |
| Duplicate records in silver labeling | `0` |
| Validation errors in silver labeling | `0` |

### Типы разметки

| Тип | Источник | Использование |
| --- | --- | --- |
| `human-gold` | Проверенная производственная разметка людей | Train, validation, test; единственный эталон качества |
| `silver_auto` | Автоматизированная/teacher разметка automatic teacher | Только train, с пониженным весом |
| `pseudo-gold` | Отобранная teacher-assisted разметка с anchors/model agreement | Только train, не экспертная истина |

## 5. Методология разметки

### 8 осей таксономии

| Ось | Назначение |
| --- | --- |
| `jkh_relevance` | Относится ли запись к ЖКХ |
| `jkh_topic` | Тема ЖКХ |
| `authority_aspect` | Аспект работы власти/ОМСУ |
| `sentiment` | Тональность реакции |
| `appeal_type` | Тип обращения или реакции |
| `responsible_party` | Кто воспринимается ответственным |
| `sarcasm` | Наличие сарказма |
| `quality` | Качество и пригодность текста |

### Роль поста и комментария

В текущей постановке единицей анализа является связка "пост + комментарий". Пост задает основной предмет обсуждения, поэтому именно пост определяет направление темы и релевантность ЖКХ. Например, короткий комментарий "ну наконец-то" под постом об отоплении все равно относится к теме отопления, хотя сам по себе не содержит слова "отопление".

Комментарий отвечает за общественную реакцию: тональность, сарказм, тип обращения, качество текста, эмоциональную направленность и дополнительные детали. Это важно для аналитики общественного восприятия: пост сообщает, о какой проблеме идет речь, а комментарий показывает, как люди на нее реагируют.

Validation/test нельзя строить на `silver` или `pseudo-gold`, потому что эти слои не являются независимой экспертной истиной. Они полезны для расширения train, но если проверять модель на них же, метрика будет отражать согласие с teacher-правилами, а не реальное качество.

## 6. Распределение и проблема дисбаланса

### Ранний accepted snapshot по `jkh_relevance`

Официальный snapshot от `2026-05-25` показывал сильный перекос:

| Класс | Количество | Доля |
| --- | ---: | ---: |
| Positive ЖКХ | `351` | `7.90%` |
| Non-ЖКХ | `4073` | `91.69%` |
| Всего training-ready approved labels | `4442` | `100%` |

### Silver distribution

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

### OMSU impact distribution

Dataset:

```text
data/ml_experiments/omsu_score_2026-06-06/dataset_gold_silver_omsu_fixed_split.csv
```

| `omsu_impact_class` | Count |
| --- | ---: |
| `neutral_or_no_impact` | `236340` |
| `strong_negative` | `13734` |
| `negative` | `10122` |
| `positive` | `3897` |

| `omsu_negative_signal` | Count |
| --- | ---: |
| `not_negative_omsu` | `240237` |
| `negative_omsu` | `23856` |

В human-gold test split для OMSU-задачи:

| Класс | Count |
| --- | ---: |
| `negative_omsu` | `47` |
| `not_negative_omsu` | `608` |

### Редкие классы в human-gold train

| Axis | Class | Gold train count |
| --- | --- | ---: |
| `jkh_topic` | `house_common_property` | `4` |
| `jkh_topic` | `management_company` | `9` |
| `jkh_topic` | `payments_tariffs` | `10` |
| `authority_aspect` | `tariff_policy` | `8` |
| `authority_aspect` | `supervision` | `11` |
| `authority_aspect` | `positive_feedback` | `14` |
| `responsible_party` | `housing_inspection` | `9` |
| `responsible_party` | `specific_person` | `12` |
| `responsible_party` | `residents` | `13` |
| `appeal_type` | `demand` | `34` |
| `quality` | `duplicate` | `3` |

Аналитический вывод: accuracy и weighted-F1 могут быть завышены из-за доминирующих классов. Поэтому основной метрикой для выбора модели является macro-F1: она штрафует ситуацию, когда модель хорошо угадывает массовые классы, но почти не умеет распознавать редкие.

## 7. Лучший original taxonomy checkpoint

Путь:

```text
data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/final_w03_weighted_lr1e5_e4/
```

| Параметр | Значение |
| --- | --- |
| Модель | `cointegrated/rubert-tiny2` |
| Text mode | `post_comment` |
| Target heads | 8 original taxonomy heads |
| Epochs | `4` |
| Batch size | `32` |
| Max length | `256` |
| Learning rate | `1e-5` |
| Dropout | `0.3` |
| Class weights | `weighted_balanced` |
| Silver weight override | `0.3` |
| Device | `cuda` |
| Total rows | `264093` |
| Train rows | `262783` |
| Validation rows | `655` human-gold |
| Test rows | `655` human-gold |
| Best validation macro-F1 | `0.3086` |
| Test mean macro-F1 headline | `0.3003` |

Test per-head metrics до cascade consistency rules:

| Axis | Accuracy | Macro-F1 | Weighted-F1 |
| --- | ---: | ---: | ---: |
| `jkh_relevance` | `0.7893` | `0.4475` | `0.8279` |
| `jkh_topic` | `0.7405` | `0.3088` | `0.8103` |
| `authority_aspect` | `0.6824` | `0.1921` | `0.7709` |
| `sentiment` | `0.4580` | `0.3710` | `0.4327` |
| `appeal_type` | `0.3298` | `0.2519` | `0.3256` |
| `responsible_party` | `0.7053` | `0.1482` | `0.7892` |
| `sarcasm` | `0.5847` | `0.3214` | `0.5783` |
| `quality` | `0.8580` | `0.3612` | `0.8228` |

Вывод: модель пригодна как базовый аналитический слой, но не является высокоточной по всем классам. Самые слабые оси: `responsible_party`, `authority_aspect`, `appeal_type`, редкие классы `jkh_topic`.

## 8. Каскадная постобработка original taxonomy

Правило логической согласованности:

```text
если jkh_relevance = no,
то:
    jkh_topic = not_jkh
    authority_aspect = not_applicable
    responsible_party = not_applicable
```

Правило не меняет смысл текста, а устраняет нелогичные комбинации, когда запись признана не-ЖКХ, но зависимые поля остаются ЖКХ-специфичными.

| Показатель | Значение |
| --- | ---: |
| Baseline mean macro-F1 до правил | `0.3003` |
| Headline mean macro-F1 после правил | `0.3032` |
| Strict test mean macro-F1 после финальной all-label перепроверки | `0.2920` |
| Strict all-8 exact match после правил | `0.0885` |
| Затронуто test-записей | `36` из `655` |

Test split, `655` human-gold записей, после cascade consistency rules:

| Axis | Accuracy | Macro-F1 | Strict all-label Macro-F1 | Weighted-F1 |
| --- | ---: | ---: | ---: | ---: |
| `jkh_relevance` | `0.7893` | `0.4475` | `0.4475` | `0.8279` |
| `jkh_topic` | `0.7466` | `0.3106` | `0.3106` | `0.8143` |
| `authority_aspect` | `0.7282` | `0.2128` | `0.2128` | `0.8021` |
| `sentiment` | `0.4580` | `0.3710` | `0.3710` | `0.4327` |
| `appeal_type` | `0.3298` | `0.2519` | `0.2519` | `0.3256` |
| `responsible_party` | `0.7145` | `0.1495` | `0.1495` | `0.7952` |
| `sarcasm` | `0.5847` | `0.3214` | `0.3214` | `0.5783` |
| `quality` | `0.8580` | `0.3612` | `0.2709` | `0.8228` |

Финальная строгая перепроверка:

| Split | Strict mean macro-F1 | Strict all-8 exact match |
| --- | ---: | ---: |
| validation | `0.2969` | `0.0733` |
| test | `0.2920` | `0.0885` |

## 9. Эксперименты с большими моделями

Validation/test всегда human-gold: `655` validation и `655` test. Silver использовался только в train.

| Run | Модель | Train rows | Best validation macro-F1 | Test mean macro-F1 |
| --- | --- | ---: | ---: | ---: |
| `final_w03_weighted_lr1e5_e4` | `cointegrated/rubert-tiny2` | `262783` | `0.3086` | `0.3003` |
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

Вывод: большой RuBERT-base не превзошел optimized `rubert-tiny2`. Следовательно, основной предел не в размере энкодера, а в структуре данных, шуме silver, малом числе human-gold для редких классов и неоднозначных границах таксономии.

## 10. Grouped taxonomy

Grouped taxonomy была проверена как практическая альтернатива при отсутствии новой human-gold разметки.

### Что группировалось

| Ось | Группировка |
| --- | --- |
| `jkh_relevance` | `no` + `unsure` -> `no_or_unsure`; `yes` отдельно |
| `jkh_topic` | water/sewerage + heating/hot water -> `utilities_water_heat`; house common property + management company -> `housing_management`; остальные крупные темы отдельно |
| `authority_aspect` | poor quality + slow response + no action -> `service_problem`; supervision + tariff policy -> `governance_control`; остальные отдельно |
| `appeal_type` | complaint + demand + request -> `problem_appeal`; suggestion + gratitude -> `constructive_positive`; остальные отдельно |
| `responsible_party` | local administration + housing inspection + specific person -> `public_authority`; УК + resource provider + waste operator -> `utility_or_management`; остальные отдельно |
| `quality` | difficult + duplicate + no_context -> `problematic_or_duplicate`; normal и spam отдельно |
| `sentiment`, `sarcasm` | Не группировались |

Grouped dataset:

```text
data/ml_experiments/teacher_student_grouped_2026-06-04/dataset_gold_silver_grouped_fixed_split.csv
```

Grouped baseline checkpoint:

```text
data/ml_experiments/teacher_student_runs/grouped_taxonomy_2026-06-04/tiny2_grouped_w03_lr1e5_e4/
```

Grouped weighted capped checkpoint:

```text
data/ml_experiments/class_weight_sweep_2026-06-05/grouped_weighted_power075_cap4_full/
```

### Grouped baseline

| Epoch | Validation macro-F1 |
| ---: | ---: |
| 1 | `0.3358` |
| 2 | `0.3440` |
| 3 | `0.3463` |
| 4 | `0.3469` |

| Metric | Value |
| --- | ---: |
| Test mean macro-F1 | `0.3544` |

Baseline per-head test:

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

### Grouped weighted capped result

| Run | Best validation macro-F1 | Test mean macro-F1 |
| --- | ---: | ---: |
| `tiny2_grouped_w03_lr1e5_e4` | `0.3469` | `0.3544` |
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

Grouped taxonomy не является прямой заменой original taxonomy, потому что классы укрупнены. Это практическая альтернатива для авторазметки при отсутствии новой human-gold разметки.

## 11. Эксперименты с весами классов

### Class-weight balancing

Цель: проверить, можно ли улучшить rare-class macro-F1 за счет более аккуратной развесовки классов.

Ключевая формула smoothed capped weights:

```text
вес_класса = (общее_число / (число_классов * число_примеров_класса)) ** 0.75
верхний_предел = 4.0
silver_weight = 0.3
```

| Схема | Таксономия | Train rows | Best val macro-F1 | Test mean macro-F1 | Вывод |
| --- | --- | ---: | ---: | ---: | --- |
| `original_gold_cap3_screen` | original | `80000` | `0.2349` | `0.2267` | плохо |
| `original_gold_cap5_screen` | original | `80000` | `0.2081` | `0.2041` | плохо |
| `original_gold_power075_cap4_screen` | original | `80000` | `0.2437` | `0.2275` | плохо |
| `original_current_weighted_screen` | original | `80000` | `0.2729` | `0.2750` | screen baseline |
| `original_weighted_power075_cap4_screen` | original | `80000` | `0.2796` | `0.2682` | validation лучше, test хуже |
| `grouped_current_weighted_screen` | grouped | `80000` | `0.3346` | `0.3357` | grouped baseline |
| `grouped_weighted_power075_cap4_screen` | grouped | `80000` | `0.3472` | `0.3464` | лучший screen |
| `original_weighted_power075_cap4_full` | original | `262783` | `0.3074` | `0.2956` | не победил baseline `0.3003` |
| `grouped_weighted_power075_cap4_full` | grouped | `262783` | `0.3546` | `0.3561` | лучший grouped |

Итог: для original taxonomy новая схема весов не стала лучше baseline (`0.2956 < 0.3003`). Для grouped taxonomy capped weights дали небольшой честный прирост (`0.3561`).

### No-sample-weight class sweep

Цель: проверить идею убрать веса выборки, то есть сделать gold и silver равными по весу.

Настройка:

```text
gold_weight_override = 1.0
silver_weight_override = 1.0
```

| Run | Train rows | Epochs | Class weights | Best val macro-F1 | Test mean macro-F1 |
| --- | ---: | ---: | --- | ---: | ---: |
| `no_sample_balanced_full` | `262783` | `4` | balanced | `0.3077` | `0.2962` |
| `no_sample_balanced_power075_cap4_screen` | `80000` | `2` | balanced power `0.75`, cap `4` | `0.2804` | `0.2688` |
| `no_sample_balanced_screen` | `80000` | `2` | balanced | `0.2730` | `0.2730` |
| `no_sample_balanced_power05_cap6_screen` | `80000` | `2` | balanced power `0.5`, cap `6` | `0.2586` | `0.2532` |
| `no_sample_gold_power075_cap4_screen` | `80000` | `2` | gold balanced | `0.2436` | `0.2261` |
| `no_sample_gold_power05_cap6_screen` | `80000` | `2` | gold balanced | `0.2363` | `0.2296` |
| `no_sample_none_screen` | `80000` | `2` | none | `0.2146` | `0.2087` |

Итог: no sample weights дал `0.2962`, что ниже baseline `0.3003`. Silver без понижения веса начинает слишком сильно шуметь.

### Individual class weighting

Цель: проверить не общие веса по осям, а индивидуальные веса слабых классов original taxonomy.

Screen v2:

| Run | Best val macro-F1 | Test mean macro-F1 | Вывод |
| --- | ---: | ---: | --- |
| baseline screen | `0.2735` | `0.2733` | короткий ориентир |
| `guarded` | `0.2571` | `0.2587` | хуже |
| `fn_fp_ratio` | `0.2760` | `0.2533` | validation overfit |
| `weak_only` | `0.2730` | `0.2748` | слабый screen test, ниже по val |
| `authority_only` | `0.2717` | `0.2770` | выбран для full |

Full:

| Run | Best val macro-F1 | Test mean macro-F1 |
| --- | ---: | ---: |
| baseline `final_w03_weighted_lr1e5_e4` | `0.3086` | `0.3003` |
| `original_individual_authority_only_full` | `0.3078` | `0.3000` |

Итог: individual authority_only full дал `0.3000`, то есть не обогнал baseline `0.3003`.

## 12. Pseudo-gold layer

Pseudo-gold вводился как teacher-assisted train-слой для редких классов, когда новой ручной разметки больше не планировалось. Это не human-gold и не может использоваться для validation/test.

Путь:

```text
data/ml_experiments/pseudo_gold_2026-06-06_v2/
```

| Показатель | Значение |
| --- | ---: |
| Gold train | `3055` |
| Pseudo-gold train | `7134` |
| Gold validation/test | `1310` |
| Итоговый dataset | `11499` |

Примеры усиления редких классов:

| Axis | Class | Before | After |
| --- | --- | ---: | ---: |
| `jkh_relevance` | `yes` | `295` | `6503` |
| `jkh_topic` | `management_company` | `9` | `249` |
| `jkh_topic` | `house_common_property` | `4` | `346` |
| `authority_aspect` | `tariff_policy` | `8` | `683` |
| `authority_aspect` | `supervision` | `11` | `463` |
| `appeal_type` | `demand` | `34` | `298` |
| `appeal_type` | `request` | `83` | `283` |
| `responsible_party` | `housing_inspection` | `9` | `696` |
| `responsible_party` | `specific_person` | `12` | `120` |
| `quality` | `difficult` | `185` | `250` |
| `quality` | `duplicate` | `3` | `18` |

Проверка:

| Модель / слой | Test result |
| --- | ---: |
| Full 8-axis gold+pseudo-gold | `0.2385` mean macro-F1 |
| `responsible_party` pseudo-gold specialist | `0.1784` macro-F1 |
| Cascade baseline для `responsible_party` | `0.1495` macro-F1 |
| Hybrid cascade + `responsible_party` specialist | около `0.3069` mean 8-axis macro-F1 |

Вывод: pseudo-gold полезен как train-слой и как источник specialist-экспериментов, но не решает фундаментально проблему высокого F1 по полной original taxonomy. Широкое смешивание pseudo-gold со всеми осями ухудшило качество.

## 13. Selective taxonomy и попытки поднять F1

Selective taxonomy проверяла идею учитывать только уверенные предсказания.

| Min coverage | Mean test macro-F1 | Mean test coverage |
| ---: | ---: | ---: |
| `0.8` | `0.3083` | `0.8706` |
| `0.6` | `0.3126` | `0.7689` |
| `0.5` | `0.3220` | `0.7141` |
| `0.4` | `0.3261` | `0.6926` |
| `0.3` | `0.3284` | `0.6668` |
| `0.2` | `0.3284` | `0.6668` |
| `0.1` | `0.3363` | `0.5076` |

Дополнительные high-F1 recovery attempts:

| Подход | Результат |
| --- | --- |
| Gold-only specialists | Завершены за `28-29` минут, но не решили слабые оси |
| `responsible_party` gold-only specialist | `0.1546`, чуть выше cascade `0.1495`, но хуже pseudo-gold specialist |
| `authority_aspect` gold-only specialist | `0.1058` против cascade `0.2128` |
| `appeal_type` gold-only specialist | `0.0917` против cascade `0.2519` |
| `jkh_topic` gold-only specialist | `0.2030` против cascade `0.3106` |
| Rule-based anchor overrides | validation выглядел лучше, test не подтвердил |

Вывод: confidence filtering немного улучшает результат, но высокий F1 по всем классам не дает. Агрессивные high-confidence срезы могут методически завышать картину, если из оценки исчезают редкие классы.

## 14. OMSU score layer

OMSU score layer нужен для отдельной числовой оценки работы ОМСУ. Он не заменяет 8 осей, а использует их и отдельную binary model как рейтинговый слой.

### Поля OMSU layer

| Поле | Смысл |
| --- | --- |
| `omsu_score` | Числовая оценка влияния на восприятие работы ОМСУ |
| `omsu_negative_probability` | Вероятность негативного сигнала |
| `omsu_decision` | `negative_omsu`, `not_negative_omsu` или `low_confidence` |
| `omsu_confidence_band` | Зона уверенности |
| `omsu_score_reason` | Объяснение, из каких осей получилась оценка |

### Интерпретируемая формула `omsu_score`

```text
оценка_ОМСУ =
    округлить(
        ограничить(
            базовая_оценка * вес_связи_с_ОМСУ * вес_качества,
            от -100 до 100
        )
    )
```

```text
базовая_оценка =
    баллы_тональности
  + баллы_типа_обращения
  + баллы_аспекта_работы_власти
```

```text
вес_связи_с_ОМСУ =
    максимум(
        вес_ответственной_стороны,
        вес_темы_ЖКХ * 0.85,
        вес_аспекта_работы_власти
    )
```

Если запись не относится к ЖКХ или имеет качество `spam`/`duplicate`, то `оценка_ОМСУ = 0`.

### Распределения

| `omsu_impact_class` | Count |
| --- | ---: |
| `neutral_or_no_impact` | `236340` |
| `strong_negative` | `13734` |
| `negative` | `10122` |
| `positive` | `3897` |

| `omsu_negative_signal` | Count |
| --- | ---: |
| `not_negative_omsu` | `240237` |
| `negative_omsu` | `23856` |

### Derived from 8 axes

| Split | Negative-signal macro-F1 | Negative-signal weighted-F1 | MAE score |
| --- | ---: | ---: | ---: |
| validation | `0.6129` | `0.8618` | `11.87` |
| test | `0.6371` | `0.8502` | `13.14` |

Вывод: производная оценка от предсказанных 8 осей возможна, но недостаточно надежна для сильного рейтингового вывода.

### Direct binary OMSU classifier

Checkpoint:

```text
data/ml_experiments/omsu_score_2026-06-06/threshold/negative_signal_capped_20k/
```

| Параметр | Значение |
| --- | --- |
| Model | `cointegrated/rubert-tiny2` |
| Text mode | `post_comment` |
| Max length | `192` |
| Batch size | `16` |
| Learning rate | `1e-5` |
| Epochs | `3` |
| Train rows | `20000` |
| Class weights | `weighted_balanced`, power `0.75`, cap `4` |
| Silver weight | `0.3` |

| Метод | Test macro-F1 | Weighted-F1 | Negative F1 |
| --- | ---: | ---: | ---: |
| Argmax | `0.7321` | `0.9083` | `0.5263` |
| Threshold `0.69` | `0.7635` | `0.9302` | `0.5690` |
| Selective `>=0.85` / `<=0.15` | `0.9102` | `0.9937` | `0.8235` |

Главная таблица selective-policy на test:

| Метрика | Значение |
| --- | ---: |
| Coverage | `0.7496` |
| Accuracy | `0.9939` |
| Macro-F1 | `0.9102` |
| Weighted-F1 | `0.9937` |
| Negative F1 | `0.8235` |
| Negative precision | `0.8750` |
| Negative recall | `0.7778` |

Selective policy:

```text
если P(negative_omsu) >= 0.85 -> negative_omsu
если P(negative_omsu) <= 0.15 -> not_negative_omsu
иначе -> low_confidence
```

Вывод: для рейтинговой оценки ОМСУ нужен отдельный классификатор `negative_omsu`, потому что производная оценка только из 8 осей дала test macro-F1 около `0.6371` и MAE score около `13.14`.

## 15. Финальная архитектура системы

Финальный каскад:

1. Модель `final_w03_weighted_lr1e5_e4` предсказывает 8 осей таксономии.
2. Применяются consistency rules для зависимых полей при `jkh_relevance=no`.
3. Отдельная модель `negative_signal_capped_20k` определяет вероятность `negative_omsu`.
4. Рассчитываются `omsu_score`, `omsu_negative_probability`, `omsu_decision`, `omsu_confidence_band`, `omsu_score_reason`.
5. Результаты уходят в API, приложение, статистику и инфографику.

Схема:

```text
пост + комментарий
        |
        v
8-осевая taxonomy model
        |
        v
consistency rules
        |
        +--> аналитические оси для статистики и инфографики
        |
        v
OMSU binary model + OMSU scoring
        |
        +--> omsu_score
        +--> omsu_negative_probability
        +--> omsu_decision
        +--> omsu_confidence_band
        +--> omsu_score_reason
```

## 16. Таблица "что сработало / что не сработало"

| Подход | Результат | Сработало / нет | Почему | Как использовать в дипломе |
| --- | --- | --- | --- | --- |
| Optimized tiny2 original taxonomy | `0.3003` test mean macro-F1 headline | Частично | Лучший original checkpoint, но слабые rare classes | Основная baseline-модель 8 осей |
| Cascade rules | `0.3003 -> 0.3032` headline, strict test `0.2920` | Частично | Логически исправляет зависимые поля | Использовать как безопасную постобработку |
| Big RuBERT | Лучший full `0.2920` | Нет | Размер энкодера не решает шум и дефицит gold | Показать, что проблема не только в модели |
| Grouped taxonomy | `0.3544`, затем `0.3561` | Да, для укрупненной задачи | Укрупнение снижает шум границ | Практическая альтернатива при отсутствии новой gold |
| Capped class weights | Original `0.2956`, grouped `0.3561` | Для original нет, для grouped да | Сглаживает редкие grouped-классы, но original остается шумной | Описать как проверенный вариант нормализации весов |
| No sample weights | `0.2962 < 0.3003` | Нет | Silver без понижения веса шумит | Обосновать сохранение веса silver |
| Individual class weights | `authority_only_full=0.3000 < 0.3003` | Нет | Validation-ошибки плохо переносятся на test | Показать, что точечные веса не дали надежного прироста |
| Broad pseudo-gold | Full 8-axis `0.2385` | Нет | Pseudo-gold меняет распределение и добавляет шум | Указать ограничение pseudo-gold |
| Targeted pseudo-gold specialist | `responsible_party 0.1495 -> 0.1784` | Частично | Помогает одной оси, не решает все | Исследовательский слой, не production-final |
| Selective taxonomy | максимум `0.3363` при coverage `0.5076` | Частично | Уверенные срезы лучше, но покрытие падает | Использовать как confidence analysis |
| OMSU binary layer | selective macro-F1 `0.9102` | Да | Задача проще и целевая: негативный сигнал ОМСУ | Главный production-like ML результат |

## 17. Ограничения исследования

1. Human-gold мало для редких классов.
2. Классы сильно несбалансированы.
3. Silver помогает объемом, но содержит шум teacher-разметки.
4. Pseudo-gold не является экспертной разметкой.
5. Границы таксономии неоднозначны: например, где заканчивается реакция на УК и начинается оценка ОМСУ.
6. Accuracy и weighted-F1 не подходят как главные метрики из-за доминирующих классов.
7. Grouped taxonomy не сравнивается напрямую с original taxonomy, потому что классы укрупнены.
8. Validation/test по `655` строк малы для устойчивого подбора большого числа весов, правил и порогов.
9. OMSU layer хорош как отдельная оценочная задача, но не заменяет подробную 8-осевую таксономию.
10. Для дальнейшего роста original taxonomy нужна новая human-gold разметка или упрощение классов.

## 18. Готовые формулировки для диплома

1. В работе использовалось разделение данных на доверенную ручную разметку `human-gold` и автоматически сформированную обучающую разметку `silver`.
2. Разметка `silver` применялась только на этапе обучения и не использовалась для validation/test, что позволило сохранить независимость итоговой оценки качества.
3. Основной метрикой качества была выбрана macro-F1, поскольку корпус характеризуется выраженным дисбалансом классов.
4. Высокие значения accuracy и weighted-F1 в данной задаче могут быть связаны с доминированием массовых классов и не отражают качество распознавания редких категорий.
5. Эксперименты с полной 8-осевой таксономией показали текущий потолок качества около `0.29-0.33` mean macro-F1.
6. Увеличение размера языковой модели до RuBERT-base не привело к улучшению качества, что указывает на доминирующую роль структуры данных и качества разметки.
7. Укрупнение редких и неоднозначных классов в grouped taxonomy позволило повысить устойчивость авторазметки, однако такая постановка не является прямой заменой исходной таксономии.
8. Для оценки работы ОМСУ был введен отдельный числовой слой, который не заменяет подробную таксономию, а дополняет ее рейтинговой интерпретацией.
9. Отдельная binary-модель для `negative_omsu` показала более высокое качество, чем производная оценка, рассчитанная только из предсказанных 8 осей.
10. Финальная архитектура имеет каскадный характер: многоосевая таксономия используется для аналитики, а отдельный OMSU-layer используется для рейтингового вывода.
11. Псевдо-золотая разметка рассматривалась как обучающий слой, но не как экспертная истина, поэтому ее результаты проверялись только на human-gold test.
12. Дальнейшее улучшение качества полной таксономии требует расширения доверенной разметки редких классов или пересмотра гранулярности классов.

## 19. Готовые формулировки для защиты

| Вопрос | Короткий ответ |
| --- | --- |
| Почему F1 по 8 осям невысокий? | Потому что задача слишком детальная, классы редкие и несбалансированные, а доверенной human-gold разметки мало. |
| Это провал модели? | Нет. Модель выявила реальное ограничение данных: dominant classes угадываются хорошо, но rare classes требуют больше экспертных примеров. |
| Почему не помогла большая модель? | Большая модель не исправляет шумные границы классов и недостаток rare-class примеров. Проблема не только в мощности энкодера. |
| Зачем grouped taxonomy? | Это способ укрупнить спорные классы и получить более стабильную авторазметку без новой ручной разметки. |
| Почему OMSU слой получился сильным? | Потому что это более сфокусированная задача: определить негативный сигнал к ОМСУ, а не сразу все редкие классы таксономии. |
| Почему OMSU layer не заменяет 8 осей? | 8 осей объясняют тему и структуру обращения, а OMSU layer дает итоговую рейтинговую оценку поверх этой аналитики. |
| Почему macro-F1 важнее accuracy? | Accuracy может быть высокой за счет массовых классов, а macro-F1 показывает, как модель работает с каждым классом независимо от частоты. |
| Что нужно для роста качества? | Больше human-gold по редким классам, контрастные примеры, упрощение спорных классов или переход на grouped/cascade-подход. |

## 20. Индекс артефактов

| Путь | Что там лежит | Зачем нужно | Использовать |
| --- | --- | --- | --- |
| `docs/ml_training_master_report_2026-06-06.md` | Главный ML-отчет | Полная история экспериментов и выводов | Диплом, защита |
| `docs/final_training_summary_2026-06-06.md` | Финальное закрытие обучения | Короткий итог последнего этапа | Диплом, защита |
| `docs/analytics_metrics_master_2026-06-06.md` | Этот аналитический свод | Единая таблица данных, метрик и выводов | Диплом, презентация |
| `docs/project_data_archive.md` | Индекс архивов и данных | Где лежат данные/модели/архивы | Восстановление, отчет |
| `exports/diploma_full_project_archive_2026-06-06_06-52.tar.zst` | Полный локальный архив проекта | Сборка диплома и резервная копия | Локально, не в git |
| `data/exports/teacher_student_full_export_2026-06-03_01-06/` | Gold export, audit, statistics, silver batches | Исходник teacher-student этапа | Диплом, аудит |
| `data/ml_experiments/teacher_student_full_2026-06-03_01-06/dataset_gold_silver_fixed_split.csv` | Fixed gold+silver dataset | Основной ML dataset | Обучение |
| `data/ml_experiments/teacher_student_full_2026-06-03_01-06/dataset_gold_only_fixed_split.csv` | Gold-only fixed dataset | Контроль и validation/test | Оценка |
| `data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/final_w03_weighted_lr1e5_e4/` | Лучший original checkpoint | Базовая 8-axis model | Приложение, аналитика |
| `data/ml_experiments/cascade_eval_2026-06-06_01-48/` | Cascade evaluation outputs | Проверка rules + OMSU layer | Диплом, приложение |
| `data/ml_experiments/omsu_score_2026-06-06/dataset_gold_silver_omsu_fixed_split.csv` | Dataset с OMSU полями | Обучение/оценка OMSU layer | Диплом, приложение |
| `data/ml_experiments/omsu_score_2026-06-06/threshold/negative_signal_capped_20k/` | Лучший OMSU checkpoint | Отдельный `negative_omsu` классификатор | Приложение |
| `data/ml_experiments/omsu_score_2026-06-06/threshold/selective_policy_085_015/` | Selective policy results | Метрики уверенного решения | Диплом, защита |
| `data/ml_experiments/teacher_student_runs/large_model_presets_2026-06-04/comparison/` | Сравнение large presets | Доказательство, что big RuBERT не помог | Диплом |
| `data/ml_experiments/teacher_student_runs/large_model_full_2026-06-04/rubert_base_conversational_last2_all_train_lr5e5_e1_b32/` | Full-data large run | Сравнение с tiny2 | Диплом |
| `data/ml_experiments/teacher_student_grouped_2026-06-04/dataset_gold_silver_grouped_fixed_split.csv` | Grouped dataset | Укрупненная таксономия | Исследование |
| `data/ml_experiments/teacher_student_runs/grouped_taxonomy_2026-06-04/tiny2_grouped_w03_lr1e5_e4/` | Grouped baseline checkpoint | Практический grouped baseline | Исследование |
| `data/ml_experiments/class_weight_sweep_2026-06-05/grouped_weighted_power075_cap4_full/` | Лучший grouped weighted checkpoint | Лучший grouped result `0.3561` | Исследование |
| `data/ml_experiments/class_weight_sweep_2026-06-05/original_weighted_power075_cap4_full/` | Original capped class weights | Проверка весов | Диплом |
| `data/ml_experiments/no_sample_weight_class_sweep_2026-06-05/` | No sample weights sweep | Проверка равного веса gold/silver | Диплом |
| `data/ml_experiments/individual_class_weighting_2026-06-05/` | Individual class weights | Проверка весов отдельных классов | Диплом |
| `data/ml_experiments/pseudo_gold_2026-06-06_v2/` | Pseudo-gold dataset и specialists | Targeted pseudo-gold | Диплом, исследование |
| `data/ml_experiments/selective_taxonomy_2026-06-06_strict/` | Selective taxonomy metrics | Coverage/F1 анализ | Диплом |
| `data/ml_experiments/gold_specialists_2026-06-06/` | Gold-only specialists | Проверка слабых осей | Диплом |
| `data/ml_experiments/final_taxonomy_ensemble_2026-06-06/` | Validation-selected ensemble | Финальная проверка, отклонена | Диплом |
| `data/ml_experiments/jkh_internal_specialist_2026-06-06/` | ЖКХ-internal specialist | Финальная проверка, отклонена | Диплом |
| `data/exports/full_corpus_confusions_2026-06-03/` | Full-corpus predictions, `265181` rows | Матрицы ошибок | Презентация, caveat про silver |
| `data/exports/full_corpus_confusion_counts_matplotlib_2026-06-03/` | PNG/SVG/CSV count matrices | Визуальные матрицы ошибок | Презентация |
| `data/exports/full_corpus_binary_agreement_matrices_2026-06-03/` | Binary agreement matrices | Да/нет сходится по осям | Презентация |
| `data/exports/full_corpus_one_vs_rest_label_matrices_2026-06-03/` | One-vs-rest matrices по каждому классу | Анализ отдельных метрик/classes | Презентация, аналитика |
| `experiments/train_rubert_multitask.py` | Multitask trainer | Воспроизводимость обучения | Код |
| `experiments/evaluate_cascade_system.py` | Cascade evaluator | Финальная оценка каскада | Код |
| `experiments/omsu_scoring.py` | Интерпретируемая формула OMSU score | Объяснимый рейтинг | Код, диплом |
| `experiments/evaluate_selective_taxonomy_policy.py` | Selective taxonomy evaluator | Confidence/coverage анализ | Код |
| `experiments/build_grouped_taxonomy_dataset.py` | Grouped dataset builder | Укрупнение классов | Код |
| `experiments/build_pseudo_gold_layer.py` | Pseudo-gold builder | Teacher-assisted train layer | Код |

## Короткий финальный вывод

ML-часть проекта завершилась честным разделением результатов. Полная 8-осевая таксономия полезна как аналитическая структура, но с текущим объемом human-gold и редкими классами ее потолок находится примерно в зоне `0.29-0.33` mean macro-F1. Большие модели, веса классов, no-sample-weight, pseudo-gold и specialists не дали надежного прорыва по original taxonomy.

При этом отдельный слой оценки ОМСУ оказался сильным: selective binary model для `negative_omsu` достигает test macro-F1 `0.9102` при coverage `0.7496`. Поэтому финальная система должна использовать каскад: 8 осей для объяснимой аналитики и статистики, а OMSU selective layer для рейтинговой оценки работы ОМСУ.
