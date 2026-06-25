from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from annotation.maintenance import (
    DEFAULT_MESSAGE,
    DEFAULT_TITLE,
    disable_maintenance,
    enable_maintenance,
    read_maintenance_state,
)


def parse_duration(value):
    if not value:
        return None

    raw = value.strip().lower()
    units = {
        "seconds": 1,
        "second": 1,
        "sec": 1,
        "s": 1,
        "minutes": 60,
        "minute": 60,
        "min": 60,
        "m": 60,
        "hours": 3600,
        "hour": 3600,
        "hr": 3600,
        "h": 3600,
        "days": 86400,
        "day": 86400,
        "d": 86400,
    }
    number = raw
    multiplier = 1
    for suffix, seconds in units.items():
        if raw.endswith(suffix):
            number = raw[: -len(suffix)].strip()
            multiplier = seconds
            break

    try:
        amount = float(number)
    except ValueError as exc:
        raise CommandError("Duration must look like 20m, 1h, or 900s.") from exc

    if amount <= 0:
        raise CommandError("Duration must be greater than zero.")

    return timezone.now() + timedelta(seconds=int(amount * multiplier))


class Command(BaseCommand):
    help = "Enable, disable, or inspect the public maintenance mode."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["on", "off", "status"])
        parser.add_argument("--title", default=DEFAULT_TITLE)
        parser.add_argument("--message", default=DEFAULT_MESSAGE)
        parser.add_argument("--eta", default="", help="Optional visible estimate, for example: 15 minutes.")
        parser.add_argument("--duration", default="", help="Optional countdown duration, for example: 20m, 1h, or 900s.")

    def handle(self, *args, **options):
        action = options["action"]
        if action == "on":
            ends_at = parse_duration(options["duration"])
            eta = options["eta"]
            if ends_at and not eta:
                eta = options["duration"]
            state = enable_maintenance(
                title=options["title"],
                message=options["message"],
                eta=eta,
                ends_at=ends_at.isoformat() if ends_at else "",
            )
            self.stdout.write(self.style.WARNING(f"Maintenance mode enabled: {state['title']}"))
            if state["ends_at"]:
                self.stdout.write(f"Ends at: {state['ends_at']}")
            return
        if action == "off":
            disable_maintenance()
            self.stdout.write(self.style.SUCCESS("Maintenance mode disabled."))
            return
        if action == "status":
            state = read_maintenance_state()
            status = "enabled" if state["enabled"] else "disabled"
            self.stdout.write(f"Maintenance mode: {status}")
            if state["enabled"]:
                self.stdout.write(f"Title: {state['title']}")
                self.stdout.write(f"Message: {state['message']}")
                if state["eta"]:
                    self.stdout.write(f"ETA: {state['eta']}")
                if state["ends_at"]:
                    self.stdout.write(f"Ends at: {state['ends_at']}")
                if state["updated_at"]:
                    self.stdout.write(f"Updated at: {state['updated_at']}")
            return
        raise CommandError(f"Unknown action: {action}")
