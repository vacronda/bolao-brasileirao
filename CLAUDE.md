# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
# Install dependencies (Python 3.12)
pip install -r requirements.txt

# Run locally (uses local bolao.db when Turso env vars are absent)
python app.py

# Production (Railway/Render)
gunicorn app:app --bind 0.0.0.0:${PORT:-8080}
```

**Environment variables** (set in `.env` or hosting platform):
- `SECRET_KEY` — Flask session signing key (required in production)
- `TURSO_URL` / `TURSO_AUTH_TOKEN` — Turso database (omit for local SQLite fallback)
- `FOOTBALL_API_KEY` — football-data.org (for auto_score.py)
- `ODDS_API_KEY` — The Odds API (optional, for auto_score.py)

**Auto-scoring cron** (runs every 3h via GitHub Actions, or manually):
```bash
python auto_score.py
```

**No test suite exists.** Verify changes by running the app and testing routes manually.

## Architecture

### Core Files
- **`app.py`** — Flask app factory (`create_app()`), all routes defined as closures inside it. `app = create_app()` at module level for gunicorn.
- **`db.py`** — All database access. Dual-mode: Turso (cloud libSQL) when env vars are set, local SQLite otherwise. Uses `_ConnWrapper`/`_DictCursor` to normalize row access as dicts across both backends. Every public function uses `with get_conn() as conn:`.
- **`auth.py`** — bcrypt hashing, Flask session/cookie auth via DB-backed tokens in `sessions` table. Three decorators: `@login_required`, `@admin_required`, `@league_member_required`.
- **`auto_score.py`** — Standalone script (does NOT use `db.py`). Connects to Turso directly with raw SQL. Scores matches, syncs kick-off times, fetches odds, places bot bets. Scoring logic is duplicated from `db.py._score_bet()`.

### League System
Leagues are the central organizing concept. Each league references a competition (`"Brasileirão"` or `"Premier League"`) and optionally scopes matches by date range.

Key design decisions:
- **Bets are per-league**: `UNIQUE(user_id, match_id, league_id)` — same user can bet differently on the same match across leagues
- **Scoring is per-league**: `league_scoring` table stores point values per league. Changing scoring immediately recalculates all bets for that league
- **Two admin levels**: site admin (`users.is_admin=1`) and league admin (`league_members.role='admin'`)
- **Bot users** (Olavo, PVC) are auto-added to every new league. Olavo uses seeded random; PVC uses odds-based logic
- `_get_league_match_filter()` builds the SQL WHERE clause (competition + date range) used by all league-scoped queries

### Auth Flow
1. Login creates a random token stored in both the `sessions` DB table and Flask's signed cookie
2. `@app.before_request` calls `restore_session()` → reads token → looks up user → sets `g.user`
3. Context processor injects `user_leagues`, `active_league` into all templates
4. `session["active_league_id"]` tracks the selected league in the navbar dropdown

### Route Groups
- **Public**: `/`, `/login`, `/register`, `/logout`, `/join/<invite_code>`
- **Profile**: `/profile` (change username, password, avatar)
- **League CRUD**: `/leagues`, `/league/create`, `/league/join`
- **League-scoped** (require membership): `/league/<id>`, `/league/<id>/bets`, `/league/<id>/leaderboard`, `/league/<id>/settings`, `/league/<id>/delete`
- **Admin** (site admin only): `/admin` (tabbed: matches, add, results, users, leagues)

## Important Conventions

- **Language**: All UI text and flash messages are in Brazilian Portuguese (pt-BR)
- **Flash categories**: `"success"`, `"warning"`, `"danger"`, `"info"`
- **Templates**: All extend `base.html`. League routes pass `league`, `leaderboard`, `avatars`, `upcoming_matches`, `user_bets`, `logos`, `odds`, `league_role`
- **Match times**: Stored as naive ISO strings. Locking uses `datetime.now()` comparison. BRT for Brasileirão, UTC for Premier League — timezone handling is imprecise
- **Competitions are hard-coded** to `"Brasileirão"` and `"Premier League"` — validated at league creation, must match `matches.league` column
- **`scoring_config` table (global, singleton)** is legacy. `auto_score.py` uses it as fallback. New code should use per-league `league_scoring`
- **`auto_score.py` has its own team name maps** (`TEAM_MAP_PL`, `TEAM_MAP_BSA`, `ODDS_TEAM_MAP_*`) to translate API names to DB names. Update these when teams change

## CI/CD

Only pipeline: `.github/workflows/auto_score.yml` — GitHub Actions cron every 3 hours + manual dispatch. No build/test/deploy pipeline. Deployment is manual via `railway up` or git push to hosting platform.
