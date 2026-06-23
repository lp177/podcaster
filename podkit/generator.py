from datetime import date, datetime
from pathlib import Path

from podcastfy.client import generate_podcast

from . import catalog, env, languages, memory, research
from .duration import plan_for
from .paths import AUDIO, TRANSCRIPTS, ensure_dirs
from .providers import NoProviderError, llm_candidates, prepare, tts_candidates


def _noop(_message: str):
    pass


def _base_config(theme, language: str, plan: dict) -> dict:
    return {
        "output_language": languages.name_of(language),
        "podcast_name": theme.title,
        "podcast_tagline": theme.summary or "Daily briefing",
        "creativity": 0.7,
        "conversation_style": ["informative", "engaging", "concise"],
        "roles_person1": "news anchor giving the briefing",
        "roles_person2": "sharp analyst asking clarifying questions",
        "dialogue_structure": ["Headlines", "Analysis", "What to watch next"],
        "user_instructions": (
            f"Daily news briefing of about {plan['minutes']} minutes "
            f"(~{plan['target_words']} words). Be factual and specific with numbers, "
            f"names and figures. Group related stories. Speak entirely in "
            f"{languages.name_of(language)}."
        ),
        "text_to_speech": {
            "output_directories": {"transcripts": str(TRANSCRIPTS), "audio": str(AUDIO)},
            "audio_format": "mp3",
        },
    }


def _tts_config(base: dict, candidate: dict, language: str) -> dict:
    config = {**base, "text_to_speech": dict(base["text_to_speech"])}
    config["text_to_speech"]["default_tts_model"] = candidate["tts_model"]
    voices = languages.voices_for(language, candidate["tts_model"])
    if voices:
        config["text_to_speech"][candidate["tts_model"]] = {"default_voices": voices}
    return config


def _write_transcript(digest: str, base: dict, plan: dict, log) -> tuple[str, str]:
    errors = []
    for candidate in llm_candidates():
        prepare(candidate)
        log(f"Scripting with {candidate['provider']} ({candidate['model']})…")
        try:
            path = generate_podcast(
                text=digest,
                transcript_only=True,
                longform=plan["longform"],
                llm_model_name=candidate["model"],
                api_key_label=candidate["api_key_label"],
                conversation_config=base,
            )
            return path, candidate["provider"]
        except Exception as error:
            errors.append(f"{candidate['provider']}: {error}")
            log(f"  {candidate['provider']} failed, trying next…")
    raise RuntimeError("All language model providers failed:\n" + "\n".join(errors))


def _synthesize(transcript_path: str, base: dict, language: str, log) -> tuple[str, str]:
    candidates = tts_candidates()
    errors = []
    for candidate in candidates:
        log(f"Voicing with {candidate['provider']}…")
        try:
            audio_path = generate_podcast(
                transcript_file=transcript_path,
                tts_model=candidate["tts_model"],
                conversation_config=_tts_config(base, candidate, language),
            )
            return audio_path, candidate["provider"]
        except Exception as error:
            errors.append(f"{candidate['provider']}: {error}")
            log(f"  {candidate['provider']} failed, trying next…")
    raise RuntimeError("All text-to-speech providers failed:\n" + "\n".join(errors))


def _summary_of(result: dict) -> str:
    if result["items"]:
        return " · ".join(item["headline"] for item in result["items"][:4])
    return result["digest"][:240].strip()


def generate_episode(theme, language: str | None = None, minutes: int | None = None, on_log=None) -> dict:
    ensure_dirs()
    env.load_env()
    log = on_log or _noop
    language = languages.resolve(language or theme.language)
    plan = plan_for(minutes or theme.minutes)

    log("Researching fresh stories…")
    result = research.gather(theme, language, memory.recent_brief(theme.key))
    if not result["digest"].strip():
        raise RuntimeError("Research returned no content.")

    base = _base_config(theme, language, plan)
    transcript_path, llm_provider = _write_transcript(result["digest"], base, plan, log)
    audio_path, tts_provider = _synthesize(transcript_path, base, language, log)

    meta = {
        "id": catalog.new_id(),
        "theme_key": theme.key,
        "theme_title": theme.title,
        "icon": theme.icon,
        "accent": theme.accent,
        "date": date.today().isoformat(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "language": language,
        "language_label": languages.LANGUAGES[language]["label"],
        "minutes": plan["minutes"],
        "title": f"{theme.title} — {date.today().isoformat()}",
        "headline": result["items"][0]["headline"] if result["items"] else theme.title,
        "summary": _summary_of(result),
        "sources": result["sources"],
        "audio_file": Path(audio_path).name,
        "transcript_file": Path(transcript_path).name,
        "llm_provider": llm_provider,
        "tts_provider": tts_provider,
    }
    catalog.save_episode(meta)
    catalog.enforce_retention(theme.key)
    memory.record(theme.key, result["items"])
    log(f"Done: {meta['title']} ({tts_provider} voice).")
    return meta


def regenerate_language(episode_id: str, language: str, on_log=None) -> dict:
    log = on_log or _noop
    source = catalog.get_episode(episode_id)
    if not source:
        raise KeyError("Episode not found")
    from .themes import get_theme

    theme = get_theme(source["theme_key"])
    log(f"Regenerating in {languages.name_of(language)}…")
    transcript = (TRANSCRIPTS / source["transcript_file"]).read_text()
    language = languages.resolve(language)
    plan = plan_for(source.get("minutes", theme.minutes))
    base = _base_config(theme, language, plan)

    translated = _translate(transcript, language, log)
    tmp = TRANSCRIPTS / f"translated_{catalog.new_id()}.txt"
    tmp.write_text(translated)
    audio_path, tts_provider = _synthesize(str(tmp), base, language, log)

    meta = {
        **source,
        "id": catalog.new_id(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "language": language,
        "language_label": languages.LANGUAGES[language]["label"],
        "title": f"{theme.title} — {source['date']} ({languages.LANGUAGES[language]['label']})",
        "audio_file": Path(audio_path).name,
        "transcript_file": tmp.name,
        "tts_provider": tts_provider,
        "variant_of": episode_id,
        "share_key": None,
    }
    catalog.save_episode(meta)
    log("Translation episode ready.")
    return meta


def _translate(transcript: str, language: str, log) -> str:
    from langchain_community.chat_models import ChatLiteLLM
    from langchain_google_genai import ChatGoogleGenerativeAI

    prompt = (
        f"Translate this podcast transcript into {languages.name_of(language)}. "
        f"Keep the exact same structure and any <Person1>/<Person2> speaker tags. "
        f"Translate only the spoken text.\n\n{transcript}"
    )
    for candidate in llm_candidates():
        prepare(candidate)
        try:
            if candidate["provider"] == "gemini":
                llm = ChatGoogleGenerativeAI(api_key=env.get("GEMINI_API_KEY"), model=candidate["model"])
            else:
                llm = ChatLiteLLM(model=candidate["model"], api_key=env.get(candidate["api_key_label"]) or "x")
            return llm.invoke(prompt).content
        except Exception:
            log(f"  {candidate['provider']} translation failed, trying next…")
    raise RuntimeError("Translation failed on all providers.")
