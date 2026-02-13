"""
Authentication helpers for the Bolão application.
Uses bcrypt for password hashing.
"""

import bcrypt
import streamlit as st


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def login_user(user: dict):
    st.session_state["user"] = user


def logout_user():
    st.session_state.pop("user", None)


def get_current_user() -> dict | None:
    return st.session_state.get("user")


def is_logged_in() -> bool:
    return "user" in st.session_state


def is_admin() -> bool:
    user = get_current_user()
    return user is not None and user.get("is_admin", 0) == 1
