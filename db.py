"""
Database layer for the Bolão application.
Uses Turso (libsql) for cloud-hosted SQLite that persists across redeployments.
Falls back to local SQLite for development.
"""

import os
from datetime import datetime
from contextlib import contextmanager

import streamlit as st

# ─── Connection setup ──────────────────────────────────────────────────────────
# Turso (production): reads TURSO_URL and TURSO_AUTH_TOKEN from st.secrets
# Local (development): uses a local bolao.db file if secrets are not set

def _get_turso_config() -> tuple[str, str] | None:
    try:
        url = st.secrets["TURSO_URL"]
        token = st.secrets["TURSO_AUTH_TOKEN"]
        return (url, token)
    except (FileNotFoundError, KeyError):
        return None


def _connect():
    turso = _get_turso_config()
    if turso:
        import libsql_experimental as libsql
        conn = libsql.connect("bolao.db", sync_url=turso[0], auth_token=turso[1])
        conn.sync()
    else:
        import sqlite3
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bolao.db")
        conn = sqlite3.connect(db_path)
    conn.row_factory = _dict_row_factory(turso is not None)
    return conn, turso is not None


def _dict_row_factory(is_libsql: bool):
    """Return a row_factory that produces dict-like rows for both sqlite3 and libsql."""
    if is_libsql:
        # libsql_experimental doesn't support sqlite3.Row; use a custom factory
        def factory(cursor, row):
            cols = [d[0] for d in cursor.description]
            return dict(zip(cols, row))
        return factory
    else:
        import sqlite3
        return sqlite3.Row


@contextmanager
def get_conn():
    conn, is_turso = _connect()
    try:
        yield conn
        conn.commit()
        if is_turso:
            conn.sync()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _row_to_dict(row) -> dict:
    """Convert a row to dict, handling both sqlite3.Row and plain dict."""
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    return dict(row)


def _rows_to_dicts(rows) -> list[dict]:
    return [_row_to_dict(r) for r in rows]


# ─── Schema init ───────────────────────────────────────────────────────────────

def init_db():
    with get_conn() as conn:
        # libsql doesn't support executescript; run each statement individually
        statements = [
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )""",
            """CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_number INTEGER,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                match_time TEXT NOT NULL,
                home_score INTEGER,
                away_score INTEGER,
                is_finished INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )""",
            """CREATE TABLE IF NOT EXISTS bets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                match_id INTEGER NOT NULL,
                home_score INTEGER NOT NULL,
                away_score INTEGER NOT NULL,
                points_awarded INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (match_id) REFERENCES matches(id),
                UNIQUE(user_id, match_id)
            )""",
            """CREATE TABLE IF NOT EXISTS scoring_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                exact_score INTEGER DEFAULT 10,
                correct_winner_goal_diff INTEGER DEFAULT 5,
                correct_winner INTEGER DEFAULT 3,
                correct_draw INTEGER DEFAULT 3,
                wrong INTEGER DEFAULT 0
            )""",
        ]
        for stmt in statements:
            conn.execute(stmt)
        conn.commit()

        # Seed default scoring config if not present
        row = _row_to_dict(conn.execute("SELECT COUNT(*) as cnt FROM scoring_config").fetchone())
        if row["cnt"] == 0:
            conn.execute("INSERT INTO scoring_config (id) VALUES (1)")

        # Seed default admin user (admin / admin123) if no users exist
        row = _row_to_dict(conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone())
        if row["cnt"] == 0:
            from auth import hash_password
            conn.execute(
                "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)",
                ("admin", hash_password("admin123")),
            )


# ─── User operations ──────────────────────────────────────────────────────────

def create_user(username: str, password_hash: str) -> int | None:
    with get_conn() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            return cur.lastrowid
        except Exception:
            return None


def get_user_by_username(username: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return _row_to_dict(row) if row else None


def get_all_users() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, username, is_admin FROM users ORDER BY username"
        ).fetchall()
        return _rows_to_dicts(rows)


# ─── Match operations ─────────────────────────────────────────────────────────

def add_match(round_number: int, home_team: str, away_team: str, match_time: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO matches (round_number, home_team, away_team, match_time) VALUES (?, ?, ?, ?)",
            (round_number, home_team, away_team, match_time),
        )
        return cur.lastrowid


def get_upcoming_matches() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM matches WHERE is_finished = 0 ORDER BY match_time ASC"
        ).fetchall()
        return _rows_to_dicts(rows)


def get_finished_matches() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM matches WHERE is_finished = 1 ORDER BY match_time DESC"
        ).fetchall()
        return _rows_to_dicts(rows)


def get_all_matches() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM matches ORDER BY match_time DESC"
        ).fetchall()
        return _rows_to_dicts(rows)


def get_unfinished_matches() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM matches WHERE is_finished = 0 ORDER BY match_time ASC"
        ).fetchall()
        return _rows_to_dicts(rows)


def set_match_result(match_id: int, home_score: int, away_score: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE matches SET home_score = ?, away_score = ?, is_finished = 1 WHERE id = ?",
            (home_score, away_score, match_id),
        )
        _calculate_points_for_match(conn, match_id, home_score, away_score)


def delete_match(match_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM bets WHERE match_id = ?", (match_id,))
        conn.execute("DELETE FROM matches WHERE id = ?", (match_id,))


def _calculate_points_for_match(conn, match_id: int, real_home: int, real_away: int):
    config = _row_to_dict(
        conn.execute("SELECT * FROM scoring_config WHERE id = 1").fetchone()
    )
    bets = _rows_to_dicts(
        conn.execute("SELECT * FROM bets WHERE match_id = ?", (match_id,)).fetchall()
    )
    for bet in bets:
        points = _score_bet(
            bet["home_score"], bet["away_score"],
            real_home, real_away,
            config,
        )
        conn.execute(
            "UPDATE bets SET points_awarded = ? WHERE id = ?",
            (points, bet["id"]),
        )


def _score_bet(
    pred_home: int, pred_away: int,
    real_home: int, real_away: int,
    config: dict,
) -> int:
    # Exact score
    if pred_home == real_home and pred_away == real_away:
        return config["exact_score"]

    pred_diff = pred_home - pred_away
    real_diff = real_home - real_away

    # Determine outcomes
    pred_outcome = (1 if pred_home > pred_away else (-1 if pred_home < pred_away else 0))
    real_outcome = (1 if real_home > real_away else (-1 if real_home < real_away else 0))

    # Correct winner + correct goal difference
    if pred_outcome == real_outcome and pred_diff == real_diff and pred_outcome != 0:
        return config["correct_winner_goal_diff"]

    # Correct winner (non-draw)
    if pred_outcome == real_outcome and pred_outcome != 0:
        return config["correct_winner"]

    # Correct draw (but not exact score, already handled)
    if pred_outcome == 0 and real_outcome == 0:
        return config["correct_draw"]

    return config["wrong"]


# ─── Bet operations ────────────────────────────────────────────────────────────

def upsert_bet(user_id: int, match_id: int, home_score: int, away_score: int) -> bool:
    """Insert or update a bet. Returns False if match already started."""
    with get_conn() as conn:
        match = _row_to_dict(
            conn.execute(
                "SELECT match_time, is_finished FROM matches WHERE id = ?", (match_id,)
            ).fetchone()
        )
        if not match:
            return False

        match_dt = datetime.fromisoformat(match["match_time"])
        if match["is_finished"] or datetime.now() >= match_dt:
            return False

        conn.execute(
            """INSERT INTO bets (user_id, match_id, home_score, away_score, updated_at)
               VALUES (?, ?, ?, ?, datetime('now'))
               ON CONFLICT(user_id, match_id) DO UPDATE SET
                   home_score = excluded.home_score,
                   away_score = excluded.away_score,
                   updated_at = datetime('now')
            """,
            (user_id, match_id, home_score, away_score),
        )
        return True


def get_user_bets(user_id: int) -> dict[int, dict]:
    """Returns {match_id: {home_score, away_score, points_awarded}}"""
    with get_conn() as conn:
        rows = _rows_to_dicts(
            conn.execute("SELECT * FROM bets WHERE user_id = ?", (user_id,)).fetchall()
        )
        return {r["match_id"]: r for r in rows}


# ─── Leaderboard ──────────────────────────────────────────────────────────────

def get_leaderboard() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                u.id as user_id,
                u.username,
                COALESCE(SUM(b.points_awarded), 0) as total_points,
                COALESCE(SUM(CASE WHEN b.points_awarded = (
                    SELECT exact_score FROM scoring_config WHERE id = 1
                ) THEN 1 ELSE 0 END), 0) as exact_count,
                COUNT(b.id) as total_bets
            FROM users u
            LEFT JOIN bets b ON b.user_id = u.id AND b.points_awarded IS NOT NULL
            WHERE u.is_admin = 0
            GROUP BY u.id
            ORDER BY total_points DESC, exact_count DESC, u.username ASC
        """).fetchall()
        return _rows_to_dicts(rows)


# ─── Scoring config ───────────────────────────────────────────────────────────

def get_scoring_config() -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM scoring_config WHERE id = 1").fetchone()
        return _row_to_dict(row)


def update_scoring_config(
    exact_score: int,
    correct_winner_goal_diff: int,
    correct_winner: int,
    correct_draw: int,
    wrong: int,
):
    with get_conn() as conn:
        conn.execute(
            """UPDATE scoring_config SET
                exact_score = ?,
                correct_winner_goal_diff = ?,
                correct_winner = ?,
                correct_draw = ?,
                wrong = ?
               WHERE id = 1""",
            (exact_score, correct_winner_goal_diff, correct_winner, correct_draw, wrong),
        )


def recalculate_all_points():
    """Recalculate points for all finished matches (used after scoring config changes)."""
    with get_conn() as conn:
        config = _row_to_dict(
            conn.execute("SELECT * FROM scoring_config WHERE id = 1").fetchone()
        )
        finished = _rows_to_dicts(
            conn.execute("SELECT * FROM matches WHERE is_finished = 1").fetchall()
        )
        for match in finished:
            bets = _rows_to_dicts(
                conn.execute("SELECT * FROM bets WHERE match_id = ?", (match["id"],)).fetchall()
            )
            for bet in bets:
                points = _score_bet(
                    bet["home_score"], bet["away_score"],
                    match["home_score"], match["away_score"],
                    config,
                )
                conn.execute(
                    "UPDATE bets SET points_awarded = ? WHERE id = ?",
                    (points, bet["id"]),
                )
