# Сервер ручной разметки

Цель: дать студентам доступ к разметке обращений по ЖКХ с разных компьютеров, а администраторам - инструменты проверки, начисления баллов и штрафов.

## Роли

- Центральный администратор: Django superuser. Утверждает учетные записи, назначает роли `Студент` или `Администратор разметки`.
- Администратор разметки: проверяет ответы студентов, принимает или отклоняет их, вручную начисляет баллы и штрафы.
- Студент: размечает записи и видит только утвержденную статистику по баллам.

Новые учетные записи не получают доступ автоматически. После регистрации пользователь попадает в состояние ожидания утверждения.

## Поток работы

1. Данные импортируются в очередь командой `import_records`.
2. Студент получает следующую доступную запись.
3. Студент размечает запись по ЖКХ-таксономии.
4. Ответ попадает в очередь проверки.
5. Администратор принимает или отклоняет ответ.
6. Баллы и штрафы создаются только администратором при проверке.
7. Экспорт утвержденных ответов выполняется командой `export_annotations`.

## Команды

```powershell
python manage.py import_records path\to\dataset.csv --source-name Normalizaciya
python manage.py export_annotations exports\approved_annotations.csv
python manage.py export_annotations exports\all_annotations.csv --all
```

## Развертывание

Для локальной проверки используется SQLite. На сервере рекомендуется PostgreSQL через переменную окружения `DATABASE_URL`.

Минимальные шаги на сервере:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
gunicorn labeling_server.wsgi:application --bind 0.0.0.0:8000 --workers 2
```

PostgreSQL 15/16 на Ubuntu может требовать отдельные права на схему `public`.
Если `python manage.py migrate` падает с `permission denied for schema public`, выполнить:

```bash
sudo -u postgres psql <<'SQL'
ALTER DATABASE diplom OWNER TO diplom;
\c diplom
GRANT ALL ON SCHEMA public TO diplom;
ALTER SCHEMA public OWNER TO diplom;
SQL
```

Docker-вариант:

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

На публичном сервере обязательно задать `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` и закрыть прямой доступ к базе данных.

## Временный внешний доступ через Cloudflare Quick Tunnel

Для тестирования со студентами можно открыть локальный сервер наружу без белого IP и без проброса портов:

```bash
curl -L --output /tmp/cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i /tmp/cloudflared.deb
cloudflared tunnel --url http://localhost:8000
```

Cloudflare выдаст временную публичную ссылку вида `https://example.trycloudflare.com`.

Ограничение: Quick Tunnel удобен для тестов, но ссылка временная. Для постоянной ссылки позже лучше создать named tunnel в Cloudflare Zero Trust и привязать домен или поддомен.
