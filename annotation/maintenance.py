import json
from pathlib import Path

from django.conf import settings
from django.utils import timezone


DEFAULT_TITLE = "Сервис временно на обслуживании"
DEFAULT_MESSAGE = "Идут технические работы. Скоро разметчик снова будет доступен."


def maintenance_file():
    return Path(settings.MAINTENANCE_MODE_FILE)


def default_state():
    return {
        "enabled": False,
        "title": DEFAULT_TITLE,
        "message": DEFAULT_MESSAGE,
        "eta": "",
        "ends_at": "",
        "updated_at": "",
    }


def read_maintenance_state():
    path = maintenance_file()
    if not path.exists():
        return default_state()
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        payload = {}
    state = default_state()
    state.update(
        {
            "enabled": bool(payload.get("enabled", True)),
            "title": payload.get("title") or DEFAULT_TITLE,
            "message": payload.get("message") or DEFAULT_MESSAGE,
            "eta": payload.get("eta") or "",
            "ends_at": payload.get("ends_at") or "",
            "updated_at": payload.get("updated_at") or "",
        }
    )
    return state


def enable_maintenance(title=DEFAULT_TITLE, message=DEFAULT_MESSAGE, eta="", ends_at=""):
    path = maintenance_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "enabled": True,
        "title": title,
        "message": message,
        "eta": eta,
        "ends_at": ends_at,
        "updated_at": timezone.now().isoformat(),
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def disable_maintenance():
    path = maintenance_file()
    if path.exists():
        path.unlink()
