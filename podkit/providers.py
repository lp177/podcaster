import os

from . import env

LLM_PROVIDERS = [
    {"provider": "gemini", "model": "gemini-2.5-flash", "api_key_label": "GEMINI_API_KEY", "requires": "GEMINI_API_KEY"},
    {"provider": "openai", "model": "gpt-4o-mini", "api_key_label": "OPENAI_API_KEY", "requires": "OPENAI_API_KEY"},
    {"provider": "anthropic", "model": "claude-3-5-haiku-20241022", "api_key_label": "ANTHROPIC_API_KEY", "requires": "ANTHROPIC_API_KEY"},
    {"provider": "ollama", "model": "ollama/llama3", "api_key_label": "OLLAMA_API_KEY", "requires": "OLLAMA_API_BASE"},
]

TTS_PROVIDERS = [
    {"provider": "gemini", "tts_model": "gemini", "requires": "GEMINI_API_KEY"},
    {"provider": "openai", "tts_model": "openai", "requires": "OPENAI_API_KEY"},
    {"provider": "edge", "tts_model": "edge", "requires": None},
]


class NoProviderError(RuntimeError):
    def __init__(self, role: str, needed: list[str]):
        self.role = role
        self.needed = needed
        listing = ", ".join(needed)
        super().__init__(
            f"No usable {role} provider configured. Add one of these API keys "
            f"in Settings or in .env: {listing}."
        )


def _available(providers: list[dict]) -> list[dict]:
    return [p for p in providers if p["requires"] is None or env.has(p["requires"])]


def llm_candidates() -> list[dict]:
    candidates = _available(LLM_PROVIDERS)
    if not candidates:
        raise NoProviderError("language model", [p["requires"] for p in LLM_PROVIDERS])
    return candidates


def tts_candidates() -> list[dict]:
    return _available(TTS_PROVIDERS)


def prepare(candidate: dict):
    if candidate["provider"] == "ollama":
        os.environ.setdefault("OLLAMA_API_KEY", "ollama")
        base = env.get("OLLAMA_API_BASE")
        if base:
            os.environ["OLLAMA_API_BASE"] = base
