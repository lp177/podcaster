import argparse
import sys

from .duration import DEFAULT_MINUTES
from .generator import generate_episode
from .providers import NoProviderError


def _stdout_log(message: str):
    print(f"  {message}", flush=True)


def run_theme(theme, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"Generate the '{theme.title}' podcast.")
    parser.add_argument("--lang", "-l", default=theme.language, help="Language code (fr, en, …)")
    parser.add_argument("--minutes", "-m", type=int, default=theme.minutes, help="Target length in minutes")
    args = parser.parse_args(argv)

    print(f"▶ {theme.icon} {theme.title}")
    try:
        meta = generate_episode(theme, language=args.lang, minutes=args.minutes, on_log=_stdout_log)
    except NoProviderError as error:
        print(f"✖ {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"✖ Generation failed: {error}", file=sys.stderr)
        return 1
    print(f"✓ Audio: data/audio/{meta['audio_file']}")
    return 0
