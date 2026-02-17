"""
Bolão - Soccer Betting Pool.
Flask application with user-created leagues.
"""

import os
import urllib.request
import json
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for, flash, g, session,
)
from dotenv import load_dotenv

load_dotenv()

import db
import auth


# ─── App factory ──────────────────────────────────────────────────────────────

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Initialize database
    db.init_db()
    db.cleanup_old_sessions()

    # Turnstile config (optional — if keys not set, only honeypot is used)
    TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "")
    TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "")

    def verify_turnstile(token: str) -> bool:
        """Verify Cloudflare Turnstile token. Returns True if valid or if Turnstile is not configured."""
        if not TURNSTILE_SECRET_KEY:
            return True
        try:
            data = json.dumps({"secret": TURNSTILE_SECRET_KEY, "response": token}).encode()
            req = urllib.request.Request(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                result = json.loads(resp.read())
            return result.get("success", False)
        except Exception:
            return True  # fail open — don't block users if Cloudflare is down

    # ─── Request lifecycle: shared DB connection ────────────────────────

    @app.before_request
    def before_request():
        db.begin_shared_conn()
        auth.restore_session()

    @app.teardown_request
    def teardown_request(exc):
        db.end_shared_conn(commit=(exc is None))

    # ─── Context processor: inject common variables into all templates ────

    @app.context_processor
    def inject_globals():
        ctx = {"user_leagues": [], "active_league": None, "turnstile_site_key": TURNSTILE_SITE_KEY}
        if g.user:
            ctx["user_leagues"] = db.get_user_leagues(g.user["id"])
            # Determine active league
            active_id = session.get("active_league_id")
            if ctx["user_leagues"]:
                # Validate active_id is still a valid league
                valid_ids = {lg["id"] for lg in ctx["user_leagues"]}
                if active_id not in valid_ids:
                    active_id = ctx["user_leagues"][0]["id"]
                    session["active_league_id"] = active_id
                ctx["active_league"] = db.get_league_by_id(active_id)
        return ctx

    # ─── Helper: format match display time ────────────────────────────────

    def _enrich_matches(matches, user_bets=None):
        """Add _display_time and _locked flags to match dicts."""
        now = datetime.now()
        for m in matches:
            try:
                dt = datetime.fromisoformat(m["match_time"])
                m["_display_time"] = dt.strftime("%d/%m %H:%M")
                m["_locked"] = now >= dt or m.get("is_finished", 0)
            except (ValueError, TypeError):
                m["_display_time"] = m["match_time"][:16]
                m["_locked"] = True
        return matches

    # ─── Public routes ────────────────────────────────────────────────────

    @app.route("/")
    def home():
        pending_league = None
        invite_code = session.get("pending_invite")
        if invite_code:
            pending_league = db.get_league_by_invite_code(invite_code)
        return render_template("home.html", pending_league=pending_league)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = db.get_user_by_username(username)
            if user and auth.verify_password(password, user["password_hash"]):
                auth.login_user(user)
                # Handle pending invite
                invite_code = session.pop("pending_invite", None)
                if invite_code:
                    league = db.get_league_by_invite_code(invite_code)
                    if league:
                        db.join_league(league["id"], user["id"])
                        session["active_league_id"] = league["id"]
                        flash(f"Você entrou na liga '{league['name']}'!", "success")
                        return redirect(url_for("league_dashboard", league_id=league["id"]))
                next_url = request.form.get("next") or url_for("home")
                return redirect(next_url)
            flash("Usuário ou senha incorretos.", "danger")
        return render_template("login.html", next_url=request.args.get("next"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            # Honeypot: if the hidden field is filled, it's a bot
            if request.form.get("website", ""):
                flash("Registro bloqueado.", "danger")
                return redirect(url_for("register"))
            # Turnstile verification (skipped if not configured)
            turnstile_token = request.form.get("cf-turnstile-response", "")
            if TURNSTILE_SECRET_KEY and not verify_turnstile(turnstile_token):
                flash("Verificação de segurança falhou. Tente novamente.", "danger")
                return redirect(url_for("register"))
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            password2 = request.form.get("password2", "")
            if len(username) < 3:
                flash("O nome de usuário deve ter pelo menos 3 caracteres.", "warning")
            elif len(password) < 4:
                flash("A senha deve ter pelo menos 4 caracteres.", "warning")
            elif password != password2:
                flash("As senhas não coincidem.", "warning")
            else:
                user_id = db.create_user(username, auth.hash_password(password))
                if user_id:
                    user = db.get_user_by_username(username)
                    auth.login_user(user)
                    # Handle pending invite
                    invite_code = session.pop("pending_invite", None)
                    if invite_code:
                        league = db.get_league_by_invite_code(invite_code)
                        if league:
                            db.join_league(league["id"], user["id"])
                            session["active_league_id"] = league["id"]
                            flash(f"Conta criada! Você entrou na liga '{league['name']}'.", "success")
                            return redirect(url_for("league_dashboard", league_id=league["id"]))
                    flash("Conta criada com sucesso!", "success")
                    return redirect(url_for("home"))
                flash("Este nome de usuário já está em uso.", "warning")
        return render_template("register.html")

    @app.route("/logout")
    def logout():
        auth.logout_user()
        flash("Você saiu da sua conta.", "info")
        return redirect(url_for("home"))

    @app.route("/join/<invite_code>")
    def join_via_link(invite_code):
        league = db.get_league_by_invite_code(invite_code)
        if not league:
            flash("Código de convite inválido.", "danger")
            return redirect(url_for("home"))
        if not g.user:
            session["pending_invite"] = invite_code
            flash("Faça login ou crie uma conta para entrar na liga.", "info")
            return redirect(url_for("login"))
        already_member = db.is_league_member(league["id"], g.user["id"])
        return render_template("league_join.html", league=league, already_member=already_member)

    # ─── Profile ─────────────────────────────────────────────────────────

    @app.route("/profile", methods=["GET", "POST"])
    @auth.login_required
    def profile():
        user = g.user
        if request.method == "POST":
            action = request.form.get("action")

            if action == "username":
                new_name = request.form.get("username", "").strip()
                if len(new_name) < 3:
                    flash("O nome de usuário deve ter pelo menos 3 caracteres.", "warning")
                elif db.update_username(user["id"], new_name):
                    flash("Nome de usuário atualizado!", "success")
                    # Refresh session user data
                    user = db.get_user_by_username(new_name)
                    g.user = user
                else:
                    flash("Este nome de usuário já está em uso.", "warning")

            elif action == "password":
                current = request.form.get("current_password", "")
                new_pw = request.form.get("new_password", "")
                confirm = request.form.get("confirm_password", "")
                if not auth.verify_password(current, user["password_hash"]):
                    flash("Senha atual incorreta.", "danger")
                elif len(new_pw) < 4:
                    flash("A nova senha deve ter pelo menos 4 caracteres.", "warning")
                elif new_pw != confirm:
                    flash("As senhas não conferem.", "warning")
                else:
                    db.update_password(user["id"], auth.hash_password(new_pw))
                    flash("Senha atualizada!", "success")

            elif action == "avatar":
                avatar_url = request.form.get("avatar_url", "").strip()
                db.update_user_avatar(user["id"], avatar_url)
                flash("Avatar atualizado!" if avatar_url else "Avatar removido.", "success")

            return redirect(url_for("profile"))

        return render_template("profile.html", user=user)

    # ─── League switcher ──────────────────────────────────────────────────

    @app.route("/switch-league")
    @auth.login_required
    def switch_league():
        league_id = request.args.get("league_id", type=int)
        if league_id and db.is_league_member(league_id, g.user["id"]):
            session["active_league_id"] = league_id
        return redirect(request.referrer or url_for("home"))

    # ─── League CRUD routes ───────────────────────────────────────────────

    @app.route("/leagues")
    @auth.login_required
    def leagues_list():
        leagues = db.get_user_leagues(g.user["id"])
        return render_template("leagues.html", leagues=leagues)

    @app.route("/league/create", methods=["GET", "POST"])
    @auth.login_required
    def league_create():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            competition = request.form.get("competition", "Brasileirão")
            start_date = request.form.get("start_date") or None
            end_date = request.form.get("end_date") or None
            if not name:
                flash("O nome da liga é obrigatório.", "warning")
            elif competition not in ("Brasileirão", "Premier League"):
                flash("Competição inválida.", "danger")
            else:
                league = db.create_league(name, competition, g.user["id"], start_date, end_date)
                session["active_league_id"] = league["id"]
                flash(f"Liga '{name}' criada com sucesso!", "success")
                return redirect(url_for("league_leaderboard", league_id=league["id"]))
        return render_template("league_create.html")

    @app.route("/league/join", methods=["GET"])
    @auth.login_required
    def league_join_form():
        return render_template("league_join.html", league=None)

    @app.route("/league/join", methods=["POST"])
    @auth.login_required
    def league_join_by_code():
        invite_code = request.form.get("invite_code", "").strip()
        league = db.get_league_by_invite_code(invite_code)
        if not league:
            flash("Código de convite inválido.", "danger")
            return redirect(url_for("league_join_form"))
        if db.join_league(league["id"], g.user["id"]):
            session["active_league_id"] = league["id"]
            flash(f"Você entrou na liga '{league['name']}'!", "success")
        else:
            flash("Você já é membro desta liga.", "info")
        return redirect(url_for("league_dashboard", league_id=league["id"]))

    # ─── League-scoped routes ─────────────────────────────────────────────

    @app.route("/league/<int:league_id>")
    @auth.league_member_required
    def league_dashboard(league_id):
        league = db.get_league_by_id(league_id)
        if not league:
            flash("Liga não encontrada.", "danger")
            return redirect(url_for("leagues_list"))

        session["active_league_id"] = league_id

        leaderboard = db.get_league_leaderboard(league_id)
        avatars = db.get_user_avatars()
        upcoming = db.get_league_upcoming_matches(league_id)
        upcoming = _enrich_matches(upcoming)
        user_bets = db.get_user_bets(g.user["id"], league_id)
        league_role = db.get_league_member_role(league_id, g.user["id"])

        # Get team logos and odds
        all_teams = set()
        match_ids = []
        for m in upcoming:
            all_teams.add(m["home_team"])
            all_teams.add(m["away_team"])
            match_ids.append(m["id"])
        logos = db.get_team_logos(list(all_teams))
        odds = db.get_odds_for_matches(match_ids)

        return render_template("league_dashboard.html",
                               league=league, leaderboard=leaderboard, avatars=avatars,
                               upcoming_matches=upcoming, user_bets=user_bets,
                               logos=logos, odds=odds, league_role=league_role)

    @app.route("/league/<int:league_id>/bets")
    @auth.league_member_required
    def league_bets(league_id):
        league = db.get_league_by_id(league_id)
        if not league:
            flash("Liga não encontrada.", "danger")
            return redirect(url_for("leagues_list"))

        session["active_league_id"] = league_id

        all_matches = db.get_league_upcoming_matches(league_id)
        finished = db.get_league_finished_matches(league_id)
        all_matches = _enrich_matches(all_matches)
        finished = _enrich_matches(finished)

        open_matches = [m for m in all_matches if not m["_locked"]]
        locked_upcoming = [m for m in all_matches if m["_locked"]]
        locked_matches = locked_upcoming + finished

        user_bets = db.get_user_bets(g.user["id"], league_id)

        # Logos and odds
        all_teams = set()
        match_ids = []
        for m in all_matches + finished:
            all_teams.add(m["home_team"])
            all_teams.add(m["away_team"])
            match_ids.append(m["id"])
        logos = db.get_team_logos(list(all_teams))
        odds = db.get_odds_for_matches(match_ids)

        return render_template("bets.html", league=league,
                               open_matches=open_matches, locked_matches=locked_matches,
                               user_bets=user_bets, logos=logos, odds=odds)

    @app.route("/league/<int:league_id>/bets", methods=["POST"])
    @auth.league_member_required
    def league_bets_submit(league_id):
        league = db.get_league_by_id(league_id)
        if not league:
            flash("Liga não encontrada.", "danger")
            return redirect(url_for("leagues_list"))

        saved = 0
        for key in request.form:
            if key.startswith("home_"):
                match_id = int(key.replace("home_", ""))
                home_val = request.form.get(f"home_{match_id}", "").strip()
                away_val = request.form.get(f"away_{match_id}", "").strip()
                if home_val != "" and away_val != "":
                    try:
                        home_score = int(home_val)
                        away_score = int(away_val)
                        if 0 <= home_score <= 99 and 0 <= away_score <= 99:
                            if db.upsert_bet(g.user["id"], match_id, league_id, home_score, away_score):
                                saved += 1
                    except (ValueError, TypeError):
                        pass

        if saved:
            flash(f"{saved} palpite(s) salvo(s)!", "success")
        else:
            flash("Nenhum palpite foi salvo.", "warning")

        referrer = request.referrer
        if referrer and "bets" in referrer:
            return redirect(url_for("league_bets", league_id=league_id))
        return redirect(url_for("league_dashboard", league_id=league_id))

    @app.route("/league/<int:league_id>/leaderboard")
    @auth.league_member_required
    def league_leaderboard(league_id):
        league = db.get_league_by_id(league_id)
        if not league:
            flash("Liga não encontrada.", "danger")
            return redirect(url_for("leagues_list"))

        session["active_league_id"] = league_id

        leaderboard = db.get_league_leaderboard(league_id)
        avatars = db.get_user_avatars()
        scoring = db.get_league_scoring(league_id)
        members = db.get_league_members(league_id)
        league_role = db.get_league_member_role(league_id, g.user["id"])

        invite_url = request.host_url.rstrip("/") + url_for("join_via_link", invite_code=league["invite_code"])

        return render_template("leaderboard.html",
                               league=league, leaderboard=leaderboard, avatars=avatars,
                               scoring=scoring, members=members, league_role=league_role,
                               invite_url=invite_url)

    # ─── League settings routes ───────────────────────────────────────────

    @app.route("/league/<int:league_id>/settings")
    @auth.league_member_required
    def league_settings(league_id):
        league = db.get_league_by_id(league_id)
        if not league:
            return redirect(url_for("leagues_list"))
        role = db.get_league_member_role(league_id, g.user["id"])
        if role != "admin":
            flash("Apenas o admin da liga pode acessar as configurações.", "warning")
            return redirect(url_for("league_dashboard", league_id=league_id))
        scoring = db.get_league_scoring(league_id)
        invite_url = request.host_url.rstrip("/") + url_for("join_via_link", invite_code=league["invite_code"])
        return render_template("league_settings.html", league=league, scoring=scoring, invite_url=invite_url)

    @app.route("/league/<int:league_id>/settings", methods=["POST"])
    @auth.league_member_required
    def league_settings_update(league_id):
        role = db.get_league_member_role(league_id, g.user["id"])
        if role != "admin":
            flash("Sem permissão.", "danger")
            return redirect(url_for("league_dashboard", league_id=league_id))

        name = request.form.get("name", "").strip()
        start_date = request.form.get("start_date") or None
        end_date = request.form.get("end_date") or None
        if name:
            db.update_league(league_id, name, start_date, end_date)
            flash("Configurações salvas!", "success")
        return redirect(url_for("league_settings", league_id=league_id))

    @app.route("/league/<int:league_id>/scoring", methods=["POST"])
    @auth.league_member_required
    def league_scoring_update(league_id):
        role = db.get_league_member_role(league_id, g.user["id"])
        if role != "admin":
            flash("Sem permissão.", "danger")
            return redirect(url_for("league_dashboard", league_id=league_id))

        try:
            exact = int(request.form.get("exact_score", 10))
            winner_diff = int(request.form.get("correct_winner_goal_diff", 5))
            winner = int(request.form.get("correct_winner", 3))
            draw = int(request.form.get("correct_draw", 3))
            wrong = int(request.form.get("wrong", 0))
            db.update_league_scoring(league_id, exact, winner_diff, winner, draw, wrong)
            flash("Pontuação atualizada e recalculada!", "success")
        except (ValueError, TypeError):
            flash("Valores inválidos.", "danger")
        return redirect(url_for("league_settings", league_id=league_id))

    @app.route("/league/<int:league_id>/leave", methods=["POST"])
    @auth.league_member_required
    def league_leave(league_id):
        if db.leave_league(league_id, g.user["id"]):
            flash("Você saiu da liga.", "info")
            session.pop("active_league_id", None)
            return redirect(url_for("leagues_list"))
        flash("O admin da liga não pode sair.", "warning")
        return redirect(url_for("league_dashboard", league_id=league_id))

    @app.route("/league/<int:league_id>/remove-member", methods=["POST"])
    @auth.league_member_required
    def league_remove_member(league_id):
        role = db.get_league_member_role(league_id, g.user["id"])
        if role != "admin":
            flash("Sem permissão.", "danger")
            return redirect(url_for("league_leaderboard", league_id=league_id))
        user_id = request.form.get("user_id", type=int)
        if user_id:
            db.remove_league_member(league_id, user_id)
            flash("Membro removido.", "info")
        return redirect(url_for("league_leaderboard", league_id=league_id))

    @app.route("/league/<int:league_id>/delete", methods=["POST"])
    @auth.login_required
    def league_delete(league_id):
        league = db.get_league_by_id(league_id)
        if not league:
            flash("Liga não encontrada.", "danger")
            return redirect(url_for("leagues_list"))
        role = db.get_league_member_role(league_id, g.user["id"])
        if role != "admin" and not auth.is_admin():
            flash("Sem permissão para deletar esta liga.", "danger")
            return redirect(url_for("league_dashboard", league_id=league_id))
        db.delete_league(league_id)
        if session.get("active_league_id") == league_id:
            session.pop("active_league_id", None)
        flash(f"Liga '{league['name']}' deletada.", "info")
        return redirect(url_for("leagues_list"))

    # ─── Admin routes ─────────────────────────────────────────────────────

    @app.route("/admin")
    @auth.admin_required
    def admin_dashboard():
        tab = request.args.get("tab", "matches")
        all_matches = db.get_all_matches() if tab == "matches" else []
        unfinished_matches = db.get_unfinished_matches() if tab == "results" else []
        all_users = db.get_all_users() if tab == "users" else []
        all_leagues = db.get_all_leagues() if tab == "leagues" else []
        return render_template("admin.html", tab=tab,
                               all_matches=all_matches,
                               unfinished_matches=unfinished_matches,
                               all_users=all_users,
                               all_leagues=all_leagues)

    @app.route("/admin/match", methods=["POST"])
    @auth.admin_required
    def admin_add_match():
        league = request.form.get("league", "Brasileirão")
        round_number = request.form.get("round_number", type=int)
        home_team = request.form.get("home_team", "").strip()
        away_team = request.form.get("away_team", "").strip()
        match_date = request.form.get("match_date", "")
        match_time = request.form.get("match_time", "")
        if home_team and away_team and match_date and match_time:
            match_datetime = f"{match_date}T{match_time}:00"
            db.add_match(round_number or 1, home_team, away_team, match_datetime, league)
            flash(f"Jogo adicionado: {home_team} vs {away_team}", "success")
        else:
            flash("Preencha todos os campos.", "warning")
        return redirect(url_for("admin_dashboard", tab="add"))

    @app.route("/admin/result", methods=["POST"])
    @auth.admin_required
    def admin_set_result():
        match_id = request.form.get("match_id", type=int)
        home_score = request.form.get("home_score", type=int)
        away_score = request.form.get("away_score", type=int)
        if match_id is not None and home_score is not None and away_score is not None:
            db.set_match_result(match_id, home_score, away_score)
            flash("Resultado salvo e pontos calculados!", "success")
        else:
            flash("Dados inválidos.", "danger")
        return redirect(url_for("admin_dashboard", tab="results"))

    @app.route("/admin/match/<int:match_id>/delete", methods=["POST"])
    @auth.admin_required
    def admin_delete_match(match_id):
        db.delete_match(match_id)
        flash("Jogo deletado.", "info")
        return redirect(url_for("admin_dashboard", tab="matches"))

    @app.route("/admin/user/delete", methods=["POST"])
    @auth.admin_required
    def admin_delete_user():
        user_id = request.form.get("user_id", type=int)
        if user_id and db.delete_user(user_id):
            flash("Usuário deletado.", "info")
        else:
            flash("Não foi possível deletar este usuário.", "warning")
        return redirect(url_for("admin_dashboard", tab="users"))

    return app


# ─── Run ──────────────────────────────────────────────────────────────────────

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
