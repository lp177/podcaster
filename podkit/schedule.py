import json
import shutil
import subprocess
import sys
from datetime import datetime

from . import languages
from .duration import clamp_minutes
from .paths import ROOT, SCHEDULES_FILE

CRON_MARKER = "# podkit-scheduler"
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def load_schedules() -> list[dict]:
    if not SCHEDULES_FILE.exists():
        return []
    return json.loads(SCHEDULES_FILE.read_text())


def save_schedules(schedules: list[dict]):
    SCHEDULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    SCHEDULES_FILE.write_text(json.dumps(schedules, ensure_ascii=False, indent=2))


def add_schedule(theme_key: str, cadence: str, hour: int, weekday: int = 0,
                 language: str | None = None, minutes: int = 10) -> dict:
    import secrets

    entry = {
        "id": secrets.token_hex(6),
        "theme_key": theme_key,
        "cadence": "weekly" if cadence == "weekly" else "daily",
        "hour": max(0, min(23, int(hour))),
        "weekday": max(0, min(6, int(weekday))),
        "language": languages.resolve(language),
        "minutes": clamp_minutes(minutes),
        "enabled": True,
        "last_run": None,
    }
    schedules = load_schedules()
    schedules.append(entry)
    save_schedules(schedules)
    return entry


def delete_schedule(schedule_id: str):
    save_schedules([s for s in load_schedules() if s["id"] != schedule_id])


def set_enabled(schedule_id: str, enabled: bool):
    schedules = load_schedules()
    for entry in schedules:
        if entry["id"] == schedule_id:
            entry["enabled"] = enabled
    save_schedules(schedules)


def _is_due(entry: dict, now: datetime) -> bool:
    if not entry.get("enabled", True):
        return False
    if now.hour != entry["hour"]:
        return False
    if entry["cadence"] == "weekly" and now.weekday() != entry["weekday"]:
        return False
    last_run = entry.get("last_run")
    if last_run and last_run[:10] == now.date().isoformat():
        return False
    return True


def due_now(now: datetime | None = None) -> list[dict]:
    now = now or datetime.now()
    return [entry for entry in load_schedules() if _is_due(entry, now)]


def mark_ran(schedule_id: str, now: datetime | None = None):
    now = now or datetime.now()
    schedules = load_schedules()
    for entry in schedules:
        if entry["id"] == schedule_id:
            entry["last_run"] = now.isoformat(timespec="seconds")
    save_schedules(schedules)


def describe(entry: dict) -> str:
    when = f"{entry['hour']:02d}:00"
    if entry["cadence"] == "weekly":
        return f"Weekly · {WEEKDAYS[entry['weekday']]} {when}"
    return f"Daily · {when}"


def cron_command() -> str:
    return f"cd {ROOT} && {sys.executable} {ROOT / 'scheduler.py'} tick >> {ROOT / 'data' / 'scheduler.log'} 2>&1"


def cron_line() -> str:
    return f"0 * * * * {cron_command()} {CRON_MARKER}"


def crontab_available() -> bool:
    """Host cron is absent in containers (and some minimal hosts); detect it so
    status checks degrade gracefully instead of raising FileNotFoundError."""
    return shutil.which("crontab") is not None


_NO_CRONTAB = (
    "crontab is not available here — schedule with the bundled scheduler instead "
    "(run `python scheduler.py loop`, or the `scheduler` service in docker-compose)."
)


def _current_crontab() -> str:
    if not crontab_available():
        return ""
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    except OSError:
        return ""
    return result.stdout if result.returncode == 0 else ""


def cron_installed() -> bool:
    return CRON_MARKER in _current_crontab()


def install_cron() -> str:
    if not crontab_available():
        raise RuntimeError(_NO_CRONTAB)
    lines = [line for line in _current_crontab().splitlines() if CRON_MARKER not in line]
    lines.append(cron_line())
    payload = "\n".join(lines) + "\n"
    subprocess.run(["crontab", "-"], input=payload, text=True, check=True)
    return cron_line()


def uninstall_cron():
    if not crontab_available():
        return
    lines = [line for line in _current_crontab().splitlines() if CRON_MARKER not in line]
    payload = ("\n".join(lines) + "\n") if lines else ""
    subprocess.run(["crontab", "-"], input=payload, text=True, check=True)
