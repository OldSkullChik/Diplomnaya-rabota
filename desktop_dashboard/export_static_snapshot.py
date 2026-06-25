from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_API_BASE = "https://label.zhkh-razmetka.ru/api/v1/omsu"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "assets" / "static_dashboard_snapshot.json"
DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env.monitoring-test"


def api_key_from_env_file(path: Path) -> str:
    if not path.exists():
        return ""
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "OMSU_API_KEYS":
            return value.strip().strip("\"'").split(",", 1)[0].strip()
    return ""


def fetch_json(base_url: str, path: str, *, api_key: str, params: dict[str, str] | None = None) -> dict:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    if params:
        url = f"{url}?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "X-OMSU-API-Key": api_key,
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            payload = json.loads(response.read().decode(charset))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} while fetching {url}: {body}") from exc
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Failed to fetch {url}: {exc}") from exc

    if payload.get("status") == "error":
        raise SystemExit(f"API returned error for {url}: {payload}")
    return payload


def export_snapshot(base_url: str, api_key: str, output_path: Path, *, latest_limit: int = 1) -> dict:
    snapshot = fetch_json(base_url, "snapshot/", api_key=api_key)
    areas = snapshot.get("areas") or []
    comments_added = 0

    for area in areas:
        slug = area.get("slug")
        if not slug:
            continue
        payload = fetch_json(
            base_url,
            "latest-comment/",
            api_key=api_key,
            params={"area": slug, "limit": str(latest_limit)},
        )
        comments = payload.get("comments") or []
        comment = payload.get("comment") or (comments[0] if comments else None)
        if comment:
            area["latest_comment"] = comment
            comments_added += 1

    snapshot["api_version"] = f"static-from-api:{snapshot.get('api_version', 'v1')}"
    snapshot["static_exported_at"] = datetime.now(timezone.utc).isoformat()
    snapshot["static_source"] = base_url.rstrip("/")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "output": str(output_path),
        "areas": len(areas),
        "latest_comments_embedded": comments_added,
        "generated_at": snapshot.get("generated_at"),
        "served_at": snapshot.get("served_at"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export OMSU API snapshot into desktop static JSON.")
    parser.add_argument("--api-base", default=os.environ.get("OMSU_API_BASE", DEFAULT_API_BASE))
    parser.add_argument("--api-key", default=os.environ.get("OMSU_API_KEY", "").strip())
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--latest-limit", type=int, default=1)
    args = parser.parse_args()

    api_key = args.api_key or api_key_from_env_file(args.env_file)
    if not api_key:
        raise SystemExit("Set OMSU_API_KEY or pass --api-key. The key is not written to the output file.")

    result = export_snapshot(args.api_base, api_key, args.output, latest_limit=max(1, args.latest_limit))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
