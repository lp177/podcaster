#!/usr/bin/env python
import sys

from podkit.cli import run_theme
from podkit.themes import all_themes, get_theme


def _list():
    print("Available themes:")
    for theme in all_themes().values():
        tag = "" if theme.builtin else "  (custom)"
        print(f"  {theme.key:22} {theme.icon} {theme.title}{tag}")


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("--list", "-ls", "list"):
        _list()
        return 0
    key, rest = argv[0], argv[1:]
    try:
        theme = get_theme(key)
    except KeyError:
        print(f"Unknown theme: {key}\n", file=sys.stderr)
        _list()
        return 2
    return run_theme(theme, rest)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
