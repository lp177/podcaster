from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
DATA = ROOT / "data"
AUDIO = DATA / "audio"
TRANSCRIPTS = DATA / "transcripts"
EPISODES = DATA / "episodes"
MEMORY = DATA / "memory"
SHARES = DATA / "shares"
CUSTOM_THEMES_FILE = DATA / "custom_themes.json"
SCHEDULES_FILE = DATA / "schedules.json"
USERS_FILE = DATA / "users.json"
SESSIONS_FILE = DATA / "sessions.json"
WEB = ROOT / "web"


def ensure_dirs():
    for directory in (DATA, AUDIO, TRANSCRIPTS, EPISODES, MEMORY, SHARES):
        directory.mkdir(parents=True, exist_ok=True)


def audio_url(filename: str) -> str:
    return f"/media/audio/{filename}"
