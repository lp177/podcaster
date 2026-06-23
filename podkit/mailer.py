"""Best-effort SMTP email. No-ops cleanly when SMTP is not configured."""
import smtplib
import ssl
from email.message import EmailMessage

from . import env


def is_configured() -> bool:
    return bool(env.get("SMTP_HOST") and env.get("SMTP_FROM"))


def _port() -> int:
    try:
        return int(env.get("SMTP_PORT") or 587)
    except ValueError:
        return 587


def send(to: str, subject: str, text: str, html: str | None = None) -> bool:
    if not is_configured():
        return False
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = env.get("SMTP_FROM")
    message["To"] = to
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")

    host, port = env.get("SMTP_HOST"), _port()
    user, password = env.get("SMTP_USER"), env.get("SMTP_PASSWORD")
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=20) as server:
                if user:
                    server.login(user, password or "")
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.starttls(context=ssl.create_default_context())
                if user:
                    server.login(user, password or "")
                server.send_message(message)
        return True
    except Exception:  # noqa: BLE001 — notifications are non-critical
        return False
