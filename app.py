"""
Bolão do Brasileirão - Soccer Betting Pool.
Main Streamlit application.
"""

import streamlit as st
from datetime import datetime, timedelta

import db
import auth

# ─── Page Config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Bolão do Brasileirão",
    page_icon="⚽",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    /* ── Base ─────────────────────────────────────────────────────── */
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .block-container { padding-top: 0.5rem; padding-bottom: 1rem; max-width: 720px; }
    #MainMenu, footer { visibility: hidden; }
    [data-testid="stSidebar"] { min-width: 200px; max-width: 260px; }
    .stNumberInput > div > div > input { text-align: center; font-weight: 600; font-size: 1.05rem; }

    /* ── Hero banner (logged out) ─────────────────────────────────── */
    .hero {
        background: linear-gradient(135deg, #1b1b2f 0%, #162447 60%, #1f4037 100%);
        color: white; padding: 2.5rem 1.5rem; border-radius: 14px;
        text-align: center; margin-bottom: 1.2rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    }
    .hero h1 { font-size: 2.2rem; margin: 0; color: white; font-weight: 800; letter-spacing: -0.5px; }
    .hero p { font-size: 0.95rem; margin: 0.5rem 0 0; color: #b0bec5; font-weight: 400; }

    /* ── Welcome bar (logged in) ──────────────────────────────────── */
    .welcome-bar {
        background: linear-gradient(135deg, #1b1b2f 0%, #162447 60%, #1f4037 100%);
        color: white; padding: 1rem 1.5rem; border-radius: 12px;
        margin-bottom: 1rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    }
    .welcome-bar h2 { font-size: 1.3rem; margin: 0; color: white; font-weight: 700; }
    .welcome-bar p { margin: 0.15rem 0 0; font-size: 0.85rem; color: #b0bec5; }

    /* ── Section headers ──────────────────────────────────────────── */
    .section-header {
        display: flex; align-items: center; gap: 8px;
        margin: 1.5rem 0 0.6rem; padding-bottom: 6px;
        border-bottom: 3px solid #00a86b;
    }
    .section-header span { font-size: 1rem; font-weight: 700; color: #222; text-transform: uppercase; letter-spacing: 0.5px; }

    /* ── League label ─────────────────────────────────────────────── */
    .league-label {
        display: inline-flex; align-items: center; gap: 6px;
        background: #222; color: white; padding: 4px 12px; border-radius: 6px;
        font-size: 0.8rem; font-weight: 600; margin: 10px 0 6px;
        text-transform: uppercase; letter-spacing: 0.3px;
    }
    .league-label.brasileirao { background: #00a86b; }
    .league-label.premier { background: #3d185b; }

    /* ── Match card (home preview, read-only) ─────────────────────── */
    .match-card {
        background: #fff; border-radius: 10px; padding: 12px 16px;
        margin-bottom: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        display: flex; align-items: center; justify-content: space-between;
        border-left: 4px solid #e0e0e0; transition: box-shadow 0.15s;
    }
    .match-card:hover { box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
    .match-card.brasileirao { border-left-color: #00a86b; }
    .match-card.premier { border-left-color: #3d185b; }
    .match-card.locked { opacity: 0.55; }
    .mc-teams { font-weight: 600; font-size: 0.92rem; color: #222; }
    .mc-meta { font-size: 0.75rem; color: #999; font-weight: 500; }

    /* ── Leaderboard table ────────────────────────────────────────── */
    .lb-table { width: 100%; border-collapse: separate; border-spacing: 0 4px; }
    .lb-table th {
        text-align: left; font-size: 0.7rem; text-transform: uppercase;
        color: #999; font-weight: 600; padding: 0 12px 4px; letter-spacing: 0.5px;
    }
    .lb-table th:last-child, .lb-table td:last-child { text-align: right; }
    .lb-table td {
        background: #fff; padding: 10px 12px; font-size: 0.9rem;
    }
    .lb-table tr td:first-child { border-radius: 8px 0 0 8px; }
    .lb-table tr td:last-child { border-radius: 0 8px 8px 0; }
    .lb-table tr { box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
    .lb-rank-cell { font-weight: 800; font-size: 1rem; width: 40px; text-align: center !important; }
    .lb-name-cell { font-weight: 600; color: #222; }
    .lb-pts-cell { font-weight: 700; color: #00a86b; }
    .lb-exact-cell { font-size: 0.8rem; color: #888; }
    .lb-stat-cell { font-size: 0.8rem; color: #888; text-align: center !important; }
    .lb-me td { background: #e8f8f0; }
    .lb-top1 td:first-child { border-left: 4px solid #f5c518; }
    .lb-top2 td:first-child { border-left: 4px solid #aaa; }
    .lb-top3 td:first-child { border-left: 4px solid #cd7f32; }

    /* ── Scoring rules card ───────────────────────────────────────── */
    .rules-grid {
        display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 4px;
    }
    .rule-chip {
        background: #fff; border-radius: 8px; padding: 10px 14px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06); text-align: center;
    }
    .rule-chip .pts { font-size: 1.3rem; font-weight: 800; color: #00a86b; }
    .rule-chip .label { font-size: 0.72rem; color: #666; margin-top: 2px; }

    /* ── Odds display ────────────────────────────────────────────── */
    .odds-row {
        display: flex; align-items: center; justify-content: center; gap: 6px;
        margin-top: 4px;
    }
    .odds-badge {
        background: #f0f2f5; border-radius: 5px; padding: 2px 8px;
        font-size: 0.72rem; font-weight: 600; color: #555;
        text-align: center; min-width: 40px;
    }
    .odds-badge.home { color: #1a7f4b; background: #e6f5ed; }
    .odds-badge.draw { color: #7a6b00; background: #fef9e7; }
    .odds-badge.away { color: #6b1a1a; background: #fce8e8; }
    .odds-label { font-size: 0.62rem; color: #999; font-weight: 500; }
    .odds-source { font-size: 0.58rem; color: #bbb; margin-left: 4px; }
</style>
""", unsafe_allow_html=True)

# ─── Init DB ───────────────────────────────────────────────────────────────────

db.init_db()

# ─── Sidebar Navigation ───────────────────────────────────────────────────────

PAGES = ["Inicio", "Meus Palpites", "Classificacao"]

with st.sidebar:
    st.title("⚽ Bolão")

    if auth.is_logged_in():
        user = auth.get_current_user()
        st.write(f"Olá, **{user['username']}**!")
        if st.button("Sair", use_container_width=True):
            auth.logout_user()
            st.rerun()
        pages = list(PAGES)
        if auth.is_admin():
            pages.append("Admin")
        page = st.radio("Navegação", pages, index=0, label_visibility="collapsed")
    else:
        pages = [PAGES[0]]
        page = st.radio("Navegação", pages, index=0, label_visibility="collapsed")


# ─── Home Dashboard (shared widget) ──────────────────────────────────────────

def widget_upcoming_matches():
    """Show matches in the next 7 days."""
    now = datetime.now()
    cutoff = now + timedelta(days=7)
    all_upcoming = db.get_upcoming_matches()
    soon = [m for m in all_upcoming
            if now < datetime.fromisoformat(m["match_time"]) <= cutoff]

    if not soon:
        st.caption("Nenhuma partida nos próximos 7 dias.")
        return

    # Load odds for these matches
    match_ids = [m["id"] for m in soon]
    odds_map = db.get_odds_for_matches(match_ids)

    by_league: dict[str, list] = {}
    for m in soon:
        lg = m.get("league", "Brasileirão")
        by_league.setdefault(lg, []).append(m)

    for league, matches in sorted(by_league.items()):
        css_class = "brasileirao" if "Brasil" in league else "premier"
        flag = "🇧🇷" if "Brasil" in league else "🏴󠁧󠁢󠁥󠁮󠁧󠁿"
        st.markdown(f'<div class="league-label {css_class}">{flag} {league}</div>', unsafe_allow_html=True)
        for m in matches:
            match_dt = datetime.fromisoformat(m["match_time"])
            day_name = _weekday_pt(match_dt)
            date_str = match_dt.strftime(f"%d/%m ({day_name}) %H:%M")
            odds = odds_map.get(m["id"])
            st.markdown(
                f'<div class="match-card {css_class}">'
                f'<div><span class="mc-teams">{m["home_team"]} x {m["away_team"]}</span>'
                f'{_odds_html(odds)}</div>'
                f'<span class="mc-meta">R{m["round_number"] or "?"} &middot; {date_str}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )


def _odds_html(odds: dict | None) -> str:
    """Return HTML for odds display, or empty string if no odds."""
    if not odds:
        return ""
    return (
        f'<div class="odds-row">'
        f'<span class="odds-label">Odds:</span>'
        f'<span class="odds-badge home">{odds["home_win"]:.2f}</span>'
        f'<span class="odds-badge draw">{odds["draw"]:.2f}</span>'
        f'<span class="odds-badge away">{odds["away_win"]:.2f}</span>'
        f'<span class="odds-source">{odds.get("bookmaker", "")}</span>'
        f'</div>'
    )


def _weekday_pt(dt: datetime) -> str:
    days = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    return days[dt.weekday()]


def widget_leaderboard_mini():
    """Show top 5 of the leaderboard."""
    leaderboard = db.get_leaderboard()
    current_user = auth.get_current_user() if auth.is_logged_in() else None

    if not leaderboard:
        st.caption("Nenhuma pontuação registrada ainda.")
        return

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    # Decide which entries to show
    top = leaderboard[:5]
    extra_me = None
    if current_user and len(leaderboard) > 5:
        for i, entry in enumerate(leaderboard):
            if entry["user_id"] == current_user["id"] and i >= 5:
                extra_me = (i, entry)
                break

    rows_html = ""
    for i, entry in enumerate(top):
        rank = i + 1
        medal = medals.get(rank, f"{rank}.")
        is_me = current_user and entry["user_id"] == current_user["id"]
        row_class = "lb-me " if is_me else ""
        row_class += f"lb-top{rank}" if rank <= 3 else ""
        me_tag = " &#9668;" if is_me else ""
        rows_html += (
            f'<tr class="{row_class}">'
            f'<td class="lb-rank-cell">{medal}</td>'
            f'<td class="lb-name-cell">{entry["username"]}{me_tag}</td>'
            f'<td class="lb-pts-cell">{entry["total_points"]} pts</td>'
            f'</tr>'
        )

    if extra_me:
        idx, entry = extra_me
        rows_html += (
            f'<tr class="lb-me" style="border-top:2px dashed #ccc;">'
            f'<td class="lb-rank-cell">{idx+1}.</td>'
            f'<td class="lb-name-cell">{entry["username"]} &#9668;</td>'
            f'<td class="lb-pts-cell">{entry["total_points"]} pts</td>'
            f'</tr>'
        )

    st.markdown(
        f'<table class="lb-table">'
        f'<thead><tr><th></th><th>Jogador</th><th>Pontos</th></tr></thead>'
        f'<tbody>{rows_html}</tbody></table>',
        unsafe_allow_html=True,
    )


def widget_upcoming_bets():
    """Show next 7 days matches with inline betting for logged-in users."""
    user = auth.get_current_user()
    now = datetime.now()
    cutoff = now + timedelta(days=7)
    all_upcoming = db.get_upcoming_matches()
    soon = [m for m in all_upcoming
            if now < datetime.fromisoformat(m["match_time"]) <= cutoff]

    if not soon:
        st.caption("Nenhuma partida nos próximos 7 dias.")
        return

    user_bets = db.get_user_bets(user["id"])

    # Load odds for these matches
    match_ids = [m["id"] for m in soon]
    odds_map = db.get_odds_for_matches(match_ids)

    # Group by league
    by_league: dict[str, list] = {}
    for m in soon:
        lg = m.get("league", "Brasileirão")
        by_league.setdefault(lg, []).append(m)

    for league, matches in sorted(by_league.items()):
        flag = "🇧🇷" if "Brasil" in league else "🏴󠁧󠁢󠁥󠁮󠁧󠁿"
        css_class = "brasileirao" if "Brasil" in league else "premier"
        st.markdown(f'<div class="league-label {css_class}">{flag} {league}</div>', unsafe_allow_html=True)

        for m in matches:
            match_dt = datetime.fromisoformat(m["match_time"])
            is_locked = now >= match_dt
            existing = user_bets.get(m["id"])
            day_name = _weekday_pt(match_dt)
            date_str = match_dt.strftime(f"%d/%m ({day_name}) %H:%M")

            if is_locked:
                if existing:
                    score_txt = f"{existing['home_score']} x {existing['away_score']}"
                else:
                    score_txt = "- x -"
                odds = odds_map.get(m["id"])
                st.markdown(
                    f'<div class="match-card {css_class} locked">'
                    f'<div><span class="mc-teams">🔒 {m["home_team"]} {score_txt} {m["away_team"]}</span>'
                    f'{_odds_html(odds)}</div>'
                    f'<span class="mc-meta">{date_str}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                odds = odds_map.get(m["id"])
                with st.form(key=f"home_bet_{m['id']}"):
                    st.caption(f"R{m['round_number'] or '?'} · {date_str}")
                    if odds:
                        st.markdown(_odds_html(odds), unsafe_allow_html=True)
                    cols = st.columns([3, 1, 0.5, 1, 3])
                    cols[0].markdown(f"**{m['home_team']}**")
                    home_val = existing["home_score"] if existing else 0
                    away_val = existing["away_score"] if existing else 0
                    home_score = cols[1].number_input(
                        "H", min_value=0, max_value=20, value=home_val,
                        label_visibility="collapsed", key=f"hb_{m['id']}"
                    )
                    cols[2].markdown(
                        "<div style='text-align:center;padding-top:8px;font-weight:bold;'>x</div>",
                        unsafe_allow_html=True,
                    )
                    away_score = cols[3].number_input(
                        "A", min_value=0, max_value=20, value=away_val,
                        label_visibility="collapsed", key=f"ab_{m['id']}"
                    )
                    cols[4].markdown(f"**{m['away_team']}**")

                    col_btn, col_status = st.columns([1, 1])
                    submitted = col_btn.form_submit_button("Salvar", use_container_width=True)
                    if existing:
                        col_status.success("✅ Salvo")

                    if submitted:
                        ok = db.upsert_bet(user["id"], m["id"], int(home_score), int(away_score))
                        if ok:
                            st.rerun()
                        else:
                            st.error("Não foi possível salvar. A partida pode já ter começado.")


# ─── Page: Home ──────────────────────────────────────────────────────────────

def page_home():
    if auth.is_logged_in():
        user = auth.get_current_user()
        st.markdown(
            f'<div class="welcome-bar">'
            f'<div><h2>⚽ Bolão</h2><p>Olá, {user["username"]}!</p></div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="hero">'
            '<h1>⚽ Bolão</h1>'
            '<p>Palpites entre amigos &mdash; Brasileirão &amp; Premier League</p>'
            '</div>',
            unsafe_allow_html=True,
        )

    # ── Login / Register (only if not logged in) ──
    if not auth.is_logged_in():
        st.markdown(
            '<div class="section-header"><span>🔑 Entrar ou Criar Conta</span></div>',
            unsafe_allow_html=True,
        )

        tab_login, tab_register = st.tabs(["Entrar", "Criar Conta"])

        with tab_login:
            with st.form("login_form"):
                username = st.text_input("Usuário")
                password = st.text_input("Senha", type="password")
                submitted = st.form_submit_button("Entrar", use_container_width=True)
                if submitted:
                    if not username or not password:
                        st.error("Preencha todos os campos.")
                    else:
                        u = db.get_user_by_username(username)
                        if u and auth.verify_password(password, u["password_hash"]):
                            auth.login_user(u)
                            st.rerun()
                        else:
                            st.error("Usuário ou senha incorretos.")

        with tab_register:
            with st.form("register_form"):
                new_user = st.text_input("Novo Usuário")
                new_pass = st.text_input("Senha", type="password", key="reg_pass")
                new_pass2 = st.text_input("Confirmar Senha", type="password", key="reg_pass2")
                submitted = st.form_submit_button("Criar Conta", use_container_width=True)
                if submitted:
                    if not new_user or not new_pass:
                        st.error("Preencha todos os campos.")
                    elif len(new_user) < 3:
                        st.error("Usuário deve ter pelo menos 3 caracteres.")
                    elif len(new_pass) < 4:
                        st.error("Senha deve ter pelo menos 4 caracteres.")
                    elif new_pass != new_pass2:
                        st.error("As senhas não coincidem.")
                    else:
                        hashed = auth.hash_password(new_pass)
                        uid = db.create_user(new_user, hashed)
                        if uid:
                            st.success("Conta criada! Faça login.")
                        else:
                            st.error("Usuário já existe.")

    # ── Leaderboard ──
    st.markdown(
        '<div class="section-header"><span>🏆 Classificação</span></div>',
        unsafe_allow_html=True,
    )
    widget_leaderboard_mini()

    # ── Upcoming matches (with betting if logged in) ──
    st.markdown(
        '<div class="section-header"><span>📅 Próximos Jogos (7 dias)</span></div>',
        unsafe_allow_html=True,
    )
    if auth.is_logged_in():
        widget_upcoming_bets()
    else:
        widget_upcoming_matches()


# ─── Page: My Bets ────────────────────────────────────────────────────────────

def page_bets():
    st.header("🎯 Meus Palpites")

    user = auth.get_current_user()
    matches = db.get_upcoming_matches()
    user_bets = db.get_user_bets(user["id"])

    if not matches:
        st.info("Nenhuma partida disponível no momento. Aguarde o admin cadastrar os jogos.")
        return

    # Load odds for all matches
    all_match_ids = [m["id"] for m in matches]
    odds_map = db.get_odds_for_matches(all_match_ids)

    now = datetime.now()

    # Split into open (bettable) and locked (already started)
    open_matches = [m for m in matches if now < datetime.fromisoformat(m["match_time"])]
    locked_matches = [m for m in matches if now >= datetime.fromisoformat(m["match_time"])]

    # League filter (applied to both lists)
    all_for_filter = open_matches + locked_matches
    leagues = sorted(set(m.get("league", "Brasileirão") for m in all_for_filter))
    if len(leagues) > 1:
        selected_league = st.selectbox("Liga", leagues, key="bet_league")
        open_matches = [m for m in open_matches if m.get("league", "Brasileirão") == selected_league]
        locked_matches = [m for m in locked_matches if m.get("league", "Brasileirão") == selected_league]

    # ── Locked matches (already started, collapsed) ──
    if locked_matches:
        with st.expander(f"🔒 Jogos já iniciados ({len(locked_matches)})"):
            for m in locked_matches:
                match_dt = datetime.fromisoformat(m["match_time"])
                existing = user_bets.get(m["id"])
                date_str = match_dt.strftime("%d/%m %H:%M")
                league_tag = m.get("league", "")

                cols = st.columns([3, 1, 0.5, 1, 3])
                cols[0].write(f"**{m['home_team']}**")
                if existing:
                    cols[1].write(f"**{existing['home_score']}**")
                    cols[2].write("x")
                    cols[3].write(f"**{existing['away_score']}**")
                else:
                    cols[1].write("-")
                    cols[2].write("x")
                    cols[3].write("-")
                cols[4].write(f"**{m['away_team']}**")
                pts_str = ""
                if existing and existing.get("points_awarded") is not None:
                    pts_str = f" · **{existing['points_awarded']} pts**"
                st.caption(f"[{league_tag}] R{m['round_number'] or '?'} · {date_str}{pts_str}")

    # ── Open matches (bettable) ──
    if not open_matches:
        st.info("Nenhuma partida aberta para palpites no momento.")
    else:
        rounds: dict[int, list] = {}
        for m in open_matches:
            r = m.get("round_number") or 0
            rounds.setdefault(r, []).append(m)

        for round_num in sorted(rounds.keys()):
            round_matches = rounds[round_num]
            label = f"Rodada {round_num}" if round_num else "Sem rodada definida"
            st.subheader(label)

            for m in round_matches:
                match_dt = datetime.fromisoformat(m["match_time"])
                existing = user_bets.get(m["id"])
                date_str = match_dt.strftime("%d/%m %H:%M")
                odds = odds_map.get(m["id"])

                with st.form(key=f"bet_{m['id']}"):
                    st.markdown(f"**{date_str}**")
                    if odds:
                        st.markdown(_odds_html(odds), unsafe_allow_html=True)
                    cols = st.columns([3, 1, 1, 1, 3])
                    cols[0].markdown(f"**{m['home_team']}**")
                    home_val = existing["home_score"] if existing else 0
                    away_val = existing["away_score"] if existing else 0
                    home_score = cols[1].number_input(
                        "H", min_value=0, max_value=20, value=home_val,
                        label_visibility="collapsed", key=f"h_{m['id']}"
                    )
                    cols[2].markdown("<div style='text-align:center;padding-top:8px;'>x</div>", unsafe_allow_html=True)
                    away_score = cols[3].number_input(
                        "A", min_value=0, max_value=20, value=away_val,
                        label_visibility="collapsed", key=f"a_{m['id']}"
                    )
                    cols[4].markdown(f"**{m['away_team']}**")

                    col_btn, col_status = st.columns([1, 1])
                    submitted = col_btn.form_submit_button("Salvar", use_container_width=True)
                    if existing:
                        col_status.success("✅ Salvo")

                    if submitted:
                        ok = db.upsert_bet(user["id"], m["id"], int(home_score), int(away_score))
                        if ok:
                            st.rerun()
                        else:
                            st.error("Não foi possível salvar. A partida pode já ter começado.")

            st.divider()


# ─── Page: Leaderboard ────────────────────────────────────────────────────────

def page_leaderboard():
    st.markdown(
        '<div class="section-header"><span>🏆 Classificação Geral</span></div>',
        unsafe_allow_html=True,
    )

    leaderboard = db.get_leaderboard()
    user = auth.get_current_user() if auth.is_logged_in() else None

    if not leaderboard:
        st.info("Nenhuma pontuação registrada ainda.")
        return

    config = db.get_scoring_config()
    with st.expander("Regras de Pontuação"):
        st.markdown(
            f'<div class="rules-grid">'
            f'<div class="rule-chip"><div class="pts">{config["exact_score"]}</div><div class="label">Placar exato</div></div>'
            f'<div class="rule-chip"><div class="pts">{config["correct_winner_goal_diff"]}</div><div class="label">Vencedor + saldo</div></div>'
            f'<div class="rule-chip"><div class="pts">{config["correct_winner"]}</div><div class="label">Acertou vencedor</div></div>'
            f'<div class="rule-chip"><div class="pts">{config["correct_draw"]}</div><div class="label">Acertou empate</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    rows_html = ""
    for i, entry in enumerate(leaderboard):
        rank = i + 1
        medal = medals.get(rank, f"{rank}.")
        is_me = user and entry["user_id"] == user["id"]
        row_class = "lb-me " if is_me else ""
        row_class += f"lb-top{rank}" if rank <= 3 else ""
        me_tag = " &#9668;" if is_me else ""
        rows_html += (
            f'<tr class="{row_class}">'
            f'<td class="lb-rank-cell">{medal}</td>'
            f'<td class="lb-name-cell">{entry["username"]}{me_tag}</td>'
            f'<td class="lb-stat-cell">{entry["total_bets"]}</td>'
            f'<td class="lb-stat-cell">{entry["exact_count"]}</td>'
            f'<td class="lb-stat-cell">{entry["zero_count"]}</td>'
            f'<td class="lb-stat-cell">{entry["missed_count"]}</td>'
            f'<td class="lb-pts-cell">{entry["total_points"]} pts</td>'
            f'</tr>'
        )

    st.markdown(
        f'<table class="lb-table">'
        f'<thead><tr><th></th><th>Jogador</th><th>Palpites</th><th>Cravadas</th><th>Zeradas</th><th>Sem palpite</th><th>Pontos</th></tr></thead>'
        f'<tbody>{rows_html}</tbody></table>',
        unsafe_allow_html=True,
    )


# ─── Page: Admin ──────────────────────────────────────────────────────────────

def page_admin():
    st.header("⚙️ Painel do Admin")

    if not auth.is_admin():
        st.error("Acesso negado.")
        return

    tab_add, tab_results, tab_scoring, tab_manage = st.tabs([
        "Adicionar Jogos", "Inserir Resultados", "Pontuação", "Gerenciar Jogos"
    ])

    LEAGUES = ["Brasileirão", "Premier League"]

    # --- Add Matches ---
    with tab_add:
        st.subheader("Novo Jogo")

        with st.form("add_match"):
            league = st.selectbox("Liga", LEAGUES)
            round_num = st.number_input("Rodada", min_value=1, max_value=38, value=1)
            col1, col2 = st.columns(2)
            home_team = col1.text_input("Mandante")
            away_team = col2.text_input("Visitante")
            match_date = st.date_input("Data")
            match_time = st.time_input("Horário")
            submitted = st.form_submit_button("Adicionar Jogo", use_container_width=True)
            if submitted:
                if not home_team or not away_team:
                    st.error("Preencha os dois times!")
                elif home_team == away_team:
                    st.error("Times iguais!")
                else:
                    dt = datetime.combine(match_date, match_time).isoformat()
                    db.add_match(round_num, home_team, away_team, dt, league)
                    st.success(f"Jogo adicionado: {home_team} x {away_team}")
                    st.rerun()

        with st.expander("Adicionar vários jogos (rodada inteira)"):
            st.caption("Adicione múltiplos jogos com a mesma rodada, data e horário.")
            with st.form("bulk_add"):
                bulk_league = st.selectbox("Liga", LEAGUES, key="bulk_lg")
                bulk_round = st.number_input("Rodada", min_value=1, max_value=38, value=1, key="bulk_r")
                bulk_date = st.date_input("Data padrão", key="bulk_d")
                bulk_time = st.time_input("Horário padrão", key="bulk_t")
                bulk_text = st.text_area(
                    "Jogos (um por linha: Mandante x Visitante)",
                    placeholder="Flamengo x Palmeiras\nCorinthians x São Paulo",
                    height=200,
                )
                bulk_submit = st.form_submit_button("Adicionar Todos", use_container_width=True)
                if bulk_submit and bulk_text.strip():
                    dt = datetime.combine(bulk_date, bulk_time).isoformat()
                    lines = [l.strip() for l in bulk_text.strip().split("\n") if l.strip()]
                    count = 0
                    for line in lines:
                        parts = [p.strip() for p in line.split(" x ")]
                        if len(parts) == 2 and parts[0] and parts[1]:
                            db.add_match(bulk_round, parts[0], parts[1], dt, bulk_league)
                            count += 1
                    st.success(f"{count} jogo(s) adicionado(s)!")
                    st.rerun()

    # --- Enter Results ---
    with tab_results:
        st.subheader("Inserir Resultados")
        unfinished = db.get_unfinished_matches()
        if not unfinished:
            st.info("Nenhuma partida pendente.")
        else:
            for m in unfinished:
                match_dt = datetime.fromisoformat(m["match_time"])
                date_str = match_dt.strftime("%d/%m %H:%M")
                with st.form(key=f"result_{m['id']}"):
                    league_tag = m.get("league", "")
                    st.markdown(f"**[{league_tag}] R{m['round_number'] or '?'} — {date_str}**")
                    cols = st.columns([3, 1, 1, 1, 3])
                    cols[0].write(f"**{m['home_team']}**")
                    home_s = cols[1].number_input(
                        "H", min_value=0, max_value=20, value=0,
                        label_visibility="collapsed", key=f"rh_{m['id']}"
                    )
                    cols[2].markdown("<div style='text-align:center;padding-top:8px;'>x</div>", unsafe_allow_html=True)
                    away_s = cols[3].number_input(
                        "A", min_value=0, max_value=20, value=0,
                        label_visibility="collapsed", key=f"ra_{m['id']}"
                    )
                    cols[4].write(f"**{m['away_team']}**")
                    if st.form_submit_button("Confirmar Resultado", use_container_width=True):
                        db.set_match_result(m["id"], int(home_s), int(away_s))
                        st.success(f"Resultado salvo: {m['home_team']} {home_s} x {away_s} {m['away_team']}")
                        st.rerun()

    # --- Scoring Config ---
    with tab_scoring:
        st.subheader("Configuração de Pontuação")
        config = db.get_scoring_config()
        with st.form("scoring_form"):
            exact = st.number_input("Placar exato", value=config["exact_score"], min_value=0)
            winner_diff = st.number_input("Vencedor + saldo de gols", value=config["correct_winner_goal_diff"], min_value=0)
            winner = st.number_input("Acertou vencedor", value=config["correct_winner"], min_value=0)
            draw = st.number_input("Acertou empate", value=config["correct_draw"], min_value=0)
            wrong = st.number_input("Errou", value=config["wrong"], min_value=0)
            col1, col2 = st.columns(2)
            if col1.form_submit_button("Salvar", use_container_width=True):
                db.update_scoring_config(int(exact), int(winner_diff), int(winner), int(draw), int(wrong))
                st.success("Configuração salva!")
                st.rerun()
            if col2.form_submit_button("Salvar e Recalcular Tudo", use_container_width=True):
                db.update_scoring_config(int(exact), int(winner_diff), int(winner), int(draw), int(wrong))
                db.recalculate_all_points()
                st.success("Pontuação recalculada para todos os jogos!")
                st.rerun()

    # --- Manage Matches ---
    with tab_manage:
        st.subheader("Jogos Cadastrados")
        all_matches = db.get_all_matches()
        if not all_matches:
            st.info("Nenhum jogo cadastrado.")
        else:
            for m in all_matches:
                match_dt = datetime.fromisoformat(m["match_time"])
                date_str = match_dt.strftime("%d/%m/%Y %H:%M")
                status = "✅ Finalizado" if m["is_finished"] else "⏳ Pendente"
                result_str = ""
                if m["is_finished"]:
                    result_str = f" — {m['home_score']} x {m['away_score']}"

                cols = st.columns([5, 1])
                league_tag = m.get("league", "")
                cols[0].write(
                    f"[{league_tag}] R{m['round_number'] or '?'} | {m['home_team']} x {m['away_team']} "
                    f"| {date_str} | {status}{result_str}"
                )
                if cols[1].button("🗑️", key=f"del_{m['id']}"):
                    db.delete_match(m["id"])
                    st.rerun()


# ─── Router ───────────────────────────────────────────────────────────────────

if page == PAGES[0]:
    page_home()
elif page == PAGES[1]:
    if not auth.is_logged_in():
        st.warning("Faça login para ver seus palpites.")
        page_home()
    else:
        page_bets()
elif page == PAGES[2]:
    page_leaderboard()
elif page == "Admin":
    page_admin()
