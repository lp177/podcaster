import os
from dataclasses import dataclass

from dotenv import load_dotenv

from .paths import ENV_FILE


@dataclass(frozen=True)
class KeySpec:
    name: str
    label: str
    role: str
    hint: str


SUPPORTED_KEYS = [
    KeySpec("GEMINI_API_KEY", "Google Gemini", "llm+tts", "Default provider. Powers news research, scripting and TTS."),
    KeySpec("OPENAI_API_KEY", "OpenAI", "llm+tts", "Fallback for scripting and TTS (gpt / tts-1-hd)."),
    KeySpec("ANTHROPIC_API_KEY", "Anthropic Claude", "llm", "Fallback for scripting."),
    KeySpec("OLLAMA_API_BASE", "Ollama / OpenAI-compatible", "llm", "Local or generic endpoint, e.g. http://localhost:11434."),
    KeySpec("ELEVENLABS_API_KEY", "ElevenLabs", "tts", "Optional premium voices."),
]

_loaded = False


def load_env():
    global _loaded
    if not _loaded and ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=False)
    _loaded = True


def get(name: str) -> str | None:
    load_env()
    value = os.environ.get(name)
    return value or None


def has(name: str) -> bool:
    return bool(get(name))


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "•" * len(value)
    return f"{value[:4]}…{value[-4:]}"


def key_status() -> list[dict]:
    return [
        {
            "name": spec.name,
            "label": spec.label,
            "role": spec.role,
            "hint": spec.hint,
            "configured": has(spec.name),
            "preview": _mask(get(spec.name)) if has(spec.name) else "",
        }
        for spec in SUPPORTED_KEYS
    ]


def supported_key_names() -> list[str]:
    return [spec.name for spec in SUPPORTED_KEYS]


def update_keys(values: dict[str, str]):
    load_env()
    existing = _read_env_file()
    for name, value in values.items():
        value = (value or "").strip()
        if value:
            existing[name] = value
            os.environ[name] = value
        else:
            existing.pop(name, None)
            os.environ.pop(name, None)
    _write_env_file(existing)


def _read_env_file() -> dict[str, str]:
    result: dict[str, str] = {}
    if not ENV_FILE.exists():
        return result
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        result[name.strip()] = value.strip()
    return result


def _write_env_file(values: dict[str, str]):
    lines = [f"{name}={value}" for name, value in values.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n")
