LANGUAGES = {
    "fr": {
        "name": "French",
        "label": "Français",
        "edge": {"question": "fr-FR-HenriNeural", "answer": "fr-FR-DeniseNeural"},
        "openai": {"question": "echo", "answer": "shimmer"},
        "gemini": {"question": "fr-FR-Standard-B", "answer": "fr-FR-Standard-A"},
    },
    "en": {
        "name": "English",
        "label": "English",
        "edge": {"question": "en-US-EricNeural", "answer": "en-US-JennyNeural"},
        "openai": {"question": "echo", "answer": "shimmer"},
        "gemini": {"question": "en-US-Journey-D", "answer": "en-US-Journey-O"},
    },
    "es": {
        "name": "Spanish",
        "label": "Español",
        "edge": {"question": "es-ES-AlvaroNeural", "answer": "es-ES-ElviraNeural"},
        "openai": {"question": "echo", "answer": "shimmer"},
        "gemini": {"question": "es-ES-Standard-B", "answer": "es-ES-Standard-A"},
    },
    "de": {
        "name": "German",
        "label": "Deutsch",
        "edge": {"question": "de-DE-ConradNeural", "answer": "de-DE-KatjaNeural"},
        "openai": {"question": "echo", "answer": "shimmer"},
        "gemini": {"question": "de-DE-Standard-B", "answer": "de-DE-Standard-A"},
    },
    "it": {
        "name": "Italian",
        "label": "Italiano",
        "edge": {"question": "it-IT-DiegoNeural", "answer": "it-IT-ElsaNeural"},
        "openai": {"question": "echo", "answer": "shimmer"},
        "gemini": {"question": "it-IT-Standard-C", "answer": "it-IT-Standard-A"},
    },
}

DEFAULT_LANGUAGE = "fr"


def resolve(code: str | None) -> str:
    code = (code or DEFAULT_LANGUAGE).lower()
    return code if code in LANGUAGES else DEFAULT_LANGUAGE


def name_of(code: str) -> str:
    return LANGUAGES[resolve(code)]["name"]


def voices_for(code: str, tts_model: str) -> dict | None:
    lang = LANGUAGES[resolve(code)]
    return lang.get(tts_model)


def options() -> list[dict]:
    return [{"code": code, "label": data["label"], "name": data["name"]} for code, data in LANGUAGES.items()]
