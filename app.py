"""
Bolão do Brasileirão - Soccer Betting Pool for the Brazilian Série A.
Main Streamlit application.
"""

import streamlit as st
from datetime import datetime

import db
import auth

# ─── Page Config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Bolão do Brasileirão",
    page_icon="⚽",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Mobile-friendly CSS
st.markdown("""
<style>
    /* Compact layout for mobile */
    .block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 720px; }
    /* Match card styling */
    .match-card {
        background: #f8f9fa; border-radius: 10px; padding: 12px;
        margin-bottom: 8px; border-left: 4px solid #1a5276;
    }
    .match-card-locked {
        background: #f0f0f0; border-radius: 10px; padding: 12px;
        margin-bottom: 8px; border-left: 4px solid #aaa; opacity: 0.7;
    }
    /* Highlight row */
    .highlight-row { background-color: #fff3cd !important; font-weight: bold; }
    /* Sidebar adjustments */
    [data-testid="stSidebar"] { min-width: 200px; max-width: 260px; }
    /* Hide Streamlit branding */
    #MainMenu, footer { visibility: hidden; }
    /* Score input compact */
    .stNumberInput > div > div > input { text-align: center; }
</style>
""", unsafe_allow_html=True)

# ─── Init DB ───────────────────────────────────────────────────────────────────

db.init_db()

# ─── Sidebar Navigation ───────────────────────────────────────────────────────

PAGES = ["Login / Registro", "Meus Palpites", "Classificação"]

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
        page = st.radio("Navegação", pages, index=1, label_visibility="collapsed")
    else:
        page = PAGES[0]
        st.info("Faça login para acessar.")


# ─── Page: Login / Register ───────────────────────────────────────────────────

def page_login():
    st.header("⚽ Bolão do Brasileirão")
    st.caption("Série A - Palpites entre amigos")

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
                    user = db.get_user_by_username(username)
                    if user and auth.verify_password(password, user["password_hash"]):
                        auth.login_user(user)
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
                # Locked match display
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
                # Open match - allow betting
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

    # Build table
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

    # --- Add Matches ---
    with tab_add:
        st.subheader("Novo Jogo")

        TEAMS = [
            "Atlético-MG", "Athletico-PR", "Bahia", "Botafogo",
            "Bragantino", "Corinthians", "Criciúma", "Cruzeiro",
            "Cuiabá", "Flamengo", "Fluminense", "Fortaleza",
            "Grêmio", "Internacional", "Juventude", "Mirassol",
            "Palmeiras", "Santos", "São Paulo", "Sport", "Vasco",
            "Vitória", "Ceará", "Goiás", "Coritiba", "Ponte Preta",
        ]

        with st.form("add_match"):
            round_num = st.number_input("Rodada", min_value=1, max_value=38, value=1)
            col1, col2 = st.columns(2)
            home_team = col1.selectbox("Mandante", TEAMS, index=0)
            away_team = col2.selectbox("Visitante", TEAMS, index=1)
            match_date = st.date_input("Data")
            match_time = st.time_input("Horário")
            submitted = st.form_submit_button("Adicionar Jogo", use_container_width=True)
            if submitted:
                if home_team == away_team:
                    st.error("Times iguais!")
                else:
                    dt = datetime.combine(match_date, match_time).isoformat()
                    db.add_match(round_num, home_team, away_team, dt)
                    st.success(f"Jogo adicionado: {home_team} x {away_team}")
                    st.rerun()

        # Bulk add
        with st.expander("Adicionar vários jogos (rodada inteira)"):
            st.caption("Adicione múltiplos jogos com a mesma rodada, data e horário.")
            with st.form("bulk_add"):
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
                            db.add_match(bulk_round, parts[0], parts[1], dt)
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
                    st.markdown(f"**R{m['round_number'] or '?'} — {date_str}**")
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
                cols[0].write(
                    f"R{m['round_number'] or '?'} | {m['home_team']} x {m['away_team']} "
                    f"| {date_str} | {status}{result_str}"
                )
                if cols[1].button("🗑️", key=f"del_{m['id']}"):
                    db.delete_match(m["id"])
                    st.rerun()


# ─── Router ───────────────────────────────────────────────────────────────────

if page == PAGES[0]:
    if auth.is_logged_in():
        page_bets()
    else:
        page_login()
elif page == PAGES[1]:
    if not auth.is_logged_in():
        st.warning("Faça login para ver seus palpites.")
        page_login()
    else:
        page_bets()
elif page == PAGES[2]:
    page_leaderboard()
elif page == "Admin":
    page_admin()
