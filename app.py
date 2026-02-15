"""
Bolão do Brasileirão - Soccer Betting Pool.
Main Streamlit application.
"""

import streamlit as st
from datetime import datetime, timedelta

import pandas as pd

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

    /* ── Compact betting form rows ──────────────────────────────── */
    [data-testid="stForm"] [data-testid="stVerticalBlock"] { gap: 0rem !important; }
    [data-testid="stForm"] [data-testid="stHorizontalBlock"] {
        gap: 0.2rem !important;
        flex-wrap: nowrap !important;
        flex-direction: row !important;
        align-items: center !important;
    }
    [data-testid="stForm"] [data-testid="stHorizontalBlock"] [data-testid="column"] {
        min-width: 0 !important;
        overflow: hidden;
    }
    [data-testid="stForm"] .stNumberInput { margin-bottom: 0 !important; }
    [data-testid="stForm"] .stNumberInput > div,
    [data-testid="stForm"] .stNumberInput > div > div {
        min-width: 0 !important;
    }
    [data-testid="stForm"] .stNumberInput > div > div > input {
        padding: 2px 1px !important; font-size: 0.9rem !important; height: 1.8rem !important;
        min-width: 0 !important; width: 100% !important;
        -moz-appearance: textfield !important;
    }
    [data-testid="stForm"] .stNumberInput > div > div > input::-webkit-outer-spin-button,
    [data-testid="stForm"] .stNumberInput > div > div > input::-webkit-inner-spin-button {
        -webkit-appearance: none !important; margin: 0 !important;
    }
    [data-testid="stForm"] .stNumberInput button { display: none !important; }
    [data-testid="stForm"] .stMarkdown { margin-bottom: 0 !important; }
    [data-testid="stForm"] .stMarkdown p {
        font-size: 0.82rem !important; line-height: 1.2 !important;
        white-space: nowrap !important; overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    [data-testid="stForm"] .stCaption { margin-bottom: 0 !important; }
    [data-testid="stForm"] .stCaption p { font-size: 0.65rem !important; line-height: 1.1 !important; }
    [data-testid="stForm"] [data-testid="stVerticalBlockBorderWrapper"] { padding: 0 !important; }
    .compact-row-border { border-bottom: 1px solid #e8e8e8; padding-bottom: 0; margin-bottom: 0; }

    /* ── Date label above team name ────────────────────────────── */
    .bet-date { font-size: 0.65rem; color: #999; font-weight: 500; }

    /* ── Mobile: hide odds & date, shrink everything ──────────── */
    @media (max-width: 768px) {
        .block-container { padding-left: 0.5rem !important; padding-right: 0.5rem !important; }
        [data-testid="stForm"] { padding: 0.3rem !important; }
        [data-testid="stForm"] [data-testid="stHorizontalBlock"] {
            gap: 0.15rem !important; max-width: 100% !important;
        }
        [data-testid="stForm"] .odds-row { display: none !important; }
        [data-testid="stForm"] .bet-date { display: none !important; }
        [data-testid="stForm"] .stMarkdown img { width: 14px !important; height: 14px !important; }
        [data-testid="stForm"] .stMarkdown p { font-size: 0.72rem !important; }
        [data-testid="stForm"] .stNumberInput > div > div > input {
            font-size: 0.85rem !important; height: 1.5rem !important; padding: 1px 0 !important;
        }
        .compact-row-border { margin: 0 !important; padding: 0 !important; }
    }
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
        with st.expander("👤 Minha Conta"):
            with st.form("sidebar_change_name"):
                new_name = st.text_input("Novo nome de usuário", value=user["username"], key="sb_new_name")
                if st.form_submit_button("Salvar Nome", use_container_width=True):
                    new_name = new_name.strip()
                    if not new_name or len(new_name) < 3:
                        st.error("Mínimo 3 caracteres.")
                    elif new_name == user["username"]:
                        st.info("Nome não alterado.")
                    else:
                        ok = db.update_username(user["id"], new_name)
                        if ok:
                            st.session_state["user"]["username"] = new_name
                            st.success("Nome alterado!")
                            st.rerun()
                        else:
                            st.error("Este nome já está em uso.")
            st.divider()
            with st.form("sidebar_change_pw"):
                cur_pw = st.text_input("Senha atual", type="password", key="sb_cur_pw")
                new_pw = st.text_input("Nova senha", type="password", key="sb_new_pw")
                new_pw2 = st.text_input("Confirmar", type="password", key="sb_new_pw2")
                if st.form_submit_button("Alterar Senha", use_container_width=True):
                    stored = db.get_user_by_username(user["username"])
                    if not auth.verify_password(cur_pw, stored["password_hash"]):
                        st.error("Senha atual incorreta.")
                    elif not new_pw or len(new_pw) < 4:
                        st.error("Mínimo 4 caracteres.")
                    elif new_pw != new_pw2:
                        st.error("Senhas não coincidem.")
                    else:
                        db.reset_user_password(user["id"], auth.hash_password(new_pw))
                        st.success("Senha alterada!")
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

    # Load odds and logos for these matches
    match_ids = [m["id"] for m in soon]
    odds_map = db.get_odds_for_matches(match_ids)
    all_teams = list({m["home_team"] for m in soon} | {m["away_team"] for m in soon})
    logos = db.get_team_logos(all_teams)

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
            home_html = _team_html(m["home_team"], logos)
            away_html = _team_html(m["away_team"], logos)
            st.markdown(
                f'<div class="match-card {css_class}">'
                f'<div><span class="mc-teams">{home_html} x {away_html}</span>'
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


def _team_html(name: str, logos: dict[str, str], size: int = 22) -> str:
    """Return team name with optional crest image."""
    logo = logos.get(name, "")
    if logo:
        return f'<img src="{logo}" width="{size}" height="{size}" style="vertical-align:middle;margin-right:4px">{name}'
    return name


def _team_md(name: str, logos: dict[str, str], size: int = 22) -> str:
    """Return markdown-safe team name with optional crest image (for st.markdown)."""
    logo = logos.get(name, "")
    if logo:
        return f'<img src="{logo}" width="{size}" height="{size}" style="vertical-align:middle;margin-right:4px"> **{name}**'
    return f"**{name}**"


def _weekday_pt(dt: datetime) -> str:
    days = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    return days[dt.weekday()]


def widget_leaderboard_mini():
    """Show full leaderboard on the home page."""
    leaderboard = db.get_leaderboard()
    current_user = auth.get_current_user() if auth.is_logged_in() else None

    if not leaderboard:
        st.caption("Nenhuma pontuação registrada ainda.")
        return

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    rows_html = ""
    for i, entry in enumerate(leaderboard):
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

    # Load odds and logos for these matches
    match_ids = [m["id"] for m in soon]
    odds_map = db.get_odds_for_matches(match_ids)
    all_teams = list({m["home_team"] for m in soon} | {m["away_team"] for m in soon})
    logos = db.get_team_logos(all_teams)

    # Group by league
    by_league: dict[str, list] = {}
    for m in soon:
        lg = m.get("league", "Brasileirão")
        by_league.setdefault(lg, []).append(m)

    # Render locked matches outside the form
    locked_matches = []
    open_matches = []
    for league, matches in sorted(by_league.items()):
        css_class = "brasileirao" if "Brasil" in league else "premier"
        for m in matches:
            match_dt = datetime.fromisoformat(m["match_time"])
            if now >= match_dt:
                locked_matches.append((league, css_class, m))
            else:
                open_matches.append((league, css_class, m))

    # Show locked matches first
    current_league = None
    for league, css_class, m in locked_matches:
        if league != current_league:
            flag = "🇧🇷" if "Brasil" in league else "🏴󠁧󠁢󠁥󠁮󠁧󠁿"
            st.markdown(f'<div class="league-label {css_class}">{flag} {league}</div>', unsafe_allow_html=True)
            current_league = league
        existing = user_bets.get(m["id"])
        match_dt = datetime.fromisoformat(m["match_time"])
        day_name = _weekday_pt(match_dt)
        date_str = match_dt.strftime(f"%d/%m ({day_name}) %H:%M")
        score_txt = f"{existing['home_score']} x {existing['away_score']}" if existing else "- x -"
        odds = odds_map.get(m["id"])
        home_html = _team_html(m["home_team"], logos)
        away_html = _team_html(m["away_team"], logos)
        st.markdown(
            f'<div class="match-card {css_class} locked">'
            f'<div><span class="mc-teams">🔒 {home_html} {score_txt} {away_html}</span>'
            f'{_odds_html(odds)}</div>'
            f'<span class="mc-meta">{date_str}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Show open matches inside a single compact form
    if open_matches:
        with st.form(key="home_bet_all"):
            open_match_ids = []
            current_league = None
            for league, css_class, m in open_matches:
                if league != current_league:
                    flag = "🇧🇷" if "Brasil" in league else "🏴󠁧󠁢󠁥󠁮󠁧󠁿"
                    st.markdown(f'<div class="league-label {css_class}">{flag} {league}</div>', unsafe_allow_html=True)
                    current_league = league
                existing = user_bets.get(m["id"])
                match_dt = datetime.fromisoformat(m["match_time"])
                day_name = _weekday_pt(match_dt)
                date_str = match_dt.strftime(f"%d/%m ({day_name}) %H:%M")
                saved_icon = " ✅" if existing else ""
                home_val = existing["home_score"] if existing else 0
                away_val = existing["away_score"] if existing else 0
                odds = odds_map.get(m["id"])
                odds_html = (
                    f'<span class="odds-row" style="margin-top:0;gap:3px;justify-content:flex-start;display:inline-flex;">'
                    f'<span class="odds-badge home">{odds["home_win"]:.2f}</span>'
                    f'<span class="odds-badge draw">{odds["draw"]:.2f}</span>'
                    f'<span class="odds-badge away">{odds["away_win"]:.2f}</span>'
                    f'</span>'
                ) if odds else ""
                home_md = _team_md(m['home_team'], logos)
                away_md = _team_md(m['away_team'], logos)
                cols = st.columns([3, 1, 0.5, 1, 3])
                cols[0].markdown(
                    f'<span class="bet-date">{date_str}</span><br>{home_md} {odds_html}',
                    unsafe_allow_html=True,
                )
                cols[1].number_input(
                    "H", min_value=0, max_value=20, value=home_val,
                    label_visibility="collapsed", key=f"hb_{m['id']}"
                )
                cols[2].markdown(
                    "<div style='text-align:center;padding-top:8px;font-weight:bold;'>x</div>",
                    unsafe_allow_html=True,
                )
                cols[3].number_input(
                    "A", min_value=0, max_value=20, value=away_val,
                    label_visibility="collapsed", key=f"ab_{m['id']}"
                )
                cols[4].markdown(f'{away_md}{saved_icon}', unsafe_allow_html=True)
                open_match_ids.append(m["id"])
                st.markdown('<div class="compact-row-border"></div>', unsafe_allow_html=True)

            if st.form_submit_button("Salvar Todos", use_container_width=True):
                errors = []
                for mid in open_match_ids:
                    h = int(st.session_state.get(f"hb_{mid}", 0))
                    a = int(st.session_state.get(f"ab_{mid}", 0))
                    ok = db.upsert_bet(user["id"], mid, h, a)
                    if not ok:
                        errors.append(mid)
                if errors:
                    st.error(f"{len(errors)} palpite(s) não salvos (partida já começou?).")
                else:
                    st.success("Todos os palpites salvos!")
                st.rerun()


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

    # Load odds and logos for all matches
    all_match_ids = [m["id"] for m in matches]
    odds_map = db.get_odds_for_matches(all_match_ids)
    all_teams = list({m["home_team"] for m in matches} | {m["away_team"] for m in matches})
    logos = db.get_team_logos(all_teams)

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
                cols[0].markdown(_team_md(m['home_team'], logos), unsafe_allow_html=True)
                if existing:
                    cols[1].write(f"**{existing['home_score']}**")
                    cols[2].write("x")
                    cols[3].write(f"**{existing['away_score']}**")
                else:
                    cols[1].write("-")
                    cols[2].write("x")
                    cols[3].write("-")
                cols[4].markdown(_team_md(m['away_team'], logos), unsafe_allow_html=True)
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

        with st.form(key="bet_all"):
            all_open_ids = []
            for round_num in sorted(rounds.keys()):
                round_matches = rounds[round_num]
                label = f"Rodada {round_num}" if round_num else "Sem rodada definida"
                st.subheader(label)

                for m in round_matches:
                    match_dt = datetime.fromisoformat(m["match_time"])
                    existing = user_bets.get(m["id"])
                    date_str = match_dt.strftime("%d/%m %H:%M")
                    saved_icon = " ✅" if existing else ""
                    home_val = existing["home_score"] if existing else 0
                    away_val = existing["away_score"] if existing else 0
                    odds = odds_map.get(m["id"])
                    odds_html = (
                        f'<span class="odds-row" style="margin-top:0;gap:3px;justify-content:flex-start;display:inline-flex;">'
                        f'<span class="odds-badge home">{odds["home_win"]:.2f}</span>'
                        f'<span class="odds-badge draw">{odds["draw"]:.2f}</span>'
                        f'<span class="odds-badge away">{odds["away_win"]:.2f}</span>'
                        f'</span>'
                    ) if odds else ""
                    home_md = _team_md(m['home_team'], logos)
                    away_md = _team_md(m['away_team'], logos)
                    cols = st.columns([3, 1, 0.5, 1, 3])
                    cols[0].markdown(
                        f'<span class="bet-date">{date_str}</span><br>{home_md} {odds_html}',
                        unsafe_allow_html=True,
                    )
                    cols[1].number_input(
                        "H", min_value=0, max_value=20, value=home_val,
                        label_visibility="collapsed", key=f"h_{m['id']}"
                    )
                    cols[2].markdown(
                        "<div style='text-align:center;padding-top:8px;'>x</div>",
                        unsafe_allow_html=True,
                    )
                    cols[3].number_input(
                        "A", min_value=0, max_value=20, value=away_val,
                        label_visibility="collapsed", key=f"a_{m['id']}"
                    )
                    cols[4].markdown(f'{away_md}{saved_icon}', unsafe_allow_html=True)
                    all_open_ids.append(m["id"])
                    st.markdown('<div class="compact-row-border"></div>', unsafe_allow_html=True)

            if st.form_submit_button("Salvar Todos", use_container_width=True):
                errors = []
                for mid in all_open_ids:
                    h = int(st.session_state.get(f"h_{mid}", 0))
                    a = int(st.session_state.get(f"a_{mid}", 0))
                    ok = db.upsert_bet(user["id"], mid, h, a)
                    if not ok:
                        errors.append(mid)
                if errors:
                    st.error(f"{len(errors)} palpite(s) não salvos (partida já começou?).")
                else:
                    st.success("Todos os palpites salvos!")
                st.rerun()


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

    # ── Leaderboard Evolution Chart ──
    evolution = db.get_leaderboard_evolution()
    if evolution:
        # Get top 5 player names from current leaderboard
        top5_names = [e["username"] for e in leaderboard[:5]]

        # Build cumulative points per player over time
        records = []
        cumulative = {name: 0 for name in top5_names}
        # Group by match_time to accumulate
        from itertools import groupby
        for match_time, group in groupby(evolution, key=lambda r: r["match_time"]):
            for row in group:
                if row["username"] in cumulative:
                    cumulative[row["username"]] += row["points_awarded"]
            records.append({"match_time": match_time, **cumulative.copy()})

        if records:
            df = pd.DataFrame(records)
            df["match_time"] = pd.to_datetime(df["match_time"])
            df = df.set_index("match_time")[top5_names]

            st.markdown(
                '<div class="section-header"><span>📈 Evolução</span></div>',
                unsafe_allow_html=True,
            )
            st.line_chart(df)


# ─── Page: Admin ──────────────────────────────────────────────────────────────

def page_admin():
    st.header("⚙️ Painel do Admin")

    if not auth.is_admin():
        st.error("Acesso negado.")
        return

    tab_add, tab_results, tab_scoring, tab_manage, tab_bets, tab_players, tab_pw = st.tabs([
        "Adicionar Jogos", "Inserir Resultados", "Pontuação", "Gerenciar Jogos", "Palpites", "Jogadores", "Minha Senha"
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

    # --- View & Manage Bets ---
    with tab_bets:
        st.subheader("Palpites dos Jogadores")
        all_matches = db.get_all_matches()
        if not all_matches:
            st.info("Nenhum jogo cadastrado.")
        else:
            match_options = {
                m["id"]: f"[{m.get('league', '')}] {m['home_team']} x {m['away_team']} — "
                         f"{datetime.fromisoformat(m['match_time']).strftime('%d/%m/%Y %H:%M')}"
                for m in all_matches
            }
            selected_id = st.selectbox(
                "Selecione o jogo",
                options=list(match_options.keys()),
                format_func=lambda x: match_options[x],
                key="admin_bet_match",
            )

            if selected_id:
                bets = db.get_all_bets_for_match(selected_id)
                if not bets:
                    st.caption("Nenhum palpite registrado para este jogo.")
                else:
                    for bet in bets:
                        pts = bet["points_awarded"]
                        pts_str = f" | **{pts} pts**" if pts is not None else ""
                        with st.form(key=f"admin_edit_bet_{bet['id']}"):
                            cols = st.columns([2, 1, 0.5, 1, 1, 1])
                            cols[0].markdown(f"**{bet['username']}**{pts_str}")
                            new_home = cols[1].number_input(
                                "H", min_value=0, max_value=20, value=bet["home_score"],
                                label_visibility="collapsed", key=f"aeh_{bet['id']}",
                            )
                            cols[2].markdown(
                                "<div style='text-align:center;padding-top:8px;font-weight:bold;'>x</div>",
                                unsafe_allow_html=True,
                            )
                            new_away = cols[3].number_input(
                                "A", min_value=0, max_value=20, value=bet["away_score"],
                                label_visibility="collapsed", key=f"aea_{bet['id']}",
                            )
                            save = cols[4].form_submit_button("💾")
                            delete = cols[5].form_submit_button("🗑️")
                            if save:
                                db.admin_upsert_bet(bet["user_id"], selected_id, int(new_home), int(new_away))
                                st.rerun()
                            if delete:
                                db.admin_delete_bet(bet["id"])
                                st.rerun()

                # Add new bet for any user
                st.divider()
                st.caption("Adicionar palpite")
                users = db.get_all_users()
                with st.form("admin_add_bet"):
                    user_map = {u["id"]: u["username"] for u in users}
                    sel_user = st.selectbox(
                        "Jogador",
                        options=list(user_map.keys()),
                        format_func=lambda x: user_map[x],
                        key="admin_new_bet_user",
                    )
                    cols = st.columns([1, 0.5, 1])
                    new_h = cols[0].number_input(
                        "Casa", min_value=0, max_value=20, value=0, key="admin_new_h"
                    )
                    cols[1].markdown(
                        "<div style='text-align:center;padding-top:28px;font-weight:bold;'>x</div>",
                        unsafe_allow_html=True,
                    )
                    new_a = cols[2].number_input(
                        "Fora", min_value=0, max_value=20, value=0, key="admin_new_a"
                    )
                    if st.form_submit_button("Adicionar Palpite", use_container_width=True):
                        db.admin_upsert_bet(sel_user, selected_id, int(new_h), int(new_a))
                        st.success("Palpite adicionado!")
                        st.rerun()

    # --- Manage Players ---
    with tab_players:
        st.subheader("Gerenciar Jogadores")
        users = [u for u in db.get_all_users() if not u["is_admin"]]
        if not users:
            st.info("Nenhum jogador cadastrado.")
        else:
            for u in users:
                with st.expander(f"👤 {u['username']}"):
                    current_avatar = u.get("avatar_url") or ""
                    if current_avatar:
                        st.image(current_avatar, width=60)
                    with st.form(key=f"avatar_{u['id']}"):
                        avatar_input = st.text_input(
                            "URL do avatar", value=current_avatar, key=f"avatar_input_{u['id']}"
                        )
                        if st.form_submit_button("Salvar Avatar", use_container_width=True):
                            db.update_user_avatar(u["id"], avatar_input.strip())
                            st.success(f"Avatar de {u['username']} atualizado!")
                            st.rerun()
                    with st.form(key=f"reset_pw_{u['id']}"):
                        new_pw = st.text_input(
                            "Nova senha", type="password", key=f"pw_input_{u['id']}"
                        )
                        if st.form_submit_button("Redefinir Senha", use_container_width=True):
                            if not new_pw or len(new_pw) < 4:
                                st.error("A senha deve ter pelo menos 4 caracteres.")
                            else:
                                hashed = auth.hash_password(new_pw)
                                db.reset_user_password(u["id"], hashed)
                                st.success(f"Senha de {u['username']} redefinida!")
                    if st.button(f"🗑️ Excluir {u['username']}", key=f"del_user_{u['id']}"):
                        ok = db.delete_user(u["id"])
                        if ok:
                            st.success(f"Jogador {u['username']} excluído.")
                            st.rerun()
                        else:
                            st.error("Não foi possível excluir este usuário.")

    # --- Change Admin Password ---
    with tab_pw:
        st.subheader("Alterar Minha Senha")
        admin_user = auth.get_current_user()
        with st.form("change_admin_pw"):
            cur_pw = st.text_input("Senha atual", type="password")
            new_pw = st.text_input("Nova senha", type="password")
            new_pw2 = st.text_input("Confirmar nova senha", type="password")
            if st.form_submit_button("Alterar Senha", use_container_width=True):
                stored = db.get_user_by_username(admin_user["username"])
                if not auth.verify_password(cur_pw, stored["password_hash"]):
                    st.error("Senha atual incorreta.")
                elif not new_pw or len(new_pw) < 4:
                    st.error("A nova senha deve ter pelo menos 4 caracteres.")
                elif new_pw != new_pw2:
                    st.error("As senhas não coincidem.")
                else:
                    db.reset_user_password(admin_user["id"], auth.hash_password(new_pw))
                    st.success("Senha alterada com sucesso!")


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
