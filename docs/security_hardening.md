# Security Hardening Plan

This document records the security measures for the public annotation server.

## Goals

The annotation server is public-facing and stores user accounts, annotation history, scoring history, and reviewed datasets. The security model should protect credentials, prevent unauthorised access, reduce brute-force and spam risks, and keep the service recoverable after failures.

## Implemented in the project

- Role-based access: student, annotation administrator, and central administrator.
- New accounts have no work access until the central administrator approves them.
- Annotation review, score awards, and penalties are stored with the reviewing/admin user.
- Django CSRF protection is enabled on forms.
- Password validators are enabled.
- Production security settings can be controlled through `.env`:
  - `DEBUG`
  - `ALLOWED_HOSTS`
  - `CSRF_TRUSTED_ORIGINS`
  - `SECURE_SSL_REDIRECT`
  - `SESSION_COOKIE_SECURE`
  - `CSRF_COOKIE_SECURE`
  - `CSRF_COOKIE_HTTPONLY`
  - `SECURE_HSTS_SECONDS`
  - `SECURE_HSTS_INCLUDE_SUBDOMAINS`
  - `SECURE_HSTS_PRELOAD`

## Server hardening checklist

### 1. Run through gunicorn and nginx

Copy the prepared unit and nginx files:

```bash
sudo cp /home/oldskull/apps/Diplomnaya-rabota/deploy/systemd/diplom-gunicorn.service /etc/systemd/system/diplom-gunicorn.service
sudo cp /home/oldskull/apps/Diplomnaya-rabota/deploy/nginx/diplom.conf /etc/nginx/sites-available/diplom
sudo cp /home/oldskull/apps/Diplomnaya-rabota/deploy/nginx/ratelimit.conf /etc/nginx/conf.d/diplom-ratelimit.conf
sudo cp /home/oldskull/apps/Diplomnaya-rabota/deploy/nginx/maintenance-fallback-snippet.conf /etc/nginx/snippets/diplom-maintenance-fallback.conf
```

Enable services:

```bash
sudo ln -sf /etc/nginx/sites-available/diplom /etc/nginx/sites-enabled/diplom
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl daemon-reload
sudo systemctl enable --now diplom-gunicorn
sudo nginx -t
sudo systemctl reload nginx
```

### 2. Firewall

Only SSH, HTTP, and HTTPS should be exposed:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw delete allow 8000/tcp
sudo ufw status verbose
```

Gunicorn must listen on `127.0.0.1:8000`, not on `0.0.0.0:8000`.

### 3. HTTPS

Install certbot and issue a certificate:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d label.zhkh-razmetka.ru
```

After HTTPS is confirmed, set these values in `.env`:

```env
DEBUG=0
ALLOWED_HOSTS=label.zhkh-razmetka.ru
CSRF_TRUSTED_ORIGINS=https://label.zhkh-razmetka.ru
SECURE_SSL_REDIRECT=1
SESSION_COOKIE_SECURE=1
CSRF_COOKIE_SECURE=1
CSRF_COOKIE_HTTPONLY=1
SECURE_HSTS_SECONDS=3600
SECURE_HSTS_INCLUDE_SUBDOMAINS=0
SECURE_HSTS_PRELOAD=0
```

Then restart gunicorn:

```bash
sudo systemctl restart diplom-gunicorn
```

After the HTTPS setup has been stable for several days, `SECURE_HSTS_SECONDS` can be raised, for example to `2592000`. Do not enable preload until the domain setup is final.

### 4. SSH

Recommended after key-based login is verified:

- Disable password login for SSH.
- Keep `OpenSSH` allowed in UFW.
- Do not expose PostgreSQL to the internet.

### 5. Brute-force and log protection

Install fail2ban:

```bash
sudo apt install -y fail2ban
sudo cp /home/oldskull/apps/Diplomnaya-rabota/deploy/fail2ban/nginx-auth.conf /etc/fail2ban/jail.d/nginx-auth.conf
sudo systemctl enable --now fail2ban
sudo systemctl restart fail2ban
```

For stronger application-level protection, add `django-axes` later to limit repeated failed login attempts.

### 6. Backups

Install the backup script and timer:

```bash
chmod +x /home/oldskull/apps/Diplomnaya-rabota/deploy/backup/diplom-db-backup.sh
sudo cp /home/oldskull/apps/Diplomnaya-rabota/deploy/systemd/diplom-db-backup.service /etc/systemd/system/diplom-db-backup.service
sudo cp /home/oldskull/apps/Diplomnaya-rabota/deploy/systemd/diplom-db-backup.timer /etc/systemd/system/diplom-db-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now diplom-db-backup.timer
sudo systemctl start diplom-db-backup.service
systemctl status diplom-db-backup.timer --no-pager
systemctl status diplom-db-backup.service --no-pager
ls -lh /home/oldskull/backups/diplom
```

The script writes compressed PostgreSQL dumps to `/home/oldskull/backups/diplom` and deletes copies older than 14 days. Periodically test restore on a separate database.

### 7. Maintenance and health recovery

The application includes a planned maintenance mode and a health endpoint:

```bash
python manage.py maintenance on --eta "15 минут"
python manage.py maintenance status
python manage.py maintenance off
curl https://label.zhkh-razmetka.ru/healthz/
```

The repository also includes optional systemd assets for periodic health checks and a controlled repair attempt:

```bash
chmod +x deploy/support/diplom-healthcheck.sh deploy/support/diplom-repair.sh
sudo cp deploy/systemd/diplom-healthcheck.service /etc/systemd/system/diplom-healthcheck.service
sudo cp deploy/systemd/diplom-healthcheck.timer /etc/systemd/system/diplom-healthcheck.timer
sudo systemctl daemon-reload
sudo systemctl enable --now diplom-healthcheck.timer
```

For gunicorn/nginx failures, nginx can serve `deploy/nginx/maintenance-fallback.html` using the snippet in `deploy/nginx/maintenance-fallback-snippet.conf`. Detailed operational commands are in `docs/operations_runbook.md`.

### 8. Load testing

The repository includes a conservative ApacheBench wrapper for read-only load checks:

```bash
sudo apt install -y apache2-utils
./deploy/support/diplom-load-test.sh http://127.0.0.1:8000/healthz/
```

For the public domain, use smaller stages because nginx intentionally limits bursts from one IP:

```bash
DIPLOM_LOAD_STAGES="20:1 40:2 80:4" ./deploy/support/diplom-load-test.sh https://label.zhkh-razmetka.ru/healthz/
```

The goal is to measure baseline availability and response behavior, not to attack the public server.

## Diploma text angle

The security section can be described as a layered model:

1. Network layer: public ports limited to 80/443, database kept private.
2. Transport layer: HTTPS and secure cookies.
3. Application layer: CSRF protection, host validation, disabled debug output.
4. Access layer: central approval of accounts and role separation.
5. Audit layer: reviewer, approval, scoring, and penalty history.
6. Availability layer: systemd autostart, backups, maintenance mode, health checks, and recovery checks.
