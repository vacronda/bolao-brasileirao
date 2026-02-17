"""
Database layer for the Bolão application.
Uses Turso (libsql) for cloud-hosted SQLite that persists across redeployments.
Falls back to local SQLite for development.
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Optional


# ─── Connection setup ──────────────────────────────────────────────────────────
# Turso (production): reads TURSO_URL and TURSO_AUTH_TOKEN from environment
# Local (development): uses a local bolao.db file if env vars are not set

_USE_TURSO = None  # cached flag


def _get_turso_config() -> tuple[str, str] | None:
    url = os.environ.get("TURSO_URL")
    token = os.environ.get("TURSO_AUTH_TOKEN")
    if url and token:
        return (url, token)
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
            """CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )""",
            # ─── League tables ──────────────────────────────────
            """CREATE TABLE IF NOT EXISTS leagues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                competition TEXT NOT NULL,
                invite_code TEXT UNIQUE NOT NULL,
                created_by INTEGER NOT NULL,
                start_date TEXT,
                end_date TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )""",
            """CREATE TABLE IF NOT EXISTS league_members (
                league_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                joined_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (league_id, user_id),
                FOREIGN KEY (league_id) REFERENCES leagues(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )""",
            """CREATE TABLE IF NOT EXISTS league_scoring (
                league_id INTEGER PRIMARY KEY,
                exact_score INTEGER DEFAULT 10,
                correct_winner_goal_diff INTEGER DEFAULT 5,
                correct_winner INTEGER DEFAULT 3,
                correct_draw INTEGER DEFAULT 3,
                wrong INTEGER DEFAULT 0,
                FOREIGN KEY (league_id) REFERENCES leagues(id)
            )""",
        ]
        for stmt in statements:
            conn.execute(stmt)
        conn.commit()

        # Migration: add league column to matches if missing
        try:
            conn.execute("SELECT league FROM matches LIMIT 1")
        except Exception:
            conn.execute("ALTER TABLE matches ADD COLUMN league TEXT NOT NULL DEFAULT 'Brasileirão'")

        # Migration: add avatar_url column to users if missing
        try:
            conn.execute("SELECT avatar_url FROM users LIMIT 1")
        except Exception:
            conn.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")

        # Migration: add league_id column to bets if missing
        _migrate_bets_add_league_id(conn)

        # Seed scoring config
        row = _to_dict(conn.execute("SELECT COUNT(*) as cnt FROM scoring_config").fetchone())
        if row["cnt"] == 0:
            conn.execute("INSERT INTO scoring_config (id) VALUES (1)")

        # Seed admin user
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

        # Migration: create default leagues for existing data
        _migrate_create_default_leagues(conn)


def _migrate_bets_add_league_id(conn):
    """Migrate bets table to include league_id column."""
    try:
        conn.execute("SELECT league_id FROM bets LIMIT 1")
        return  # already migrated
    except Exception:
        pass

    # Check if bets table exists with data
    try:
        row = _to_dict(conn.execute("SELECT COUNT(*) as cnt FROM bets").fetchone())
        has_data = row["cnt"] > 0
    except Exception:
        has_data = False

    if has_data:
        # Rename old table, create new, copy data
        conn.execute("ALTER TABLE bets RENAME TO bets_old")
        conn.execute("""CREATE TABLE bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            match_id INTEGER NOT NULL,
            league_id INTEGER,
            home_score INTEGER NOT NULL,
            away_score INTEGER NOT NULL,
            points_awarded INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (match_id) REFERENCES matches(id),
            FOREIGN KEY (league_id) REFERENCES leagues(id),
            UNIQUE(user_id, match_id, league_id)
        )""")
        # Copy data - league_id will be populated by _migrate_create_default_leagues
        conn.execute("""INSERT INTO bets (id, user_id, match_id, home_score, away_score,
                        points_awarded, created_at, updated_at)
                        SELECT id, user_id, match_id, home_score, away_score,
                        points_awarded, created_at, updated_at FROM bets_old""")
        conn.execute("DROP TABLE bets_old")
    else:
        # No data or table doesn't exist - create fresh
        try:
            conn.execute("DROP TABLE IF EXISTS bets")
        except Exception:
            pass
        conn.execute("""CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            match_id INTEGER NOT NULL,
            league_id INTEGER,
            home_score INTEGER NOT NULL,
            away_score INTEGER NOT NULL,
            points_awarded INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (match_id) REFERENCES matches(id),
            FOREIGN KEY (league_id) REFERENCES leagues(id),
            UNIQUE(user_id, match_id, league_id)
        )""")
    conn.commit()


def _migrate_create_default_leagues(conn):
    """Create default leagues and assign existing users/bets if leagues table is empty."""
    row = _to_dict(conn.execute("SELECT COUNT(*) as cnt FROM leagues").fetchone())
    if row["cnt"] > 0:
        return  # already migrated

    # Check if there are existing matches
    match_count = _to_dict(
        conn.execute("SELECT COUNT(*) as cnt FROM matches").fetchone()
    )["cnt"]
    if match_count == 0:
        return  # fresh install, nothing to migrate

    # Find admin user
    admin = _to_dict(conn.execute(
        "SELECT id FROM users WHERE is_admin = 1 LIMIT 1"
    ).fetchone())
    admin_id = admin["id"] if admin else 1

    # Get global scoring config for seeding league scoring
    global_config = _to_dict(
        conn.execute("SELECT * FROM scoring_config WHERE id = 1").fetchone()
    )

    # Get all distinct competitions from matches
    competitions = _to_dicts(
        conn.execute("SELECT DISTINCT league FROM matches").fetchall()
    )

    league_map = {}  # competition name -> league_id
    for comp in competitions:
        comp_name = comp["league"]
        invite_code = secrets.token_urlsafe(6)
        cur = conn.execute(
            """INSERT INTO leagues (name, competition, invite_code, created_by)
               VALUES (?, ?, ?, ?)""",
            (f"Bolão {comp_name}", comp_name, invite_code, admin_id),
        )
        lg_id = cur.lastrowid
        league_map[comp_name] = lg_id

        # Create league scoring with global config values
        if global_config:
            conn.execute(
                """INSERT INTO league_scoring (league_id, exact_score, correct_winner_goal_diff,
                   correct_winner, correct_draw, wrong) VALUES (?, ?, ?, ?, ?, ?)""",
                (lg_id, global_config["exact_score"], global_config["correct_winner_goal_diff"],
                 global_config["correct_winner"], global_config["correct_draw"], global_config["wrong"]),
            )

    # Add all users to all default leagues
    all_users = _to_dicts(conn.execute("SELECT id FROM users").fetchall())
    for lg_id in league_map.values():
        for u in all_users:
            role = "admin" if u["id"] == admin_id else "member"
            conn.execute(
                "INSERT OR IGNORE INTO league_members (league_id, user_id, role) VALUES (?, ?, ?)",
                (lg_id, u["id"], role),
            )

    # Assign league_id to existing bets based on match competition
    for comp_name, lg_id in league_map.items():
        conn.execute(
            """UPDATE bets SET league_id = ?
               WHERE league_id IS NULL
               AND match_id IN (SELECT id FROM matches WHERE league = ?)""",
            (lg_id, comp_name),
        )

    conn.commit()


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
            "SELECT id, username, is_admin, avatar_url FROM users ORDER BY username"
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
        conn.execute("DELETE FROM league_members WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return True


def update_username(user_id: int, new_username: str) -> bool:
    """Update a user's username. Returns False if the new name is already taken."""
    with get_conn() as conn:
        existing = _to_dict(
            conn.execute(
                "SELECT id FROM users WHERE username = ? AND id != ?",
                (new_username, user_id),
            ).fetchone()
        )
        if existing:
            return False
        conn.execute(
            "UPDATE users SET username = ? WHERE id = ?",
            (new_username, user_id),
        )
        return True


def update_password(user_id: int, new_password_hash: str):
    """Update a user's password hash."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_password_hash, user_id),
        )


def update_user_avatar(user_id: int, avatar_url: str):
    """Update a user's avatar URL."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET avatar_url = ? WHERE id = ?",
            (avatar_url, user_id),
        )


# ─── Match operations ─────────────────────────────────────────────────────────

def add_match(round_number: int, home_team: str, away_team: str, match_time: str, league: str = "Brasileirão") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO matches (league, round_number, home_team, away_team, match_time) VALUES (?, ?, ?, ?, ?)",
            (league, round_number, home_team, away_team, match_time),
        )
        return cur.lastrowid


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
    """Set result and calculate points for all bets on this match across all leagues."""
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
    """Calculate points for all bets on a match, using each bet's league scoring config."""
    bets = _to_dicts(
        conn.execute("SELECT * FROM bets WHERE match_id = ?", (match_id,)).fetchall()
    )
    # Cache scoring configs per league
    scoring_cache = {}
    for bet in bets:
        league_id = bet.get("league_id")
        if league_id and league_id not in scoring_cache:
            config = _to_dict(
                conn.execute("SELECT * FROM league_scoring WHERE league_id = ?", (league_id,)).fetchone()
            )
            if config:
                scoring_cache[league_id] = config

        # Use league scoring if available, else fall back to global
        config = scoring_cache.get(league_id)
        if not config:
            config = _to_dict(
                conn.execute("SELECT * FROM scoring_config WHERE id = 1").fetchone()
            )

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

def upsert_bet(user_id: int, match_id: int, league_id: int, home_score: int, away_score: int) -> bool:
    """Insert or update a bet for a specific league. Returns False if match already started."""
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
            """INSERT INTO bets (user_id, match_id, league_id, home_score, away_score, updated_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(user_id, match_id, league_id) DO UPDATE SET
                   home_score = excluded.home_score,
                   away_score = excluded.away_score,
                   updated_at = datetime('now')
            """,
            (user_id, match_id, league_id, home_score, away_score),
        )
        return True


def get_user_bets(user_id: int, league_id: int = None) -> dict[int, dict]:
    """Returns {match_id: bet_dict}. If league_id given, scoped to that league."""
    with get_conn() as conn:
        if league_id:
            rows = _to_dicts(
                conn.execute(
                    "SELECT * FROM bets WHERE user_id = ? AND league_id = ?",
                    (user_id, league_id),
                ).fetchall()
            )
        else:
            rows = _to_dicts(
                conn.execute("SELECT * FROM bets WHERE user_id = ?", (user_id,)).fetchall()
            )
        return {r["match_id"]: r for r in rows}


def get_all_bets_for_match(match_id: int, league_id: int = None) -> list[dict]:
    """Returns all bets for a match joined with username. Optionally scoped to league."""
    with get_conn() as conn:
        if league_id:
            rows = conn.execute(
                """SELECT b.id, b.user_id, u.username, b.home_score, b.away_score,
                          b.points_awarded, b.league_id
                   FROM bets b
                   JOIN users u ON u.id = b.user_id
                   WHERE b.match_id = ? AND b.league_id = ?
                   ORDER BY u.username""",
                (match_id, league_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT b.id, b.user_id, u.username, b.home_score, b.away_score,
                          b.points_awarded, b.league_id
                   FROM bets b
                   JOIN users u ON u.id = b.user_id
                   WHERE b.match_id = ?
                   ORDER BY u.username""",
                (match_id,),
            ).fetchall()
        return _to_dicts(rows)


# ─── League operations ────────────────────────────────────────────────────────

def create_league(name: str, competition: str, created_by: int,
                  start_date: str | None = None, end_date: str | None = None) -> dict:
    """Create a new league, add creator as admin, add bots, create scoring config."""
    invite_code = secrets.token_urlsafe(6)
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO leagues (name, competition, invite_code, created_by, start_date, end_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, competition, invite_code, created_by, start_date, end_date),
        )
        league_id = cur.lastrowid

        # Create league scoring with defaults
        conn.execute(
            "INSERT INTO league_scoring (league_id) VALUES (?)",
            (league_id,),
        )

        # Add creator as admin
        conn.execute(
            "INSERT INTO league_members (league_id, user_id, role) VALUES (?, ?, 'admin')",
            (league_id, created_by),
        )

        # Auto-add bot users
        for bot_name in ("Olavo", "PVC"):
            bot = _to_dict(
                conn.execute("SELECT id FROM users WHERE username = ?", (bot_name,)).fetchone()
            )
            if bot and bot["id"] != created_by:
                conn.execute(
                    "INSERT OR IGNORE INTO league_members (league_id, user_id, role) VALUES (?, ?, 'member')",
                    (league_id, bot["id"]),
                )

        return {
            "id": league_id, "name": name, "competition": competition,
            "invite_code": invite_code, "created_by": created_by,
            "start_date": start_date, "end_date": end_date,
        }


def get_league_by_invite_code(invite_code: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM leagues WHERE invite_code = ?", (invite_code,)
        ).fetchone()
        return _to_dict(row) if row else None


def get_league_by_id(league_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM leagues WHERE id = ?", (league_id,)
        ).fetchone()
        return _to_dict(row) if row else None


def update_league(league_id: int, name: str, start_date: str | None, end_date: str | None):
    with get_conn() as conn:
        conn.execute(
            "UPDATE leagues SET name = ?, start_date = ?, end_date = ? WHERE id = ?",
            (name, start_date, end_date, league_id),
        )


def delete_league(league_id: int):
    """Delete a league and all associated data."""
    with get_conn() as conn:
        conn.execute("DELETE FROM bets WHERE league_id = ?", (league_id,))
        conn.execute("DELETE FROM league_scoring WHERE league_id = ?", (league_id,))
        conn.execute("DELETE FROM league_members WHERE league_id = ?", (league_id,))
        conn.execute("DELETE FROM leagues WHERE id = ?", (league_id,))


def get_all_leagues() -> list[dict]:
    """Get all leagues (for site admin). Includes member count and creator username."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT l.*,
                   (SELECT COUNT(*) FROM league_members WHERE league_id = l.id) as member_count,
                   (SELECT username FROM users WHERE id = l.created_by) as creator_name
            FROM leagues l
            ORDER BY l.name
        """).fetchall()
        return _to_dicts(rows)


# ─── League membership ────────────────────────────────────────────────────────

def join_league(league_id: int, user_id: int) -> bool:
    """Add user to league. Returns False if already a member."""
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO league_members (league_id, user_id, role) VALUES (?, ?, 'member')",
                (league_id, user_id),
            )
            return True
        except Exception:
            return False


def leave_league(league_id: int, user_id: int) -> bool:
    """Remove user from league. Prevents league admin from leaving."""
    with get_conn() as conn:
        row = _to_dict(conn.execute(
            "SELECT role FROM league_members WHERE league_id = ? AND user_id = ?",
            (league_id, user_id),
        ).fetchone())
        if not row or row["role"] == "admin":
            return False
        conn.execute(
            "DELETE FROM league_members WHERE league_id = ? AND user_id = ?",
            (league_id, user_id),
        )
        # Also remove their bets in this league
        conn.execute(
            "DELETE FROM bets WHERE league_id = ? AND user_id = ?",
            (league_id, user_id),
        )
        return True


def remove_league_member(league_id: int, user_id: int) -> bool:
    """League admin removes a member. Cannot remove the admin."""
    return leave_league(league_id, user_id)


def get_user_leagues(user_id: int) -> list[dict]:
    """Get all leagues a user belongs to, with member count and role."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT l.*, lm.role,
                   (SELECT COUNT(*) FROM league_members WHERE league_id = l.id) as member_count
            FROM leagues l
            JOIN league_members lm ON lm.league_id = l.id
            WHERE lm.user_id = ?
            ORDER BY l.name
        """, (user_id,)).fetchall()
        return _to_dicts(rows)


def get_league_members(league_id: int) -> list[dict]:
    """Get all members of a league with their user info."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT u.id as user_id, u.username, u.avatar_url, lm.role, lm.joined_at
            FROM league_members lm
            JOIN users u ON u.id = lm.user_id
            WHERE lm.league_id = ?
            ORDER BY lm.role DESC, u.username
        """, (league_id,)).fetchall()
        return _to_dicts(rows)


def is_league_member(league_id: int, user_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM league_members WHERE league_id = ? AND user_id = ?",
            (league_id, user_id),
        ).fetchone()
        return row is not None


def get_league_member_role(league_id: int, user_id: int) -> str | None:
    """Returns 'admin', 'member', or None if not a member."""
    with get_conn() as conn:
        row = _to_dict(conn.execute(
            "SELECT role FROM league_members WHERE league_id = ? AND user_id = ?",
            (league_id, user_id),
        ).fetchone())
        return row["role"] if row else None


# ─── League scoring ───────────────────────────────────────────────────────────

def get_league_scoring(league_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM league_scoring WHERE league_id = ?", (league_id,)
        ).fetchone()
        return _to_dict(row) if row else None


def update_league_scoring(league_id: int, exact_score: int, correct_winner_goal_diff: int,
                          correct_winner: int, correct_draw: int, wrong: int):
    """Update scoring config for a league and recalculate all points."""
    with get_conn() as conn:
        conn.execute(
            """UPDATE league_scoring SET
                exact_score = ?, correct_winner_goal_diff = ?,
                correct_winner = ?, correct_draw = ?, wrong = ?
               WHERE league_id = ?""",
            (exact_score, correct_winner_goal_diff, correct_winner, correct_draw, wrong, league_id),
        )
    # Recalculate all points for this league
    recalculate_league_points(league_id)


def recalculate_league_points(league_id: int):
    """Recalculate points for all bets in a league using its scoring config."""
    with get_conn() as conn:
        config = _to_dict(
            conn.execute("SELECT * FROM league_scoring WHERE league_id = ?", (league_id,)).fetchone()
        )
        if not config:
            return

        bets = _to_dicts(conn.execute("""
            SELECT b.*, m.home_score as real_home, m.away_score as real_away
            FROM bets b
            JOIN matches m ON m.id = b.match_id
            WHERE b.league_id = ? AND m.is_finished = 1
        """, (league_id,)).fetchall())

        for bet in bets:
            points = _score_bet(
                bet["home_score"], bet["away_score"],
                bet["real_home"], bet["real_away"],
                config,
            )
            conn.execute(
                "UPDATE bets SET points_awarded = ? WHERE id = ?",
                (points, bet["id"]),
            )


# ─── League-scoped queries ───────────────────────────────────────────────────

def _get_league_match_filter(league: dict) -> tuple[str, list]:
    """Build SQL WHERE conditions for matches in a league's scope.
    Returns (where_clause, params) to append to a query."""
    conditions = ["m.league = ?"]
    params = [league["competition"]]
    if league.get("start_date"):
        conditions.append("m.match_time >= ?")
        params.append(league["start_date"])
    if league.get("end_date"):
        conditions.append("m.match_time <= ?")
        params.append(league["end_date"])
    return " AND ".join(conditions), params


def get_league_upcoming_matches(league_id: int) -> list[dict]:
    """Get upcoming unfinished matches for a league's competition within date range."""
    with get_conn() as conn:
        league = _to_dict(conn.execute(
            "SELECT * FROM leagues WHERE id = ?", (league_id,)
        ).fetchone())
        if not league:
            return []

        sql = "SELECT * FROM matches m WHERE m.is_finished = 0"
        where, params = _get_league_match_filter(league)
        sql += " AND " + where
        sql += " ORDER BY m.match_time ASC"
        return _to_dicts(conn.execute(sql, tuple(params)).fetchall())


def get_league_finished_matches(league_id: int) -> list[dict]:
    """Get finished matches for a league's competition within date range."""
    with get_conn() as conn:
        league = _to_dict(conn.execute(
            "SELECT * FROM leagues WHERE id = ?", (league_id,)
        ).fetchone())
        if not league:
            return []

        sql = "SELECT * FROM matches m WHERE m.is_finished = 1"
        where, params = _get_league_match_filter(league)
        sql += " AND " + where
        sql += " ORDER BY m.match_time DESC"
        return _to_dicts(conn.execute(sql, tuple(params)).fetchall())


def get_league_leaderboard(league_id: int) -> list[dict]:
    """Leaderboard scoped to a league's members, competition, and date range."""
    with get_conn() as conn:
        league = _to_dict(conn.execute(
            "SELECT * FROM leagues WHERE id = ?", (league_id,)
        ).fetchone())
        if not league:
            return []

        # Get match IDs in scope
        match_sql = "SELECT id FROM matches m WHERE m.is_finished = 1"
        where, params = _get_league_match_filter(league)
        match_sql += " AND " + where
        match_rows = _to_dicts(conn.execute(match_sql, tuple(params)).fetchall())
        finished_match_ids = [r["id"] for r in match_rows]
        total_finished = len(finished_match_ids)

        if not finished_match_ids:
            # Return members with 0 points
            members = conn.execute("""
                SELECT u.id as user_id, u.username,
                       0 as total_points, 0 as exact_count, 0 as zero_count,
                       0 as total_bets, 0 as missed_count
                FROM users u
                JOIN league_members lm ON lm.user_id = u.id AND lm.league_id = ?
                ORDER BY u.username
            """, (league_id,)).fetchall()
            return _to_dicts(members)

        placeholders = ",".join("?" for _ in finished_match_ids)

        # Get league scoring for exact_score comparison
        scoring = _to_dict(
            conn.execute("SELECT exact_score FROM league_scoring WHERE league_id = ?", (league_id,)).fetchone()
        )
        exact_pts = scoring["exact_score"] if scoring else 10

        rows = conn.execute(f"""
            SELECT
                u.id as user_id,
                u.username,
                COALESCE(SUM(b.points_awarded), 0) as total_points,
                COALESCE(SUM(CASE WHEN b.points_awarded = ? THEN 1 ELSE 0 END), 0) as exact_count,
                COALESCE(SUM(CASE WHEN b.points_awarded = 0 THEN 1 ELSE 0 END), 0) as zero_count,
                COUNT(b.id) as total_bets,
                ? - COUNT(b.id) as missed_count
            FROM users u
            JOIN league_members lm ON lm.user_id = u.id AND lm.league_id = ?
            LEFT JOIN bets b ON b.user_id = u.id
                AND b.league_id = ?
                AND b.match_id IN ({placeholders})
                AND b.points_awarded IS NOT NULL
            GROUP BY u.id
            ORDER BY total_points DESC, exact_count DESC, u.username ASC
        """, (exact_pts, total_finished, league_id, league_id, *finished_match_ids)).fetchall()
        return _to_dicts(rows)


def get_league_leaderboard_evolution(league_id: int) -> list[dict]:
    """Returns rows of (username, match_time, points_awarded) for the league."""
    with get_conn() as conn:
        league = _to_dict(conn.execute(
            "SELECT * FROM leagues WHERE id = ?", (league_id,)
        ).fetchone())
        if not league:
            return []

        sql = """
            SELECT u.username, m.match_time, COALESCE(b.points_awarded, 0) as points_awarded
            FROM bets b
            JOIN users u ON u.id = b.user_id
            JOIN matches m ON m.id = b.match_id
            JOIN league_members lm ON lm.user_id = u.id AND lm.league_id = ?
            WHERE b.league_id = ? AND m.is_finished = 1
        """
        params = [league_id, league_id]

        # Apply date range filter
        if league.get("start_date"):
            sql += " AND m.match_time >= ?"
            params.append(league["start_date"])
        if league.get("end_date"):
            sql += " AND m.match_time <= ?"
            params.append(league["end_date"])

        sql += " ORDER BY m.match_time ASC"
        rows = conn.execute(sql, tuple(params)).fetchall()
        return _to_dicts(rows)


def get_user_avatars() -> dict[int, str]:
    """Return {user_id: avatar_url} for all users that have an avatar."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, avatar_url FROM users WHERE avatar_url IS NOT NULL AND avatar_url <> ''"
        ).fetchall()
        return {r["id"]: r["avatar_url"] for r in (_to_dicts(rows))}


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
    """Returns {match_id: odds_dict} for given match IDs."""
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


# ─── Session operations ────────────────────────────────────────────────────

def create_session(user_id: int) -> str:
    """Create a new session token for the user and return it."""
    token = secrets.token_urlsafe(32)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (user_id, token) VALUES (?, ?)",
            (user_id, token),
        )
    return token


def get_session(token: str) -> dict | None:
    """Look up a session token and return the associated user, or None."""
    with get_conn() as conn:
        row = conn.execute(
            """SELECT u.* FROM sessions s
               JOIN users u ON u.id = s.user_id
               WHERE s.token = ?""",
            (token,),
        ).fetchone()
        return _to_dict(row) if row else None


def delete_session(token: str):
    """Remove a session by token (logout)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def cleanup_old_sessions(days: int = 30):
    """Delete sessions older than the given number of days."""
    with get_conn() as conn:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        conn.execute("DELETE FROM sessions WHERE created_at < ?", (cutoff,))


