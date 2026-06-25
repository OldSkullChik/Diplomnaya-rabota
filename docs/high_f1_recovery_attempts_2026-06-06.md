# Попытки поднять F1 после pseudo-gold, 2026-06-06

## Ограничение

Пользователь задал ограничение: не бросать обучение раньше времени, но держать лимит training-run около `40` минут.

В этой серии проверок использовались только human-gold validation/test для оценки. Pseudo-gold не переносился в validation/test.

## Базовая точка

Текущий каскад:

```text
D:\Diplom\data\ml_experiments\cascade_eval_2026-06-06_01-48\
```

Human-gold test:

- mean 8-axis macro-F1 после consistency rules: `0.3032`;
- strict all-8 exact match: `0.0885`;
- ОМСУ selective macro-F1: `0.9102` при coverage `0.7496`.

## Selective taxonomy

Добавлен скрипт:

```text
D:\Diplom\experiments\evaluate_selective_taxonomy_policy.py
```

Он подбирает threshold по validation для каждой оси и оценивает только уверенную часть. Важная методическая правка: после проверки была добавлена строгая all-label macro-F1, чтобы не завышать метрику, если high-confidence срез содержит только легкий доминирующий класс.

Артефакты:

```text
D:\Diplom\data\ml_experiments\selective_taxonomy_2026-06-06_strict\
```

Строгие результаты:

| Min coverage | Mean test macro-F1 | Mean test coverage |
| ---: | ---: | ---: |
| `0.8` | `0.3083` | `0.8706` |
| `0.6` | `0.3126` | `0.7689` |
| `0.5` | `0.3220` | `0.7141` |
| `0.4` | `0.3261` | `0.6926` |
| `0.3` | `0.3284` | `0.6668` |
| `0.2` | `0.3284` | `0.6668` |
| `0.1` | `0.3363` | `0.5076` |

Вывод: confidence filtering улучшает результат, но не дает высокого F1 по всем классам. Агрессивные срезы с красивыми present-label метриками оказались методически завышенными, потому что исключали редкие классы из среза.

## Gold-only specialist-модели

Были обучены specialist-модели на чистом human-gold dataset:

```text
D:\Diplom\data\ml_experiments\gold_specialists_2026-06-06\
```

Пакет укладывался в заданный лимит около `40` минут: фактическое время было около `28-29` минут.

Конфигурация:

- model: `cointegrated/rubert-tiny2`;
- train: `dataset_gold_only_fixed_split.csv`;
- epochs: `8`;
- batch size: `16`;
- max length: `192`;
- class weights: `balanced`, power `0.75`, cap `4`;
- отдельная модель на каждую слабую ось.

Test:

| Axis | Gold-only specialist macro-F1 | Cascade baseline macro-F1 | Вывод |
| --- | ---: | ---: | --- |
| `responsible_party` | `0.1546` | `0.1495` | маленький плюс, хуже pseudo-gold specialist |
| `authority_aspect` | `0.1058` | `0.2128` | хуже |
| `appeal_type` | `0.0917` | `0.2519` | хуже |
| `jkh_topic` | `0.2030` | `0.3106` | хуже |

Вывод: чистого gold слишком мало. Модель уходит в доминирующие классы, rare-class macro-F1 не растет.

## Pseudo-gold specialists

Из предыдущего pseudo-gold v2:

```text
D:\Diplom\data\ml_experiments\pseudo_gold_2026-06-06_v2\
```

Лучший полезный specialist:

| Axis | Pseudo-gold specialist macro-F1 | Cascade baseline macro-F1 |
| --- | ---: | ---: |
| `responsible_party` | `0.1784` | `0.1495` |

Гибрид "каскад + specialist только для `responsible_party`":

- mean 8-axis test macro-F1: `0.3069`;
- baseline cascade: `0.3032`;
- прирост: `+0.0036`.

Остальные pseudo-gold specialists ухудшили test:

| Axis | Pseudo-gold specialist macro-F1 | Cascade baseline macro-F1 |
| --- | ---: | ---: |
| `authority_aspect` | `0.1293` | `0.2128` |
| `appeal_type` | `0.1326` | `0.2519` |
| `jkh_topic` | `0.2450` | `0.3106` |

## Rule-based override

Были проверены anchor-override правила для `responsible_party` и `authority_aspect`.

Идея: если base confidence низкий, а текст содержит сильные anchor-признаки, заменить предсказание правилом.

Validation выглядел лучше, но test не подтвердил:

| Axis | Best val macro-F1 | Test macro-F1 после rules | Baseline test macro-F1 |
| --- | ---: | ---: | ---: |
| `responsible_party` | `0.2678` | `0.1481` | `0.1495` |
| `authority_aspect` | `0.2255` | `0.2041` | `0.2128` |

Вывод: простые anchor rules переобучаются на маленький validation и не подходят как automatic override.

## Итог

Высокий честный all-label macro-F1 по всем 8 осям текущими средствами не достигнут.

Что реально работает:

1. ОМСУ selective layer:
   - test macro-F1 `0.9102`;
   - coverage `0.7496`.
2. Taxonomy consistency rules:
   - mean macro-F1 `0.3003 -> 0.3032`;
   - exact match `0.0733 -> 0.0885`.
3. Pseudo-gold specialist только для `responsible_party`:
   - `0.1495 -> 0.1784`;
   - hybrid mean macro-F1 `0.3032 -> 0.3069`.
4. Strict selective taxonomy:
   - максимум `0.3363` mean macro-F1 при coverage `0.5076`;
   - это лучше, но не "высокая точность".

Что не сработало:

- broad gold+pseudo-gold training по всем 8 осям;
- gold-only specialists;
- pseudo-gold specialists для `authority_aspect`, `appeal_type`, `jkh_topic`;
- простые rule-based overrides.

## Причина

Главный дефицит не в размере модели и не в длительности обучения. Проблема в обучающем сигнале:

- human-gold train содержит слишком мало rare-class примеров;
- silver/pseudo-gold не содержит достаточно надежных границ для тонких классов;
- `authority_aspect` и `appeal_type` требуют интерпретации намерения, а не только словарных признаков;
- validation/test слишком маленькие для устойчивой настройки большого числа правил и порогов.

## Практическая рекомендация

Для приложения:

- использовать текущий каскад для 8 осей;
- добавить specialist `responsible_party` только если нужен небольшой прирост по этой оси;
- использовать selective taxonomy как "уверенный срез" для инфографики;
- обязательно показывать coverage рядом с F1/статистикой;
- ОМСУ-рейтинг строить через отдельный selective OМСУ layer, потому что именно там F1 уже высокий.

Для дальнейшего роста:

- делать pseudo-gold v3 не по anchors, а по контрастным парам:
  `complaint` vs `demand`, `request` vs `question`, `no_action` vs `poor_quality`;
- принимать specialist только после улучшения на human-gold test;
- не тратить длинное обучение на full all-axes без изменения качества labels.
