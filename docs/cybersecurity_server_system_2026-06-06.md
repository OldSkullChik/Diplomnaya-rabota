# Кибербезопасность серверной, сайтовой и системной части проекта

Дата фиксации: `2026-06-06`.

Проект: веб-система разметки и аналитики обращений/комментариев в сфере ЖКХ с последующей автоматической оценкой работы ОМСУ.

Этот файл описывает меры кибербезопасности, уже реализованные в проекте, подготовленные эксплуатационные механизмы и ближайшие меры hardening, которые планируется внедрить перед финальной эксплуатацией.

## 1. Назначение раздела

Система является публичным веб-приложением и хранит:

- учетные записи пользователей;
- роли и статусы подтверждения участников;
- историю ручной разметки;
- историю проверки, штрафов и начисления баллов;
- выгрузки approved/gold данных;
- служебные данные для обучения моделей;
- статистику и аналитические отчеты.

Поэтому кибербезопасность проекта рассматривается не как одна настройка, а как несколько уровней защиты:

1. системный уровень: ОС, systemd, PostgreSQL, резервные копии;
2. сетевой уровень: nginx, HTTPS, rate limit, закрытие лишних портов;
3. серверный уровень приложения: Django settings, cookies, CSRF, заголовки;
4. сайтовый уровень: роли, подтверждение аккаунтов, защита форм;
5. уровень данных: разграничение gold/silver, аудит действий, исключение секретов из git;
6. уровень отказоустойчивости: maintenance mode, healthcheck, backup, fallback page.

## 2. Краткий итог

| Направление | Статус | Что есть сейчас |
| --- | --- | --- |
| Аутентификация | Реализовано | Django auth, login/logout, регистрация |
| Роли пользователей | Реализовано | Студент, администратор разметки, центральный администратор |
| Подтверждение аккаунтов | Реализовано | Новые аккаунты не получают рабочий доступ до approval |
| CSRF-защита | Реализовано | `CsrfViewMiddleware`, `{% csrf_token %}` в формах |
| Password validators | Реализовано | Стандартные валидаторы Django |
| HTTPS-настройки | Реализовано/настраивается через `.env` | `SECURE_SSL_REDIRECT`, secure cookies, HSTS |
| Security headers | Реализовано | `X-Frame-Options`, `nosniff`, `Referrer-Policy`, `Permissions-Policy` |
| Reverse proxy | Реализовано | nginx -> gunicorn на `127.0.0.1:8000` |
| Rate limit | Реализовано в nginx-конфиге | `5r/s` на IP, burst `40` |
| Health endpoint | Реализовано | `/healthz/` проверяет доступность приложения и БД |
| Maintenance mode | Реализовано | Плановый режим обслуживания через management command |
| Nginx fallback | Реализовано | Статическая страница при `502/503/504` |
| PostgreSQL backups | Реализовано | `pg_dump`, gzip, `umask 077`, retention `14` дней |
| systemd service | Реализовано | gunicorn service с автоперезапуском |
| Healthcheck/repair timer | Подготовлено | systemd timer + controlled repair script |
| fail2ban | Подготовлено | Конфиг для nginx auth/log protection |
| SSH key-only | Планируется | После проверки ключевого доступа |
| django-axes / login throttling | Планируется | Для ограничения перебора паролей на уровне приложения |

## 3. Архитектура развертывания

Фактическая схема production-развертывания:

```text
Пользователь
    |
    v
HTTPS / nginx
    |
    v
gunicorn на 127.0.0.1:8000
    |
    v
Django application
    |
    v
PostgreSQL
```

Ключевой принцип: gunicorn не должен быть открыт наружу. Внешний трафик принимает nginx, а приложение доступно локально через `127.0.0.1:8000`.

Файлы, связанные с развертыванием:

| Файл | Назначение |
| --- | --- |
| `deploy/nginx/diplom.conf` | nginx reverse proxy, headers, static, rate limit |
| `deploy/nginx/ratelimit.conf` | зона rate limiting |
| `deploy/nginx/maintenance-fallback-snippet.conf` | fallback для ошибок `502/503/504` |
| `deploy/nginx/maintenance-fallback.html` | статическая аварийная страница |
| `deploy/systemd/diplom-gunicorn.service` | systemd unit для gunicorn |
| `deploy/systemd/diplom-db-backup.service` | oneshot backup service |
| `deploy/systemd/diplom-db-backup.timer` | ежедневный backup timer |
| `deploy/systemd/diplom-healthcheck.service` | controlled healthcheck/repair |
| `deploy/systemd/diplom-healthcheck.timer` | периодический healthcheck |
| `deploy/support/diplom-healthcheck.sh` | проверка `/healthz/` |
| `deploy/support/diplom-repair.sh` | контролируемый restart/repair |
| `deploy/backup/diplom-db-backup.sh` | PostgreSQL backup |
| `deploy/fail2ban/nginx-auth.conf` | fail2ban jail для nginx auth |

## 4. Сайтовая безопасность

### 4.1. Аутентификация и роли

Используется стандартная аутентификация Django. Поверх стандартной модели пользователя реализован профиль `UserProfile`.

Роли:

| Роль | Назначение |
| --- | --- |
| Студент | Размечает записи |
| Администратор разметки | Проверяет разметку, утверждает/отклоняет ответы, подтверждает студентов |
| Центральный администратор | Полный контроль проекта, ручные корректировки, доступ к полной статистике |

Важная деталь: проектный "суперадмин" намеренно привязан к superuser с username `oldskull`, а не ко всем пользователям с `is_superuser=True`. Это снижает риск случайной выдачи проектных полномочий техническому superuser-аккаунту.

### 4.2. Подтверждение пользователей

Новые аккаунты не получают рабочий доступ автоматически. Для начала работы участник должен быть подтвержден администратором.

Это защищает систему от:

- случайных внешних регистраций;
- спама в очереди разметки;
- доступа посторонних к данным и интерфейсу разметки;
- неконтролируемого влияния на обучающий датасет.

### 4.3. Разделение действий

Пользователь, который размечает данные, не является автоматически тем, кто их принимает в датасет. Проверка выполняется отдельным административным действием.

Для проверки и аудита сохраняются:

- кто отправил разметку;
- кто проверил разметку;
- какое решение принято;
- какие баллы начислены или списаны;
- причина ручной корректировки, если она была.

Модель `ScoreEvent` хранит историю начислений и штрафов, поэтому итоговые баллы не являются просто перезаписываемым числом.

### 4.4. Защита форм

В Django включен middleware:

```text
django.middleware.csrf.CsrfViewMiddleware
```

Формы в шаблонах используют:

```django
{% csrf_token %}
```

Это защищает критические POST-действия от CSRF-атак: отправка разметки, проверка ответа, выход из аккаунта, подтверждение пользователей и административные действия.

## 5. Серверная безопасность Django

### 5.1. Настройки через `.env`

Производственные настройки вынесены в переменные окружения и `.env`, а не захардкожены в коде.

Ключевые параметры:

| Параметр | Назначение |
| --- | --- |
| `SECRET_KEY` | криптографический ключ Django |
| `DEBUG` | отключение debug-режима в production |
| `ALLOWED_HOSTS` | список разрешенных host-заголовков |
| `CSRF_TRUSTED_ORIGINS` | доверенные origins для CSRF |
| `DATABASE_URL` | строка подключения к PostgreSQL |
| `SECURE_SSL_REDIRECT` | принудительный HTTPS |
| `SESSION_COOKIE_SECURE` | отправка session cookie только по HTTPS |
| `CSRF_COOKIE_SECURE` | отправка CSRF cookie только по HTTPS |
| `CSRF_COOKIE_HTTPONLY` | запрет чтения CSRF cookie из JS, если включено |
| `SECURE_HSTS_SECONDS` | HSTS |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | HSTS для поддоменов |
| `SECURE_HSTS_PRELOAD` | HSTS preload |

Секреты не должны попадать в git. `.env`, ключи, сертификаты и приватные файлы исключаются из коммитов и из полного локального архива проекта.

### 5.2. Защитные HTTP-настройки

В `settings.py` включены:

| Настройка | Значение / смысл |
| --- | --- |
| `SECURE_PROXY_SSL_HEADER` | корректная работа за nginx/proxy |
| `SESSION_COOKIE_HTTPONLY` | session cookie недоступна JS |
| `SESSION_COOKIE_SAMESITE` | `Lax` |
| `CSRF_COOKIE_SAMESITE` | `Lax` |
| `SECURE_CONTENT_TYPE_NOSNIFF` | запрет MIME sniffing |
| `SECURE_REFERRER_POLICY` | `same-origin` |
| `X_FRAME_OPTIONS` | `DENY`, защита от clickjacking |
| `DATA_UPLOAD_MAX_MEMORY_SIZE` | ограничение размера upload |

### 5.3. Password validators

Включены стандартные валидаторы паролей Django:

- `UserAttributeSimilarityValidator`;
- `MinimumLengthValidator`;
- `CommonPasswordValidator`;
- `NumericPasswordValidator`.

Это снижает риск использования слишком простых паролей.

## 6. Nginx и сетевой уровень

### 6.1. Reverse proxy

Nginx принимает внешний HTTP/HTTPS-трафик и проксирует его в gunicorn:

```text
proxy_pass http://127.0.0.1:8000;
```

Это важно, потому что приложение не должно напрямую слушать внешний интерфейс.

### 6.2. Rate limiting

В nginx подготовлено ограничение:

```nginx
limit_req_zone $binary_remote_addr zone=diplom_app:10m rate=5r/s;
```

В основном location:

```nginx
limit_req zone=diplom_app burst=40 nodelay;
```

Это снижает риск простых burst-атак, случайного перегруза и агрессивного перебора страниц с одного IP.

### 6.3. Security headers

В nginx добавлены заголовки:

| Header | Назначение |
| --- | --- |
| `X-Content-Type-Options: nosniff` | защита от MIME sniffing |
| `X-Frame-Options: DENY` | защита от clickjacking |
| `Referrer-Policy: same-origin` | ограничение утечки referrer |
| `Permissions-Policy` | запрет геолокации, микрофона и камеры |

Публичная проверка `/healthz/` ранее подтверждала ответ по HTTPS и наличие security headers, включая `Strict-Transport-Security`.

### 6.4. HTTPS

Для production-домена используется:

```text
https://label.zhkh-razmetka.ru/
```

В проекте подготовлена инструкция установки certbot:

```bash
sudo certbot --nginx -d label.zhkh-razmetka.ru
```

После подтверждения HTTPS в `.env` используются production-настройки:

```env
DEBUG=0
ALLOWED_HOSTS=label.zhkh-razmetka.ru
CSRF_TRUSTED_ORIGINS=https://label.zhkh-razmetka.ru
SECURE_SSL_REDIRECT=1
SESSION_COOKIE_SECURE=1
CSRF_COOKIE_SECURE=1
CSRF_COOKIE_HTTPONLY=1
SECURE_HSTS_SECONDS=3600
```

HSTS preload и длительный HSTS intentionally не включаются сразу: сначала нужно убедиться, что домен и HTTPS-конфигурация окончательные.

## 7. Системная безопасность

### 7.1. systemd service

Приложение запускается через systemd unit:

```text
deploy/systemd/diplom-gunicorn.service
```

Ключевые свойства:

- запуск от пользователя `oldskull`;
- рабочая директория `/home/oldskull/apps/Diplomnaya-rabota`;
- переменные окружения из `.env`;
- gunicorn слушает `127.0.0.1:8000`;
- `Restart=always`;
- `RestartSec=5`.

Это повышает доступность сервиса и позволяет автоматически поднимать приложение после сбоя процесса.

### 7.2. PostgreSQL

Для production используется PostgreSQL через `DATABASE_URL`. База не должна быть доступна из интернета. Доступ к ней должен идти только локально с сервера приложения.

В проекте уже используются миграции Django, а производственные операции выполняются через management commands.

### 7.3. Резервные копии

Backup-скрипт:

```text
deploy/backup/diplom-db-backup.sh
```

Механизм:

- читает `DATABASE_URL` из `.env`;
- создает PostgreSQL dump через `pg_dump`;
- сжимает через `gzip -9`;
- пишет во временный файл и затем атомарно переименовывает;
- использует `umask 077`, то есть backup-файлы доступны только владельцу;
- удаляет копии старше `14` дней.

Systemd timer:

```text
deploy/systemd/diplom-db-backup.timer
```

Расписание:

```text
ежедневно в 03:30 + RandomizedDelaySec=10m
```

По истории проекта backup automation уже устанавливалась на сервере, а первый backup создавался в:

```text
/home/oldskull/backups/diplom/
```

### 7.4. Healthcheck и controlled repair

Health endpoint:

```text
/healthz/
```

Ожидаемый ответ:

```json
{"status": "ok", "database": "ok", "maintenance": false}
```

Скрипты:

| Скрипт | Назначение |
| --- | --- |
| `deploy/support/diplom-healthcheck.sh` | Быстрая проверка health URL |
| `deploy/support/diplom-repair.sh` | Контролируемая попытка восстановления |

`diplom-repair.sh`:

1. проверяет health URL;
2. если PostgreSQL неактивен, перезапускает PostgreSQL;
3. перезапускает `diplom-gunicorn`;
4. проверяет `nginx -t`;
5. reload nginx;
6. повторно проверяет health endpoint.

Это не заменяет мониторинг, но дает базовый механизм самовосстановления.

## 8. Отказоустойчивость и maintenance mode

### 8.1. Плановое обслуживание

В проекте реализован режим обслуживания:

```bash
python manage.py maintenance on --duration "20m"
python manage.py maintenance status
python manage.py maintenance off
```

Особенности:

- состояние хранится в локальном JSON-файле;
- обычные страницы возвращают `503 Service Unavailable`;
- `/healthz/` остается доступным;
- `/static/` остается доступным;
- можно указать duration и автоматическое выключение через systemd-run.

### 8.2. Nginx fallback

Если Django/gunicorn недоступен, nginx может отдать статическую fallback-страницу:

```text
deploy/nginx/maintenance-fallback.html
```

Подключение:

```nginx
error_page 502 503 504 /maintenance-fallback.html;
```

Это защищает пользовательский опыт и не показывает техническую ошибку backend-а.

## 9. Безопасность данных и ML-артефактов

В проекте есть несколько типов данных:

- raw corpus;
- production annotations;
- human-gold labels;
- silver labels;
- pseudo-gold labels;
- обученные checkpoint-и;
- матрицы ошибок и статистика;
- архивы для диплома.

Принцип безопасности данных:

1. секреты не коммитятся;
2. `.env`, ключи, сертификаты и приватные файлы не включаются в git;
3. runtime exports и тяжелые ML-артефакты хранятся локально, а не в репозитории;
4. human-gold, silver и pseudo-gold разделяются в отчетах;
5. validation/test считаются только на human-gold;
6. generated participant CSV и рейтинги не публикуются без необходимости, потому что содержат идентификаторы участников.

Полный локальный дипломный архив создан отдельно:

```text
D:\Diplom\exports\diploma_full_project_archive_2026-06-06_06-52.tar.zst
```

Он исключает `.git`, `.venv`, `.venv-ml`, `.env`, key/certificate-like files и кэши.

## 10. Что уже реализовано

### 10.1. На уровне сайта

- регистрация и вход пользователей;
- роли пользователей;
- подтверждение аккаунтов перед доступом к работе;
- разделение студента, администратора разметки и центрального администратора;
- CSRF protection на формах;
- история проверки аннотаций;
- история баллов через `ScoreEvent`;
- ручные score corrections только для project superadmin;
- защита от повторной выдачи записи нескольким студентам через reservation mechanism;
- bulk/offline review с dry-run перед применением.

### 10.2. На уровне Django

- password validators;
- `ALLOWED_HOSTS`;
- `CSRF_TRUSTED_ORIGINS`;
- secure cookie settings через `.env`;
- HSTS через `.env`;
- `X_FRAME_OPTIONS = DENY`;
- `SECURE_CONTENT_TYPE_NOSNIFF = True`;
- `SECURE_REFERRER_POLICY = same-origin`;
- upload memory limit;
- health endpoint;
- maintenance middleware.

### 10.3. На уровне nginx

- reverse proxy;
- static files через nginx;
- rate limit по IP;
- security headers;
- fallback page для `502/503/504`;
- HTTPS-домен в production;
- прокидывание `X-Forwarded-Proto` для корректной HTTPS-логики Django.

### 10.4. На уровне системы

- gunicorn systemd service;
- autostart/autorestart приложения;
- PostgreSQL backup script;
- daily backup timer;
- healthcheck script;
- controlled repair script;
- optional healthcheck timer;
- operational runbook.

## 11. Что будет реализовано вскоре

### Приоритет 1. Закрепить production hardening

| Мера | Зачем |
| --- | --- |
| Проверить и зафиксировать `DEBUG=0` на production | Исключить debug tracebacks наружу |
| Проверить `ALLOWED_HOSTS` только для production-домена | Защита от host header abuse |
| Проверить `CSRF_TRUSTED_ORIGINS` только для HTTPS-домена | Корректная CSRF-защита |
| Проверить `SESSION_COOKIE_SECURE=1` и `CSRF_COOKIE_SECURE=1` | Cookies только по HTTPS |
| Увеличить `SECURE_HSTS_SECONDS` после стабильной работы HTTPS | Усилить транспортную безопасность |
| Не включать HSTS preload до финальной доменной схемы | Не заблокировать будущую смену домена |

### Приоритет 2. Сетевой контур

| Мера | Зачем |
| --- | --- |
| Включить/проверить UFW | Оставить наружу только SSH, 80, 443 |
| Убедиться, что порт `8000` не открыт наружу | Gunicorn должен быть доступен только локально |
| Не открывать PostgreSQL в интернет | Снижение риска компрометации БД |
| Проверить DNS/HTTPS renewal certbot | Предотвратить истечение сертификата |

### Приоритет 3. Защита входа

| Мера | Зачем |
| --- | --- |
| Включить fail2ban для nginx auth/error logs | Снизить риск bruteforce |
| Добавить `django-axes` или аналог | Ограничить перебор паролей на уровне приложения |
| Ограничить частоту регистрации | Защита от спам-регистраций |
| Проверить политику сложности паролей | Снижение риска слабых паролей |
| Перейти на SSH key-only login | Убрать риск перебора SSH-пароля |

### Приоритет 4. Backup и восстановление

| Мера | Зачем |
| --- | --- |
| Провести test restore на отдельной БД | Backup считается рабочим только после проверки восстановления |
| Добавить offsite-копию backup | Защита от потери локального диска |
| Рассмотреть шифрование backup-архивов | Защита данных при утечке файлов |
| Документировать RPO/RTO | Понятно, сколько данных можно потерять и за сколько восстановиться |

### Приоритет 5. Аудит и мониторинг

| Мера | Зачем |
| --- | --- |
| Включить systemd healthcheck timer, если он еще не включен | Регулярная проверка доступности |
| Собирать журнал failed login attempts | Анализ подозрительной активности |
| Добавить алерты на падение `/healthz/` | Быстрая реакция на отказ |
| Добавить security checklist перед релизом | Повторяемая процедура перед защитой/демо |
| Периодически обновлять зависимости | Снижение риска известных CVE |

## 12. Оценка остаточных рисков

| Риск | Текущий статус | Снижение риска |
| --- | --- | --- |
| Перебор паролей веб-аккаунтов | Частично закрыт ролями и approval | Добавить `django-axes`, fail2ban, rate limits на login |
| Компрометация SSH | Зависит от серверной настройки | Перейти на key-only, отключить password auth |
| Утечка `.env` | Не коммитится, исключается из архива | Проверять права файла и доступ к серверу |
| Потеря PostgreSQL | Есть backup timer | Проверить restore, добавить offsite backup |
| Перегрузка сайта | Есть nginx rate limit | Добавить мониторинг и отдельные лимиты на login/API |
| Ошибка администратора при массовых операциях | Есть dry-run commands | Сохранять CSV audit и делать backup перед крупными import/apply |
| Публикация персональных CSV | Runtime exports вне git | Санитизировать перед вставкой в диплом/презентацию |

## 13. Формулировка для диплома

В проекте реализована многоуровневая модель защиты веб-системы разметки. На уровне приложения используется стандартная аутентификация Django, ролевая модель доступа, обязательное подтверждение новых участников и CSRF-защита всех критических форм. Административные действия, проверка разметки и изменение баллов сохраняются в истории, что обеспечивает аудит действий пользователей.

На серверном уровне приложение разворачивается за nginx reverse proxy, а gunicorn слушает только локальный интерфейс `127.0.0.1:8000`. Для production-настроек используются переменные окружения: `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, secure cookies, HTTPS redirect и HSTS. Nginx добавляет защитные HTTP-заголовки, ограничивает частоту запросов и отдает статическую страницу при временной недоступности backend-а.

На системном уровне применяются systemd-сервисы для запуска приложения, резервного копирования PostgreSQL и healthcheck/repair-механизмов. Резервные копии создаются через `pg_dump`, сжимаются и сохраняются с owner-only правами доступа. Для планового обслуживания реализован maintenance mode, позволяющий временно закрыть пользовательские страницы, сохранив доступность health endpoint.

Ближайшее развитие защитного контура включает ужесточение SSH-доступа, проверку firewall-правил, включение fail2ban и/или application-level login throttling, тестовое восстановление backup-а и добавление внешнего мониторинга доступности.

## 14. Формулировка для защиты

Коротко для выступления:

> Безопасность проекта построена слоями. Снаружи стоит nginx с HTTPS, rate limit и security headers. Само Django-приложение работает за reverse proxy, а gunicorn слушает только localhost. Внутри приложения есть роли, подтверждение пользователей, CSRF-защита и аудит действий проверяющих. На системном уровне есть systemd-сервисы, резервное копирование PostgreSQL, health endpoint, maintenance mode и fallback-страница на случай сбоя backend-а. В ближайшем hardening-плане - key-only SSH, fail2ban/django-axes, проверка восстановления backup-а и внешний мониторинг.

## 15. Индекс источников

| Источник | Что подтверждает |
| --- | --- |
| `labeling_server/settings.py` | Django security settings, cookies, HSTS, CSRF, DB env |
| `annotation/permissions.py` | Проектные роли и project superadmin |
| `annotation/models.py` | `UserProfile`, approval, reservations, `ScoreEvent` |
| `annotation/views.py` | Login-required workflows, review/admin flows |
| `templates/` | CSRF tokens in forms |
| `deploy/nginx/diplom.conf` | nginx reverse proxy, headers, static, rate limit usage |
| `deploy/nginx/ratelimit.conf` | rate limit zone `5r/s` |
| `deploy/nginx/maintenance-fallback-snippet.conf` | fallback for `502/503/504` |
| `deploy/systemd/diplom-gunicorn.service` | gunicorn service, localhost bind, restart |
| `deploy/backup/diplom-db-backup.sh` | PostgreSQL backups, `umask 077`, retention |
| `deploy/systemd/diplom-db-backup.timer` | daily backup schedule |
| `deploy/support/diplom-healthcheck.sh` | healthcheck |
| `deploy/support/diplom-repair.sh` | controlled repair |
| `deploy/fail2ban/nginx-auth.conf` | prepared fail2ban jail |
| `docs/security_hardening.md` | hardening plan |
| `docs/operations_runbook.md` | эксплуатационные команды |
| `docs/deployment_evidence.md` | подтвержденные production-события |
| `docs/chat_context.md` | хронология решений проекта |

## Короткий вывод

Кибербезопасность проекта уже закрывает базовые уровни: доступ по ролям, подтверждение пользователей, CSRF, secure production settings, nginx reverse proxy, rate limiting, HTTPS, backup, healthcheck, maintenance mode и fallback при авариях. Ближайший этап hardening должен усилить защиту входа и инфраструктуры: key-only SSH, firewall audit, fail2ban/django-axes, тест восстановления backup-а, offsite backup и внешний мониторинг.
