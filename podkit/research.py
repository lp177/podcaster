import re
import time
from datetime import date

from . import env, languages

DIGEST_RE = re.compile(r"<DIGEST>(.*?)</DIGEST>", re.DOTALL)
COVERED_RE = re.compile(r"<COVERED>(.*?)</COVERED>", re.DOTALL)


def gather(theme, language: str, memory_brief: str) -> dict:
    language = languages.resolve(language)
    attempts = []
    if env.has("GEMINI_API_KEY"):
        attempts.append(lambda: _gemini_research(theme, language, memory_brief))
    if getattr(theme, "rss", None):
        attempts.append(lambda: _rss_research(theme, language, memory_brief))
    attempts.append(lambda: _plain_research(theme, language, memory_brief))

    errors = []
    for attempt in attempts:
        try:
            result = attempt()
            if result["digest"].strip():
                return result
        except Exception as error:  # noqa: BLE001
            errors.append(str(error))
    raise RuntimeError("Research failed on every source: " + " | ".join(errors))


def _call_with_retry(func, tries: int = 3):
    last = None
    for attempt in range(tries):
        try:
            return func()
        except Exception as error:  # noqa: BLE001
            last = error
            transient = any(code in str(error) for code in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED"))
            if not transient or attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise last


def _build_prompt(theme, language: str, memory_brief: str) -> str:
    today = date.today().isoformat()
    avoid = (
        f"\nAlready covered in previous episodes — do NOT repeat these unless there is "
        f"genuinely NEW progress, and if so report only what changed:\n{memory_brief}\n"
        if memory_brief
        else ""
    )
    return f"""You are a news researcher preparing a podcast brief for {today}.
Topic focus:
{theme.research_brief}

Search the web for the freshest developments from the last 48 hours.
Prioritise concrete facts: figures, prices, percentages, named companies, decisions, dates.
{avoid}
Write the brief in {languages.name_of(language)}.

Return EXACTLY this structure:
<DIGEST>
A dense, well-structured briefing (sections with short paragraphs) a host can read out loud.
</DIGEST>
<COVERED>
One line per distinct story, format: headline :: one sentence summary
</COVERED>"""


def _gemini_research(theme, language: str, memory_brief: str) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=env.get("GEMINI_API_KEY"))
    config = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
    prompt = _build_prompt(theme, language, memory_brief)
    response = _call_with_retry(
        lambda: client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=config)
    )
    parsed = _parse(response.text)
    parsed["sources"] = _extract_sources(response)
    return parsed


def _rss_research(theme, language: str, memory_brief: str) -> dict:
    import feedparser

    headlines = []
    sources = []
    for url in theme.rss:
        feed = feedparser.parse(url)
        for entry in feed.entries[:8]:
            headlines.append(f"{entry.get('title', '')} — {entry.get('summary', '')[:240]}")
            if entry.get("link"):
                sources.append({"title": entry.get("title", ""), "uri": entry["link"]})
    raw = "\n".join(headlines)
    digest = _summarize_with_llm(theme, language, memory_brief, raw)
    return {"digest": digest, "items": _items_from_lines(headlines), "sources": sources}


def _plain_research(theme, language: str, memory_brief: str) -> dict:
    digest = _summarize_with_llm(theme, language, memory_brief, theme.research_brief)
    return {"digest": digest, "items": [], "sources": []}


def _summarize_with_llm(theme, language: str, memory_brief: str, material: str) -> str:
    from .providers import llm_candidates, prepare
    from langchain_community.chat_models import ChatLiteLLM
    from langchain_google_genai import ChatGoogleGenerativeAI

    prompt = _build_prompt(theme, language, memory_brief) + f"\n\nSource material:\n{material}"
    for candidate in llm_candidates():
        prepare(candidate)
        try:
            if candidate["provider"] == "gemini":
                llm = ChatGoogleGenerativeAI(api_key=env.get("GEMINI_API_KEY"), model=candidate["model"])
            else:
                llm = ChatLiteLLM(model=candidate["model"], api_key=env.get(candidate["api_key_label"]) or "x")
            text = llm.invoke(prompt).content
            return _parse(text)["digest"] or text
        except Exception:
            continue
    return material


def _parse(text: str) -> dict:
    digest_match = DIGEST_RE.search(text or "")
    covered_match = COVERED_RE.search(text or "")
    digest = digest_match.group(1).strip() if digest_match else (text or "").strip()
    lines = covered_match.group(1).strip().splitlines() if covered_match else []
    return {"digest": digest, "items": _items_from_lines(lines)}


def _items_from_lines(lines: list[str]) -> list[dict]:
    items = []
    for line in lines:
        line = line.strip().lstrip("-*• ").strip()
        if not line:
            continue
        headline, _, summary = line.partition("::")
        items.append({"headline": headline.strip(), "summary": summary.strip()})
    return items


def _extract_sources(response) -> list[dict]:
    sources = []
    try:
        for candidate in response.candidates:
            chunks = candidate.grounding_metadata.grounding_chunks or []
            for chunk in chunks:
                web = getattr(chunk, "web", None)
                if web and getattr(web, "uri", None):
                    sources.append({"title": getattr(web, "title", "") or web.uri, "uri": web.uri})
    except Exception:
        pass
    seen = set()
    unique = []
    for source in sources:
        if source["uri"] not in seen:
            seen.add(source["uri"])
            unique.append(source)
    return unique
