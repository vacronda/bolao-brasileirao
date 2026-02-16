"""
Authentication helpers for the Bolão application.
Uses bcrypt for password hashing and Flask sessions/cookies for persistent login.
"""

from __future__ import annotations

import functools

import bcrypt
from flask import session, g, request, redirect, url_for, flash

import db

COOKIE_NAME = "bolao_token"
COOKIE_MAX_AGE_DAYS = 30


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def login_user(user: dict):
    """Log in a user: create DB session, set cookie token, store in Flask session."""
    token = db.create_session(user["id"])
    session["token"] = token
    session["user_id"] = user["id"]
    g.user = user


def logout_user():
    """Log out: delete DB session, clear Flask session."""
    token = session.get("token")
    if token:
        db.delete_session(token)
    session.clear()
    g.user = None


def restore_session():
    """Called before each request to restore user from session token."""
    g.user = None
    token = session.get("token")
    if not token:
        return
    user = db.get_session(token)
    if user:
        g.user = user
    else:
        session.clear()


def get_current_user() -> dict | None:
    return getattr(g, "user", None)


def is_logged_in() -> bool:
    return get_current_user() is not None


def is_admin() -> bool:
    user = get_current_user()
    return user is not None and user.get("is_admin", 0) == 1


def login_required(f):
    """Decorator: redirect to login page if not authenticated."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not is_logged_in():
            flash("Faça login para acessar esta página.", "warning")
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator: require app admin access."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not is_admin():
            flash("Acesso restrito a administradores.", "danger")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated


def league_member_required(f):
    """Decorator for league routes: verify user is a member of the league.
    Expects league_id as a route parameter."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not is_logged_in():
            flash("Faça login para acessar esta página.", "warning")
            return redirect(url_for("login", next=request.url))
        league_id = kwargs.get("league_id")
        if league_id and not db.is_league_member(league_id, g.user["id"]):
            flash("Você não é membro desta liga.", "warning")
            return redirect(url_for("leagues_list"))
        return f(*args, **kwargs)
    return decorated
