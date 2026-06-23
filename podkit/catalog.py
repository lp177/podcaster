import json
import secrets
import uuid
from datetime import date, datetime, timedelta

from .paths import AUDIO, EPISODES, SHARES, TRANSCRIPTS, audio_url

HISTORY_DAYS = 7


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def _file(episode_id: str):
    return EPISODES / f"{episode_id}.json"


def save_episode(meta: dict) -> dict:
    EPISODES.mkdir(parents=True, exist_ok=True)
    _file(meta["id"]).write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def get_episode(episode_id: str) -> dict | None:
    path = _file(episode_id)
    return json.loads(path.read_text()) if path.exists() else None


def all_episodes() -> list[dict]:
    items = [json.loads(path.read_text()) for path in EPISODES.glob("*.json")]
    return sorted(items, key=lambda e: e.get("created_at", ""), reverse=True)


def list_episodes(theme_key: str | None = None, days: int | None = None) -> list[dict]:
    episodes = all_episodes()
    if theme_key:
        episodes = [e for e in episodes if e.get("theme_key") == theme_key]
    if days is not None:
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        episodes = [e for e in episodes if e.get("date", "") >= cutoff]
    return episodes


def today_episodes() -> list[dict]:
    today = date.today().isoformat()
    return [e for e in all_episodes() if e.get("date") == today]


def latest_per_theme() -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for episode in all_episodes():
        latest.setdefault(episode["theme_key"], episode)
    return latest


def enforce_retention(theme_key: str, days: int = HISTORY_DAYS):
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    for episode in list_episodes(theme_key=theme_key):
        if episode.get("date", "") < cutoff:
            delete_episode(episode["id"])


def delete_episode(episode_id: str):
    meta = get_episode(episode_id)
    if not meta:
        return
    _unlink(AUDIO / (meta.get("audio_file") or ""))
    _unlink(TRANSCRIPTS / (meta.get("transcript_file") or ""))
    if meta.get("share_key"):
        _unlink(SHARES / f"{meta['share_key']}.json")
    _unlink(_file(episode_id))


def mint_share(episode_id: str) -> str | None:
    meta = get_episode(episode_id)
    if not meta:
        return None
    if meta.get("share_key"):
        return meta["share_key"]
    key = secrets.token_urlsafe(18)
    SHARES.mkdir(parents=True, exist_ok=True)
    (SHARES / f"{key}.json").write_text(json.dumps({"episode": episode_id}))
    meta["share_key"] = key
    save_episode(meta)
    return key


def resolve_share(key: str) -> dict | None:
    pointer = SHARES / f"{key}.json"
    if not pointer.exists():
        return None
    episode_id = json.loads(pointer.read_text()).get("episode")
    return get_episode(episode_id)


def to_view(meta: dict) -> dict:
    view = dict(meta)
    view["audio_url"] = audio_url(meta["audio_file"]) if meta.get("audio_file") else None
    return view


def _unlink(path):
    try:
        if path and path.exists():
            path.unlink()
    except OSError:
        pass
