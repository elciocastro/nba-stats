"""Páginas Comparar (jogador × jogador, time × time, tendências) e Notícias."""

from __future__ import annotations

from datetime import date
from typing import Any

import altair as alt
import streamlit as st

from nbastats.metrics import comparar as cp
from nbastats.metrics import load_matchup_rules, load_projection_params
from nbastats.metrics import noticias as nt
from nbastats.web import props


def _players(conn, day: str, stat: str, version) -> list[dict[str, Any]]:
    report = props._prepare(conn, day, stat, version, load_projection_params())
    return [p for g in report for p in g["jogadores"]]


def _side_by_side(a: dict[str, Any], b: dict[str, Any], stat: str, n: int = 10) -> alt.Chart:
    data = []
    for p in (a, b):
        for i, g in enumerate(reversed((p.get("historico") or [])[:n])):
            data.append({"jogador": p["jogador"], "jogo": i + 1, "valor": g[stat], "linha": p.get("linha")})
    bars = alt.Chart(alt.Data(values=data)).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
        x=alt.X("jogo:O", title=f"últimos {n} (mais antigo à esquerda)"), xOffset="jogador:N",
        y=alt.Y("valor:Q", title=None),
        color=alt.Color("jogador:N", scale=alt.Scale(range=["#3b82f6", "#f59e0b"]),
                        legend=alt.Legend(orient="top", title=None)),
        tooltip=["jogador:N", "valor:Q", "linha:Q"])
    return bars.properties(height=260)


def render(conn, version) -> None:
    st.markdown("### Comparar")
    rules = load_matchup_rules()
    day = st.date_input("Data", date.today(), format="DD/MM/YYYY", width=140)
    t1, t2, t3 = st.tabs(["Jogador × jogador", "Time × time", "Tendências"])

    with t1:
        stat = st.pills("Mercado", list(props.MARKETS), default="pra", format_func=props.MARKETS.get,
                        key="cmp_stat", label_visibility="collapsed") or "pra"
        players = _players(conn, day.isoformat(), stat, version)
        if len(players) < 2:
            st.info("Precisa de jogos nesta data para comparar.")
        else:
            names = {p["player_id"]: f"{p['jogador']} ({p['time']} x {p['adversario']})" for p in players}
            by_id = {p["player_id"]: p for p in players}
            c1, c2 = st.columns(2)
            a = c1.selectbox("Jogador A", list(names), format_func=names.get, key="cmp_a")
            b = c2.selectbox("Jogador B", list(names), index=1, format_func=names.get, key="cmp_b")
            if a == b:
                st.caption("Escolha dois jogadores diferentes.")
            else:
                pa, pb = by_id[a], by_id[b]
                st.dataframe(cp.compare_players(pa, pb), hide_index=True, width="stretch")
                st.altair_chart(_side_by_side(pa, pb, stat), width="stretch")
                cfg = props.betaniag_cfg()
                if cfg:
                    from nbastats import ia
                    ok, why = ia.status(cfg)
                    with st.expander("Pergunta livre à IA", icon=":material/auto_awesome:"):
                        if not ok:
                            st.caption(why)
                        else:
                            q = st.text_input("Pergunta", f"Compare {pa['jogador']} e {pb['jogador']} "
                                                            f"em {props.MARKETS[stat]} hoje")
                            if st.button("Perguntar"):
                                with st.spinner("Escrevendo..."):
                                    data = {"props": [ia.player_payload(p, stat, p.get("selo"), None)
                                                      for p in (pa, pb)]}
                                    st.markdown(ia.report(cfg, data, q))

    with t2:
        teams = {r["id"]: r["abbreviation"] for r in conn.execute(
            "SELECT id, abbreviation FROM teams WHERE abbreviation IS NOT NULL ORDER BY abbreviation")}
        games = [g for g in conn.execute(
            "SELECT g.home_team_id, g.visitor_team_id FROM games g WHERE g.date = ?", (day.isoformat(),))]
        pairs = {f"{teams.get(g['visitor_team_id'])} @ {teams.get(g['home_team_id'])}":
                 (g["visitor_team_id"], g["home_team_id"]) for g in games}
        pick = st.pills("Jogos do dia", list(pairs), key="cmp_game", label_visibility="collapsed")
        c1, c2 = st.columns(2)
        ids = list(teams)
        da, db = pairs[pick] if pick else (ids[0], ids[1])
        ta = c1.selectbox("Time A", ids, index=ids.index(da), format_func=teams.get, key=f"ta_{pick}")
        tb = c2.selectbox("Time B", ids, index=ids.index(db), format_func=teams.get, key=f"tb_{pick}")
        res = cp.team_compare(conn, day.isoformat(), ta, tb, rules)
        if not res:
            st.info("Sem dados para a data.")
        else:
            A, B = res["a"], res["b"]
            st.dataframe([{"Item": k, A["time"]: A[f], B["time"]: B[f]} for k, f in (
                ("Jogos", "jogos"), ("Ritmo (posses/48)", "ritmo"), ("Saldo médio", "saldo"),
                ("Pontos feitos", "pts_feitos"), ("Pontos cedidos", "pts_cedidos"))],
                hide_index=True, width="stretch")
            st.caption(f"Ritmo da liga: {res['liga_ritmo']}. DvP: rank 30 = cede mais; "
                       f"recente = últimos {rules.get('dvp_recente_dias', 15)} dias.")
            stat2 = st.segmented_control("Mercado do DvP", list(cp.COMPARE_STATS), default="pra",
                                         format_func=props.MARKETS.get, key="cmp_dvp") or "pra"
            rows = []
            for da_, db_ in zip(A["dvp"], B["dvp"]):
                if da_["stat"] != stat2:
                    continue
                rows.append({"Posição": da_["grupo"],
                             f"{A['time']} cede": da_["media"], f"{A['time']} rank": da_["rank"],
                             f"{A['time']} rank 15d": da_["rank_rec"],
                             f"{B['time']} cede": db_["media"], f"{B['time']} rank": db_["rank"],
                             f"{B['time']} rank 15d": db_["rank_rec"]})
            st.dataframe(rows, hide_index=True, width="stretch")

    with t3:
        tr = cp.trends(conn, day.isoformat(), rules)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Ganharam minutos** (L5 − temporada)")
            st.dataframe([{"Jogador": r["jogador"], "Time": r["time"], "Min L5": r["l5"],
                           "Min temp.": r["temporada"], "Dif": r["dif"], "PRA L5": r["pra_l5"]}
                          for r in tr["minutos"]], hide_index=True, width="stretch")
            st.markdown("**Ganharam uso** (taxa de uso %, L5 − temporada)")
            st.dataframe([{"Jogador": r["jogador"], "Time": r["time"], "Uso L5": r["l5"],
                           "Uso temp.": r["temporada"], "Dif": r["dif"]} for r in tr["uso"]],
                         hide_index=True, width="stretch")
        with c2:
            st.markdown("**Perderam minutos**")
            st.dataframe([{"Jogador": r["jogador"], "Time": r["time"], "Min L5": r["l5"],
                           "Min temp.": r["temporada"], "Dif": r["dif"]} for r in tr["minutos_queda"]],
                         hide_index=True, width="stretch")
            st.markdown(f"**Defesas que pioraram** (PRA cedido, últimos {rules.get('dvp_recente_dias', 15)} "
                        "dias − temporada)")
            st.dataframe([{"Time": r["time"], "Posição": r["grupo"], "Temp.": r["pra_temporada"],
                           "Recente": r["pra_recente"], "Dif": r["dif"], "Rank rec.": r["rank_recente"]}
                          for r in tr["defesas"]], hide_index=True, width="stretch")


ICON = {"entrou": "🆕", "saiu": "✅", "melhorou": "⬆️", "piorou": "⬇️", "lista": "•"}


def render_news(conn) -> None:
    st.markdown("### Notícias de lesão")
    day = st.date_input("Data", date.today(), format="DD/MM/YYYY", width=140, key="news_day")
    ch = nt.changes(conn, day.isoformat())
    if not ch["atual"]:
        st.info("Nenhum injury report guardado para esta data. Use \"Atualizar agora\".")
    else:
        st.caption(f"Último relatório: {ch['atual'][11:]} ET"
                   + (f" · comparado com {ch['anterior'][11:]} ET" if ch["anterior"] else " (primeiro do dia)"))
        rows = [{"": ICON.get(c["tipo"], ""), "Jogador": c["jogador"], "Time": c["time"],
                 "Antes": c["antes"] or "—", "Agora": c["agora"] or "fora da lista", "Motivo": c["motivo"]}
                for c in ch["mudancas"]]
        if rows:
            st.dataframe(rows, hide_index=True, width="stretch")
        else:
            st.caption("Nada mudou entre os dois últimos relatórios.")
        with st.expander("Relatórios do dia"):
            st.dataframe([{"Publicado (ET)": r["published_at"][11:], "Nomes": r["nomes"]}
                          for r in nt.reports_for(conn, day.isoformat())], hide_index=True)

    st.markdown("#### Podem voltar hoje")
    st.caption("Ficaram fora do último jogo do time e não estão como Out/Doubtful no último relatório. "
               "Médias dos últimos 5 jogos que disputaram.")
    ret = nt.returns(conn, day.isoformat())
    if not ret:
        st.caption("Ninguém relevante.")
        return
    minutes = st.slider("Com quantos minutos?", 10, 40, 28, help="Projeção simples: PRA por minuto × minutos.")
    st.dataframe([{"Jogador": r["jogador"], "Time": r["time"], "Status": r["status"],
                   "Jogos fora": r["jogos_fora"], "Min antes": r["minutos_antes"],
                   "PTS": r["pts"], "REB": r["reb"], "AST": r["ast"], "PRA": r["pra"],
                   f"PRA com {minutes} min": round(r["pra_por_min"] * minutes, 1)} for r in ret],
                 hide_index=True, width="stretch")
    st.caption("Na volta de lesão o técnico costuma limitar os minutos; a página do jogador tem o "
               "\"E se jogar X minutos\" com a projeção completa.")
