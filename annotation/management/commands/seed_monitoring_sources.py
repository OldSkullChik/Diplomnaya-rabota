import json
from pathlib import Path
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError

from annotation.models import MonitoringSource, OmsuArea
from annotation.monitoring.text import screen_name_from_url


DEFAULT_INPUT = "desktop_dashboard/assets/monitoring_groups.json"


def source_slug(area_slug: str, group_url: str) -> str:
    screen_name = screen_name_from_url(group_url)
    return f"{area_slug}-{screen_name}".lower().replace("_", "-").replace(".", "-")[:120]


class Command(BaseCommand):
    help = "Seed test monitoring VK sources from the local monitoring_groups.json asset."

    def add_arguments(self, parser):
        parser.add_argument("--input", default=DEFAULT_INPUT)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit-areas", type=int, default=0)
        parser.add_argument("--limit-groups", type=int, default=0)
        parser.add_argument("--deactivate-missing", action="store_true")

    def handle(self, *args, **options):
        path = Path(options["input"])
        if not path.exists():
            raise CommandError(f"Input file not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        objects = payload.get("objects", [])
        if options["limit_areas"]:
            objects = objects[: options["limit_areas"]]

        seen_slugs = set()
        areas_seen = 0
        sources_seen = 0
        sources_changed = 0

        for area_index, obj in enumerate(objects, start=1):
            area_slug = obj.get("slug", "").strip()
            area_name = obj.get("displayName", "").strip() or area_slug
            if not area_slug:
                continue
            areas_seen += 1
            if options["dry_run"]:
                area = None
            else:
                area, _created = OmsuArea.objects.update_or_create(
                    slug=area_slug,
                    defaults={
                        "name": area_name,
                        "region": "Нижегородская область",
                        "display_order": area_index,
                        "is_active": True,
                    },
                )

            group_urls = []
            for group_url in obj.get("groups", []):
                group_url = str(group_url or "").strip()
                if not group_url:
                    continue
                parsed = urlparse(group_url)
                if not parsed.scheme:
                    group_url = "https://vk.com/" + group_url.strip("/")
                if group_url not in group_urls:
                    group_urls.append(group_url)
            if options["limit_groups"]:
                group_urls = group_urls[: options["limit_groups"]]

            for group_index, group_url in enumerate(group_urls, start=1):
                slug = source_slug(area_slug, group_url)
                seen_slugs.add(slug)
                sources_seen += 1
                screen_name = screen_name_from_url(group_url)
                defaults = {
                    "area": area,
                    "title": f"{area_name}: {screen_name}",
                    "url": group_url,
                    "screen_name": screen_name,
                    "is_active": True,
                    "display_order": area_index * 1000 + group_index,
                }
                if options["dry_run"]:
                    self.stdout.write(f"would seed {slug}: {group_url}")
                    sources_changed += 1
                    continue
                _source, created = MonitoringSource.objects.update_or_create(slug=slug, defaults=defaults)
                sources_changed += int(created)

        deactivated = 0
        if options["deactivate_missing"] and not options["dry_run"]:
            queryset = MonitoringSource.objects.exclude(slug__in=seen_slugs).filter(kind=MonitoringSource.SOURCE_KIND_VK_GROUP)
            deactivated = queryset.update(is_active=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"areas={areas_seen}; sources={sources_seen}; changed={sources_changed}; deactivated={deactivated}"
            )
        )
