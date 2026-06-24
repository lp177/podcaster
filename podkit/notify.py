"""Notify subscribers by email when a new episode is released for their subject."""
import threading

from . import accounts, catalog, env, mailer


def _base_url() -> str:
    return (env.get("APP_BASE_URL") or "http://127.0.0.1:8077").rstrip("/")


def _send_all(theme_key: str, meta: dict):
    subscribers = accounts.subscribers_for_theme(theme_key)
    if not subscribers or not mailer.is_configured():
        return
    key = catalog.mint_share(meta["id"])
    listen = f"{_base_url()}/s/{key}" if key else _base_url()
    title = meta.get("title", theme_key)
    summary = meta.get("summary", "")
    subject = f"🎧 New episode: {title}"
    text = f"{title}\n\n{summary}\n\nListen: {listen}\n\n— Podcaster"
    html = (
        f"<div style='font-family:system-ui,sans-serif;max-width:520px'>"
        f"<h2 style='margin:0 0 8px'>{meta.get('icon', '🎧')} {title}</h2>"
        f"<p style='color:#475569'>{summary}</p>"
        f"<p><a href='{listen}' style='background:#6750a4;color:#fff;padding:10px 18px;"
        f"border-radius:999px;text-decoration:none;display:inline-block'>▶ Listen now</a></p>"
        f"<p style='color:#94a3b8;font-size:12px'>You receive this because you subscribed to "
        f"this subject. Manage subscriptions in the app.</p></div>"
    )
    for sub in subscribers:
        mailer.send(sub["email"], subject, text, html)


def episode_published(theme_key: str, meta: dict, block: bool = False):
    """Notify subscribers. Fire-and-forget by default (web server); pass
    block=True from short-lived processes (the cron scheduler) so the mail
    actually goes out before the process exits."""
    if block:
        _send_all(theme_key, meta)
    else:
        threading.Thread(target=_send_all, args=(theme_key, meta), daemon=True).start()
