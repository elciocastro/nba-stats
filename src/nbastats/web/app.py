"""Site (Streamlit). Rodar: streamlit run src/nbastats/web/app.py

As telas só chamam nbastats.metrics; nenhuma regra de negócio mora aqui.
"""

from __future__ import annotations

import hmac
from datetime import date

import streamlit as st

from nbastats import db
from nbastats.config import get_settings
from nbastats.metrics import (
    MATCHUP_STATS, boxscore, dvp_table, load_matchup_rules, load_rules, matchup_report,
    player_gamelog, player_trends, rank_potenciais, seasons,
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

page = st.sidebar.radio("Página", ["Matchups", "DvP", "Ranking", "Jogador", "Potenciais", "Jogo"])
season = st.sidebar.selectbox(
    "Temporada", available, format_func=lambda s: f"{s}-{str(s + 1)[-2:]}"
)

STAT_NAMES = {"pts": "Pontos", "reb": "Rebotes", "ast": "Assistências", "fg3m": "Bolas de 3",
              "stl": "Roubos", "blk": "Tocos", "turnover": "Erros"}
CRIT_NAMES = {"forma": "Forma", "consistencia": "Consist.", "minutos": "Minutos", "uso": "Uso",
              "dvp_temporada": "DvP temp.", "dvp_recente": "DvP rec.", "ritmo": "Ritmo",
              "blowout": "Sem blowout"}


def _mark(value):
    return "✓" if value else ("–" if value is None else "✗")


def _matchup_rows(players):
    rows = []
    for p in players:
        row = {
            "Jogador": p["jogador"] + (" ⚠" if p["fora_ultimo_jogo"] else ""),
            "Time": p["time"], "Pos": p["grupo"] or "?",
            "Min L5/L10": f"{p['min_l5']:.0f} / {p['min_l10']:.0f}",
            "Temp.": p["temporada"], "L10": p["l10"], "L5": p["l5"],
            "DvP": p["dvp"], "DvP rank": p["dvp_rank"], "DvP 15d rank": p["dvp_rec_rank"],
            "Nota": p["nota"],
        }
        row.update({CRIT_NAMES[k]: _mark(v) for k, v in p["criterios"].items()})
        if p["real"] is not None:
            row["Real"] = p["real"]
        rows.append(row)
    return rows


if page == "Matchups":
    rules = load_matchup_rules()
    st.title("Matchups do dia")
    c1, c2, c3 = st.columns([1, 1, 2])
    day = c1.date_input("Data", date.today(), format="DD/MM/YYYY")
    stats_ok = rules.get("estatisticas") or list(MATCHUP_STATS)
    stat = c2.selectbox("Estatística", stats_ok, format_func=lambda s: STAT_NAMES.get(s, s))
    so_fav = c3.toggle("Só adversário entre os piores da liga na posição (DvP)", value=False)
    report = matchup_report(conn, day.isoformat(), stat, rules)
    if not report:
        st.info("Nenhum jogo nesta data. Para jogos futuros, rode `nbastats sync-agenda`.")
        st.stop()

    rank_min = (rules.get("criterios", {}).get("dvp_temporada") or {}).get("rank_min", 26)
    with st.expander("Como ler"):
        st.markdown(f"""
- **L5 / L10 / Temp.**: média de {STAT_NAMES[stat].lower()} nos últimos 5 e 10 jogos e na temporada,
  só com jogos **antes** desta data.
- **DvP**: quanto o adversário cede por jogo à posição do jogador. **Rank 30 = cede mais**
  (alvo favorável); 1 = melhor defesa. **15d** = só os últimos {rules.get('dvp_recente_dias', 15)} dias.
- **Pos**: a nba_api só tem G, F e C (sem PG/SG/SF/PF). Híbridos seguem `config/matchup.yaml`.
- **Nota**: quantos critérios passaram (✓). Limites em `config/matchup.yaml`.
- **⚠**: não jogou a última partida do time; confirmar se joga. Lesões não vêm da fonte.
- **Real**: aparece em datas passadas, para conferir o método.
- **Teste retroativo (2025-26, pontos)**: contra defesas entre as 5 piores na posição, o jogador
  fez +0,8 ponto acima do próprio L10; contra as 5 melhores, −0,8. A nota com todos os critérios
  quase não separou (forte +0,2). Rode `nbastats backtest 2025` após mudar o YAML.
""")

    for item in report:
        g = item["jogo"]
        if g["home_team_score"] is not None:
            head = f"{g['visitor']} {g['visitor_team_score']} @ {g['home']} {g['home_team_score']}"
        else:
            head = f"{g['visitor']} @ {g['home']} · {g['status'] or ''}"
        players = item["jogadores"]
        if so_fav:
            players = [p for p in players if (p["dvp_rank"] or 0) >= rank_min]
            if not players:
                continue
        with st.container(border=True):
            st.subheader(head)
            r, sd, d = item["ritmo"], item["saldo"], item["desfalques"]
            m1, m2, m3, m4 = st.columns(4)
            if r["casa"] is not None and r["fora"] is not None:
                m1.metric("Ritmo do jogo", f"{(r['casa'] + r['fora']) / 2:.1f}",
                          f"{(r['casa'] + r['fora']) / 2 - r['liga']:+.1f} vs liga")
                m2.metric("Saldo médio", f"{g['visitor']} {sd['fora']:+.1f} · {g['home']} {sd['casa']:+.1f}")
            m3.markdown(f"**Fora no último jogo ({g['visitor']})**  \n{', '.join(d['fora']) or '—'}")
            m4.markdown(f"**Fora no último jogo ({g['home']})**  \n{', '.join(d['casa']) or '—'}")
            if not players:
                st.caption("Sem jogadores com histórico suficiente.")
                continue
            rows = _matchup_rows(players)
            st.dataframe(
                rows, hide_index=True, width="stretch",
                column_config={
                    "Nota": st.column_config.ProgressColumn(
                        "Nota", min_value=0, max_value=len(rules.get("criterios", {})), format="%d"),
                    "DvP rank": st.column_config.NumberColumn("DvP rank", format="%dº"),
                    "DvP 15d rank": st.column_config.NumberColumn("DvP 15d", format="%dº"),
                },
            )

elif page == "DvP":
    rules = load_matchup_rules()
    st.title("Defesa por posição (DvP)")
    c1, c2, c3 = st.columns(3)
    day = c1.date_input("Até a data", date.today(), format="DD/MM/YYYY")
    stat = c2.selectbox("Estatística", rules.get("estatisticas") or list(MATCHUP_STATS),
                        format_func=lambda s: STAT_NAMES.get(s, s))
    recent = c3.toggle(f"Só os últimos {rules.get('dvp_recente_dias', 15)} dias")
    st.caption("Média cedida por jogo a cada posição. Rank 30 = cede mais (defesa mais vulnerável).")
    table = dvp_table(conn, season, day.isoformat(), stat, rules, recent=recent)
    groups = sorted(set(rules.get("posicoes", {}).values()))
    sort_by = st.radio("Ordenar por", groups, horizontal=True)
    table.sort(key=lambda r: r.get(f"{sort_by}_rank", 0), reverse=True)
    st.dataframe(
        table, hide_index=True, width="stretch",
        column_config={f"{g}_rank": st.column_config.NumberColumn(f"{g} rank", format="%dº")
                       for g in groups},
    )

elif page == "Ranking":
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
