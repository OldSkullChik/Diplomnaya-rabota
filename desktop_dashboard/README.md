# Desktop dashboard

Настольное PyQt6-приложение для демонстрации результатов мониторинга ЖКХ и оценки деятельности ОМСУ по округам Нижегородской области.

Приложение является клиентским слоем: оно не выполняет ML-классификацию самостоятельно, а получает готовый серверный срез через OMSU API или читает локальный статический JSON для демонстрации без сети.

## Возможности

- стартовый экран с картой России и выбором субъекта;
- карта Нижегородской области с кликабельными округами и центрами мониторинга;
- плавное приближение к выбранному округу;
- карточка территории с оценкой, числом сообщений и служебной информацией;
- набор основных и дополнительных графиков;
- нижняя лента последнего сообщения с плавной прокруткой длинного текста;
- работа от серверного API или от локального статического среза.

## Запуск

Из корня репозитория:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r desktop_requirements.txt
.\.venv\Scripts\python desktop_dashboard\main.py
```

Если API не включен, приложение пытается прочитать:

```text
desktop_dashboard/assets/static_dashboard_snapshot.json
```

Если файл отсутствует, используются встроенные демонстрационные данные и локальные GeoJSON-слои.

## Подключение к OMSU API

```powershell
$env:OMSU_API_BASE = "https://example.org/api/v1/omsu"
$env:OMSU_API_KEY = "your-secret-key"
$env:OMSU_DASHBOARD_USE_API = "1"
.\.venv\Scripts\python desktop_dashboard\main.py
```

Ключ также можно передать вторым аргументом командной строки:

```powershell
.\.venv\Scripts\python desktop_dashboard\main.py https://example.org/api/v1/omsu your-secret-key
```

## Статический срез для показа

Для демонстрации без постоянного доступа к серверу можно один раз сохранить текущий API-срез:

```powershell
$env:OMSU_API_BASE = "https://example.org/api/v1/omsu"
$env:OMSU_API_KEY = "your-secret-key"
.\.venv\Scripts\python desktop_dashboard\export_static_snapshot.py
```

Скрипт записывает `desktop_dashboard/assets/static_dashboard_snapshot.json`. API-ключ в этот файл не сохраняется.

## Основные файлы

- `main.py` - главное окно, карта, панели, графики и обработка кликов.
- `api_client.py` - клиент OMSU API, загрузка статического среза и резервные демонстрационные данные.
- `export_static_snapshot.py` - сохранение серверного среза в локальный JSON.
- `assets/geodata/` - GeoJSON-слои для карты России и Нижегородской области.
- `assets/monitoring_groups.json` - список объектов мониторинга и их привязка к округам.
