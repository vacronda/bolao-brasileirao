"""
Auto-scoring script: fetches real match results from football-data.org,
syncs kick-off times, and fetches betting odds from The Odds API.
Designed to run via GitHub Actions cron.

Usage: python auto_score.py
Env vars: TURSO_URL, TURSO_AUTH_TOKEN, FOOTBALL_API_KEY, ODDS_API_KEY (optional)
"""

import os
import json
import urllib.request
from datetime import datetime, timedelta

import libsql_experimental as libsql

# ─── Config ───────────────────────────────────────────────────────────────────

TURSO_URL = os.environ["TURSO_URL"]
TURSO_AUTH_TOKEN = os.environ["TURSO_AUTH_TOKEN"]
FOOTBALL_API_KEY = os.environ["FOOTBALL_API_KEY"]
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")
API_BASE = "https://api.football-data.org/v4"
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# Map from football-data.org shortName → our DB team name
TEAM_MAP_PL = {
    "Arsenal": "Arsenal",
    "Aston Villa": "Aston Villa",
    "Chelsea": "Chelsea",
    "Everton": "Everton",
    "Fulham": "Fulham",
    "Liverpool": "Liverpool",
    "Man City": "Man City",
    "Man United": "Man Utd",
    "Newcastle": "Newcastle",
    "Sunderland": "Sunderland",
    "Tottenham": "Spurs",
    "Wolverhampton": "Wolves",
    "Burnley": "Burnley",
    "Leeds United": "Leeds",
    "Nottingham": "Nottingham Forest",
    "Crystal Palace": "Crystal Palace",
    "Brighton Hove": "Brighton",
    "Brentford": "Brentford",
    "West Ham": "West Ham",
    "Bournemouth": "Bournemouth",
}

TEAM_MAP_BSA = {
    "Fluminense": "Fluminense",
    "Mineiro": "Atlético-MG",
    "Grêmio": "Grêmio",
    "Paranaense": "Athletico-PR",
    "Palmeiras": "Palmeiras",
    "Botafogo": "Botafogo",
    "Cruzeiro": "Cruzeiro",
    "Chapecoense": "Chapecoense",
    "São Paulo": "São Paulo",
    "Bahia": "Bahia",
    "Corinthians": "Corinthians",
    "Vasco da Gama": "Vasco",
    "Vitória": "Vitória",
    "Flamengo": "Flamengo",
    "Coritiba": "Coritiba",
    "Bragantino": "Red Bull Bragantino",
    "Clube do Remo": "Remo",
    "Mirassol": "Mirassol",
    "Internacional": "Internacional",
    "Santos": "Santos",
}

# Map from The Odds API team names → our DB team names
ODDS_TEAM_MAP_PL = {
    "Arsenal": "Arsenal",
    "Aston Villa": "Aston Villa",
    "Chelsea": "Chelsea",
    "Everton": "Everton",
    "Fulham": "Fulham",
    "Liverpool": "Liverpool",
    "Manchester City": "Man City",
    "Manchester United": "Man Utd",
    "Newcastle United": "Newcastle",
    "Sunderland": "Sunderland",
    "Tottenham Hotspur": "Spurs",
    "Wolverhampton Wanderers": "Wolves",
    "Burnley": "Burnley",
    "Leeds United": "Leeds",
    "Nottingham Forest": "Nottingham Forest",
    "Crystal Palace": "Crystal Palace",
    "Brighton and Hove Albion": "Brighton",
    "Brentford": "Brentford",
    "West Ham United": "West Ham",
    "AFC Bournemouth": "Bournemouth",
    "Ipswich Town": "Ipswich",
    "Leicester City": "Leicester",
    "Southampton": "Southampton",
}

ODDS_TEAM_MAP_BSA = {
    "Fluminense": "Fluminense",
    "Atletico Mineiro": "Atlético-MG",
    "Gremio": "Grêmio",
    "Athletico Paranaense": "Athletico-PR",
    "Atletico Paranaense": "Athletico-PR",
    "Palmeiras": "Palmeiras",
    "Botafogo": "Botafogo",
    "Cruzeiro": "Cruzeiro",
    "Chapecoense": "Chapecoense",
    "Sao Paulo": "São Paulo",
    "Bahia": "Bahia",
    "Corinthians": "Corinthians",
    "Vasco da Gama": "Vasco",
    "Vitoria": "Vitória",
    "Flamengo": "Flamengo",
    "Coritiba": "Coritiba",
    "Red Bull Bragantino": "Red Bull Bragantino",
    "Bragantino-SP": "Red Bull Bragantino",
    "Mirassol": "Mirassol",
    "Internacional": "Internacional",
    "Santos": "Santos",
    "Sport Recife": "Sport",
    "Ceara": "Ceará",
    "Fortaleza EC": "Fortaleza",
    "Juventude": "Juventude",
    "Goias": "Goiás",
}


def api_get(path: str) -> dict:
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={"X-Auth-Token": FOOTBALL_API_KEY})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def get_matches_by_status(competition: str, status: str, date_from: str, date_to: str) -> list[dict]:
    path = f"/competitions/{competition}/matches?status={status}&dateFrom={date_from}&dateTo={date_to}"
    data = api_get(path)
    return data.get("matches", [])


def score_bet(pred_h, pred_a, real_h, real_a, config):
    if pred_h == real_h and pred_a == real_a:
        return config["exact_score"]
    pred_diff = pred_h - pred_a
    real_diff = real_h - real_a
    pred_out = (1 if pred_h > pred_a else (-1 if pred_h < pred_a else 0))
    real_out = (1 if real_h > real_a else (-1 if real_h < real_a else 0))
    if pred_out == real_out and pred_diff == real_diff and pred_out != 0:
        return config["correct_winner_goal_diff"]
    if pred_out == real_out and pred_out != 0:
        return config["correct_winner"]
    if pred_out == 0 and real_out == 0:
        return config["correct_draw"]
    return config["wrong"]


def odds_api_get(sport_key: str) -> list[dict]:
    """Fetch odds from The Odds API for a given sport."""
    url = (
        f"{ODDS_API_BASE}/sports/{sport_key}/odds/"
        f"?apiKey={ODDS_API_KEY}&regions=eu&markets=h2h&oddsFormat=decimal"
    )
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def fetch_and_store_odds(conn, unfinished):
    """Fetch odds from The Odds API and store them in match_odds table."""
    if not ODDS_API_KEY:
        print("[ODDS] No ODDS_API_KEY set, skipping odds fetch.")
        return

    # Build lookup: (league, home_team, away_team) -> match row
    db_lookup = {}
    for m in unfinished:
        key = (m["league"], m["home_team"], m["away_team"])
        db_lookup[key] = m

    odds_updated = 0

    for sport_key, league_name, team_map in [
        ("soccer_epl", "Premier League", ODDS_TEAM_MAP_PL),
        ("soccer_brazil_campeonato", "Brasileirão", ODDS_TEAM_MAP_BSA),
    ]:
        try:
            events = odds_api_get(sport_key)
        except Exception as e:
            print(f"[ODDS] Error fetching {sport_key}: {e}")
            continue

        print(f"[ODDS] {sport_key}: {len(events)} events from API")

        for event in events:
            api_home = event.get("home_team", "")
            api_away = event.get("away_team", "")
            home_name = team_map.get(api_home, api_home)
            away_name = team_map.get(api_away, api_away)

            db_match = db_lookup.get((league_name, home_name, away_name))
            if not db_match:
                continue

            # Get the first bookmaker's h2h odds
            bookmakers = event.get("bookmakers", [])
            if not bookmakers:
                continue

            bk = bookmakers[0]
            bookmaker_name = bk.get("title", "Unknown")
            h2h_market = None
            for market in bk.get("markets", []):
                if market.get("key") == "h2h":
                    h2h_market = market
                    break

            if not h2h_market:
                continue

            outcomes = {o["name"]: o["price"] for o in h2h_market.get("outcomes", [])}
            home_win = outcomes.get(api_home)
            draw_odds = outcomes.get("Draw")
            away_win = outcomes.get(api_away)

            if home_win is None or draw_odds is None or away_win is None:
                continue

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
                (db_match["id"], home_win, draw_odds, away_win, bookmaker_name),
            )
            odds_updated += 1
            print(f"  📊 {home_name} vs {away_name}: {home_win} | {draw_odds} | {away_win} ({bookmaker_name})")

    print(f"[ODDS] Updated odds for {odds_updated} match(es).")


def main():
    conn = libsql.connect(TURSO_URL, auth_token=TURSO_AUTH_TOKEN)

    today = datetime.utcnow().date()
    # For finished matches: look back 3 days
    date_from_finished = (today - timedelta(days=3)).isoformat()
    # For scheduled matches: look ahead 30 days
    date_to_scheduled = (today + timedelta(days=30)).isoformat()
    date_today = today.isoformat()

    # Get scoring config
    row = conn.execute("SELECT * FROM scoring_config WHERE id = 1").fetchone()
    cols = [d[0] for d in conn.execute("SELECT * FROM scoring_config WHERE id = 1").description]
    config = dict(zip(cols, row))

    # Get all unfinished matches from our DB
    cur = conn.execute("SELECT * FROM matches WHERE is_finished = 0")
    db_cols = [d[0] for d in cur.description]
    unfinished = [dict(zip(db_cols, r)) for r in cur.fetchall()]

    if not unfinished:
        print("No unfinished matches in DB.")
        return

    # Build lookup: (league, round, home_team, away_team) -> match row
    # Also keep a fallback by (league, home_team, away_team) for unique matchups
    db_lookup = {}
    db_lookup_no_round = {}
    for m in unfinished:
        rnd = m.get("round_number")
        key = (m["league"], rnd, m["home_team"], m["away_team"])
        db_lookup[key] = m
        team_key = (m["league"], m["home_team"], m["away_team"])
        # Only use fallback if the matchup is unique (no duplicate home/away)
        if team_key in db_lookup_no_round:
            db_lookup_no_round[team_key] = None  # mark ambiguous
        else:
            db_lookup_no_round[team_key] = m

    updated = 0
    times_updated = 0

    # Process each competition
    for comp_code, league_name, team_map in [
        ("PL", "Premier League", TEAM_MAP_PL),
        ("BSA", "Brasileirão", TEAM_MAP_BSA),
    ]:
        # ── 1. Score finished matches ──────────────────────────────────────
        try:
            finished = get_matches_by_status(comp_code, "FINISHED", date_from_finished, date_today)
        except Exception as e:
            print(f"Error fetching finished {comp_code}: {e}")
            finished = []

        print(f"[{comp_code}] Found {len(finished)} finished matches from API")

        for match in finished:
            api_home = match["homeTeam"]["shortName"]
            api_away = match["awayTeam"]["shortName"]
            home_name = team_map.get(api_home, api_home)
            away_name = team_map.get(api_away, api_away)
            matchday = match.get("matchday")

            ft = match.get("score", {}).get("fullTime", {})
            home_score = ft.get("home")
            away_score = ft.get("away")

            if home_score is None or away_score is None:
                continue

            # Try round-specific lookup first, then unique fallback
            db_match = db_lookup.get((league_name, matchday, home_name, away_name))
            if not db_match:
                fb = db_lookup_no_round.get((league_name, home_name, away_name))
                if fb is not None:
                    db_match = fb

            if not db_match:
                continue

            # Update match result
            conn.execute(
                "UPDATE matches SET home_score = ?, away_score = ?, is_finished = 1 WHERE id = ?",
                (home_score, away_score, db_match["id"]),
            )

            # Calculate points for all bets on this match
            bet_cur = conn.execute("SELECT * FROM bets WHERE match_id = ?", (db_match["id"],))
            bet_cols = [d[0] for d in bet_cur.description]
            bets = [dict(zip(bet_cols, r)) for r in bet_cur.fetchall()]

            for bet in bets:
                pts = score_bet(
                    bet["home_score"], bet["away_score"],
                    home_score, away_score,
                    config,
                )
                conn.execute(
                    "UPDATE bets SET points_awarded = ? WHERE id = ?",
                    (pts, bet["id"]),
                )

            updated += 1
            print(f"  ✓ {home_name} {home_score}-{away_score} {away_name}")

        # ── 2. Sync kick-off times for upcoming matches ────────────────────
        try:
            scheduled = get_matches_by_status(comp_code, "SCHEDULED,TIMED", date_today, date_to_scheduled)
        except Exception as e:
            print(f"Error fetching scheduled {comp_code}: {e}")
            scheduled = []

        for match in scheduled:
            api_home = match["homeTeam"]["shortName"]
            api_away = match["awayTeam"]["shortName"]
            home_name = team_map.get(api_home, api_home)
            away_name = team_map.get(api_away, api_away)
            matchday = match.get("matchday")

            # Try round-specific lookup first, then unique fallback
            db_match = db_lookup.get((league_name, matchday, home_name, away_name))
            if not db_match:
                fb = db_lookup_no_round.get((league_name, home_name, away_name))
                if fb is not None:
                    db_match = fb

            if not db_match:
                continue

            # API returns UTC datetime like "2026-02-18T20:00:00Z"
            api_time = match.get("utcDate", "")
            if not api_time:
                continue

            # Convert to "YYYY-MM-DD HH:MM" format used in our DB
            new_time = api_time.replace("T", " ").replace("Z", "")[:16]
            old_time = db_match["match_time"][:16]

            if new_time != old_time:
                conn.execute(
                    "UPDATE matches SET match_time = ? WHERE id = ?",
                    (new_time, db_match["id"]),
                )
                times_updated += 1
                print(f"  🕐 {home_name} vs {away_name}: {old_time} → {new_time}")

        if scheduled:
            print(f"[{comp_code}] Checked {len(scheduled)} upcoming matches for time changes")

    # ── 3. Fetch betting odds ──────────────────────────────────────────
    # Re-fetch unfinished matches (some may have been marked finished above)
    cur2 = conn.execute("SELECT * FROM matches WHERE is_finished = 0")
    db_cols2 = [d[0] for d in cur2.description]
    still_unfinished = [dict(zip(db_cols2, r)) for r in cur2.fetchall()]
    fetch_and_store_odds(conn, still_unfinished)

    conn.commit()
    print(f"\nDone. Updated {updated} result(s), {times_updated} match time(s).")


if __name__ == "__main__":
    main()
