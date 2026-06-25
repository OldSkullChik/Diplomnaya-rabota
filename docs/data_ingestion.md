# Data Ingestion Notes

This document records how raw appeal/comment data should enter the annotation server.

## Raw Data Rule

`raw/` is the local input folder for source files. It is intentionally ignored by git because it can contain large exports, copied datasets, and raw parser output.

The main reference format is the compacted `dataset.csv` copied from the `Normalizaciya` project. New data should be adapted to this shape whenever possible.

Canonical columns observed in `raw/dataset.csv`:

```text
text,post_text,data_type,has_post_context,group_id,group_name,post_id,comment_id,comment_url,date,author,likes,sentiment,appeal_type,addressee,file_origin
```

Meaning for the annotation server:

- `text`: the appeal/comment/post text shown as the main annotation item.
- `post_text`: source post context for comments, when available.
- `comment_url` / `comment_id` / `post_id`: stable source identity for deduplication.
- `group_name`: source community/public page name.
- `file_origin`: raw file the row originally came from.

## Supported Import Inputs

The `import_records` command now supports:

- Normalizaciya-style comma-separated `dataset.csv`.
- `posts_parsed.csv` with `post_text` as the importable text.
- Barkov-style semicolon-separated wall post exports with Russian headers such as `ССЫЛКА НА ПОСТ`, `НАЗВАНИЕ ВЛАДЕЛЬЦА`, `ТЕКСТ`.
- Barkov-style semicolon-separated comment exports with Russian headers such as `Ссылка на комментарий`, `Ссылка на пост`, `Текст комментария`.

The importer sniffs the CSV delimiter automatically and uses known header aliases for text, post context, source URL, source group, and external ID.

Large imports are processed in batches. The default batch size is `1000`; it can be changed with `--batch-size`.

## Build One Combined Dataset

Raw files should first be assembled into one canonical CSV:

```bash
python manage.py build_dataset raw \
  --output data/processed/dataset_combined.csv \
  --missing-output data/processed/missing_post_context.csv
```

The command:

- keeps the old `dataset.csv` rows as the base data;
- uses `posts_parsed.csv` to restore old missing comment context;
- reads Barkov wall post exports as post records and as context lookup;
- reads Barkov comment exports as comment records;
- joins fresh comments with their source posts by VK wall post link;
- writes comments without matching post context to `missing_post_context.csv`;
- deduplicates rows inside the combined output.

If `missing_post_context.csv` contains rows beyond the header, those post links are the candidates that may need additional parsing.

For a quick smoke test:

```bash
python manage.py build_dataset raw \
  --output data/processed/dataset_combined_sample.csv \
  --missing-output data/processed/missing_post_context_sample.csv \
  --limit 1000
```

## Import Dry Run First

Before importing the combined file into the live queue, run a dry run:

```bash
python manage.py import_records data/processed/dataset_combined.csv --source-name combined-raw --dry-run
```

If the counts look reasonable, run without `--dry-run`.

For a controlled first import, use `--limit`:

```bash
python manage.py import_records data/processed/dataset_combined.csv --source-name combined-raw --limit 10000 --batch-size 1000
```

## Deduplication

The annotation queue deduplicates source records by a SHA-256 hash built from:

```text
external_id + text + post_text
```

This means the same raw row should not be imported twice, while the same comment text under different source URLs can still be preserved when it represents a different source record.

## Current Data Strategy

Use the copied `dataset.csv` from `Normalizaciya` as the main seed dataset because it is already compacted and follows the expected schema.

Use 2025 parser outputs as already structured legacy data.

Use 2026 Barkov exports as recent additions. Prefer importing them directly with the enhanced importer before returning to parser work. Only revive parser scripts if the available structured files are insufficient.

For continuous updates on the server:

1. Put newly parsed CSV files into `raw/`.
2. Re-run `build_dataset`.
3. Check `missing_post_context.csv`.
4. Run `import_records` on the combined CSV.

Repeated imports are safe because both the combined builder and the database importer deduplicate records.

## Thematic enrichment after import

Newly imported records initially belong to the general annotation pool. When positive ЖКХ labels are underrepresented, prepare a targeted annotation campaign over unresolved active records:

```bash
python manage.py prepare_jkh_sampling_campaign \
  --ratio 100 \
  --threshold 7 \
  --seed 42 \
  --preview-output data/exports/jkh_campaign_preview.csv
```

This is a dry run. It uses transparent phrase-based evidence only from the source post to determine the record direction: reactions beneath a likely ЖКХ or municipal-благоустройство post remain candidate material even when the comment is brief. The comment is public reaction data and does not make a generic post part of the targeted ЖКХ pool. The command samples one unresolved general-control record per 100 candidates. Candidates are not automatically labeled and must pass normal human annotation and review.

After inspecting the preview CSV, append `--apply` to activate only the selected candidate/control pool. Use `python manage.py prepare_jkh_sampling_campaign --disable` to resume assignment from all active records without altering imported source data or completed annotations.

## Loading the Current Dataset to the Server

The generated files in `data/processed/` are not committed to git, so they must be copied to the server separately.

From Windows PowerShell in `D:\Diplom`:

```powershell
ssh oldskull@192.168.1.77 "mkdir -p /home/oldskull/apps/Diplomnaya-rabota/data/processed"
scp .\data\processed\dataset_combined.csv oldskull@192.168.1.77:/home/oldskull/apps/Diplomnaya-rabota/data/processed/
scp .\data\processed\missing_post_context.csv oldskull@192.168.1.77:/home/oldskull/apps/Diplomnaya-rabota/data/processed/
```

Then on the server:

```bash
cd ~/apps/Diplomnaya-rabota
git pull
source .venv/bin/activate

python manage.py import_records data/processed/dataset_combined.csv --source-name combined-raw --dry-run --limit 10000 --batch-size 1000
python manage.py import_records data/processed/dataset_combined.csv --source-name combined-raw --limit 10000 --batch-size 1000

sudo systemctl restart diplom-gunicorn
```

Start with a limited import so the interface can be checked against real records. After that, import the full dataset by removing `--limit 10000`:

```bash
python manage.py import_records data/processed/dataset_combined.csv --source-name combined-raw --batch-size 1000
```

## Full Archive Pointer

For reports, audits, recovery, and teacher-student model training, use
`docs/project_data_archive.md` as the canonical index of where project data is
stored.

The current full export pattern is:

```text
/home/oldskull/apps/Diplomnaya-rabota/data/exports/teacher_student_full_export_YYYY-MM-DD_HH-MM/
/home/oldskull/apps/Diplomnaya-rabota/data/exports/teacher_student_full_export_YYYY-MM-DD_HH-MM.tar.gz
```

After download, the local copy belongs under:

```text
D:\Diplom\data\exports\teacher_student_full_export_YYYY-MM-DD_HH-MM\
```

That archive contains the human-approved gold annotations, all-annotation
audit export, production statistics, manifest files, and numbered unresolved
silver batches for automatic teacher labeling.
