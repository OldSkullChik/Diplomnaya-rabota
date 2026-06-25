# VK monitoring test pipeline - 2026-06-17

## Goal

Build a test monitoring contour on the Ubuntu server:

1. collect VK posts/comments for the last 2 hours through Playwright/Chromium, not VK API;
2. clean and deduplicate records;
3. analyze records through the accepted taxonomy cascade plus OMSU negative-signal checkpoint;
4. write results into a test copy of the working database;
5. review positives/negatives before deciding whether to enable production hourly monitoring.

The test contour is intentionally separated from the production annotation queue. It writes to `MonitoringSource`, `MonitoringRun`, and `MonitoringItem`, and updates `OmsuDashboardSnapshot` only when `--update-dashboard` is passed.

## New Code

- `annotation.models.MonitoringSource`
- `annotation.models.MonitoringRun`
- `annotation.models.MonitoringItem`
- `annotation/monitoring/vk_playwright.py`
- `annotation/monitoring/cascade.py`
- `annotation/monitoring/dashboard.py`
- `python manage.py seed_monitoring_sources`
- `python manage.py collect_vk_monitoring_test`
- `monitoring_requirements.txt`
- `deploy/systemd/diplom-vk-monitoring-test.service`
- `deploy/systemd/diplom-vk-monitoring-test.timer`

## Server Setup

Run these on the Ubuntu server after pulling the code.

```bash
cd /home/oldskull/apps/Diplomnaya-rabota
git pull
```

Install optional monitoring dependencies into the project virtualenv:

```bash
source .venv/bin/activate
pip install -r monitoring_requirements.txt
pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m playwright install chromium
```

If Chromium system dependencies are missing:

```bash
sudo .venv/bin/python -m playwright install-deps chromium
```

Create a test database copy. This avoids touching production records while we inspect collector quality.

```bash
sudo -u postgres createdb -O diplom diplom_monitoring_test
sudo -u postgres pg_dump diplom | sudo -u postgres psql diplom_monitoring_test
```

Create a separate environment file for the test collector:

```bash
cp .env .env.monitoring-test
nano .env.monitoring-test
```

In `.env.monitoring-test`, change only the database name:

```text
DATABASE_URL=postgres://diplom:<password>@127.0.0.1:5432/diplom_monitoring_test
VK_MONITORING_BASE_URL=https://m.vk.com
VK_MONITORING_STORAGE_STATE=/home/oldskull/apps/Diplomnaya-rabota/runtime/vk_storage_state.json
TAXONOMY_CHECKPOINT=data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/final_w03_weighted_lr1e5_e4
OMSU_CHECKPOINT=data/ml_experiments/omsu_score_2026-06-06/threshold/negative_signal_capped_20k
```

Do not commit `.env.monitoring-test`.

Apply migrations to the test DB. Do not `source .env.monitoring-test` in bash:
the production `SECRET_KEY` can contain shell metacharacters. Django loads the
test dotenv file through `DJANGO_ENV_FILE`.

```bash
DJANGO_ENV_FILE=/home/oldskull/apps/Diplomnaya-rabota/.env.monitoring-test \
  python manage.py migrate
```

Make sure the two accepted model checkpoint directories exist on the server:

```bash
ls -lah data/ml_experiments/teacher_student_runs/sweep_final_2026-06-03/final_w03_weighted_lr1e5_e4/
ls -lah data/ml_experiments/omsu_score_2026-06-06/threshold/negative_signal_capped_20k/
```

If they are absent, copy them from the local machine/archive before running analysis.

## Seed Monitoring Sources

Load VK groups from the normalized 52-object monitoring asset:

```bash
DJANGO_ENV_FILE=/home/oldskull/apps/Diplomnaya-rabota/.env.monitoring-test \
  python manage.py seed_monitoring_sources \
  --input desktop_dashboard/assets/monitoring_groups.json
```

For a tiny smoke setup:

```bash
DJANGO_ENV_FILE=/home/oldskull/apps/Diplomnaya-rabota/.env.monitoring-test \
  python manage.py seed_monitoring_sources \
  --input desktop_dashboard/assets/monitoring_groups.json \
  --limit-areas 2 \
  --limit-groups 1
```

## First Smoke Run

Start with no DB writes and no ML analysis:

```bash
DJANGO_ENV_FILE=/home/oldskull/apps/Diplomnaya-rabota/.env.monitoring-test \
  python manage.py collect_vk_monitoring_test \
  --dry-run \
  --skip-analysis \
  --lookback-minutes 120 \
  --max-sources 2 \
  --max-posts-per-source 2 \
  --max-comments-per-post 20 \
  --include-unknown-dates \
  --json-output runtime/vk_monitoring_dry_run.json
```

Review:

```bash
less runtime/vk_monitoring_dry_run.json
```

If VK returns login/captcha/empty pages, create a browser session state.

Option A: create storage state locally and copy it to the server:

```bash
python -m playwright codegen --save-storage=runtime/vk_storage_state.json https://vk.com
scp runtime/vk_storage_state.json oldskull@<server>:/home/oldskull/apps/Diplomnaya-rabota/runtime/
```

Option B: create it on the server with a virtual display:

```bash
sudo apt install xvfb
xvfb-run .venv/bin/python -m playwright codegen \
  --save-storage=runtime/vk_storage_state.json \
  https://vk.com
```

## First DB Write Without ML

```bash
DJANGO_ENV_FILE=/home/oldskull/apps/Diplomnaya-rabota/.env.monitoring-test \
  python manage.py collect_vk_monitoring_test \
  --skip-analysis \
  --lookback-minutes 120 \
  --max-sources 3 \
  --max-posts-per-source 3 \
  --max-comments-per-post 30 \
  --include-unknown-dates \
  --json-output runtime/vk_monitoring_collect_only.json
```

Inspect in Django admin:

- `Monitoring sources`
- `Monitoring runs`
- `Monitoring items`

## First DB Write With Cascade Analysis

On the weak server CPU, start small:

```bash
DJANGO_ENV_FILE=/home/oldskull/apps/Diplomnaya-rabota/.env.monitoring-test \
  python manage.py collect_vk_monitoring_test \
  --lookback-minutes 120 \
  --max-sources 3 \
  --max-posts-per-source 3 \
  --max-comments-per-post 30 \
  --include-unknown-dates \
  --analysis-batch-size 8 \
  --update-dashboard \
  --json-output runtime/vk_monitoring_with_analysis.json
```

If this is too slow, run collection and analysis separately by first using `--skip-analysis`, then rerunning the command on fewer sources or increasing server resources later.

## Hourly Test Timer

Install the test timer only after manual smoke runs look sane.

```bash
sudo cp deploy/systemd/diplom-vk-monitoring-test.service /etc/systemd/system/
sudo cp deploy/systemd/diplom-vk-monitoring-test.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start diplom-vk-monitoring-test.service
journalctl -u diplom-vk-monitoring-test.service -n 100 --no-pager
```

Enable hourly execution:

```bash
sudo systemctl enable --now diplom-vk-monitoring-test.timer
systemctl list-timers | grep diplom-vk-monitoring
```

Stop it:

```bash
sudo systemctl disable --now diplom-vk-monitoring-test.timer
```

## Review Criteria

After the first analyzed run, inspect:

- how many sources returned data;
- whether records are actually from the last 2 hours;
- whether comments are attached to the correct post text;
- duplicate rate;
- empty/noisy text rate;
- VK blocking/captcha rate;
- CPU time and memory usage;
- taxonomy predictions on several hand-picked examples;
- OMSU negative-signal false positives and false negatives.

Only after this review should the monitoring contour be promoted from test DB to production DB.
