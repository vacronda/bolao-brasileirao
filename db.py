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

_USE_TURSO = None  # cached flag


def _get_turso_config() -> tuple[str, str] | None:
    try:
        url = st.secrets["TURSO_URL"]
        token = st.secrets["TURSO_AUTH_TOKEN"]
        return (url, token)
    except (FileNotFoundError, KeyError):
        return None


class _DictCursor:
    """Wraps a libsql cursor to return dicts instead of tuples."""

    def __init__(self, real_cursor):
        self._cur = real_cursor

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    @property
    def description(self):
        return self._cur.description

    def _to_dict(self, row):
        if row is None:
            return None
        cols = [d[0] for d in self._cur.description]
        return dict(zip(cols, row))

    def fetchone(self):
        row = self._cur.fetchone()
        return self._to_dict(row)

    def fetchall(self):
        rows = self._cur.fetchall()
        return [self._to_dict(r) for r in rows]


class _ConnWrapper:
    """Wraps a libsql connection so .execute() returns a _DictCursor."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        cur = self._conn.execute(sql, params)
        return _DictCursor(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def _connect():
    global _USE_TURSO
    turso = _get_turso_config()
    if turso:
        _USE_TURSO = True
        import libsql_experimental as libsql
        raw = libsql.connect(turso[0], auth_token=turso[1])
        return _ConnWrapper(raw)
    else:
        _USE_TURSO = False
        import sqlite3
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bolao.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _to_dict(row) -> dict | None:
    """Convert a row to dict. Handles sqlite3.Row, dict, or None."""
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    return dict(row)


def _to_dicts(rows) -> list[dict]:
    return [_to_dict(r) for r in rows]


# ─── Schema init ───────────────────────────────────────────────────────────────

def init_db():
    with get_conn() as conn:
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
                league TEXT NOT NULL DEFAULT 'Brasileirão',
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
            """CREATE TABLE IF NOT EXISTS match_odds (
                match_id INTEGER PRIMARY KEY,
                home_win REAL,
                draw REAL,
                away_win REAL,
                bookmaker TEXT,
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (match_id) REFERENCES matches(id)
            )""",
            """CREATE TABLE IF NOT EXISTS teams (
                name TEXT PRIMARY KEY,
                logo_url TEXT
            )""",
        ]
        for stmt in statements:
            conn.execute(stmt)
        conn.commit()

        # Migration: add league column if missing
        try:
            conn.execute("SELECT league FROM matches LIMIT 1")
        except Exception:
            conn.execute("ALTER TABLE matches ADD COLUMN league TEXT NOT NULL DEFAULT 'Brasileirão'")

        row = _to_dict(conn.execute("SELECT COUNT(*) as cnt FROM scoring_config").fetchone())
        if row["cnt"] == 0:
            conn.execute("INSERT INTO scoring_config (id) VALUES (1)")

        row = _to_dict(conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone())
        if row["cnt"] == 0:
            from auth import hash_password
            conn.execute(
                "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)",
                ("admin", hash_password("admin123")),
            )

        # Create bot users (Olavo & PVC) if they don't exist
        for bot_name in ("Olavo", "PVC"):
            existing = _to_dict(
                conn.execute("SELECT id FROM users WHERE username = ?", (bot_name,)).fetchone()
            )
            if not existing:
                from auth import hash_password
                conn.execute(
                    "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 0)",
                    (bot_name, hash_password(f"bot-{bot_name}-no-login")),
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
        return _to_dict(row) if row else None


def get_all_users() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, username, is_admin FROM users ORDER BY username"
        ).fetchall()
        return _to_dicts(rows)


def delete_user(user_id: int) -> bool:
    """Delete a user and all their bets. Refuses to delete admins."""
    with get_conn() as conn:
        user = _to_dict(
            conn.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,)).fetchone()
        )
        if not user or user["is_admin"]:
            return False
        conn.execute("DELETE FROM bets WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return True


def reset_user_password(user_id: int, new_password_hash: str):
    """Update a user's password hash."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_password_hash, user_id),
        )


# ─── Match operations ─────────────────────────────────────────────────────────

def add_match(round_number: int, home_team: str, away_team: str, match_time: str, league: str = "Brasileirão") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO matches (league, round_number, home_team, away_team, match_time) VALUES (?, ?, ?, ?, ?)",
            (league, round_number, home_team, away_team, match_time),
        )
        return cur.lastrowid


def get_leagues() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT DISTINCT league FROM matches ORDER BY league").fetchall()
        return [_to_dict(r)["league"] for r in rows]


def get_upcoming_matches() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM matches WHERE is_finished = 0 ORDER BY match_time ASC"
        ).fetchall()
        return _to_dicts(rows)


def get_matches_next_days(days: int = 7) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM matches WHERE is_finished = 0 AND match_time <= datetime('now', '+' || ? || ' days') ORDER BY match_time ASC",
            (str(days),),
        ).fetchall()
        return _to_dicts(rows)


def get_finished_matches() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM matches WHERE is_finished = 1 ORDER BY match_time DESC"
        ).fetchall()
        return _to_dicts(rows)


def get_all_matches() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM matches ORDER BY match_time DESC"
        ).fetchall()
        return _to_dicts(rows)


def get_unfinished_matches() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM matches WHERE is_finished = 0 ORDER BY match_time ASC"
        ).fetchall()
        return _to_dicts(rows)


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
    config = _to_dict(
        conn.execute("SELECT * FROM scoring_config WHERE id = 1").fetchone()
    )
    bets = _to_dicts(
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
    if pred_home == real_home and pred_away == real_away:
        return config["exact_score"]

    pred_diff = pred_home - pred_away
    real_diff = real_home - real_away

    pred_outcome = (1 if pred_home > pred_away else (-1 if pred_home < pred_away else 0))
    real_outcome = (1 if real_home > real_away else (-1 if real_home < real_away else 0))

    if pred_outcome == real_outcome and pred_diff == real_diff and pred_outcome != 0:
        return config["correct_winner_goal_diff"]

    if pred_outcome == real_outcome and pred_outcome != 0:
        return config["correct_winner"]

    if pred_outcome == 0 and real_outcome == 0:
        return config["correct_draw"]

    return config["wrong"]


# ─── Bet operations ────────────────────────────────────────────────────────────

def upsert_bet(user_id: int, match_id: int, home_score: int, away_score: int) -> bool:
    """Insert or update a bet. Returns False if match already started."""
    with get_conn() as conn:
        match = _to_dict(
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
        rows = _to_dicts(
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
                COALESCE(SUM(CASE WHEN b.points_awarded = 0 THEN 1 ELSE 0 END), 0) as zero_count,
                COUNT(b.id) as total_bets,
                (SELECT COUNT(*) FROM matches WHERE is_finished = 1) - COUNT(b.id) as missed_count
            FROM users u
            LEFT JOIN bets b ON b.user_id = u.id AND b.points_awarded IS NOT NULL
            WHERE u.is_admin = 0
            GROUP BY u.id
            ORDER BY total_points DESC, exact_count DESC, u.username ASC
        """).fetchall()
        return _to_dicts(rows)


# ─── Scoring config ───────────────────────────────────────────────────────────

def get_scoring_config() -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM scoring_config WHERE id = 1").fetchone()
        return _to_dict(row)


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


# ─── Odds operations ─────────────────────────────────────────────────────────

def upsert_odds(match_id: int, home_win: float, draw: float, away_win: float, bookmaker: str):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO match_odds (match_id, home_win, draw, away_win, bookmaker, updated_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(match_id) DO UPDATE SET
                   home_win = excluded.home_win,
                   draw = excluded.draw,
                   away_win = excluded.away_win,
                   bookmaker = excluded.bookmaker,
                   updated_at = datetime('now')
            """,
            (match_id, home_win, draw, away_win, bookmaker),
        )


def get_odds_for_matches(match_ids: list[int]) -> dict[int, dict]:
    """Returns {match_id: {home_win, draw, away_win, bookmaker}} for given match IDs."""
    if not match_ids:
        return {}
    with get_conn() as conn:
        placeholders = ",".join("?" for _ in match_ids)
        rows = _to_dicts(
            conn.execute(
                f"SELECT * FROM match_odds WHERE match_id IN ({placeholders})",
                tuple(match_ids),
            ).fetchall()
        )
        return {r["match_id"]: r for r in rows}


def get_all_bets_for_match(match_id: int) -> list[dict]:
    """Returns all bets for a match joined with username, ordered by username."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT b.id, b.user_id, u.username, b.home_score, b.away_score, b.points_awarded
               FROM bets b
               JOIN users u ON u.id = b.user_id
               WHERE b.match_id = ?
               ORDER BY u.username""",
            (match_id,),
        ).fetchall()
        return _to_dicts(rows)


def admin_upsert_bet(user_id: int, match_id: int, home_score: int, away_score: int):
    """Insert or update a bet without time/finished checks (admin override)."""
    with get_conn() as conn:
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


def admin_delete_bet(bet_id: int):
    """Delete a specific bet by ID."""
    with get_conn() as conn:
        conn.execute("DELETE FROM bets WHERE id = ?", (bet_id,))


# ─── Team operations ──────────────────────────────────────────────────────────

def upsert_team(name: str, logo_url: str):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO teams (name, logo_url)
               VALUES (?, ?)
               ON CONFLICT(name) DO UPDATE SET logo_url = excluded.logo_url
            """,
            (name, logo_url),
        )


def get_team_logos(team_names: list[str]) -> dict[str, str]:
    """Returns {name: logo_url} for given team names."""
    if not team_names:
        return {}
    with get_conn() as conn:
        placeholders = ",".join("?" for _ in team_names)
        rows = _to_dicts(
            conn.execute(
                f"SELECT name, logo_url FROM teams WHERE name IN ({placeholders})",
                tuple(team_names),
            ).fetchall()
        )
        return {r["name"]: r["logo_url"] for r in rows if r.get("logo_url")}


def get_leaderboard_evolution() -> list[dict]:
    """Returns rows of (username, match_time, points_awarded) for finished matches."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT u.username, m.match_time, COALESCE(b.points_awarded, 0) as points_awarded
            FROM bets b
            JOIN users u ON u.id = b.user_id
            JOIN matches m ON m.id = b.match_id
            WHERE m.is_finished = 1 AND u.is_admin = 0
            ORDER BY m.match_time ASC
        """).fetchall()
        return _to_dicts(rows)


def recalculate_all_points():
    """Recalculate points for all finished matches (used after scoring config changes)."""
    with get_conn() as conn:
        config = _to_dict(
            conn.execute("SELECT * FROM scoring_config WHERE id = 1").fetchone()
        )
        finished = _to_dicts(
            conn.execute("SELECT * FROM matches WHERE is_finished = 1").fetchall()
        )
        for match in finished:
            bets = _to_dicts(
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
