# План двух тестов авторазметчика

Дата фиксации: 2026-05-21.

Цель: сравнить старый и новый подходы к разметке, а затем обучить компактные multi-head модели на базе `cointegrated/rubert-tiny2` с использованием GPU.

## Где лежит полный архив данных

Канонический указатель: `docs/project_data_archive.md`.

Для teacher-student этапа полная серверная выгрузка хранится по шаблону:

```text
/home/oldskull/apps/Diplomnaya-rabota/data/exports/teacher_student_full_export_YYYY-MM-DD_HH-MM/
/home/oldskull/apps/Diplomnaya-rabota/data/exports/teacher_student_full_export_YYYY-MM-DD_HH-MM.tar.gz
```

После скачивания локальная копия должна лежать здесь:

```text
D:\Diplom\data\exports\teacher_student_full_export_YYYY-MM-DD_HH-MM\
```

Именно эта выгрузка содержит gold-часть (`01_gold_approved_annotations.csv`),
аудит всех аннотаций, статистику и numbered silver batches с неразмеченными
записями. Для отчетов и воспроизводимости указывать точный timestamp архива.

## Аппаратная база

Локальный ноутбук подходит для экспериментов:

- CPU: Intel Core i5-11400H, 6 ядер / 12 потоков;
- GPU: NVIDIA GeForce RTX 3050 Ti Laptop GPU, около 4 ГБ VRAM;
- `nvidia-smi` работает;
- Django-окружение `.venv` оставляем как есть, а для обучения желательно создать отдельное `.venv-ml` на Python 3.11.

Статус на 2026-05-21: `.venv-ml` создано и проверено. Установлены `torch 2.11.0+cu128`, `transformers 5.9.0`, `scikit-learn 1.8.0`, `pandas 3.0.3`, `numpy 2.4.6`, `rich 15.0.0`. PyTorch видит CUDA 12.8 и устройство `NVIDIA GeForce RTX 3050 Ti Laptop GPU`; smoke-тест матричного умножения на GPU прошел.

4 ГБ VRAM достаточно для `rubert-tiny2`, но не для больших LLM. Практичный режим: batch size 8-16, `max_length` 256, mixed precision на CUDA.

## Тест 1: равный объем, три общие оси

Новый проект:

- берутся все доступные утвержденные записи из текущей Django-разметки.

Старый проект:

- берется такое же количество записей из `Normalizaciya/structured/dataset_labeled.csv`;
- выборка случайная, но воспроизводимая через фиксированный seed.

Оси сравнения:

- `sentiment`;
- `appeal_type`;
- `common_addressee`.

Почему `common_addressee`: в старом проекте третья ось называется `addressee`, а в новом ближайшее поле — `responsible_party`. Для честного сравнения они приводятся к общему словарю:

- `jkh_organization`;
- `authority`;
- `residents`;
- `specific_person`;
- `none_or_unknown`.

Задачи:

- сравнить распределения меток;
- обучить маленькую multi-head ruBERT-модель на новом наборе;
- обучить такую же модель на равной старой выборке;
- сравнить accuracy, macro F1, weighted F1 и отчеты по классам.

Смысл теста: проверить, как новая разметка смотрится против старой при равном объеме и одинаковой сложности по трем общим осям.

## Тест 2: максимум доступных данных

Новый проект:

- берутся все доступные утвержденные записи.

Старый проект:

- берутся все доступные архивные размеченные записи.

Сравнение:

- для общих осей сравниваются оба проекта на всем доступном объеме;
- для нового проекта дополнительно проверяются все поля текущей ЖКХ-таксономии.

Оси нового полного теста:

- `jkh_relevance`;
- `jkh_topic`;
- `authority_aspect`;
- `sentiment`;
- `appeal_type`;
- `responsible_party`;
- `sarcasm`;
- `quality`.

Задачи:

- обучить модель на всех старых данных по общим трем осям;
- обучить модель на всех новых данных по общим трем осям;
- обучить отдельную модель на новых данных по полной ЖКХ-таксономии;
- сравнить качество, дисбаланс классов, редкие классы и устойчивость модели.

Смысл теста: получить максимальную картину — старый корпус как исторический baseline, новый корпус как целевой дипломный датасет.

## Команды подготовки

На сервере после очередной проверки разметки:

```bash
cd ~/apps/Diplomnaya-rabota
source .venv/bin/activate
python manage.py export_annotations data/exports/approved_annotations.csv
```

На локальной машине:

```powershell
cd D:\Diplom
scp oldskull@192.168.1.77:/home/oldskull/apps/Diplomnaya-rabota/data/exports/approved_annotations.csv .\data\exports\
```

Создание ML-окружения:

```powershell
cd D:\Diplom
py -3.11 -m venv .venv-ml
.\.venv-ml\Scripts\python -m pip install --upgrade pip
.\.venv-ml\Scripts\python -m pip install pandas numpy scikit-learn transformers rich
.\.venv-ml\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cu128
```

Примечание: локальный `py -3.12` на момент проверки зарегистрирован, но установка повреждена и не находит стандартную библиотеку. Для обучения используем Python 3.11.

Проверка GPU:

```powershell
.\.venv-ml\Scripts\python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

Подготовка выборок:

```powershell
.\.venv-ml\Scripts\python experiments\prepare_rubert_benchmarks.py `
  --new-approved data\exports\approved_annotations.csv `
  --old-labeled Normalizaciya\structured\dataset_labeled.csv `
  --output-dir data\ml_experiments\rubert_benchmarks `
  --seed 42
```

## Команды обучения

Тест 1, новая разметка, три общие оси:

```powershell
.\.venv-ml\Scripts\python experiments\train_rubert_multitask.py `
  --input-csv data\ml_experiments\rubert_benchmarks\test1_equal_common_axes\new_common_all.csv `
  --output-dir data\ml_experiments\rubert_runs\test1_new_common `
  --target-cols sentiment appeal_type common_addressee `
  --text-mode post_comment `
  --epochs 4 `
  --batch-size 8 `
  --max-length 256 `
  --save-model
```

Тест 1, старая разметка, равный случайный объем:

```powershell
.\.venv-ml\Scripts\python experiments\train_rubert_multitask.py `
  --input-csv data\ml_experiments\rubert_benchmarks\test1_equal_common_axes\old_common_equal_random.csv `
  --output-dir data\ml_experiments\rubert_runs\test1_old_equal_common `
  --target-cols sentiment appeal_type common_addressee `
  --text-mode post_comment `
  --epochs 4 `
  --batch-size 8 `
  --max-length 256 `
  --save-model
```

Тест 2, старые данные целиком, три общие оси:

```powershell
.\.venv-ml\Scripts\python experiments\train_rubert_multitask.py `
  --input-csv data\ml_experiments\rubert_benchmarks\test2_all_available\old_common_all.csv `
  --output-dir data\ml_experiments\rubert_runs\test2_old_all_common `
  --target-cols sentiment appeal_type common_addressee `
  --text-mode post_comment `
  --epochs 4 `
  --batch-size 8 `
  --max-length 256 `
  --save-model
```

Тест 2, новые данные целиком, три общие оси:

```powershell
.\.venv-ml\Scripts\python experiments\train_rubert_multitask.py `
  --input-csv data\ml_experiments\rubert_benchmarks\test2_all_available\new_common_all.csv `
  --output-dir data\ml_experiments\rubert_runs\test2_new_all_common `
  --target-cols sentiment appeal_type common_addressee `
  --text-mode post_comment `
  --epochs 4 `
  --batch-size 8 `
  --max-length 256 `
  --save-model
```

Тест 2, новые данные целиком, полная ЖКХ-таксономия:

```powershell
.\.venv-ml\Scripts\python experiments\train_rubert_multitask.py `
  --input-csv data\ml_experiments\rubert_benchmarks\test2_all_available\new_full_all.csv `
  --output-dir data\ml_experiments\rubert_runs\test2_new_all_full `
  --target-cols jkh_relevance jkh_topic authority_aspect sentiment appeal_type responsible_party sarcasm quality `
  --text-mode post_comment `
  --epochs 4 `
  --batch-size 8 `
  --max-length 256 `
  --save-model
```

## Мое мнение

Предложенная схема сильная: первый тест отвечает на честный вопрос "стало ли лучше при равных условиях", второй — на дипломный вопрос "что дает новая система, когда мы используем все данные и всю новую таксономию".

Я бы не пытался объявлять старую и новую разметку полностью взаимозаменяемыми. Старый корпус полезен как baseline, но он был построен под другую задачу и слабее связан с ЖКХ. Главная ценность новой системы — не просто больше меток, а другой уровень постановки: пост-контекст, проверка админами, отдельная релевантность ЖКХ, темы ЖКХ, связь с ответственными сторонами и признак качества записи.

Ожидание по результатам: старая модель может выглядеть сильнее по weighted F1 из-за более простой и перекошенной таксономии. Это не обязательно значит, что она лучше. Для диплома важнее macro F1, качество редких ЖКХ-классов и объяснимость ошибок.

## Первый запуск на утвержденных данных

Дата запуска: 2026-05-21.

Выгрузка `data/exports/approved_annotations.csv` содержит 1 432 утвержденные новые записи. Подготовка выборок дала:

- `new_common_all`: 1 432;
- `new_full_all`: 1 432;
- `old_common_equal_random`: 1 432;
- `old_common_all`: 138 680.

Быстрые полноценные прогоны на 1 432 строках:

| Прогон | Поле | Accuracy | Macro F1 | Weighted F1 |
| --- | --- | ---: | ---: | ---: |
| test1_new_common | sentiment | 0.526 | 0.355 | 0.487 |
| test1_new_common | appeal_type | 0.405 | 0.108 | 0.321 |
| test1_new_common | common_addressee | 0.916 | 0.239 | 0.876 |
| test1_old_equal_common | sentiment | 0.577 | 0.321 | 0.528 |
| test1_old_equal_common | appeal_type | 0.614 | 0.109 | 0.467 |
| test1_old_equal_common | common_addressee | 0.456 | 0.230 | 0.451 |
| test2_new_all_full | jkh_relevance | 0.888 | 0.588 | 0.857 |
| test2_new_all_full | jkh_topic | 0.926 | 0.137 | 0.890 |
| test2_new_all_full | authority_aspect | 0.930 | 0.138 | 0.897 |
| test2_new_all_full | sentiment | 0.498 | 0.305 | 0.452 |
| test2_new_all_full | appeal_type | 0.335 | 0.116 | 0.307 |
| test2_new_all_full | responsible_party | 0.916 | 0.191 | 0.876 |
| test2_new_all_full | sarcasm | 0.595 | 0.473 | 0.601 |
| test2_new_all_full | quality | 0.823 | 0.387 | 0.797 |

Промежуточная интерпретация: на текущих 1 432 новых записях модель уже ловит доминирующие классы, но редкие классы пока слабые. Это видно по разрыву между accuracy/weighted F1 и macro F1. Для диплома эти результаты полезны как первый baseline, но еще не как финальная модель.

Длинный прогон `test2_old_all_common` на всех 138 680 старых записях завершился:

| Прогон | Поле | Accuracy | Macro F1 | Weighted F1 |
| --- | --- | ---: | ---: | ---: |
| test2_old_all_common | sentiment | 0.838 | 0.790 | 0.843 |
| test2_old_all_common | appeal_type | 0.942 | 0.761 | 0.943 |
| test2_old_all_common | common_addressee | 0.963 | 0.898 | 0.964 |

Динамика обучения на старом полном корпусе:

- эпоха 1: `train_loss=2.8910`, `val_macro_f1=0.7322`;
- эпоха 2: `train_loss=1.2826`, `val_macro_f1=0.8122`;
- эпоха 3: `train_loss=0.9528`, `val_macro_f1=0.8443`;
- эпоха 4: `train_loss=0.8236`, `val_macro_f1=0.8523`.

Итоговая интерпретация: старый полный корпус ожидаемо дает сильный результат по трем общим осям, потому что данных гораздо больше и таксономия проще. Это не отменяет ценность новой разметки: новая система решает более сложную задачу с ЖКХ-релевантностью, темами, ответственными сторонами, качеством записи и сарказмом. На текущих 1 432 новых утвержденных записях уже виден рабочий baseline, но для устойчивой полной модели нужно наращивать объем утвержденной новой разметки и особенно редкие ЖКХ-классы.
