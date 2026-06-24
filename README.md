<div align="center">

<img src="web/favicon.svg" width="76" alt="Podcaster" />

# Podcaster

**Your own podcast studio for the news — self-hosted, private, on your terms.**

Generate a fresh audio briefing on *any* subject — on demand or on a schedule — running on
your server, with your API keys and your data. Nothing leaves your machine unless you say so.

🌐 **[Project site & screenshots →](https://lp177.github.io/podcaster/)** · 📦 **[Source on GitHub →](https://github.com/lp177/podcaster)**

</div>

<p align="center">
  <img src="docs/screenshots/today.png" width="49%" alt="Today — one fresh episode per subject" />
  <img src="docs/screenshots/offline.png" width="49%" alt="Offline — saved episodes, no connection" />
</p>

---

## Why Podcaster

- **🔒 Self-hosted & sovereign** — runs entirely on your own box or in a container. No SaaS,
  no account on someone else's platform, no third party between you and your audio.
- **🕵️ Private by design** — your subjects, listeners and listening history stay local.
  Share an episode only when *you* mint an unguessable private link.
- **🔑 Your keys, no lock-in** — bring any one LLM key; providers fall back automatically and
  audio is **free** via Edge TTS. Swap or self-host the model whenever you want.
- **🎙️ Any subject, on demand** — describe a topic and get a fresh, sourced news episode in
  minutes. Tech, video games, geopolitics, science, finance, sport… whatever you follow.
- **⏰ Set it and forget it** — schedule subjects daily or weekly and wake up to new episodes.

---

## Features

- **Fresh every run** — pulls the latest developments (grounded web search, with RSS and a
  plain-LLM fallback) and remembers what it already covered so episodes don't repeat.
- **On-demand or scheduled** — generate now, or run subjects automatically on a daily/weekly
  cadence.
- **Listen anywhere, even offline** — an installable app; tap *Save offline* and an episode
  plays with no connection.
- **Multi-user with roles** — run it just for yourself or open it up to a household/team:
  **admin / publisher / reader**. Publishing is gated; readers just listen and subscribe.
- **Email subscriptions** — readers subscribe to subjects and get a private listen link by
  email whenever a new episode drops.
- **Multilingual** — French, English, Spanish, German, Italian, with native voices and
  one-click regeneration into another language.
- **Private share links** — hand someone a single `/s/<key>` link to listen, no login needed.
- **Free TTS included** — Edge TTS voices every episode at no cost; plug in Gemini, OpenAI or
  ElevenLabs for premium voices if you want.

---

## Quick start

You only need **one LLM key** to start (e.g. `GEMINI_API_KEY`). Audio is free via Edge TTS.

### Docker / Podman (recommended)

```bash
cp .env.example .env          # add at least GEMINI_API_KEY
docker compose up -d          # or: podman-compose up -d
# open http://127.0.0.1:8077  — the first account you create becomes the admin
```

[docker-compose.yml](docker-compose.yml) builds the [Containerfile](Containerfile) and also
runs a `scheduler` service that fires due schedules every hour — no host cron needed. Your
`.env` and `data/` are bind-mounted, never baked into the image.

Build the image directly instead:

```bash
podman build -t podcaster -f Containerfile .          # or: docker build -f Containerfile .
podman run -d --name podcaster -p 127.0.0.1:8077:8077 \
  --env-file .env -v ./data:/app/data podcaster
```

The image pins exact, known-good versions from [requirements.lock.txt](requirements.lock.txt)
so the container matches development. No browser is installed — research uses grounded search
and RSS, not headless scraping.

### Local (Python 3.13)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add a key
python server.py              # http://127.0.0.1:8077
```

> `ffmpeg` must be on your PATH (the container image installs it for you).

---

## Configuration

All secrets live in `.env` (gitignored — **never commit it**). Copy
[.env.example](.env.example) and fill in what you have; keys are also editable from the web UI
(admin only).

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | Default provider — research, scripting, optional voices |
| `OPENAI_API_KEY` | Fallback scripting / voices |
| `ANTHROPIC_API_KEY` | Fallback scripting |
| `OLLAMA_API_BASE` | Local / OpenAI-compatible endpoint (fully offline models) |
| `ELEVENLABS_API_KEY` | Optional premium voices |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | Email notifications (optional) |
| `APP_BASE_URL` | Public URL used in notification & share links |

Provider fallback order — scripting: Gemini → OpenAI → Anthropic → Ollama. Voices: Gemini →
OpenAI → **Edge (free, always available)**.

## Roles

| Role | Can do |
| --- | --- |
| **admin** | Everything — users & roles, API keys, email, scheduler. *First registered account.* |
| **publisher** | Create subjects, generate & schedule episodes. |
| **reader** | *Default.* Listen, save offline, subscribe to subjects, get email notifications. |

---

## Command line

```bash
python generate.py markets-finance                 # generate one subject now
python generate.py markets-finance --lang en --minutes 12
python generate.py --list                          # list subjects
```

## Scheduling (host cron)

```bash
python scheduler.py install-cron     # add the one hourly crontab line
python scheduler.py tick             # what the cron runs each hour
python scheduler.py loop 3600        # foreground loop (used by the container)
python scheduler.py list             # show schedules
```

## Add a built-in subject

Drop a module in [themes/](themes/) exposing a `THEME = Theme(...)`; it is auto-discovered by
the CLI, the scheduler and the web UI. See [themes/markets_finance.py](themes/markets_finance.py).
You can also create subjects straight from the web UI.

---

## How it works

```
research (fresh news) → script (LLM) → audio (TTS) → library + memory → notify subscribers
```

- Generating a subject prunes that subject's episodes older than 7 days (retention).
- All state is plain JSON + MP3 files under `data/` (gitignored) — easy to back up or wipe.

## Project layout

```
podkit/      shared library (research, providers, generator, accounts, mailer, schedule …)
themes/      one module per built-in subject
web/         installable web app (PWA: service worker, manifest, offline)
docs/        project site + screenshots
server.py    backend API (auth, episodes, scheduling, admin)
scheduler.py cron / loop runner
generate.py  CLI
```

---

Built on the [podcastfy](https://github.com/souzatharsis/podcastfy) engine.

_Last updated: 2026-06-24._
