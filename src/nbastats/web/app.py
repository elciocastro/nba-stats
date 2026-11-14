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
from nbastats.metrics.apostas import (
    delete_bet, list_bets, load_bet_config, performance, settle_bets,
)
from nbastats.metrics.linhas import lines_for, save_line
from nbastats.sources import build_injury_source, build_source
from nbastats.web import props

st.set_page_config(page_title="NBA Stats", page_icon="🏀", layout="wide")
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
        settle_bets(conn, load_bet_config())
        if res["pulado"]:
            st.sidebar.info(f"Já atualizado há {res['minutos']} min; nada novo a buscar.")
        else:
            st.sidebar.success(f"Atualizado. Injury report de {res['relatorio'] or '—'} (ET).")


_refresh_box()
page = st.sidebar.radio("Página", ["Props", "Apostas", "Linhas", "Matchups (tabela)", "DvP",
                                   "Ranking", "Jogador", "Potenciais", "Jogo"])
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


if page == "Props":
    props.render(conn, last_refresh(conn))
    st.stop()

if page == "Apostas":
    import altair as alt

    cfg = load_bet_config()
    with st.container(horizontal=True, vertical_alignment="center"):
        st.markdown("### Apostas")
        if st.button("Conferir resultados", icon=":material/fact_check:"):
            done = settle_bets(conn, cfg)
            st.toast(f"Conferidas: {sum(done.values())}" if done else "Nada novo para conferir.")
    perf = performance(conn)
    g = perf["geral"]
    if not g["apostas"]:
        st.info("Nenhuma aposta registrada. Registre pelo detalhe do jogador na página Props "
                "(\"Registrar aposta\") ou com `nbastats apostar`.")
        st.stop()
    money = cfg.get("valor_unidade")
    cur = cfg.get("moeda", "R$")
    lucro = g["lucro_unidades"]
    cls = "over" if lucro > 0 else "under" if lucro < 0 else ""
    st.html(props.DETAIL_CSS + '<style>.over{color:#22c55e}.under{color:#ef4444}</style><div class="kp">' + "".join(
        f'<div><div class="l">{a}</div><div class="v">{b}</div><div class="s">{c}</div></div>' for a, b, c in [
            ("APOSTAS", g["apostas"], f"{g['pendentes']} pendentes"),
            ("ACERTO", f"{g['acerto_pct']:.0f}%" if g["acerto_pct"] is not None else "—",
             f"chance média {g['chance_media_pct']:.0f}%" if g["chance_media_pct"] is not None else ""),
            ("LUCRO", f'<span class="{cls}">{lucro:+.2f} u</span>',
             f"{cur} {lucro * money:+,.2f}" if money else ""),
            ("ROI", f'<span class="{cls}">{g["roi_pct"]:+.1f}%</span>' if g["roi_pct"] is not None else "—",
             f"{g['unidades_apostadas']:g} u apostadas"),
        ]) + "</div>")
    st.caption("Acerto real vs chance média calculada: se o acerto fica abaixo da chance por muitas "
               "apostas, o método está otimista. ROI só ganha significado depois de dezenas de apostas.")
    if len(perf["curva"]) >= 2:
        curve = [{"data": c["data"][8:] + "/" + c["data"][5:7], **c} for c in perf["curva"]]
        chart = alt.Chart(alt.Data(values=curve)).mark_area(
            line={"color": "#22c55e"}, point={"color": "#22c55e"}, color="#22c55e", opacity=0.12).encode(
            x=alt.X("data:O", title=None, sort=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("lucro_acumulado:Q", title="lucro (u)"),
            tooltip=["data:N", "lucro_acumulado:Q"])
        st.altair_chart(chart, width="stretch", height=180)
    else:
        st.caption("A curva de lucro aparece a partir do segundo dia com apostas conferidas.")

    tab1, tab2 = st.tabs(["Apostas", "Desempenho por grupo"])
    with tab1:
        status = st.pills("Status", ["pendente", "ganha", "perdida", "devolvida", "anulada"],
                          label_visibility="collapsed")
        bets = list_bets(conn, status=status)
        icon = {"ganha": "✅", "perdida": "❌", "devolvida": "↩️", "anulada": "⛔", "pendente": "⏳"}
        rows = [{"id": b["id"], "": icon.get(b["status"], ""), "Data": b["date"][8:] + "/" + b["date"][5:7],
                 "Jogador": b["jogador"], "Aposta": f"{b['side'].capitalize()} {b['line']:g} {props.MARKETS.get(b['market'], b['market'])}",
                 "Odd": b["odd"], "Unid.": b["units"], "Chance": b["prob"],
                 "Real": "" if b["actual"] is None else f"{b['actual']:g}",
                 "Lucro (u)": "" if b["profit_units"] is None else f"{b['profit_units']:+.2f}",
                 "Casa": b["bookmaker"] or ""}
                for b in bets]
        ev = st.dataframe(rows, hide_index=True, width="stretch", on_select="rerun",
                          selection_mode="single-row", key="bets_table",
                          column_order=["", "Jogador", "Aposta", "Lucro (u)", "Real", "Odd", "Unid.",
                                        "Chance", "Data", "Casa"],
                          column_config={"Chance": st.column_config.ProgressColumn(
                              "Chance", min_value=0, max_value=1, format="percent")})
        sel = ev.selection.rows if ev and ev.selection else []
        if sel and st.button(f"Apagar aposta #{rows[sel[0]]['id']}", type="secondary"):
            delete_bet(conn, rows[sel[0]]["id"])
            st.rerun()
    with tab2:
        for key, title in (("mercado", "Por mercado"), ("unidades", "Por unidades (stake)"),
                           ("faixa_chance", "Por faixa de chance calculada"), ("lado", "Over x under")):
            st.markdown(f"**{title}**")
            st.dataframe([{"Grupo": k, "Apostas": v["conferidas"], "Acerto %": v["acerto_pct"],
                           "Chance média %": v["chance_media_pct"], "Lucro (u)": v["lucro_unidades"],
                           "ROI %": v["roi_pct"]} for k, v in perf[key].items()],
                         hide_index=True, width="stretch")
    st.stop()

if page == "Linhas":
    st.title("Linhas da casa")
    st.caption("Digite a linha e as odds (decimais) de cada jogador. Linha vazia apaga. "
               "A página Props usa estas linhas no lugar da referência.")
    c1, c2 = st.columns(2)
    day = c1.date_input("Data", date.today(), format="DD/MM/YYYY")
    stat = c2.selectbox("Mercado", list(props.MARKETS), format_func=props.MARKETS.get)
    report = props._report(conn, day.isoformat(), stat, last_refresh(conn))
    saved = lines_for(conn, day.isoformat(), stat)
    rows = [{"id": p["player_id"], "Jogador": p["jogador"], "Jogo": f"{g['jogo']['visitor']} @ {g['jogo']['home']}",
             "L10": p["l10"], "Projeção": p.get("proj"),
             "Linha": (saved.get(p["player_id"]) or {}).get("line"),
             "Odd over": (saved.get(p["player_id"]) or {}).get("odd_over"),
             "Odd under": (saved.get(p["player_id"]) or {}).get("odd_under")}
            for g in report for p in g["jogadores"]]
    if not rows:
        st.info("Nenhum jogo nesta data.")
        st.stop()
    edited = st.data_editor(
        rows, hide_index=True, width="stretch", key=f"ed_{day}_{stat}",
        disabled=["Jogador", "Jogo", "L10", "Projeção"], column_order=[
            "Jogador", "Jogo", "L10", "Projeção", "Linha", "Odd over", "Odd under"],
        column_config={"Linha": st.column_config.NumberColumn(step=0.5, format="%.1f"),
                       "Odd over": st.column_config.NumberColumn(step=0.01, format="%.2f"),
                       "Odd under": st.column_config.NumberColumn(step=0.01, format="%.2f"),
                       "Projeção": st.column_config.NumberColumn(format="%.1f")})
    if st.button("Salvar linhas", type="primary"):
        n = 0
        for old, new in zip(rows, edited):
            if (old["Linha"], old["Odd over"], old["Odd under"]) != (new["Linha"], new["Odd over"], new["Odd under"]):
                save_line(conn, day.isoformat(), new["id"], stat,
                          new["Linha"] if new["Linha"] not in ("", None) else None,
                          new["Odd over"] or None, new["Odd under"] or None)
                n += 1
        st.success(f"{n} linha(s) salva(s).")
    st.stop()

if page == "Matchups (tabela)":
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
