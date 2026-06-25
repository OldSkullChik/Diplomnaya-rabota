# Operations Runbook

This document records the basic recovery and maintenance procedures for the public annotation server.

## Health endpoint

The application exposes a lightweight health endpoint:

```bash
curl -I https://label.zhkh-razmetka.ru/healthz/
curl https://label.zhkh-razmetka.ru/healthz/
```

Expected healthy response:

```json
{"status": "ok", "database": "ok", "maintenance": false}
```

The endpoint checks that Django can talk to the database. It stays available during maintenance mode so that monitoring does not confuse planned work with a crash.

## Manual maintenance mode

Maintenance mode is controlled by a local JSON flag file and does not require editing code.

Enable:

```bash
cd /home/oldskull/apps/Diplomnaya-rabota
source .venv/bin/activate
python manage.py maintenance on --eta "15 минут"
```

Enable with a custom message:

```bash
python manage.py maintenance on \
  --title "Идут технические работы" \
  --message "Обновляем разметчик и проверяем базу данных. Доступ скоро вернется." \
  --eta "15 минут"
```

Enable with a live countdown:

```bash
python manage.py maintenance on \
  --title "Вскоре" \
  --message "Сервис временно переведен в режим обслуживания. Исправляем найденные ошибки и скоро вернем разметчик в работу." \
  --duration "20m"
```

`--duration` accepts values such as `20m`, `1h`, or `900s`. It stores an `ends_at` timestamp in the maintenance JSON file, and the maintenance page renders a live browser countdown.

Enable with a live countdown and automatic shutdown:

```bash
python manage.py maintenance on \
  --title "Вскоре" \
  --message "Сервис временно переведен в режим обслуживания. Исправляем найденные ошибки и скоро вернем разметчик в работу." \
  --duration "20m"

sudo systemd-run \
  --unit=diplom-maintenance-off \
  --on-active=20m \
  --working-directory=/home/oldskull/apps/Diplomnaya-rabota \
  /home/oldskull/apps/Diplomnaya-rabota/.venv/bin/python manage.py maintenance off
```

Check status:

```bash
python manage.py maintenance status
```

Disable:

```bash
python manage.py maintenance off
```

When enabled, normal site pages return `503 Service Unavailable` with a visible maintenance screen. Static files and `/healthz/` remain open.

After visual asset updates, collect static files before testing the maintenance screen:

```bash
python manage.py collectstatic --noinput
sudo systemctl reload nginx
```

## Server self-check scripts

The repository includes support scripts:

```bash
deploy/support/diplom-healthcheck.sh
deploy/support/diplom-repair.sh
```

Manual check:

```bash
/home/oldskull/apps/Diplomnaya-rabota/deploy/support/diplom-healthcheck.sh
```

Manual repair attempt:

```bash
sudo /home/oldskull/apps/Diplomnaya-rabota/deploy/support/diplom-repair.sh
```

The repair script checks local nginx-to-Django health. If the check fails, it restarts `postgresql` only when PostgreSQL is inactive, restarts `diplom-gunicorn`, verifies nginx configuration, reloads nginx, and checks health again.

## Optional systemd watchdog timer

Install the two-minute healthcheck timer:

```bash
cd /home/oldskull/apps/Diplomnaya-rabota
chmod +x deploy/support/diplom-healthcheck.sh deploy/support/diplom-repair.sh
sudo cp deploy/systemd/diplom-healthcheck.service /etc/systemd/system/diplom-healthcheck.service
sudo cp deploy/systemd/diplom-healthcheck.timer /etc/systemd/system/diplom-healthcheck.timer
sudo systemctl daemon-reload
sudo systemctl enable --now diplom-healthcheck.timer
systemctl status diplom-healthcheck.timer --no-pager
```

View recent repair attempts:

```bash
sudo journalctl -u diplom-healthcheck.service -n 80 --no-pager
```

## Load and stress smoke test

Use only read-only endpoints for load testing. Do not stress-test annotation POST requests on production data.

Install ApacheBench:

```bash
sudo apt install -y apache2-utils
```

Run the application-level test directly against gunicorn from the server:

```bash
cd /home/oldskull/apps/Diplomnaya-rabota
chmod +x deploy/support/diplom-load-test.sh
./deploy/support/diplom-load-test.sh http://127.0.0.1:8000/healthz/
```

The helper sends `X-Forwarded-Proto: https` by default. This keeps local gunicorn checks from being converted into HTTPS redirects when production `SECURE_SSL_REDIRECT=1` is enabled.

The default stages are:

```text
30 requests / 1 concurrent client
120 requests / 4 concurrent clients
300 requests / 10 concurrent clients
600 requests / 20 concurrent clients
```

Logs are written to:

```text
/home/oldskull/load-tests/diplom/<date_time>/
```

For a gentler public-domain test through nginx, HTTPS, DNS, and router forwarding:

```bash
DIPLOM_LOAD_STAGES="20:1 40:2 80:4" \
./deploy/support/diplom-load-test.sh https://label.zhkh-razmetka.ru/healthz/
```

The public-domain test may produce `503` responses if the nginx rate limiter is triggered. This is expected under burst load because the deployed nginx limit is `5r/s` per client IP.

After a run, check service health:

```bash
curl https://label.zhkh-razmetka.ru/healthz/
sudo systemctl status diplom-gunicorn --no-pager
sudo journalctl -u diplom-gunicorn -n 60 --no-pager
```

## Cumulative annotation statistics snapshot

After a review batch has been applied, generate the official cumulative snapshot from the production database:

```bash
cd /home/oldskull/apps/Diplomnaya-rabota
source .venv/bin/activate
STAMP=$(date +%F_%H-%M)
python manage.py export_annotation_statistics "data/exports/statistics_${STAMP}"
```

The report directory contains:

- `annotation_statistics.json` with exact machine-readable totals;
- `annotation_statistics.md` with a human-readable table for the diploma/report;
- `annotation_statistics_infographic.svg` with a ready-to-use infographic;
- `participants.csv` and `reviewers.csv` with detailed score/review breakdowns;
- `approved_taxonomy.csv` with the distribution of labels in the accepted training set.

Interpret the headline figures carefully:

- `annotations_checked` counts accepted and rejected submitted answers retained in the database history;
- `annotations_approved_dataset` excludes confirmed deleted posts and is the relevant accepted-training-data count;
- `deleted_posts_confirmed` is reported separately because these decisions exclude records without awarding points;
- `annotations_rejected_total` counts rejected attempts even when the record was later labeled again;
- `net_points` includes any manual score correction recorded in `ScoreEvent`.

Keep the generated export outside git unless a sanitized snapshot is deliberately selected as diploma evidence.

## Full data archive for reports and training

The canonical pointer for full project data exports is `docs/project_data_archive.md`.
Use it when preparing diploma reports, audit notes, teacher-student training
datasets, or recovery instructions.

The full teacher-student export is stored on the production server under:

```text
/home/oldskull/apps/Diplomnaya-rabota/data/exports/teacher_student_full_export_YYYY-MM-DD_HH-MM/
/home/oldskull/apps/Diplomnaya-rabota/data/exports/teacher_student_full_export_YYYY-MM-DD_HH-MM.tar.gz
```

After download, keep the local copy under:

```text
D:\Diplom\data\exports\teacher_student_full_export_YYYY-MM-DD_HH-MM\
```

This archive contains the approved gold labels, all-annotation audit export,
statistics, manifest files, and numbered unresolved silver batches. Always cite
the exact timestamped archive used.

To create the extended SVG dashboard from a downloaded statistics snapshot:

```powershell
python manage.py render_statistics_dashboard `
  data\exports\<statistics-dir>\annotation_statistics.json `
  data\exports\<statistics-dir>\annotation_dashboard_full.svg
```

On a workstation with Chrome installed, render the SVG to a large PNG:

```powershell
$dir = (Resolve-Path 'data\exports\<statistics-dir>').Path
$url = 'file:///' + (($dir + '\annotation_dashboard_full.svg') -replace '\\','/')
& 'C:\Program Files\Google\Chrome\Application\chrome.exe' `
  --headless=new --disable-gpu --hide-scrollbars `
  --force-device-scale-factor=1 --window-size=1800,2700 `
  --screenshot="$dir\annotation_dashboard_full.png" $url
```

## Targeted ЖКХ annotation campaign

Use this campaign when the verified training set needs more positive ЖКХ examples. A source record represents a post together with a public reaction: only the post defines whether the discussion concerns ЖКХ or municipal благоустройство, while the comment supplies the reaction for sentiment, appeal type, sarcasm and context details. The campaign does not turn heuristic candidates into labels; it only changes which unresolved records are offered to human annotators.

After deploying the migration, run a dry preview first:

```bash
cd ~/apps/Diplomnaya-rabota
source .venv/bin/activate
python manage.py prepare_jkh_sampling_campaign \
  --ratio 100 \
  --threshold 7 \
  --seed 42 \
  --preview-output data/exports/jkh_campaign_preview.csv
```

The output reports the number of available unresolved records, likely ЖКХ candidates, confirms `selection_subject=post_context_only`, and reports randomly selected control records and ordinary records that would be paused. Check the printed post as the candidate topic and the comment as its reaction before enabling the queue.

Enable the selected pool after the preview is plausible:

```bash
python manage.py prepare_jkh_sampling_campaign \
  --ratio 100 \
  --threshold 7 \
  --seed 42 \
  --preview-output data/exports/jkh_campaign_preview.csv \
  --apply
```

While the campaign is active, assignment draws only from the marked likely-ЖКХ candidates and control sample. Existing data is not deleted; `is_active` continues to mean genuine queue exclusion, including confirmed deleted posts. Records imported later enter the general pool and require another campaign preparation run before they are included.

To immediately return to the full active queue:

```bash
python manage.py prepare_jkh_sampling_campaign --disable
```

After enough records are reviewed, generate a new cumulative statistics snapshot and compare the approved positive-ЖКХ share with the `351/4442` baseline from 2026-05-25.

## Offline labeling of unresolved campaign records

Use this path when the remaining active `jkh_candidate` records need to be labeled outside the web queue. The command exports unresolved records only: active records from the selected sampling pool that do not already have a submitted or approved annotation. Rejected-only records may be exported again because the web queue also treats them as assignable.

Export a batch from production:

```bash
cd ~/apps/Diplomnaya-rabota
source .venv/bin/activate
STAMP=$(date +%F_%H-%M)
OUT="data/exports/offline_jkh_labels_${STAMP}"
mkdir -p "$OUT"

python manage.py export_unresolved_records \
  "$OUT/unresolved_jkh_candidates.csv" \
  --pool jkh_candidate \
  --limit 500

tar -czf "${OUT}.tar.gz" -C data/exports "$(basename "$OUT")"
echo "ARCHIVE=/home/oldskull/apps/Diplomnaya-rabota/${OUT}.tar.gz"
```

The exported CSV is filled offline. Use `offline_action=approve` for usable labels, `offline_action=deleted_confirm` only for genuinely deleted posts, and leave `offline_action` blank or set `skip` for records that should not be imported yet. Label values must use the internal choice keys such as `yes`, `not_jkh`, `heating_hot_water`, `negative`, `complaint`, `resource_provider`, `no`, `normal`.

Apply the completed CSV after a dry run:

```bash
python manage.py apply_offline_record_labels \
  "$OUT/unresolved_jkh_candidates_labeled.csv" \
  --reviewer oldskull \
  --student oldskull \
  --award-points \
  --dry-run

python manage.py apply_offline_record_labels \
  "$OUT/unresolved_jkh_candidates_labeled.csv" \
  --reviewer oldskull \
  --student oldskull \
  --award-points
```

Offline labels are inserted as already approved annotations. When `--award-points` is passed, ordinary approved labels create standard `+1` score events for the selected `--student`; confirmed deleted posts remain excluded without points, matching the web-review rules.

## nginx fallback page

The Django maintenance screen works when Django is alive. If gunicorn is down and nginx receives a `502/503/504`, nginx can serve a static fallback page.

Copy the snippet:

```bash
sudo cp deploy/nginx/maintenance-fallback-snippet.conf /etc/nginx/snippets/diplom-maintenance-fallback.conf
```

The fallback page uses `/static/annotation/img/error.png`, so run `collectstatic` after pulling new visual assets:

```bash
python manage.py collectstatic --noinput
```

Then include this line inside the active `server { ... }` block for `label.zhkh-razmetka.ru`:

```nginx
include /etc/nginx/snippets/diplom-maintenance-fallback.conf;
```

After editing nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Do not overwrite the active nginx site file blindly after Certbot has edited it for HTTPS.
