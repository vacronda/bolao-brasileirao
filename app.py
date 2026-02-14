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
    .block-container { padding-top: 0.5rem; padding-bottom: 1rem; max-width: 720px; }

    /* Hero banner */
    .hero {
        background: linear-gradient(135deg, #1a5276 0%, #2e86c1 50%, #27ae60 100%);
        color: white; padding: 2rem 1.5rem; border-radius: 16px;
        text-align: center; margin-bottom: 1.5rem;
    }
    .hero h1 { font-size: 2rem; margin: 0; color: white; }
    .hero p { font-size: 1rem; margin: 0.3rem 0 0; opacity: 0.9; color: #e8e8e8; }

    /* Welcome bar (logged in) */
    .welcome-bar {
        background: linear-gradient(135deg, #1a5276 0%, #2e86c1 50%, #27ae60 100%);
        color: white; padding: 1rem 1.5rem; border-radius: 12px;
        margin-bottom: 1rem; display: flex; align-items: center; justify-content: space-between;
    }
    .welcome-bar h2 { font-size: 1.3rem; margin: 0; color: white; }
    .welcome-bar p { margin: 0; opacity: 0.9; font-size: 0.9rem; color: #e8e8e8; }

    /* Section headers */
    .section-header {
        display: flex; align-items: center; gap: 8px;
        margin: 1.2rem 0 0.5rem; padding-bottom: 4px;
        border-bottom: 2px solid #2e86c1;
    }
    .section-header span { font-size: 1.1rem; font-weight: 700; color: #1a5276; }

    /* Match row for home preview */
    .match-row {
        background: #f8f9fa; border-radius: 10px; padding: 10px 14px;
        margin-bottom: 6px; border-left: 4px solid #2e86c1;
        display: flex; justify-content: space-between; align-items: center;
    }
    .match-row.brasileirao { border-left-color: #27ae60; }
    .match-row.premier { border-left-color: #6c3483; }
    .match-teams { font-weight: 600; font-size: 0.95rem; }
    .match-meta { font-size: 0.78rem; color: #777; }

    /* Leaderboard card */
    .lb-card {
        background: #fefefe; border: 1px solid #e8e8e8; border-radius: 10px;
        padding: 10px 14px; margin-bottom: 5px;
    }
    .lb-card.top1 { border-left: 4px solid #f1c40f; background: #fffde7; }
    .lb-card.top2 { border-left: 4px solid #95a5a6; background: #fafafa; }
    .lb-card.top3 { border-left: 4px solid #cd6155; background: #fdf2f0; }
    .lb-rank { font-weight: 800; font-size: 1.1rem; }
    .lb-name { font-weight: 600; }
    .lb-pts { color: #2e86c1; font-weight: 700; }

    /* Login card */
    .login-card {
        background: white; border: 1px solid #ddd; border-radius: 12px;
        padding: 1.5rem; margin-top: 0.5rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }

    /* Sidebar */
    [data-testid="stSidebar"] { min-width: 200px; max-width: 260px; }
    #MainMenu, footer { visibility: hidden; }
    .stNumberInput > div > div > input { text-align: center; }

    /* Match card styling (bets page) */
    .match-card-locked {
        background: #f0f0f0; border-radius: 10px; padding: 12px;
        margin-bottom: 8px; border-left: 4px solid #aaa; opacity: 0.7;
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
    soon = [m for m in all_upcoming if datetime.fromisoformat(m["match_time"]) <= cutoff]

    if not soon:
        st.caption("Nenhuma partida nos próximos 7 dias.")
        return

    # Group by league
    by_league: dict[str, list] = {}
    for m in soon:
        lg = m.get("league", "Brasileirão")
        by_league.setdefault(lg, []).append(m)

    for league, matches in sorted(by_league.items()):
        css_class = "brasileirao" if "Brasil" in league else "premier"
        flag = "🇧🇷" if "Brasil" in league else "🏴󠁧󠁢󠁥󠁮󠁧󠁿"
        st.markdown(f"**{flag} {league}**")
        for m in matches:
            match_dt = datetime.fromisoformat(m["match_time"])
            day_name = _weekday_pt(match_dt)
            date_str = match_dt.strftime(f"%d/%m ({day_name}) %H:%M")
            st.markdown(
                f'<div class="match-row {css_class}">'
                f'<span class="match-teams">{m["home_team"]} x {m["away_team"]}</span>'
                f'<span class="match-meta">R{m["round_number"] or "?"} &middot; {date_str}</span>'
                f'</div>',
                unsafe_allow_html=True,
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

    top = leaderboard[:5]
    medals = ["🥇", "🥈", "🥉"]

    for i, entry in enumerate(top):
        rank = i + 1
        medal = medals[i] if i < 3 else f"{rank}."
        css = f"top{rank}" if rank <= 3 else ""
        is_me = current_user and entry["user_id"] == current_user["id"]
        name_extra = " 👈" if is_me else ""

        st.markdown(
            f'<div class="lb-card {css}" style="display:flex;justify-content:space-between;align-items:center;">'
            f'<span><span class="lb-rank">{medal}</span> '
            f'<span class="lb-name">{entry["username"]}{name_extra}</span></span>'
            f'<span class="lb-pts">{entry["total_points"]} pts</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if len(leaderboard) > 5:
        # Show current user if not in top 5
        if current_user:
            for i, entry in enumerate(leaderboard):
                if entry["user_id"] == current_user["id"] and i >= 5:
                    st.markdown(
                        f'<div class="lb-card" style="display:flex;justify-content:space-between;align-items:center;border:2px solid #f0c040;">'
                        f'<span><span class="lb-rank">{i+1}.</span> '
                        f'<span class="lb-name">{entry["username"]} 👈</span></span>'
                        f'<span class="lb-pts">{entry["total_points"]} pts</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    break


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

    # ── Upcoming matches ──
    st.markdown(
        '<div class="section-header"><span>📅 Próximos Jogos (7 dias)</span></div>',
        unsafe_allow_html=True,
    )
    widget_upcoming_matches()

    # ── Leaderboard ──
    st.markdown(
        '<div class="section-header"><span>🏆 Classificação</span></div>',
        unsafe_allow_html=True,
    )
    widget_leaderboard_mini()

    # ── Login / Register (only if not logged in) ──
    if not auth.is_logged_in():
        st.markdown("---")
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


# ─── Page: My Bets ────────────────────────────────────────────────────────────

def page_bets():
    st.header("🎯 Meus Palpites")

    user = auth.get_current_user()
    matches = db.get_upcoming_matches()
    user_bets = db.get_user_bets(user["id"])

    if not matches:
        st.info("Nenhuma partida disponível no momento. Aguarde o admin cadastrar os jogos.")
        return

    # League filter
    leagues = sorted(set(m.get("league", "Brasileirão") for m in matches))
    if len(leagues) > 1:
        selected_league = st.selectbox("Liga", leagues, key="bet_league")
        matches = [m for m in matches if m.get("league", "Brasileirão") == selected_league]

    # Group by round
    rounds: dict[int, list] = {}
    for m in matches:
        r = m.get("round_number") or 0
        rounds.setdefault(r, []).append(m)

    now = datetime.now()

    for round_num in sorted(rounds.keys()):
        round_matches = rounds[round_num]
        label = f"Rodada {round_num}" if round_num else "Sem rodada definida"
        st.subheader(label)

        for m in round_matches:
            match_dt = datetime.fromisoformat(m["match_time"])
            is_locked = now >= match_dt
            existing = user_bets.get(m["id"])

            date_str = match_dt.strftime("%d/%m %H:%M")

            if is_locked:
                st.markdown(f'<div class="match-card-locked">', unsafe_allow_html=True)
                cols = st.columns([3, 1, 1, 1, 3])
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
                st.caption(f"🔒 {date_str} — Bloqueado")
                if existing and existing.get("points_awarded") is not None:
                    st.caption(f"Pontos: **{existing['points_awarded']}**")
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                with st.form(key=f"bet_{m['id']}"):
                    st.markdown(f"**{date_str}**")
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
    st.header("🏆 Classificação")

    leaderboard = db.get_leaderboard()
    user = auth.get_current_user() if auth.is_logged_in() else None

    if not leaderboard:
        st.info("Nenhuma pontuação registrada ainda.")
        return

    config = db.get_scoring_config()
    with st.expander("ℹ️ Regras de Pontuação"):
        st.markdown(f"""
        | Tipo | Pontos |
        |------|--------|
        | Placar exato | **{config['exact_score']}** |
        | Vencedor + saldo de gols | **{config['correct_winner_goal_diff']}** |
        | Acertou o vencedor | **{config['correct_winner']}** |
        | Acertou empate | **{config['correct_draw']}** |
        | Errou | **{config['wrong']}** |
        """)

    for i, entry in enumerate(leaderboard):
        rank = i + 1
        is_me = user and entry["user_id"] == user["id"]

        if rank == 1:
            medal = "🥇"
        elif rank == 2:
            medal = "🥈"
        elif rank == 3:
            medal = "🥉"
        else:
            medal = f"  {rank}."

        cols = st.columns([1, 3, 2, 2])
        cols[0].write(medal)
        name = f"**{entry['username']}** 👈" if is_me else entry["username"]
        cols[1].write(name)
        cols[2].write(f"**{entry['total_points']}** pts")
        cols[3].write(f"{entry['exact_count']} exato(s)")

        if is_me:
            st.markdown(
                '<hr style="border:1px solid #f0c040; margin:0;">',
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
