#!/usr/bin/env python
import threading
import uuid
from datetime import date

from fastapi import Body, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from podkit import accounts, catalog, env, languages, mailer, notify, schedule
from podkit.duration import DEFAULT_MINUTES, MAX_MINUTES, MIN_MINUTES, clamp_minutes
from podkit.generator import generate_episode, regenerate_language
from podkit.paths import AUDIO, WEB, ensure_dirs
from podkit.themes import Theme, all_themes, get_theme, save_custom_theme, delete_custom_theme, slugify

ensure_dirs()
env.load_env()
app = FastAPI(title="Podcast du jour")

JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()

SESSION_MAX_AGE = 60 * 60 * 24 * 30


# ------------------------------- auth -----------------------------------
def current_user(request: Request) -> dict | None:
    return accounts.user_for_token(request.cookies.get(accounts.SESSION_COOKIE))


def require_user(request: Request) -> dict:
    user = current_user(request)
    if not user:
        raise HTTPException(401, "Login required.")
    return user


def require_publisher(request: Request) -> dict:
    user = require_user(request)
    if user.get("role") not in accounts.PUBLISH_ROLES:
        raise HTTPException(403, "Publisher role required to publish.")
    return user


def require_admin(request: Request) -> dict:
    user = require_user(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "Admin role required.")
    return user


def _set_session_cookie(response: Response, token: str):
    response.set_cookie(
        accounts.SESSION_COOKIE, token, max_age=SESSION_MAX_AGE,
        httponly=True, samesite="lax", path="/",
    )


# ------------------------------- jobs -----------------------------------
def _start_job(runner) -> str:
    job_id = uuid.uuid4().hex[:10]
    with _LOCK:
        JOBS[job_id] = {"id": job_id, "status": "running", "log": [], "episode_id": None, "error": None}

    def log(message: str):
        with _LOCK:
            JOBS[job_id]["log"].append(message)

    def execute():
        try:
            meta = runner(log)
            with _LOCK:
                JOBS[job_id].update(status="done", episode_id=meta["id"])
        except Exception as error:  # noqa: BLE001
            with _LOCK:
                JOBS[job_id].update(status="error", error=str(error))
                JOBS[job_id]["log"].append(f"✖ {error}")

    threading.Thread(target=execute, daemon=True).start()
    return job_id


def _publish_runner(theme: Theme, language, minutes):
    def runner(log):
        meta = generate_episode(theme, language, minutes, on_log=log)
        notify.episode_published(theme.key, meta)
        return meta

    return runner


def _theme_view(theme: Theme, latest: dict, user: dict | None) -> dict:
    episode = latest.get(theme.key)
    subscriptions = (user or {}).get("subscriptions", [])
    return {
        **theme.to_dict(),
        "today": catalog.to_view(episode) if episode and episode["date"] == date.today().isoformat() else None,
        "latest": catalog.to_view(episode) if episode else None,
        "subscribed": theme.key in subscriptions,
    }


# ----------------------------- bootstrap --------------------------------
@app.get("/api/bootstrap")
def bootstrap(request: Request):
    user = current_user(request)
    latest = catalog.latest_per_theme()
    is_admin = bool(user and user.get("role") == "admin")
    return {
        "user": user and accounts._public(user),
        "needs_setup": not accounts.has_users(),
        "themes": [_theme_view(theme, latest, user) for theme in all_themes().values()],
        "languages": languages.options(),
        "duration": {"min": MIN_MINUTES, "max": MAX_MINUTES, "default": DEFAULT_MINUTES},
        "keys": env.key_status() if is_admin else [],
        "schedules": _schedules_view(),
        "cron": _cron_view() if is_admin else {"installed": False, "line": "", "command": ""},
        "smtp_configured": mailer.is_configured(),
    }


# ------------------------------- auth API -------------------------------
class RegisterBody(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginBody(BaseModel):
    email: str
    password: str


@app.post("/api/auth/register")
def register(body: RegisterBody, response: Response):
    try:
        user = accounts.register(body.email, body.password, body.name)
    except accounts.AuthError as error:
        raise HTTPException(400, str(error))
    token = accounts.create_session(user["id"])
    _set_session_cookie(response, token)
    return user


@app.post("/api/auth/login")
def login(body: LoginBody, response: Response):
    user = accounts.authenticate(body.email, body.password)
    if not user:
        raise HTTPException(401, "Invalid email or password.")
    token = accounts.create_session(user["id"])
    _set_session_cookie(response, token)
    return accounts._public(user)


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    accounts.destroy_session(request.cookies.get(accounts.SESSION_COOKIE))
    response.delete_cookie(accounts.SESSION_COOKIE, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(request: Request):
    user = current_user(request)
    return user and accounts._public(user)


# --------------------------- subscriptions ------------------------------
class SubscriptionBody(BaseModel):
    theme_key: str
    subscribed: bool = True


@app.post("/api/subscriptions")
def set_subscription(body: SubscriptionBody, user: dict = Depends(require_user)):
    subs = accounts.set_subscription(user["id"], body.theme_key, body.subscribed)
    return {"subscriptions": subs}


# ------------------------------ admin -----------------------------------
@app.get("/api/users")
def users(_: dict = Depends(require_admin)):
    return accounts.list_users()


class RoleBody(BaseModel):
    role: str


@app.post("/api/users/{user_id}/role")
def set_user_role(user_id: str, body: RoleBody, _: dict = Depends(require_admin)):
    try:
        return accounts.set_role(user_id, body.role)
    except accounts.AuthError as error:
        raise HTTPException(400, str(error))


@app.delete("/api/users/{user_id}")
def remove_user(user_id: str, admin: dict = Depends(require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(400, "You cannot delete your own account.")
    try:
        accounts.delete_user(user_id)
    except accounts.AuthError as error:
        raise HTTPException(400, str(error))
    return {"ok": True}


# ------------------------------ themes ----------------------------------
@app.get("/api/themes")
def themes_endpoint(request: Request):
    user = current_user(request)
    latest = catalog.latest_per_theme()
    return [_theme_view(theme, latest, user) for theme in all_themes().values()]


@app.get("/api/episodes")
def episodes(theme: str | None = None, days: int | None = None):
    return [catalog.to_view(e) for e in catalog.list_episodes(theme_key=theme, days=days)]


@app.get("/api/episodes/{episode_id}")
def episode(episode_id: str):
    meta = catalog.get_episode(episode_id)
    if not meta:
        raise HTTPException(404, "Episode not found")
    return catalog.to_view(meta)


@app.delete("/api/episodes/{episode_id}")
def remove_episode(episode_id: str, _: dict = Depends(require_publisher)):
    catalog.delete_episode(episode_id)
    return {"ok": True}


class GenerateBody(BaseModel):
    theme_key: str
    language: str | None = None
    minutes: int | None = None


@app.post("/api/generate")
def generate(body: GenerateBody, _: dict = Depends(require_publisher)):
    try:
        theme = get_theme(body.theme_key)
    except KeyError:
        raise HTTPException(404, "Unknown theme")
    job = _start_job(_publish_runner(theme, body.language, body.minutes))
    return {"job": job}


class RegenBody(BaseModel):
    language: str


@app.post("/api/episodes/{episode_id}/regenerate")
def regenerate(episode_id: str, body: RegenBody, _: dict = Depends(require_publisher)):
    if not catalog.get_episode(episode_id):
        raise HTTPException(404, "Episode not found")
    job = _start_job(lambda log: regenerate_language(episode_id, body.language, on_log=log))
    return {"job": job}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    with _LOCK:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job")
    result = dict(job)
    if job["episode_id"]:
        result["episode"] = catalog.to_view(catalog.get_episode(job["episode_id"]))
    return result


@app.post("/api/episodes/{episode_id}/share")
def share(episode_id: str, _: dict = Depends(require_user)):
    key = catalog.mint_share(episode_id)
    if not key:
        raise HTTPException(404, "Episode not found")
    return {"key": key, "path": f"/s/{key}"}


@app.get("/api/languages")
def languages_endpoint():
    return languages.options()


@app.get("/api/settings/keys")
def get_keys(_: dict = Depends(require_admin)):
    return env.key_status()


@app.post("/api/settings/keys")
def set_keys(values: dict = Body(...), _: dict = Depends(require_admin)):
    env.update_keys(values)
    return env.key_status()


class CustomThemeBody(BaseModel):
    title: str
    summary: str = ""
    research_brief: str
    icon: str = "🎙️"
    accent: str = "#6750a4"
    language: str | None = None
    minutes: int = DEFAULT_MINUTES
    mode: str = "once"
    hour: int = 7
    weekday: int = 0


@app.post("/api/custom-theme")
def custom_theme(body: CustomThemeBody, _: dict = Depends(require_publisher)):
    key = slugify(body.title)
    theme = Theme(
        key=key,
        title=body.title.strip() or key,
        icon=body.icon or "🎙️",
        accent=body.accent or "#6750a4",
        summary=body.summary.strip(),
        research_brief=body.research_brief.strip(),
        language=languages.resolve(body.language),
        minutes=clamp_minutes(body.minutes),
        builtin=False,
    ).normalized()
    save_custom_theme(theme)

    response = {"theme": theme.to_dict(), "job": None, "schedule": None}
    if body.mode in ("daily", "weekly"):
        response["schedule"] = schedule.add_schedule(
            key, body.mode, body.hour, body.weekday, theme.language, theme.minutes
        )
    if body.mode == "once" or body.mode in ("daily", "weekly"):
        response["job"] = _start_job(_publish_runner(theme, theme.language, theme.minutes))
    return response


@app.delete("/api/themes/{theme_key}")
def delete_theme(theme_key: str, _: dict = Depends(require_publisher)):
    delete_custom_theme(theme_key)
    return {"ok": True}


def _schedules_view():
    return [{**entry, "human": schedule.describe(entry)} for entry in schedule.load_schedules()]


def _cron_view():
    return {"installed": schedule.cron_installed(), "line": schedule.cron_line(), "command": schedule.cron_command()}


@app.get("/api/schedules")
def list_schedules():
    return _schedules_view()


class ScheduleBody(BaseModel):
    theme_key: str
    cadence: str = "daily"
    hour: int = 7
    weekday: int = 0
    language: str | None = None
    minutes: int = DEFAULT_MINUTES


@app.post("/api/schedules")
def create_schedule(body: ScheduleBody, _: dict = Depends(require_publisher)):
    entry = schedule.add_schedule(body.theme_key, body.cadence, body.hour, body.weekday, body.language, body.minutes)
    return {**entry, "human": schedule.describe(entry)}


@app.delete("/api/schedules/{schedule_id}")
def remove_schedule(schedule_id: str, _: dict = Depends(require_publisher)):
    schedule.delete_schedule(schedule_id)
    return {"ok": True}


@app.post("/api/schedules/{schedule_id}/toggle")
def toggle_schedule(schedule_id: str, enabled: bool = Body(..., embed=True), _: dict = Depends(require_publisher)):
    schedule.set_enabled(schedule_id, enabled)
    return {"ok": True}


@app.get("/api/cron")
def cron_status(_: dict = Depends(require_admin)):
    return _cron_view()


@app.post("/api/cron/install")
def cron_install(_: dict = Depends(require_admin)):
    try:
        line = schedule.install_cron()
    except Exception as error:  # noqa: BLE001
        raise HTTPException(500, f"Could not install crontab: {error}")
    return {"installed": True, "line": line}


@app.post("/api/cron/uninstall")
def cron_uninstall(_: dict = Depends(require_admin)):
    schedule.uninstall_cron()
    return {"installed": False}


@app.get("/api/shared/{key}")
def shared(key: str):
    meta = catalog.resolve_share(key)
    if not meta:
        raise HTTPException(404, "Unknown link")
    view = catalog.to_view(meta)
    view["audio_url"] = f"/media/shared/{key}"
    return {
        "title": view["title"],
        "icon": view["icon"],
        "summary": view["summary"],
        "date": view["date"],
        "language_label": view.get("language_label"),
        "audio_url": view["audio_url"],
        "sources": view.get("sources", []),
    }


@app.get("/media/audio/{filename}")
def media_audio(filename: str):
    path = AUDIO / filename
    if not path.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(path, media_type="audio/mpeg", filename=filename)


@app.get("/media/shared/{key}")
def media_shared(key: str):
    meta = catalog.resolve_share(key)
    if not meta:
        raise HTTPException(404, "Unknown link")
    path = AUDIO / meta["audio_file"]
    if not path.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(path, media_type="audio/mpeg")


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/s/{key}")
def shared_page(key: str):
    return FileResponse(WEB / "share.html")


@app.get("/{asset}")
def asset(asset: str):
    candidate = WEB / asset
    if candidate.exists() and candidate.is_file():
        return FileResponse(candidate)
    return JSONResponse({"error": "not found"}, status_code=404)


if __name__ == "__main__":
    import os

    import uvicorn

    host = os.environ.get("PDJ_HOST", "127.0.0.1")
    port = int(os.environ.get("PDJ_PORT", "8077"))
    uvicorn.run(app, host=host, port=port)
