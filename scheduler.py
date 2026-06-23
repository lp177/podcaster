#!/usr/bin/env python
import sys
import time
from datetime import datetime

from podkit import notify, schedule
from podkit.generator import generate_episode
from podkit.themes import get_theme


def _log(message: str):
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {message}", flush=True)


def tick() -> int:
    due = schedule.due_now()
    if not due:
        _log("tick: nothing due")
        return 0
    _log(f"tick: {len(due)} job(s) due")
    for entry in due:
        try:
            theme = get_theme(entry["theme_key"])
            _log(f"running {entry['theme_key']} ({entry['language']}, {entry['minutes']}min)")
            meta = generate_episode(theme, entry["language"], entry["minutes"], on_log=lambda m: _log(f"  {m}"))
            schedule.mark_ran(entry["id"])
            notify.episode_published(entry["theme_key"], meta, block=True)
            _log(f"done {meta['id']}")
        except Exception as error:
            _log(f"ERROR on {entry['theme_key']}: {error}")
    return 0


def install_cron() -> int:
    line = schedule.install_cron()
    _log(f"installed crontab line:\n{line}")
    return 0


def main(argv: list[str]) -> int:
    command = argv[0] if argv else "tick"
    if command == "tick":
        return tick()
    if command == "loop":
        interval = int(argv[1]) if len(argv) > 1 else 3600
        _log(f"scheduler loop started (every {interval}s) — for containers without cron")
        while True:
            tick()
            time.sleep(interval)
    if command == "install-cron":
        return install_cron()
    if command == "uninstall-cron":
        schedule.uninstall_cron()
        _log("removed scheduler crontab line")
        return 0
    if command == "cron-line":
        print(schedule.cron_line())
        return 0
    if command == "list":
        for entry in schedule.load_schedules():
            print(f"  {entry['id']}  {entry['theme_key']:22} {schedule.describe(entry)}  "
                  f"[{entry['language']}, {entry['minutes']}min]"
                  f"{'' if entry.get('enabled', True) else '  (disabled)'}")
        return 0
    print(f"Usage: scheduler.py [tick|loop [seconds]|install-cron|uninstall-cron|cron-line|list]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
