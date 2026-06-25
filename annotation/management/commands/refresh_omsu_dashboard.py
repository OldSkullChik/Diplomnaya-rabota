import json

from django.core.management.base import BaseCommand

from annotation.monitoring.dashboard import refresh_dashboard_from_monitoring


class Command(BaseCommand):
    help = "Refresh OMSU dashboard snapshots from analyzed monitoring items."

    def add_arguments(self, parser):
        parser.add_argument("--window-hours", type=int, default=24)
        parser.add_argument("--latest-per-area", type=int, default=3)
        parser.add_argument("--json-output", default="")

    def handle(self, *args, **options):
        summary = refresh_dashboard_from_monitoring(
            window_hours=options["window_hours"],
            latest_per_area=options["latest_per_area"],
        )
        if options["json_output"]:
            with open(options["json_output"], "w", encoding="utf-8") as handle:
                json.dump(summary, handle, ensure_ascii=False, indent=2)
        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))
