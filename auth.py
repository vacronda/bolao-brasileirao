"""
Authentication helpers for the Bolão application.
Uses bcrypt for password hashing and cookies for persistent sessions.
"""

import bcrypt
import streamlit as st
from streamlit_cookies_controller import CookieController

import db

cookie_controller = CookieController()

COOKIE_NAME = "bolao_token"
COOKIE_MAX_AGE_DAYS = 30


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def login_user(user: dict):
    st.session_state["user"] = user
    token = db.create_session(user["id"])
    cookie_controller.set(COOKIE_NAME, token, max_age=COOKIE_MAX_AGE_DAYS * 86400)


def logout_user():
    token = cookie_controller.get(COOKIE_NAME)
    if token:
        db.delete_session(token)
        cookie_controller.remove(COOKIE_NAME)
    st.session_state.pop("user", None)


def restore_session():
    """Check for a session cookie and restore the user if valid."""
    if "user" in st.session_state:
        return
    token = cookie_controller.get(COOKIE_NAME)
    if not token:
        return
    user = db.get_session(token)
    if user:
        st.session_state["user"] = user
    else:
        cookie_controller.remove(COOKIE_NAME)


def get_current_user() -> dict | None:
    return st.session_state.get("user")


def is_logged_in() -> bool:
    return "user" in st.session_state


def is_admin() -> bool:
    user = get_current_user()
    return user is not None and user.get("is_admin", 0) == 1
