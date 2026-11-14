"""Site (Streamlit). Rodar: streamlit run src/nbastats/web/app.py

As telas só chamam nbastats.metrics; nenhuma regra de negócio mora aqui.
"""

from __future__ import annotations

import hmac
from datetime import date, datetime, timezone

import streamlit as st

from nbastats import db
from nbastats.config import get_settings
from nbastats.ingest import last_refresh, refresh
from nbastats.metrics import (
    MATCHUP_STATS, boxscore, dvp_table, load_matchup_rules, load_projection_params, load_rules,
    matchup_report,
    player_gamelog, player_trends, rank_potenciais, seasons,
)
from nbastats.sources import build_injury_source, build_source

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

def _refresh_box():
    last = last_refresh(conn)
    if last:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() / 60
        st.sidebar.caption(f"Última atualização: há {age:.0f} min")
    else:
        st.sidebar.caption("Nenhuma atualização completa ainda.")
    if st.sidebar.button("Atualizar agora", help="Estatísticas recentes, agenda e injury report"):
        with st.spinner("Buscando dados..."):
            try:
                res = refresh(conn, build_source(settings.fonte, settings), build_injury_source())
            except Exception as exc:  # erro fica no sync_log; aqui só avisa
                st.sidebar.error(f"Falhou: {exc}")
                return
        if res["pulado"]:
            st.sidebar.info(f"Já atualizado há {res['minutos']} min; nada novo a buscar.")
        else:
            st.sidebar.success(f"Atualizado. Injury report de {res['relatorio'] or '—'} (ET).")


_refresh_box()
page = st.sidebar.radio("Página", ["Matchups", "DvP", "Ranking", "Jogador", "Potenciais", "Jogo"])
season = st.sidebar.selectbox(
    "Temporada", available, format_func=lambda s: f"{s}-{str(s + 1)[-2:]}"
)

STAT_NAMES = {
    "pts": "Pontos", "reb": "Rebotes", "ast": "Assistências",
    "pra": "PRA (pts+reb+ast)", "pr": "PR (pts+reb)", "pa": "PA (pts+ast)", "ra": "RA (reb+ast)",
    "fg2m": "2FM (bolas de 2 certas)", "fg2a": "2FA (bolas de 2 tentadas)",
    "fg3m": "3FM (bolas de 3 certas)", "fg3a": "3FA (bolas de 3 tentadas)",
    "ftm": "FTM (lances livres certos)", "fta": "FTA (lances livres tentados)",
    "stl": "Roubos", "blk": "Tocos", "turnover": "Turnovers",
    "dd": "Duplo-duplo (frequência)", "td": "Triplo-duplo (frequência)",
}
CRIT_NAMES = {"forma": "Forma", "consistencia": "Consist.", "minutos": "Minutos", "uso": "Uso",
              "dvp_temporada": "DvP temp.", "dvp_recente": "DvP rec.", "ritmo": "Ritmo",
              "blowout": "Sem blowout"}


def _mark(value):
    return "✓" if value else ("–" if value is None else "✗")


def _matchup_rows(players, show_criteria):
    rows = []
    for p in players:
        com_sem = "; ".join(f"sem {c['companheiro']}: {c['sem']} ({c['jogos_sem']} j) · com: {c['com']}"
                            for c in p.get("com_sem", []) if c["jogos_sem"])
        row = {
            "Jogador": p["jogador"] + (" ⚠" if p["fora_ultimo_jogo"] and not p["lesao"] else ""),
            "Lesão": p["lesao"] or "",
            "Time": p["time"], "Pos": f"{p['grupo'] or '?'} · {p['posicao_est'] or '?'}",
            "Min L5/L10": f"{p['min_l5']:.0f} / {p['min_l10']:.0f}",
            "Temp.": p["temporada"], "L10": p["l10"], "L5": p["l5"],
            "Projeção": p.get("proj"), "vs L10": p.get("proj_vs_l10"),
            "DvP rank": p["dvp_rank"], "DvP 15d": p["dvp_rec_rank"],
            "Zonas (p.p.)": p.get("encaixe_zonas"),
            "Com/sem desfalque": com_sem,
        }
        if show_criteria:
            row["Nota"] = p["nota"]
            row.update({CRIT_NAMES[k]: _mark(v) for k, v in p["criterios"].items()})
        if p["real"] is not None:
            row["Real"] = p["real"]
        rows.append(row)
    return rows


def _explain(p, stat):
    d = p.get("proj_detalhe")
    if not d:
        return "Sem projeção (histórico insuficiente)."
    parts = [
        f"**{p['jogador']}** · {STAT_NAMES.get(stat, stat)}: projeção **{d['valor']}** "
        f"(L10 {p['l10']}, temporada {p['temporada']})",
        f"- Base: {d['base']} = taxa por minuto (L10 e temporada) × **{d['minutos']} min** esperados",
        f"- Defesa adversária (DvP, já com o peso da amostra): ×{d['f_dvp']}",
        f"- Ritmo do jogo: ×{d['f_ritmo']}",
        f"- Ajuste calibrado (nível + {100 * d['ausencia']:.0f}% da produção do time fora): ×{d['f_ajuste']}",
    ]
    if d.get("erro_tipico"):
        parts.append(f"- Erro típico deste mercado: ±{d['erro_tipico']}")
    for c in p.get("com_sem", []):
        parts.append(f"- Com {c['companheiro']}: {c['com']} em {c['jogos_com']} jogos · "
                     f"sem: {c['sem'] if c['sem'] is not None else '—'} em {c['jogos_sem']} jogos")
    return "\n".join(parts)


if page == "Matchups":
    rules, params = load_matchup_rules(), load_projection_params()
    st.title("Matchups do dia")
    c1, c2, c3 = st.columns([1, 1, 2])
    day = c1.date_input("Data", date.today(), format="DD/MM/YYYY")
    stats_ok = rules.get("estatisticas") or list(MATCHUP_STATS)
    stat = c2.selectbox("Mercado", stats_ok, format_func=lambda s: STAT_NAMES.get(s, s))
    with c3:
        so_fav = st.toggle("Só adversário entre os piores da liga na posição (DvP)", value=False)
        show_criteria = st.toggle("Mostrar critérios da anotação (✓/✗)", value=False)
    report = matchup_report(conn, day.isoformat(), stat, rules, params)
    if not report:
        st.info("Nenhum jogo nesta data. Use \"Atualizar agora\" para buscar a agenda.")
        st.stop()

    rank_min = (rules.get("criterios", {}).get("dvp_temporada") or {}).get("rank_min", 26)
    with st.expander("Como ler"):
        st.markdown(f"""
- **Projeção**: o número esperado para o jogo. Taxa por minuto (L10 e temporada) × minutos
  esperados × defesa adversária × ritmo × ajuste por desfalques do próprio time, calibrado com a
  temporada passada. Fora da amostra, erra **2 a 4% menos que o L10** em todos os mercados.
  **vs L10** = quanto a projeção fica acima ou abaixo da média recente. A lista vem ordenada por isso.
- **L5 / L10 / Temp.**: médias nos últimos 5 e 10 jogos e na temporada, só com jogos **antes**
  desta data.
- **DvP rank**: posição do adversário no que cede à posição do jogador. **30 = cede mais**.
- **Pos**: grupo do DvP (G/F/C) · posição **estimada** (PG/SG/SF/PF/C, pela altura e pelo perfil).
- **Lesão**: injury report oficial. Out some da lista; Doubtful, Questionable e Probable ficam.
- **Com/sem desfalque**: média do jogador nos jogos sem o companheiro que está fora hoje.
- **Zonas (p.p.)**: aproveitamento que o adversário cede acima (+) ou abaixo (−) da liga, pesado
  pelas zonas onde o jogador arremessa. Em 3FM/3FA só as zonas de 3; em 2FM/2FA só as de 2.
  Detalhe por zona em "Detalhar a projeção". Ainda **não validado** no teste retroativo.
- **Margem esperada e risco de blowout**: pelo saldo dos times, mando e desfalques. Com margem
  esperada de 15+, cerca de 6 em cada 10 jogos terminaram decididos por 15+.
- **⚠**: não jogou a última partida e não está no injury report (confirmar se joga).
- **Real**: aparece em datas passadas, para conferir.
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
            r, d = item["ritmo"], item["desfalques"]
            m1, m2, m3, m4 = st.columns(4)
            m = item.get("margem_esperada")
            if m is not None:
                fav = g["home"] if m >= 0 else g["visitor"]
                m1.metric("Margem esperada", f"{fav} por {abs(m):.1f}")
                m2.metric("Risco de blowout (15+)", f"{100 * item['risco_blowout']:.0f}%")
            elif r["casa"] is not None and r["fora"] is not None:
                m1.metric("Ritmo do jogo", f"{(r['casa'] + r['fora']) / 2:.1f}")
            label = (f"Injury report {item['injury_report'][11:]} ET" if item["injury_report"]
                     else "Fora no último jogo")
            m3.markdown(f"**{label} · {g['visitor']}**  \n{', '.join(d['fora']) or '—'}")
            m4.markdown(f"**{label} · {g['home']}**  \n{', '.join(d['casa']) or '—'}")
            if r["casa"] is not None and r["fora"] is not None:
                st.caption(f"Ritmo: {g['visitor']} {r['fora']} · {g['home']} {r['casa']} "
                           f"(liga {r['liga']}) · posses por 48 min")
            if not players:
                st.caption("Sem jogadores com histórico suficiente.")
                continue
            st.dataframe(
                _matchup_rows(players, show_criteria), hide_index=True, width="stretch",
                column_config={
                    "Projeção": st.column_config.NumberColumn("Projeção", format="%.1f"),
                    "vs L10": st.column_config.NumberColumn("vs L10", format="%+.1f"),
                    "Nota": st.column_config.ProgressColumn(
                        "Nota", min_value=0, max_value=len(rules.get("criterios", {})), format="%d"),
                    "DvP rank": st.column_config.NumberColumn("DvP rank", format="%dº"),
                    "DvP 15d": st.column_config.NumberColumn("DvP 15d", format="%dº"),
                    "Zonas (p.p.)": st.column_config.NumberColumn("Zonas (p.p.)", format="%+.1f"),
                },
            )
            chosen = st.selectbox("Detalhar a projeção de", [None] + players, key=f"det{g['id']}",
                                  format_func=lambda p: "—" if p is None else p["jogador"])
            if chosen:
                st.markdown(_explain(chosen, stat))
                zm = chosen.get("zonas")
                if zm:
                    st.markdown(f"**Zonas de arremesso** · encaixe {zm['encaixe_pp']:+.1f} p.p. "
                                f"(aproveitamento que o adversário cede acima da liga, nas zonas dele)")
                    st.dataframe([{
                        "Zona": z["zona"], "% dos arremessos dele": z["arremessos_dele_pct"],
                        "FG% dele": z["fg_dele"], "FG% cedido pelo adversário": z["fg_cedido"],
                        "FG% da liga": z["fg_liga"],
                        "Volume cedido (% / liga)": f"{z['volume_cedido_pct']} / {z['volume_liga_pct']}",
                    } for z in zm["zonas"]], hide_index=True, width="stretch")
                    st.caption("Temporada até a última carga das zonas; não entra no teste retroativo.")

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
