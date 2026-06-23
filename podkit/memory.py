import json
from datetime import date, datetime, timedelta

from .paths import MEMORY

RETENTION_DAYS = 45
RECENT_DAYS = 10
MAX_RECENT_ITEMS = 40


def _file(theme_key: str):
    return MEMORY / f"{theme_key}.json"


def load(theme_key: str) -> list[dict]:
    path = _file(theme_key)
    if not path.exists():
        return []
    return json.loads(path.read_text())


def _save(theme_key: str, items: list[dict]):
    MEMORY.mkdir(parents=True, exist_ok=True)
    _file(theme_key).write_text(json.dumps(items, ensure_ascii=False, indent=2))


def record(theme_key: str, covered: list[dict]):
    today = date.today().isoformat()
    items = load(theme_key)
    for entry in covered:
        items.append(
            {
                "date": today,
                "headline": entry.get("headline", "").strip(),
                "summary": entry.get("summary", "").strip(),
            }
        )
    _save(theme_key, _prune(items))


def _prune(items: list[dict]) -> list[dict]:
    cutoff = (date.today() - timedelta(days=RETENTION_DAYS)).isoformat()
    return [item for item in items if item.get("date", "") >= cutoff]


def recent(theme_key: str) -> list[dict]:
    cutoff = (date.today() - timedelta(days=RECENT_DAYS)).isoformat()
    items = [item for item in load(theme_key) if item.get("date", "") >= cutoff]
    return items[-MAX_RECENT_ITEMS:]


def recent_brief(theme_key: str) -> str:
    items = recent(theme_key)
    if not items:
        return ""
    lines = [f"- ({item['date']}) {item['headline']}: {item['summary']}" for item in items]
    return "\n".join(lines)
