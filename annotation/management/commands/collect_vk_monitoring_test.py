import json
import os
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from annotation.models import MonitoringItem, MonitoringRun, MonitoringSource
from annotation.monitoring.cascade import (
    DEFAULT_OMSU_CHECKPOINT,
    DEFAULT_TAXONOMY_CHECKPOINT,
    CascadeAnalyzer,
)
from annotation.monitoring.dashboard import refresh_dashboard_from_monitoring
from annotation.monitoring.vk_playwright import VkPlaywrightScraper


class Command(BaseCommand):
    help = "Test VK monitoring collection through Playwright and optional cascade analysis."

    def add_arguments(self, parser):
        parser.add_argument("--lookback-minutes", type=int, default=120)
        parser.add_argument("--max-sources", type=int, default=5)
        parser.add_argument("--max-posts-per-source", type=int, default=5)
        parser.add_argument("--max-comments-per-post", type=int, default=50)
        parser.add_argument("--source", dest="source_slugs", action="append", default=[])
        parser.add_argument("--source-shard-count", type=int, default=1)
        parser.add_argument("--source-shard-index", type=int, default=0)
        parser.add_argument("--base-url", default=os.environ.get("VK_MONITORING_BASE_URL", "https://m.vk.com"))
        parser.add_argument("--storage-state", default=os.environ.get("VK_MONITORING_STORAGE_STATE", "runtime/vk_storage_state.json"))
        parser.add_argument("--user-data-dir", default=os.environ.get("VK_MONITORING_USER_DATA_DIR", ""))
        parser.add_argument("--headed", action="store_true", help="Run Chromium with a visible window.")
        parser.add_argument("--include-unknown-dates", action="store_true")
        parser.add_argument("--timeout-ms", type=int, default=30000)
        parser.add_argument("--scroll-rounds", type=int, default=3)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--force", action="store_true", help="Ignore an existing running MonitoringRun.")
        parser.add_argument("--skip-analysis", action="store_true")
        parser.add_argument("--analysis-batch-size", type=int, default=32)
        parser.add_argument("--analysis-device", default="auto")
        parser.add_argument("--taxonomy-checkpoint", default=os.environ.get("TAXONOMY_CHECKPOINT", DEFAULT_TAXONOMY_CHECKPOINT))
        parser.add_argument("--omsu-checkpoint", default=os.environ.get("OMSU_CHECKPOINT", DEFAULT_OMSU_CHECKPOINT))
        parser.add_argument("--negative-threshold", type=float, default=0.85)
        parser.add_argument("--nonnegative-threshold", type=float, default=0.15)
        parser.add_argument("--strong-score-negative-threshold", type=int, default=-60)
        parser.add_argument("--strong-score-probability-threshold", type=float, default=0.65)
        parser.add_argument("--update-dashboard", action="store_true")
        parser.add_argument("--dashboard-window-hours", type=int, default=24)
        parser.add_argument("--json-output", default="")

    def handle(self, *args, **options):
        if options["lookback_minutes"] < 1:
            raise CommandError("--lookback-minutes must be positive")
        if options["analysis_batch_size"] < 1:
            raise CommandError("--analysis-batch-size must be positive")
        if options["source_shard_count"] < 1:
            raise CommandError("--source-shard-count must be positive")
        if not 0 <= options["source_shard_index"] < options["source_shard_count"]:
            raise CommandError("--source-shard-index must be between 0 and --source-shard-count - 1")

        running_cutoff = timezone.now() - timedelta(hours=6)
        if (
            not options["dry_run"]
            and not options["force"]
            and MonitoringRun.objects.filter(status=MonitoringRun.STATUS_RUNNING, started_at__gte=running_cutoff).exists()
        ):
            raise CommandError("Another monitoring run is still marked as running. Use --force if this is stale.")

        since = timezone.now() - timedelta(minutes=options["lookback_minutes"])
        sources = self.load_sources(options)
        if not sources:
            raise CommandError("No active monitoring sources found. Run seed_monitoring_sources first.")

        if options["dry_run"]:
            run = None
        else:
            run = MonitoringRun.objects.create(
                lookback_minutes=options["lookback_minutes"],
                max_sources=options["max_sources"],
                max_posts_per_source=options["max_posts_per_source"],
                max_comments_per_post=options["max_comments_per_post"],
                sources_total=len(sources),
                dry_run=False,
                update_dashboard=options["update_dashboard"],
                meta={
                    "base_url": options["base_url"],
                    "storage_state": options["storage_state"],
                    "user_data_dir": options["user_data_dir"],
                    "include_unknown_dates": options["include_unknown_dates"],
                    "negative_threshold": options["negative_threshold"],
                    "nonnegative_threshold": options["nonnegative_threshold"],
                    "strong_score_negative_threshold": options["strong_score_negative_threshold"],
                    "strong_score_probability_threshold": options["strong_score_probability_threshold"],
                    "source_shard_count": options["source_shard_count"],
                    "source_shard_index": options["source_shard_index"],
                },
            )

        summary = {
            "dry_run": options["dry_run"],
            "since": since.isoformat(),
            "sources_total": len(sources),
            "sources_ok": 0,
            "sources_failed": 0,
            "posts_found": 0,
            "comments_found": 0,
            "items_created": 0,
            "items_existing": 0,
            "items_analyzed": 0,
            "errors": [],
            "sample_items": [],
            "dashboard": {},
            "source_shard_count": options["source_shard_count"],
            "source_shard_index": options["source_shard_index"],
        }

        try:
            scraped_by_source = []
            failed_sources = []
            with VkPlaywrightScraper(
                base_url=options["base_url"],
                headless=not options["headed"],
                storage_state=options["storage_state"],
                user_data_dir=options["user_data_dir"],
                timeout_ms=options["timeout_ms"],
                scroll_rounds=options["scroll_rounds"],
            ) as scraper:
                for source in sources:
                    try:
                        scraped = scraper.scrape_source(
                            screen_name=source.screen_name,
                            since=since,
                            max_posts=options["max_posts_per_source"],
                            max_comments_per_post=options["max_comments_per_post"],
                            include_unknown_dates=options["include_unknown_dates"],
                        )
                        summary["sources_ok"] += 1
                        summary["posts_found"] += sum(1 for item in scraped if item.item_type == "post")
                        summary["comments_found"] += sum(1 for item in scraped if item.item_type == "comment")
                        if options["dry_run"]:
                            summary["sample_items"].extend([self.serialize_scraped_item(source, item) for item in scraped[:10]])
                        else:
                            scraped_by_source.append((source, scraped))
                    except Exception as exc:
                        summary["sources_failed"] += 1
                        error = {"source": source.slug, "error": str(exc)}
                        summary["errors"].append(error)
                        if not options["dry_run"]:
                            failed_sources.append((source, str(exc)))
                        self.stderr.write(self.style.WARNING(f"{source.slug}: {exc}"))

            if not options["dry_run"]:
                for source, scraped in scraped_by_source:
                    created, existing = self.save_items(run, source, scraped)
                    summary["items_created"] += created
                    summary["items_existing"] += existing
                    source.last_success_at = timezone.now()
                    source.last_error = ""
                    source.parser_state = {
                        **(source.parser_state or {}),
                        "last_test_run_id": run.id,
                        "last_seen_items": len(scraped),
                    }
                    source.save(update_fields=["last_success_at", "last_error", "parser_state"])

                for source, error_text in failed_sources:
                    source.last_error = error_text
                    source.save(update_fields=["last_error"])

            if not options["dry_run"] and not options["skip_analysis"]:
                items = MonitoringItem.objects.filter(run=run, analyzed_at__isnull=True).order_by("id")
                summary["items_analyzed"] = self.analyze_items(items, options)

            if not options["dry_run"] and options["update_dashboard"]:
                summary["dashboard"] = refresh_dashboard_from_monitoring(
                    window_hours=options["dashboard_window_hours"]
                )

            if not options["dry_run"]:
                self.finish_run(run, summary)

        except Exception:
            if not options["dry_run"] and run:
                run.finish(MonitoringRun.STATUS_FAILED)
                run.error_log = summary["errors"]
                run.meta = {**(run.meta or {}), "summary": summary}
                run.save(update_fields=["status", "finished_at", "error_log", "meta"])
            raise

        if options["json_output"]:
            with open(options["json_output"], "w", encoding="utf-8") as handle:
                json.dump(summary, handle, ensure_ascii=False, indent=2)
        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))

    def load_sources(self, options):
        queryset = MonitoringSource.objects.filter(is_active=True).exclude(screen_name="")
        if options["source_slugs"]:
            queryset = queryset.filter(slug__in=options["source_slugs"])
        sources = list(queryset.select_related("area").order_by("display_order", "slug"))
        if not options["source_slugs"]:
            never_checked_at = timezone.now() - timedelta(days=36500)
            sources.sort(
                key=lambda source: (
                    source.last_success_at is not None,
                    source.last_success_at or never_checked_at,
                    source.display_order,
                    source.slug,
                )
            )
        shard_count = int(options.get("source_shard_count") or 1)
        shard_index = int(options.get("source_shard_index") or 0)
        if shard_count > 1:
            sources = [
                source
                for index, source in enumerate(sources)
                if index % shard_count == shard_index
            ]
        if options["max_sources"]:
            sources = sources[: options["max_sources"]]
        return sources

    def save_items(self, run, source, scraped_items):
        if not scraped_items:
            return 0, 0
        pending = []
        for item in scraped_items:
            source_hash = MonitoringItem.build_hash(
                source_url=item.source_url,
                external_id=item.external_id,
                text=item.text,
                post_text=item.post_text,
            )
            pending.append(
                MonitoringItem(
                    source=source,
                    run=run,
                    area=source.area,
                    item_type=item.item_type,
                    external_id=item.external_id,
                    source_hash=source_hash,
                    source_url=item.source_url,
                    post_external_id=item.post_external_id,
                    post_url=item.post_url,
                    text=item.text,
                    post_text=item.post_text,
                    author_name=item.author_name,
                    published_at=item.published_at,
                    published_at_raw=item.published_at_raw,
                    raw=item.raw,
                    cleaned_meta={"collector": "playwright_mvk_test"},
                )
            )
        hashes = [item.source_hash for item in pending]
        existing = set(MonitoringItem.objects.filter(source_hash__in=hashes).values_list("source_hash", flat=True))
        new_items = [item for item in pending if item.source_hash not in existing]
        with transaction.atomic():
            created = MonitoringItem.objects.bulk_create(new_items, ignore_conflicts=True, batch_size=500)
        return len(created), len(pending) - len(created)

    def analyze_items(self, queryset, options):
        try:
            analyzer = CascadeAnalyzer(
                taxonomy_checkpoint=options["taxonomy_checkpoint"],
                omsu_checkpoint=options["omsu_checkpoint"],
                device=options["analysis_device"],
                negative_threshold=options["negative_threshold"],
                nonnegative_threshold=options["nonnegative_threshold"],
                strong_score_negative_threshold=options["strong_score_negative_threshold"],
                strong_score_probability_threshold=options["strong_score_probability_threshold"],
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        return analyzer.analyze_items(queryset, batch_size=options["analysis_batch_size"])

    def finish_run(self, run, summary):
        if summary["sources_failed"] and summary["sources_ok"]:
            status = MonitoringRun.STATUS_PARTIAL
        elif summary["sources_failed"] and not summary["sources_ok"]:
            status = MonitoringRun.STATUS_FAILED
        else:
            status = MonitoringRun.STATUS_SUCCESS
        run.finish(status)
        run.sources_total = summary["sources_total"]
        run.sources_ok = summary["sources_ok"]
        run.sources_failed = summary["sources_failed"]
        run.posts_found = summary["posts_found"]
        run.comments_found = summary["comments_found"]
        run.items_created = summary["items_created"]
        run.items_existing = summary["items_existing"]
        run.items_analyzed = summary["items_analyzed"]
        run.error_log = summary["errors"]
        run.meta = {**(run.meta or {}), "summary": summary}
        run.save()

    @staticmethod
    def serialize_scraped_item(source, item):
        return {
            "source": source.slug,
            "area": source.area.slug if source.area else "",
            "item_type": item.item_type,
            "external_id": item.external_id,
            "source_url": item.source_url,
            "post_url": item.post_url,
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "published_at_raw": item.published_at_raw,
            "text": item.text[:500],
            "post_text": item.post_text[:500],
        }
