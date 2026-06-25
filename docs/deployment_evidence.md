# Deployment Evidence

This file stores reusable command outputs and server/application evidence for the diploma text, presentation, and defense notes.

Do not store secrets here: no `.env`, no private keys, no database passwords, no API tokens.

## 2026-05-18 - HTTPS Certificate

Command:

```bash
sudo env LANG=C.UTF-8 LC_ALL=C.UTF-8 certbot --nginx -d label.zhkh-razmetka.ru --email <notification-email> --agree-tos --no-eff-email --redirect -n
```

Output excerpt:

```text
Saving debug log to /var/log/letsencrypt/letsencrypt.log
Account registered.
Requesting a certificate for label.zhkh-razmetka.ru

Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/label.zhkh-razmetka.ru/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/label.zhkh-razmetka.ru/privkey.pem
This certificate expires on 2026-08-16.
These files will be updated when the certificate renews.
Certbot has set up a scheduled task to automatically renew this certificate in the background.

Deploying certificate
Successfully deployed certificate for label.zhkh-razmetka.ru to /etc/nginx/sites-enabled/diplom
Congratulations! You have successfully enabled HTTPS on https://label.zhkh-razmetka.ru
```

## 2026-05-18 - HTTPS and HTTP Redirect Check

Commands:

```bash
curl -I https://label.zhkh-razmetka.ru
curl -I http://label.zhkh-razmetka.ru
```

Output excerpt:

```text
HTTP/1.1 302 Found
Server: nginx/1.24.0 (Ubuntu)
Date: Mon, 18 May 2026 17:16:15 GMT
Content-Type: text/html; charset=utf-8
Location: /login/?next=/
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: same-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()

HTTP/1.1 301 Moved Permanently
Server: nginx/1.24.0 (Ubuntu)
Date: Mon, 18 May 2026 17:16:15 GMT
Location: https://label.zhkh-razmetka.ru/
```

## 2026-05-18 - Django Production Security Check

Command:

```bash
python manage.py check --deploy
```

Output:

```text
System check identified some issues:

WARNINGS:
?: (security.W005) You have not set the SECURE_HSTS_INCLUDE_SUBDOMAINS setting to True. Without this, your site is potentially vulnerable to attack via an insecure connection to a subdomain. Only set this to True if you are certain that all subdomains of your domain should be served exclusively via SSL.
?: (security.W021) You have not set the SECURE_HSTS_PRELOAD setting to True. Without this, your site cannot be submitted to the browser preload list.

System check identified 2 issues (0 silenced).
```

Interpretation for the diploma:

```text
The Django deployment check reports only optional HSTS subdomain/preload warnings. The project keeps these settings disabled until all domain/subdomain behavior is finalized, while HTTPS redirect, secure cookies, host validation, CSRF origin validation, and basic security headers are enabled.
```

## 2026-05-18 - Fail2ban Jail Check

Commands:

```bash
sudo fail2ban-client status
sudo fail2ban-client status nginx-http-auth
```

Output excerpt:

```text
Status for the jail: nginx-http-auth
|- Filter
|  |- Currently failed: 0
|  |- Total failed:     0
|  `- Journal matches:  _SYSTEMD_UNIT=nginx.service + _COMM=nginx
`- Actions
   |- Currently banned: 0
   |- Total banned:     0
   `- Banned IP list:
```

## 2026-05-18 - PostgreSQL Backup Timer

Commands:

```bash
systemctl status diplom-db-backup.timer --no-pager
systemctl status diplom-db-backup.service --no-pager
ls -lh /home/oldskull/backups/diplom
```

Output excerpt:

```text
● diplom-db-backup.timer - Run Diplom annotation server PostgreSQL backup daily
     Loaded: loaded (/etc/systemd/system/diplom-db-backup.timer; enabled; preset: enabled)
     Active: active (waiting) since Mon 2026-05-18 17:31:39 UTC; 293ms ago
    Trigger: Tue 2026-05-19 03:38:09 UTC; 10h left
   Triggers: ● diplom-db-backup.service

○ diplom-db-backup.service - Diplom annotation server PostgreSQL backup
     Loaded: loaded (/etc/systemd/system/diplom-db-backup.service; static)
     Active: inactive (dead) since Mon 2026-05-18 17:31:40 UTC; 29ms ago
TriggeredBy: ● diplom-db-backup.timer
    Process: 82349 ExecStart=/home/oldskull/apps/Diplomnaya-rabota/deploy/backup/diplom-db-backup.sh (code=exited, status=0/SUCCESS)
   Main PID: 82349 (code=exited, status=0/SUCCESS)

May 18 17:31:40 home diplom-db-backup.sh[82349]: Backup written: /home/oldskull/backups/diplom/diplom_2026-05-18_17-31-39.sql.gz
May 18 17:31:40 home systemd[1]: Finished diplom-db-backup.service - Diplom annotation server PostgreSQL backup.

total 8.0K
-rw------- 1 oldskull oldskull 6.0K May 18 17:31 diplom_2026-05-18_17-31-39.sql.gz
```

## 2026-05-18 - Public Availability Check

Command:

```bash
for i in {1..30}; do
  date
  curl -s -o /dev/null -w "%{http_code} %{time_total}\n" https://label.zhkh-razmetka.ru/
  sleep 10
done
```

Output excerpt:

```text
Mon May 18 05:33:00 PM UTC 2026
302 0.120370
Mon May 18 05:33:10 PM UTC 2026
302 0.088758
Mon May 18 05:33:20 PM UTC 2026
302 0.080275
Mon May 18 05:33:30 PM UTC 2026
302 0.091324
Mon May 18 05:33:40 PM UTC 2026
302 0.125060
Mon May 18 05:33:50 PM UTC 2026
302 0.081036
Mon May 18 05:34:01 PM UTC 2026
302 0.081487
Mon May 18 05:34:11 PM UTC 2026
302 0.081147
Mon May 18 05:34:21 PM UTC 2026
302 0.092562
Mon May 18 05:34:31 PM UTC 2026
302 0.083964
Mon May 18 05:34:41 PM UTC 2026
302 0.095135
Mon May 18 05:34:51 PM UTC 2026
302 0.259386
Mon May 18 05:35:01 PM UTC 2026
302 0.265608
Mon May 18 05:35:12 PM UTC 2026
302 0.091172
Mon May 18 05:35:22 PM UTC 2026
302 0.085311
Mon May 18 05:35:32 PM UTC 2026
302 0.084713
Mon May 18 05:35:42 PM UTC 2026
302 0.091737
Mon May 18 05:35:52 PM UTC 2026
302 0.093601
Mon May 18 05:36:02 PM UTC 2026
302 0.086402
Mon May 18 05:36:12 PM UTC 2026
302 0.566925
Mon May 18 05:36:23 PM UTC 2026
302 0.090537
Mon May 18 05:36:33 PM UTC 2026
302 0.091445
```

Interpretation for the diploma:

```text
During the initial public availability check, all requests returned HTTP 302, which is expected for an unauthenticated user because the application redirects to the login page. No 500/502/530/000 responses were observed. Typical response time was around 0.08-0.13 seconds, with one short spike to about 0.57 seconds.
```

## 2026-05-18 - Raw Data Import Dry Run

Commands:

```powershell
.\.venv\Scripts\python manage.py import_records raw\dataset.csv --source-name normalizaciya-main --dry-run --limit 20
.\.venv\Scripts\python manage.py import_records raw\vk.barkov.net-wallposts-2026-05-18_06-26-34.csv --source-name barkov-wallposts-2026 --dry-run --limit 20
.\.venv\Scripts\python manage.py import_records raw\vk.barkov.net-comments-2026-05-18_07-31-45.csv --source-name barkov-comments-2026 --dry-run --limit 20
```

Output:

```text
Would import: 15; skipped: 5
Would import: 20; skipped: 0
Would import: 18; skipped: 2
```

Interpretation for the diploma:

```text
The annotation server import command successfully recognizes the main Normalizaciya dataset schema and recent Barkov wall post/comment exports. The dry-run mode allows checking how many rows would be accepted or skipped before writing records into the annotation queue.
```

## 2026-05-18 - Combined Raw Dataset Smoke Test

Command:

```powershell
.\.venv\Scripts\python manage.py build_dataset raw --output data\processed\dataset_combined_sample.csv --missing-output data\processed\missing_post_context_sample.csv --limit 1000
```

Output:

```text
Built dataset: data\processed\dataset_combined_sample.csv; written=1000; duplicates=0; skipped_empty=0; missing_context=0; post_contexts=306948
Would import: 995; skipped: 5
```

Interpretation for the diploma:

```text
The raw data assembly command successfully built a canonical sample dataset from the local raw folder. The command used the existing structured dataset, recovered post context, and recent wall post/comment exports. In the 1000-row smoke test, no missing comment context was detected. The following import dry run accepted 995 records and skipped 5 that were already present in the local development database.
```

## 2026-05-18 - Full Combined Raw Dataset Build

Command:

```powershell
.\.venv\Scripts\python manage.py build_dataset raw --output data\processed\dataset_combined.csv --missing-output data\processed\missing_post_context.csv
```

Output after fixing old comment URL handling:

```text
Built dataset: data\processed\dataset_combined.csv; written=413670; duplicates=62193; skipped_empty=22363; missing_context=3322; post_contexts=306948
```

Interpretation for the diploma:

```text
The full local raw-data assembly produced 413,670 canonical records for the annotation pipeline. 62,193 rows were identified as duplicates inside the assembled sources, and 22,363 empty or unusable text rows were skipped. 3,322 non-empty comment records still have no matched source post context; these rows are saved separately in missing_post_context.csv and can be used as a targeted list for additional parsing if needed.
```

## 2026-05-18 - 2026 Data Counts

Command:

```powershell
@'
import csv
import re
from collections import Counter
from pathlib import Path

combined = Path('data/processed/dataset_combined.csv')
stats = Counter()
by_type_date_2026 = Counter()
by_type_origin_2026 = Counter()
by_origin_year = Counter()
by_date_year = Counter()

origin_year_re = re.compile(r'(20\d{2})')

def year_from_date(value):
    value = (value or '').strip()
    if not value:
        return ''
    m = re.search(r'\b(20\d{2})\b', value)
    return m.group(1) if m else ''

with combined.open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        stats['total'] += 1
        dtype = row.get('data_type') or 'unknown'
        date_year = year_from_date(row.get('date'))
        origin_match = origin_year_re.search(row.get('file_origin') or '')
        origin_year = origin_match.group(1) if origin_match else ''
        by_date_year[date_year or 'no_date'] += 1
        by_origin_year[origin_year or 'no_origin_year'] += 1
        if date_year == '2026':
            stats['date_2026'] += 1
            by_type_date_2026[dtype] += 1
        if origin_year == '2026':
            stats['origin_2026'] += 1
            by_type_origin_2026[dtype] += 1

print('combined_total', stats['total'])
print('date_2026_total', stats['date_2026'])
print('date_2026_by_type', dict(by_type_date_2026))
print('origin_2026_total', stats['origin_2026'])
print('origin_2026_by_type', dict(by_type_origin_2026))
print('by_date_year', dict(sorted(by_date_year.items())))
print('by_origin_year', dict(sorted(by_origin_year.items())))
'@ | .\.venv\Scripts\python -
```

Output:

```text
combined_total 413670
date_2026_total 45925
date_2026_by_type {'post': 33418, 'comment': 12507}
origin_2026_total 174568
origin_2026_by_type {'post': 140753, 'comment': 33815}
by_date_year {'2013': 5, '2014': 12, '2015': 47, '2016': 1450, '2017': 364, '2018': 1498, '2019': 2451, '2020': 1929, '2021': 3665, '2022': 4841, '2023': 13739, '2024': 38234, '2025': 299455, '2026': 45925, 'no_date': 55}
by_origin_year {'2025': 239102, '2026': 174568}
```

Interpretation for the diploma:

```text
The combined dataset contains 413,670 canonical records. If "2026 data" is counted by the publication/comment date, there are 45,925 records from 2026: 33,418 posts and 12,507 comments. If "2026 data" is counted by source file origin, i.e. records coming from files parsed in 2026, there are 174,568 records: 140,753 posts and 33,815 comments. The difference appears because 2026 parsing exports can contain records published in earlier years.
```

## 2026-05-18 - Annotation UI and Batch Import Local Verification

Commands:

```powershell
.\.venv\Scripts\python manage.py check
.\.venv\Scripts\python manage.py test annotation
.\.venv\Scripts\python manage.py import_records data\processed\dataset_combined_sample.csv --source-name combined-sample --dry-run --batch-size 500
```

Output:

```text
System check identified no issues (0 silenced).

Found 10 test(s).
System check identified no issues (0 silenced).
Creating test database for alias 'default'...
..........
----------------------------------------------------------------------
Ran 10 tests in 3.196s

OK
Destroying test database for alias 'default'...

Would import: 995; skipped: 5
```

Interpretation for the diploma:

```text
After the annotation interface was redesigned and the importer was switched to batch processing, Django system checks and the annotation test suite still passed. The sample dry-run import preserved the previous expected result: 995 records would be imported, and 5 records would be skipped as already present in the local development database.
```

## 2026-05-19 - Annotation Reservation Local Verification

Commands:

```powershell
.\.venv\Scripts\python manage.py check
.\.venv\Scripts\python manage.py test annotation
```

Output:

```text
System check identified no issues (0 silenced).

Found 15 test(s).
System check identified no issues (0 silenced).
Creating test database for alias 'default'...
...............
----------------------------------------------------------------------
Ran 15 tests in 9.678s

OK
Destroying test database for alias 'default'...
```

Interpretation for the diploma:

```text
The annotation queue now uses a 15-minute database-backed reservation mechanism. Local tests verify that a selected record is reserved for the current student, another student skips the reserved record, expired reservations can be reused, and records with submitted annotations are not issued again. This reduces duplicate work during simultaneous annotation sessions.
```

## 2026-05-19 - Maintenance Mode and Healthcheck Local Verification

Commands:

```powershell
.\.venv\Scripts\python manage.py check
.\.venv\Scripts\python manage.py test annotation
```

Output:

```text
System check identified no issues (0 silenced).

Found 18 test(s).
System check identified no issues (0 silenced).
Creating test database for alias 'default'...
..................
----------------------------------------------------------------------
Ran 18 tests in 9.410s

OK
Destroying test database for alias 'default'...
```

Interpretation for the diploma:

```text
The public annotation server now has an operational support layer: a health endpoint checks Django and database availability, maintenance mode can intentionally return a controlled 503 page, and support scripts/systemd timer assets are prepared for recovery after service hangs or crashes. Local tests verify that health checks remain available during maintenance mode and that maintenance mode can be enabled and disabled through the management command.
```

## 2026-05-19 - First Server Load Test Summary

Commands:

```bash
./deploy/support/diplom-load-test.sh http://127.0.0.1:8000/healthz/

DIPLOM_LOAD_STAGES="20:1 40:2 80:4" \
./deploy/support/diplom-load-test.sh https://label.zhkh-razmetka.ru/healthz/

curl https://label.zhkh-razmetka.ru/healthz/
sudo systemctl status diplom-gunicorn --no-pager
```

Observed local gunicorn stages:

```text
30 requests, concurrency 1: 0 failed, 1197.17 requests/sec, 0.835 ms/request
120 requests, concurrency 4: 0 failed, 1938.17 requests/sec, 2.064 ms/request
300 requests, concurrency 10: 0 failed, 2553.89 requests/sec, 3.916 ms/request
600 requests, concurrency 20: 0 failed, 3025.57 requests/sec, 6.610 ms/request

Memory before: 725 MiB used, 4.8 GiB free, 0 swap used
Memory after: 680 MiB used, 4.8 GiB free, 0 swap used
```

Observed public-domain stages:

```text
20 requests, concurrency 1: 0 failed, 35.33 requests/sec, 28.307 ms/request
40 requests, concurrency 2: 0 failed, 67.43 requests/sec, 29.659 ms/request
80 requests, concurrency 4: 49 failed/non-2xx, 160.03 requests/sec, 24.995 ms/request
```

Post-test health:

```json
{"status": "ok", "database": "ok", "maintenance": false}
```

Interpretation for the diploma:

```text
The first load test did not crash the application. Local gunicorn health checks remained fast and stable under the tested concurrency levels, with no swap usage and no failed local requests. The public-domain test began returning non-2xx responses at a higher burst level; this matches the deployed nginx rate limiter and should be described as protective throttling rather than application failure. After the tests, the health endpoint remained OK and the gunicorn service stayed active.

Note: the first local run reported non-2xx responses because production HTTPS redirect logic was active for plain local HTTP. The load-test helper was updated to send X-Forwarded-Proto: https so future local gunicorn tests measure the health endpoint directly instead of measuring redirects.
```

## 2026-05-19 - Clean Server Health Load Test

Commands:

```bash
cd ~/apps/Diplomnaya-rabota
git pull
chmod +x deploy/support/diplom-load-test.sh
./deploy/support/diplom-load-test.sh http://127.0.0.1:8000/healthz/

LATEST=$(ls -td ~/load-tests/diplom/* | head -1)
cat "$LATEST/summary.txt"
curl https://label.zhkh-razmetka.ru/healthz/
sudo systemctl status diplom-gunicorn --no-pager
```

Output summary:

```text
target_url=http://127.0.0.1:8000/healthz/
health_url=http://127.0.0.1:8000/healthz/
forwarded_proto=https
stages=30:1 120:4 300:10 600:20

System before:
load average: 0.00, 0.00, 0.00
Mem: 6.7Gi total, 674Mi used, 4.8Gi free, 6.1Gi available
Swap: 4.0Gi total, 0B used
gunicorn: active
nginx: active

30 requests, concurrency 1:
Failed requests: 0
Requests per second: 37.58
Time per request: 26.612 ms
health_after_stage={"status": "ok", "database": "ok", "maintenance": false}

120 requests, concurrency 4:
Failed requests: 0
Requests per second: 81.25
Time per request: 49.229 ms
health_after_stage={"status": "ok", "database": "ok", "maintenance": false}

300 requests, concurrency 10:
Failed requests: 0
Requests per second: 86.53
Time per request: 115.568 ms
health_after_stage={"status": "ok", "database": "ok", "maintenance": false}

600 requests, concurrency 20:
Failed requests: 0
Requests per second: 90.90
Time per request: 220.024 ms
health_after_stage={"status": "ok", "database": "ok", "maintenance": false}

System after:
load average: 0.35, 0.08, 0.03
Mem: 6.7Gi total, 658Mi used, 4.8Gi free, 6.1Gi available
Swap: 4.0Gi total, 0B used

Post-test public health:
{"status": "ok", "database": "ok", "maintenance": false}

diplom-gunicorn:
Active: active (running)
Memory: 86.3M (peak: 87.1M)
CPU: 22.612s
```

Interpretation for the diploma:

```text
After correcting the load-test helper to pass X-Forwarded-Proto: https, the clean local health load test completed without failed requests on all stages up to 600 total requests with 20 concurrent clients. The application remained healthy after each stage, nginx and gunicorn stayed active, memory usage remained stable, and swap was not used. This confirms baseline availability of the Django application and PostgreSQL connection under short burst load on the deployed physical server.
```

## 2026-05-19 - Local Login Page Load Test

Purpose:

```text
This test used the deployed physical server and targeted the real Django login page through local gunicorn (`http://127.0.0.1:8000/login/`). It bypassed public nginx rate limiting while still exercising Django template rendering and the production application process. The helper sent `X-Forwarded-Proto: https` to avoid production HTTPS redirects during local HTTP testing.
```

Commands:

```bash
DIPLOM_LOAD_STAGES="5000:25 10000:50 15000:100" \
./deploy/support/diplom-load-test.sh http://127.0.0.1:8000/login/

LATEST=$(ls -td ~/load-tests/diplom/* | head -1)
cat "$LATEST/summary.txt"
curl https://label.zhkh-razmetka.ru/healthz/
sudo systemctl status diplom-gunicorn --no-pager
```

Output summary:

```text
target_url=http://127.0.0.1:8000/login/
health_url=http://127.0.0.1:8000/healthz/
forwarded_proto=https
stages=5000:25 10000:50 15000:100

System before:
load average: 0.05, 0.06, 0.01
Mem: 6.7Gi total, 669Mi used, 4.8Gi free, 6.1Gi available
Swap: 4.0Gi total, 0B used
gunicorn: active
nginx: active

5000 requests, concurrency 25:
Failed requests: 0
Requests per second: 638.60
Time per request: 39.148 ms
Longest request: 72 ms
health_after_stage={"status": "ok", "database": "ok", "maintenance": false}

10000 requests, concurrency 50:
Failed requests: 0
Requests per second: 640.86
Time per request: 78.021 ms
Longest request: 114 ms
health_after_stage={"status": "ok", "database": "ok", "maintenance": false}

15000 requests, concurrency 100:
Failed requests: 0
Requests per second: 642.91
Time per request: 155.543 ms
Longest request: 212 ms
health_after_stage={"status": "ok", "database": "ok", "maintenance": false}

System after:
load average: 1.16, 0.38, 0.13
Mem: 6.7Gi total, 671Mi used, 4.8Gi free, 6.1Gi available
Swap: 4.0Gi total, 0B used

Post-test public health:
{"status": "ok", "database": "ok", "maintenance": false}

diplom-gunicorn:
Active: active (running)
Memory: 89.6M (peak: 90.4M)
CPU: 2min 1.529s
```

Harder follow-up output:

```text
target_url=http://127.0.0.1:8000/login/
health_url=http://127.0.0.1:8000/healthz/
forwarded_proto=https
stages=20000:100 30000:150

System before:
load average: 0.33, 0.29, 0.11
Mem: 6.7Gi total, 694Mi used, 4.8Gi free, 6.0Gi available
Swap: 4.0Gi total, 0B used
gunicorn: active
nginx: active

20000 requests, concurrency 100:
Failed requests: 0
Requests per second: 641.49
Time per request: 155.887 ms
Longest request: 215 ms
health_after_stage={"status": "ok", "database": "ok", "maintenance": false}

30000 requests, concurrency 150:
Failed requests: 0
Requests per second: 641.66
Time per request: 233.770 ms
Longest request: 321 ms
health_after_stage={"status": "ok", "database": "ok", "maintenance": false}

System after:
load average: 1.50, 0.72, 0.28
Mem: 6.7Gi total, 682Mi used, 4.8Gi free, 6.1Gi available
Swap: 4.0Gi total, 0B used
```

Interpretation for the diploma:

```text
The deployed Django application handled sustained local login-page load up to 30,000 total requests with 150 concurrent clients without failed requests. Throughput stabilized around 640 requests/sec, while average request latency increased predictably with concurrency: about 39 ms at 25 concurrent clients, 78 ms at 50, 156 ms at 100, and 234 ms at 150. The health endpoint stayed OK after every stage, gunicorn remained active, memory stayed below 100 MB for the service, and swap was not used.

This test demonstrates a stable reserve for the expected annotation workload. It should not be described as a full real-user workflow test, because it repeatedly requested the login page and did not submit annotation forms. Public-domain burst tests are expected to show non-2xx responses earlier because nginx intentionally rate-limits one client IP for security.
```

## 2026-05-19 - High Concurrency Login Page Stress Test

Server hardware note:

```text
CPU: AMD A10-7860K Radeon R7
Observed during test with btop: CPU load stayed around 53-54%, RAM usage stayed around 10%, and swap was not used.
Gunicorn profile during the test: sync workers, 2 workers total.
```

Commands:

```bash
DIPLOM_LOAD_STAGES="50000:200 75000:300 100000:400" \
./deploy/support/diplom-load-test.sh http://127.0.0.1:8000/login/

LATEST=$(ls -td ~/load-tests/diplom/* | head -1)
cat "$LATEST/summary.txt"
curl https://label.zhkh-razmetka.ru/healthz/
sudo systemctl status diplom-gunicorn --no-pager
```

Output summary:

```text
target_url=http://127.0.0.1:8000/login/
health_url=http://127.0.0.1:8000/healthz/
forwarded_proto=https
stages=50000:200 75000:300 100000:400

System before:
load average: 0.14, 0.29, 0.21
Mem: 6.7Gi total, 686Mi used, 4.8Gi free, 6.1Gi available
Swap: 4.0Gi total, 0B used
gunicorn: active
nginx: active

50000 requests, concurrency 200:
Failed requests: 0
Requests per second: 644.25
Time per request: 310.437 ms
Longest request: 422 ms
health_after_stage={"status": "ok", "database": "ok", "maintenance": false}

75000 requests, concurrency 300:
Failed requests: 0
Requests per second: 644.05
Time per request: 465.806 ms
Longest request: 604 ms
health_after_stage={"status": "ok", "database": "ok", "maintenance": false}

100000 requests, concurrency 400:
Failed requests: 0
Requests per second: 644.74
Time per request: 620.405 ms
Longest request: 781 ms
health_after_stage={"status": "ok", "database": "ok", "maintenance": false}

System after:
load average: 1.90, 1.53, 0.83
Mem: 6.7Gi total, 674Mi used, 4.8Gi free, 6.1Gi available
Swap: 4.0Gi total, 0B used

Post-test public health:
{"status": "ok", "database": "ok", "maintenance": false}

diplom-gunicorn:
Active: active (running)
Memory: 89.8M (peak: 90.8M)
CPU: 16min 15.711s
```

Interpretation for the diploma:

```text
The high-concurrency local stress test completed 225,000 login-page requests across three stages with concurrency 200, 300, and 400. No failed requests were recorded at any stage, and the application health endpoint remained OK after every stage. Average throughput stayed practically constant at about 644 requests/sec, while latency increased linearly as concurrency grew. This indicates that, under the current 2-worker synchronous gunicorn profile, the application reached a stable throughput plateau rather than failing under load.

The server remained operational after the test: gunicorn stayed active, memory stayed below 100 MB for the application service, the system did not use swap, and the observed CPU load was around 53-54%. Because the CPU was not fully saturated, the plateau is likely related to the current gunicorn worker configuration and request scheduling, not to a hard hardware failure limit. A later comparison with 3-4 gunicorn workers can be used as a separate tuning experiment.
```

## 2026-05-19 - Gunicorn Worker Tuning Comparison

Change applied on the server:

```ini
[Service]
ExecStart=
ExecStart=/home/oldskull/apps/Diplomnaya-rabota/.venv/bin/gunicorn labeling_server.wsgi:application --bind 127.0.0.1:8000 --workers 4 --timeout 60
```

Verification:

```text
Drop-In: /etc/systemd/system/diplom-gunicorn.service.d/override.conf
Tasks: 5
Memory: 150.0M (peak: 150.5M)
healthz: {"status": "ok", "database": "ok", "maintenance": false}
```

Command:

```bash
DIPLOM_LOAD_STAGES="50000:200 75000:300 100000:400" \
./deploy/support/diplom-load-test.sh http://127.0.0.1:8000/login/

LATEST=$(ls -td ~/load-tests/diplom/* | head -1)
cat "$LATEST/summary.txt"
curl https://label.zhkh-razmetka.ru/healthz/
sudo systemctl status diplom-gunicorn --no-pager
```

Output summary with 4 gunicorn workers:

```text
target_url=http://127.0.0.1:8000/login/
health_url=http://127.0.0.1:8000/healthz/
forwarded_proto=https
stages=50000:200 75000:300 100000:400

System before:
load average: 0.02, 0.26, 0.45
Mem: 6.7Gi total, 738Mi used, 4.7Gi free, 6.0Gi available
Swap: 4.0Gi total, 0B used
gunicorn: active
nginx: active

50000 requests, concurrency 200:
Failed requests: 0
Requests per second: 1061.30
Time per request: 188.449 ms
Longest request: 279 ms
health_after_stage={"status": "ok", "database": "ok", "maintenance": false}

75000 requests, concurrency 300:
Failed requests: 0
Requests per second: 1064.77
Time per request: 281.752 ms
Longest request: 383 ms
health_after_stage={"status": "ok", "database": "ok", "maintenance": false}

100000 requests, concurrency 400:
Failed requests: 0
Requests per second: 1064.46
Time per request: 375.778 ms
Longest request: 511 ms
health_after_stage={"status": "ok", "database": "ok", "maintenance": false}

System after:
load average: 3.80, 2.29, 1.24
Mem: 6.7Gi total, 755Mi used, 4.7Gi free, 6.0Gi available
Swap: 4.0Gi total, 0B used

Post-test public health:
{"status": "ok", "database": "ok", "maintenance": false}

diplom-gunicorn:
Active: active (running)
Tasks: 5
Memory: 164.8M (peak: 165.6M)
CPU: 13min 23.029s
```

Comparison with the previous 2-worker run:

```text
Concurrency 200:
2 workers: 644.25 req/s, 310.437 ms/request
4 workers: 1061.30 req/s, 188.449 ms/request
Throughput change: +64.7%
Latency change: -39.3%

Concurrency 300:
2 workers: 644.05 req/s, 465.806 ms/request
4 workers: 1064.77 req/s, 281.752 ms/request
Throughput change: +65.3%
Latency change: -39.5%

Concurrency 400:
2 workers: 644.74 req/s, 620.405 ms/request
4 workers: 1064.46 req/s, 375.778 ms/request
Throughput change: +65.1%
Latency change: -39.4%
```

Interpretation for the diploma:

```text
Increasing the number of synchronous gunicorn workers from 2 to 4 significantly improved application throughput on the AMD A10-7860K server. Under the same high-concurrency login-page test, throughput increased from approximately 644 requests/sec to approximately 1064 requests/sec, while average latency decreased by about 39% at concurrency levels 200, 300, and 400. The application still recorded zero failed requests, health checks remained OK, and swap was not used.

The memory cost of the tuning was acceptable: gunicorn memory usage increased from roughly 90 MB to roughly 165 MB, which remains small relative to the available 6.7 GiB of RAM. This confirms that the previous plateau was caused primarily by worker configuration rather than insufficient RAM or immediate CPU exhaustion. For the deployed annotation service, 4 gunicorn workers are a better production profile than 2 workers on this hardware.
```
## Production annotation statistics snapshot after completed review (2026-05-25)

After the final submitted annotation queue was reviewed and applied, the
read-only statistics export was run against the production PostgreSQL
database. The report generation time recorded inside the export is
`2026-05-25T09:33:40+03:00`.

```text
annotations_submitted_all_time=5867
annotations_checked=5867
annotations_approved_dataset=4442
deleted_posts_confirmed=728
annotations_rejected_total=697
annotations_pending=0
net_points=3367
```

The generated report passed internal consistency checks:

```text
checked outcomes: 5867 = 5170 approved total + 697 rejected
approved split:   5170 = 4442 training-ready + 728 confirmed deleted posts
record history:   5867 checked annotations over 5866 unique source records
points:           +3367 = +3066 review outcomes + +301 manual corrections
```

The accepted training-ready dataset contains `351` positive ЖКХ labels
(`7.90%`), `4073` non-ЖКХ labels (`91.69%`), and `18` uncertain labels
(`0.41%`). This is evidence that the deployed workflow has already produced a
verified dataset, while also showing a strong class imbalance that should be
addressed through targeted collection of ЖКХ-related appeals.

## Targeted ЖКХ campaign pre-activation preview (2026-05-26)

The first server-side dry run after displaying post/comment pairs was intentionally
not activated:

```text
available_unlabelled_records=259788
likely_jkh_candidates=20320
selected_by_post_context=16661
selected_by_comment_signal=3659
control_records=204
paused_general_records=239264
```

Inspection confirmed that post context must be the sole source of the subject
direction. The preview recovered valid reactions under posts about heating,
water, waste and management-company work, but also exposed false candidates
from adjacent post themes such as Shukhov tower presentation, waterfront
residential development, an eco-industrial park and nuclear power plant
construction. Before campaign activation, the selector was therefore tightened
to use only `post_text` for targeted ЖКХ inclusion and to report
`selection_subject=post_context_only`; comments remain reaction material for
human labeling and do not redefine a generic post as ЖКХ.

After deploying the post-only rule, a second dry run was performed and again
left inactive:

```text
available_unlabelled_records=259788
likely_jkh_candidates=16234
selection_subject=post_context_only
control_records=163
paused_general_records=243391
```

This preview substantially improved semantic alignment, with suitable examples
for waste collection, капремонт, water supply, heating and station-aeration
oversight. It also exposed remaining adjacent subjects that match broad
infrastructure vocabulary without being targeted ЖКХ posts: construction of
industrial treatment facilities at a brewery, an ice palace project, a weather
warning about heavy snow and stadium redevelopment. The live campaign was not
activated; these explicit post topics were added to the pre-activation
exclusions.

A third preview after those exclusions remained inactive while one additional
adjacent topic was identified:

```text
available_unlabelled_records=259788
likely_jkh_candidates=15907
selection_subject=post_context_only
control_records=160
paused_general_records=243721
```

The random sample is now predominantly appropriate for targeted annotation:
waste collection/TKO, sewer odour, heating, water shutdowns, капремонт,
management-company liability, livenvki and aeration-station oversight. One
clear false candidate remained: a post about opening an ice arena selected
through the phrase `благоустройство площади`. Ice arenas were added to the
same exclusion as ice palaces and stadium developments. Truncated ambiguous
posts are reserved for full-text inspection rather than removed from an
excerpt.

A fourth preview after the ice-arena exclusion was also retained as a dry run:

```text
available_unlabelled_records=259788
likely_jkh_candidates=15326
selection_subject=post_context_only
control_records=154
paused_general_records=244308
```

Full-text inspection kept record `23592`, whose post directly concerns sewer
odour, and identified narrowly removable non-JKH mechanisms: a weapon/112
incident in an entrance hall (`51202`), adolescent vandalism with police
advice (`233457`), construction of a spiritual education centre on a yard
(`217605`), and repair of a hospital (`72226`). The campaign was still not
activated. Exclusions were added for those post themes while retaining
utility-service failures involving water, heat, waste or sewage.

The final pre-activation dry run after these narrow exclusions reported:

```text
available_unlabelled_records=259788
likely_jkh_candidates=14954
selection_subject=post_context_only
control_records=150
paused_general_records=244684
```

Its deterministic 25-record sample was predominantly aligned with the
collection objective: heating, water supply, sewage odour, waste collection,
communal tariffs, yard service, municipal street cleaning and public
improvement. A few borderline shared-property or residential-neighbourhood
subjects remain acceptable at this stage because campaign membership only
prioritizes records for human annotation and is not itself a trusted label.
This configuration was accepted for production activation as the most precise
tested enrichment queue.

## Targeted JKH campaign activation (2026-05-26)

The approved post-only queue configuration was applied in production:

```text
mode=apply
available_unlabelled_records=259788
likely_jkh_candidates=14954
selection_subject=post_context_only
control_records=150
paused_general_records=244684
target_candidate_to_control_ratio=100:1
minimum_candidate_score=7
control_random_seed=42
Campaign activated: 14954 likely JKH candidates and 150 control records are now assignable.
```

The command completed before gunicorn was restarted, so campaign assignment
state was written successfully. The immediately following public health
request returned the nginx emergency fallback HTML instead of the expected
JSON health document. This is consistent with a request during application
restart, but service recovery must be verified with a delayed health request
and `systemctl status` before the deployment is recorded as healthy.

Delayed post-restart verification confirmed successful recovery:

```text
diplom-gunicorn.service: active (running)
Drop-In: override.conf
Tasks: 5
Memory: 150.4M (peak: 151.3M)
gunicorn workers booted: 4

HTTP/1.1 200 OK
Content-Type: application/json
{"status": "ok", "database": "ok", "maintenance": false}
```

Therefore the emergency HTML page observed immediately after restart was a
temporary startup fallback, not a persistent production failure. The targeted
JKH enrichment campaign is active and the application is healthy.

## First offline JKH batch applied (2026-06-03)

The first locally audited offline batch of prioritized JKH candidates was
applied to production with points awarded to `oldskull`. The dry run and the
real apply produced identical counters:

```text
mode=dry-run
reviewer=oldskull
student=oldskull
rows=500
award_points=True
approve: 500
deleted_confirm: 0
skip: 0
score_events: 500
failed: 0
Dry run only. Re-run without --dry-run to apply labels.

mode=apply
reviewer=oldskull
student=oldskull
rows=500
award_points=True
approve: 500
deleted_confirm: 0
skip: 0
score_events: 500
failed: 0
Applied offline labels: 500
```

This confirms that all `500` prepared offline labels were accepted without
row-level conflicts and were inserted as approved annotations.

## Full teacher-student data archive pointer (2026-06-03)

The durable index for all project data exports used in reports, audits and
teacher-student model training is:

```text
docs/project_data_archive.md
```

The full teacher-student export is stored on the production server under the
timestamped pattern:

```text
/home/oldskull/apps/Diplomnaya-rabota/data/exports/teacher_student_full_export_YYYY-MM-DD_HH-MM/
/home/oldskull/apps/Diplomnaya-rabota/data/exports/teacher_student_full_export_YYYY-MM-DD_HH-MM.tar.gz
```

After downloading, the corresponding local copy belongs under:

```text
D:\Diplom\data\exports\teacher_student_full_export_YYYY-MM-DD_HH-MM\
```

The archive contains gold approved annotations, all-annotation audit data,
statistics, manifest files and numbered unresolved silver batches. Future
reports should cite the exact timestamped archive used.

## Production OMSU API deployment (2026-06-07)

The production server pulled the desktop/API dashboard changes through commit
`ef9ba5c` and applied the new OMSU API migration:

```text
Updating b6b9d99..ef9ba5c
Fast-forward

System check identified no issues (0 silenced).

Operations to perform:
  Apply all migrations: admin, annotation, auth, contenttypes, sessions
Running migrations:
  Applying annotation.0005_omsuarea_omsudashboardsnapshot_omsulatestcomment... OK

Seeded 8 OMSU demo areas.
```

The production `.env` was configured to require an OMSU API key and to use
`300` seconds for snapshot refreshes and `2` seconds for latest-comment
refreshes. The generated key was printed in the terminal/chat transcript and is
therefore considered exposed; it is intentionally omitted here and should be
rotated before real client use.

A first public request during the restart interval returned the configured
nginx emergency fallback:

```text
HTTP/1.1 502 Bad Gateway
Server: nginx/1.24.0 (Ubuntu)
Content-Type: text/html
title: Сервис временно недоступен
screen: аварийный экран nginx / Сервис перезапускается
```

Immediately afterward, the public API recovered and returned JSON through
nginx:

```text
HTTP/1.1 200 OK
Content-Type: application/json

{
  "api_version": "v1",
  "domain": "zhkh_omsu_monitoring",
  "snapshot_refresh_seconds": 300,
  "comment_refresh_seconds": 2,
  "endpoints": {
    "snapshot": "/api/v1/omsu/snapshot/",
    "area_detail": "/api/v1/omsu/areas/{slug}/",
    "latest_comment": "/api/v1/omsu/latest-comment/"
  }
}
```

A protected snapshot request with the API-key header returned a JSON payload
containing the seeded demo territories, including `nizhny-novgorod` with score,
previous score, confidence band, counters, topics and polygon geometry. This
confirms that the production API and key-gated access path are working; the
current data is still demo data, not the final ML-backed aggregator.

## Follow-up OMSU API verification (2026-06-07)

The user saved a later production verification transcript locally as
`C:\Users\OldSkull\Desktop\1111.txt`. Sanitized result:

```text
Already up to date.
System check identified no issues (0 silenced).

Operations to perform:
  Apply all migrations: admin, annotation, auth, contenttypes, sessions
Running migrations:
  No migrations to apply.

Seeded 8 OMSU demo areas.
```

Key-gated API behavior:

```text
Request without API key:
401

Authenticated manifest request:
api_version: v1
domain: zhkh_omsu_monitoring
snapshot_refresh_seconds: 300
comment_refresh_seconds: 2
endpoints:
  snapshot: /api/v1/omsu/snapshot/
  area_detail: /api/v1/omsu/areas/{slug}/
  latest_comment: /api/v1/omsu/latest-comment/

Authenticated snapshot request:
api_version: v1
snapshot_refresh_seconds: 300
comment_refresh_seconds: 2
areas include seeded demo territory nizhny-novgorod
```

The transcript did not contain the generated API key value; the printed key
line was blank in the captured file. Treat the active key as not safely
captured and rotate it again before distributing it to production clients.
