# Псевдо-золотая разметка, 2026-06-06

## Решение по методике

Пользователь предложил использовать "псевдо-золотую разметку": не выдавать ее за human-gold, но построить более строгий teacher-assisted слой, основанный на закономерностях human-gold, текстовых признаках и проверках модели.

Методически это допустимо только при явном разделении:

- `human-gold` остается единственным эталоном для validation/test;
- `pseudo-gold` используется только в train;
- в дипломе pseudo-gold описывается как автоматизированно проверенная обучающая разметка, а не как ручная экспертная.

## Почему это понадобилось

Human-gold train содержит всего `3055` строк. Для слабых классов этого мало:

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

Цель pseudo-gold слоя: добрать обучающие примеры именно для таких классов.

## Builder

Добавлен скрипт:

```text
D:\Diplom\experiments\build_pseudo_gold_layer.py
```

Он использует:

- исходный fixed-split dataset:
  `data/ml_experiments/teacher_student_full_2026-06-03_01-06/dataset_gold_silver_fixed_split.csv`;
- model-score audit:
  `data/ml_experiments/diamond_dataset_2026-06-03/silver_model_scores.csv`;
- target minimum по редким классам;
- anchor-паттерны по темам ЖКХ, аспектам власти, типам обращения, ответственным сторонам и качеству текста;
- model agreement / class probability;
- logic consistency.

Выход:

```text
D:\Diplom\data\ml_experiments\pseudo_gold_2026-06-06_v2\
```

Основные файлы:

- `pseudo_gold_train.csv`;
- `dataset_gold_pseudogold_fixed_split.csv`;
- `pseudo_gold_selection_details.csv`;
- `pseudo_gold_summary.json`;
- `pseudo_gold_summary.md`.

## Pseudo-gold v2 counts

Собрано:

- gold train: `3055`;
- pseudo-gold train: `7134`;
- gold validation/test: `1310`;
- итоговый dataset: `11499`.

Примеры выравнивания train:

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

`quality=duplicate` почти не удалось добрать: это нормально, потому что дублей мало и их нельзя надежно "изобрести" текстовыми правилами.

## Проверка полной 8-осевой модели

Run:

```text
D:\Diplom\data\ml_experiments\pseudo_gold_2026-06-06_v2\runs\all8_pseudogold_screen_e2\
```

Конфигурация:

- model: `cointegrated/rubert-tiny2`;
- epochs: `2`;
- batch size: `16`;
- max length: `192`;
- class weights: `weighted_balanced`, power `0.75`, cap `4`;
- train: gold + pseudo-gold;
- validation/test: только human-gold.

Test mean macro-F1:

```text
0.2385
```

Это хуже текущего baseline `0.3003`. Полный pseudo-gold слой нельзя подключать как замену текущей 8-осевой модели: он слишком сильно меняет распределение и добавляет шум в некоторые оси.

## Specialist-проверки

Были обучены отдельные specialist-модели на weak axes.

| Specialist | Validation macro-F1 | Test macro-F1 | Baseline cascade test macro-F1 | Вывод |
| --- | ---: | ---: | ---: | --- |
| `responsible_party` | `0.2972` | `0.1784` | `0.1495` | улучшает |
| `authority_aspect` | `0.1762` | `0.1293` | `0.2128` | ухудшает |
| `appeal_type` | n/a | `0.1326` | `0.2519` | ухудшает |
| `jkh_topic` | n/a | `0.2450` | `0.3106` | ухудшает |

Гибрид "базовая 8-осевая модель + specialist только для `responsible_party`" дает:

- mean 8-axis macro-F1 на test: `0.3069`;
- было после cascade consistency rules: `0.3032`;
- прирост: примерно `+0.0036`.

Это небольшой, но реальный прирост на human-gold test.

## Вывод

Псевдо-золотая разметка как термин и методика подходит, но только в строгом варианте:

1. Не смешивать pseudo-gold со всеми осями без проверки.
2. Использовать pseudo-gold как targeted training layer для конкретных слабых осей.
3. Подключать specialist-модели только если они улучшают human-gold test.
4. Не переносить pseudo-gold в validation/test.

На текущем шаге pseudo-gold дал полезный сигнал только для `responsible_party`.

Главная причина: anchor-правила хорошо находят явных ответственных (`администрация`, `УК`, `ГЖИ`, ресурсник), но хуже отличают тонкие смысловые классы вроде `appeal_type` и `authority_aspect`, где нужны не слова, а интерпретация намерения.

Следующий практический шаг для роста качества:

- сделать отдельный, более строгий pseudo-gold v3 для `authority_aspect` и `appeal_type`;
- не брать весь класс по anchors, а формировать контрастные пары:
  `complaint` vs `demand`, `request` vs `question`, `no_action` vs `poor_quality`;
- проверять каждый specialist отдельно на human-gold test;
- в приложение подключать только те specialist-оси, которые дают прирост.
