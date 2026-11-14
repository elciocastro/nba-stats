"""Site (Streamlit). Rodar: streamlit run src/nbastats/web/app.py

As telas só chamam nbastats.metrics; nenhuma regra de negócio mora aqui.
"""

from __future__ import annotations

import hmac

import streamlit as st

from nbastats import db
from nbastats.config import get_settings
from nbastats.metrics import (
    boxscore, load_rules, player_gamelog, player_trends, rank_potenciais, seasons,
)

st.set_page_config(page_title="NBA Stats", layout="wide")
settings = get_settings()


def check_password() -> bool:
    if not settings.password:
        return True  # dev local sem senha
    if st.session_state.get("auth"):
        return True
    typed = st.text_input("Senha", type="password")
    if typed and hmac.compare_digest(typed, settings.password):
        st.session_state["auth"] = True
        st.rerun()
    elif typed:
        st.error("Senha incorreta")
    return False


if not check_password():
    st.stop()

conn = db.connect(settings.db_path)
db.init_db(conn)

available = seasons(conn)
if not available:
    st.title("NBA Stats")
    st.info("Base vazia. Rode `nbastats sync-season <ano>` para carregar uma temporada.")
    st.stop()

page = st.sidebar.radio("Página", ["Ranking", "Jogador", "Potenciais", "Jogo"])
season = st.sidebar.selectbox(
    "Temporada", available, format_func=lambda s: f"{s}-{str(s + 1)[-2:]}"
)

if page == "Ranking":
    st.title("Ranking de jogadores")
    min_games = st.sidebar.number_input("Mínimo de jogos", 1, 82, 10)
    last_n = st.sidebar.number_input("Janela recente (jogos)", 3, 30, 10)
    st.caption(f"Colunas com _n são a média dos últimos {last_n} jogos.")
    st.dataframe(player_trends(conn, season, last_n, min_games),
                 hide_index=True, width="stretch")

elif page == "Jogador":
    st.title("Ficha do jogador")
    players = player_trends(conn, season)
    chosen = st.selectbox("Jogador", players, format_func=lambda r: f"{r['jogador']} ({r['time']})")
    if chosen:
        log = player_gamelog(conn, chosen["player_id"], season)
        cols = st.columns(4)
        for col, stat in zip(cols, ("pts", "reb", "ast", "minutes")):
            delta = round(chosen[f"{stat}_n"] - chosen[stat], 1)
            col.metric(stat.upper(), chosen[stat], delta)
        stat = st.radio("Estatística", ["pts", "reb", "ast", "stl", "blk", "fg3m"], horizontal=True)
        st.line_chart(log, x="data", y=stat)
        st.dataframe(log, hide_index=True, width="stretch")

elif page == "Potenciais":
    st.title("Jogadores em potencial")
    rules = load_rules()
    st.caption("Regras em config/potencial.yaml. A nota compara os últimos "
               f"{rules.get('ultimos_jogos', 10)} jogos com a média da temporada.")
    with st.expander("Regras em uso"):
        st.json(rules)
    st.dataframe(rank_potenciais(conn, season, rules), hide_index=True, width="stretch")

else:
    st.title("Box score de um jogo")
    a, b, c = st.columns(3)
    team_a = a.text_input("Time A (sigla)", "GSW")
    team_b = b.text_input("Time B (sigla)", "CHI")
    on_date = c.text_input("Data (AAAA-MM-DD, opcional)", "")
    found = boxscore(conn, team_a, team_b, on_date or None)
    if not found:
        st.warning("Jogo não encontrado na base.")
    else:
        g = found["jogo"]
        st.subheader(f"{g['date']}: {g['visitor']} {g['visitor_team_score']} @ "
                     f"{g['home']} {g['home_team_score']}")
        st.dataframe(found["jogadores"], hide_index=True, width="stretch")
