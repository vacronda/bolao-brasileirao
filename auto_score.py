"""
Auto-scoring script: fetches real match results from football-data.org
and updates the Turso database. Designed to run via GitHub Actions cron.

Usage: python auto_score.py
Env vars: TURSO_URL, TURSO_AUTH_TOKEN, FOOTBALL_API_KEY
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
API_BASE = "https://api.football-data.org/v4"

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


def api_get(path: str) -> dict:
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={"X-Auth-Token": FOOTBALL_API_KEY})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def get_finished_matches(competition: str, date_from: str, date_to: str) -> list[dict]:
    path = f"/competitions/{competition}/matches?status=FINISHED&dateFrom={date_from}&dateTo={date_to}"
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


def main():
    conn = libsql.connect(TURSO_URL, auth_token=TURSO_AUTH_TOKEN)

    # Date range: last 3 days
    today = datetime.utcnow().date()
    date_from = (today - timedelta(days=3)).isoformat()
    date_to = today.isoformat()

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

    # Build lookup: (league, home_team, away_team) -> match row
    db_lookup = {}
    for m in unfinished:
        key = (m["league"], m["home_team"], m["away_team"])
        db_lookup[key] = m

    updated = 0

    # Process each competition
    for comp_code, league_name, team_map in [
        ("PL", "Premier League", TEAM_MAP_PL),
        ("BSA", "Brasileirão", TEAM_MAP_BSA),
    ]:
        try:
            finished = get_finished_matches(comp_code, date_from, date_to)
        except Exception as e:
            print(f"Error fetching {comp_code}: {e}")
            continue

        print(f"[{comp_code}] Found {len(finished)} finished matches from API")

        for match in finished:
            api_home = match["homeTeam"]["shortName"]
            api_away = match["awayTeam"]["shortName"]
            home_name = team_map.get(api_home, api_home)
            away_name = team_map.get(api_away, api_away)

            ft = match.get("score", {}).get("fullTime", {})
            home_score = ft.get("home")
            away_score = ft.get("away")

            if home_score is None or away_score is None:
                continue

            key = (league_name, home_name, away_name)
            db_match = db_lookup.get(key)

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

    conn.commit()
    print(f"\nDone. Updated {updated} match(es).")


if __name__ == "__main__":
    main()
