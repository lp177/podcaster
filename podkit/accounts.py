"""Users, sessions, roles and per-subject subscriptions.

Local-first: everything is JSON on disk. Passwords are PBKDF2-HMAC-SHA256.
The first account ever created becomes the admin; everyone else is a reader.
"""
import hashlib
import hmac
import json
import secrets
import threading
from datetime import datetime

from .paths import SESSIONS_FILE, USERS_FILE

ROLES = ["admin", "publisher", "reader"]
DEFAULT_ROLE = "reader"
PUBLISH_ROLES = {"admin", "publisher"}
SESSION_COOKIE = "pdj_session"
_PBKDF2_ROUNDS = 200_000
_LOCK = threading.Lock()


# ----------------------------- storage ----------------------------------
def _read(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text())
    except (ValueError, OSError):
        return fallback


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _load_users() -> list[dict]:
    return _read(USERS_FILE, [])


def _save_users(users: list[dict]):
    _write(USERS_FILE, users)


def _load_sessions() -> dict:
    return _read(SESSIONS_FILE, {})


def _save_sessions(sessions: dict):
    _write(SESSIONS_FILE, sessions)


# ----------------------------- passwords --------------------------------
def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        _, rounds, salt, _ = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(stored, f"pbkdf2_sha256${rounds}${salt}${digest.hex()}")
    except (ValueError, AttributeError):
        return False


# ----------------------------- public view -----------------------------
def _public(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user.get("name") or user["email"].split("@")[0],
        "role": user.get("role", DEFAULT_ROLE),
        "subscriptions": user.get("subscriptions", []),
        "can_publish": user.get("role", DEFAULT_ROLE) in PUBLISH_ROLES,
        "is_admin": user.get("role") == "admin",
        "created_at": user.get("created_at"),
    }


def has_users() -> bool:
    return bool(_load_users())


# ----------------------------- registration -----------------------------
class AuthError(ValueError):
    pass


def register(email: str, password: str, name: str = "") -> dict:
    email = (email or "").strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise AuthError("A valid email is required.")
    if len(password or "") < 8:
        raise AuthError("Password must be at least 8 characters.")
    with _LOCK:
        users = _load_users()
        if any(u["email"] == email for u in users):
            raise AuthError("An account with this email already exists.")
        user = {
            "id": secrets.token_hex(8),
            "email": email,
            "name": (name or "").strip(),
            "password": _hash_password(password),
            "role": "admin" if not users else DEFAULT_ROLE,
            "subscriptions": [],
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        users.append(user)
        _save_users(users)
    return _public(user)


def authenticate(email: str, password: str) -> dict | None:
    email = (email or "").strip().lower()
    for user in _load_users():
        if user["email"] == email and _verify_password(password, user["password"]):
            return user
    return None


# ----------------------------- sessions ---------------------------------
def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    with _LOCK:
        sessions = _load_sessions()
        sessions[token] = {"user_id": user_id, "created_at": datetime.now().isoformat(timespec="seconds")}
        _save_sessions(sessions)
    return token


def destroy_session(token: str):
    if not token:
        return
    with _LOCK:
        sessions = _load_sessions()
        if sessions.pop(token, None) is not None:
            _save_sessions(sessions)


def user_for_token(token: str) -> dict | None:
    if not token:
        return None
    session = _load_sessions().get(token)
    if not session:
        return None
    return _get_user(session["user_id"])


def _get_user(user_id: str) -> dict | None:
    return next((u for u in _load_users() if u["id"] == user_id), None)


# ----------------------------- subscriptions ----------------------------
def set_subscription(user_id: str, theme_key: str, subscribed: bool) -> list[str]:
    with _LOCK:
        users = _load_users()
        for user in users:
            if user["id"] == user_id:
                subs = set(user.get("subscriptions", []))
                subs.add(theme_key) if subscribed else subs.discard(theme_key)
                user["subscriptions"] = sorted(subs)
                _save_users(users)
                return user["subscriptions"]
    return []


def subscribers_for_theme(theme_key: str) -> list[dict]:
    return [_public(u) for u in _load_users() if theme_key in u.get("subscriptions", [])]


# ----------------------------- admin ------------------------------------
def list_users() -> list[dict]:
    return [_public(u) for u in _load_users()]


def set_role(user_id: str, role: str):
    if role not in ROLES:
        raise AuthError(f"Unknown role: {role}")
    with _LOCK:
        users = _load_users()
        admins = [u for u in users if u.get("role") == "admin"]
        for user in users:
            if user["id"] == user_id:
                if user.get("role") == "admin" and role != "admin" and len(admins) == 1:
                    raise AuthError("Cannot demote the last admin.")
                user["role"] = role
                _save_users(users)
                return _public(user)
    raise AuthError("User not found.")


def delete_user(user_id: str):
    with _LOCK:
        users = _load_users()
        target = next((u for u in users if u["id"] == user_id), None)
        if not target:
            return
        if target.get("role") == "admin" and len([u for u in users if u.get("role") == "admin"]) == 1:
            raise AuthError("Cannot delete the last admin.")
        users = [u for u in users if u["id"] != user_id]
        _save_users(users)
        sessions = {t: s for t, s in _load_sessions().items() if s["user_id"] != user_id}
        _save_sessions(sessions)
