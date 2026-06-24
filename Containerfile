# Containerfile — "Podcaster" (FastAPI/uvicorn), built on the `podcastfy`
# engine. Built + run rootless under the `podman` user on flame (see
# deploy/flame/podcastify-deploy.sh). No chromium (playwright unused; research uses
# Gemini + RSS), but ffmpeg IS required (pydub, via podcastfy audio assembly).
# Deps come from requirements.lock.txt = the exact working venv (incl. podcastfy
# and its langchain/litellm/google/edge-tts stack), so the image matches dev.
# data/ and .env are bind-mounted at runtime, not baked in (see .containerignore).
# Full (not -slim) image: it ships the complete C/C++ toolchain (buildpack-deps),
# needed because some pinned deps (e.g. numpy==1.26.4) have no cp313 wheel and build
# from source. Bigger base, but a one-shot reliable build that matches the dev venv.
FROM python:3.13

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ffmpeg: pydub audio assembly. cron: in-container scheduling (provides the
# `crontab` binary + daemon used by the Settings → scheduler feature).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg cron \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock.txt ./
RUN pip install -r requirements.lock.txt

COPY . .

EXPOSE 8077
# Start the cron daemon (so schedules installed from the UI actually fire), then
# run uvicorn on 0.0.0.0 so the rootless PublishPort (host 127.0.0.1:8077) reaches
# it. `;` not `&&` — a cron hiccup must never stop the web server from starting.
CMD ["sh", "-c", "/usr/sbin/cron; exec uvicorn server:app --host 0.0.0.0 --port 8077"]
