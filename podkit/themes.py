import importlib
import json
import pkgutil
from dataclasses import dataclass, asdict, field

from . import languages
from .duration import DEFAULT_MINUTES, clamp_minutes
from .paths import CUSTOM_THEMES_FILE


@dataclass
class Theme:
    key: str
    title: str
    icon: str = "🎙️"
    accent: str = "#6366f1"
    summary: str = ""
    research_brief: str = ""
    language: str = languages.DEFAULT_LANGUAGE
    minutes: int = DEFAULT_MINUTES
    rss: list = field(default_factory=list)
    builtin: bool = True

    def normalized(self) -> "Theme":
        self.language = languages.resolve(self.language)
        self.minutes = clamp_minutes(self.minutes)
        return self

    def to_dict(self) -> dict:
        return asdict(self)


def _builtin_themes() -> dict[str, Theme]:
    import themes as package

    found: dict[str, Theme] = {}
    for module in pkgutil.iter_modules(package.__path__):
        loaded = importlib.import_module(f"{package.__name__}.{module.name}")
        theme = getattr(loaded, "THEME", None)
        if isinstance(theme, Theme):
            theme.builtin = True
            found[theme.key] = theme.normalized()
    return found


def _custom_themes() -> dict[str, Theme]:
    if not CUSTOM_THEMES_FILE.exists():
        return {}
    raw = json.loads(CUSTOM_THEMES_FILE.read_text())
    return {item["key"]: Theme(**{**item, "builtin": False}).normalized() for item in raw}


def all_themes() -> dict[str, Theme]:
    merged = _builtin_themes()
    merged.update(_custom_themes())
    return merged


def get_theme(key: str) -> Theme:
    theme = all_themes().get(key)
    if theme is None:
        raise KeyError(f"Unknown theme: {key}")
    return theme


def save_custom_theme(theme: Theme):
    theme.builtin = False
    themes = _custom_themes()
    themes[theme.key] = theme.normalized()
    _write_custom(themes)


def delete_custom_theme(key: str):
    themes = _custom_themes()
    if key in themes:
        del themes[key]
        _write_custom(themes)


def _write_custom(themes: dict[str, Theme]):
    CUSTOM_THEMES_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = [theme.to_dict() for theme in themes.values()]
    CUSTOM_THEMES_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def slugify(text: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in text)
    parts = [part for part in cleaned.split("-") if part]
    return "-".join(parts)[:48] or "theme"
