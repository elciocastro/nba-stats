"""Página "Props do dia": lista dinâmica por mercado, com barras dos últimos
jogos contra a linha, chance de over/under e detalhe ao tocar no jogador.

Só apresentação: números vêm de nbastats.metrics.
"""

from __future__ import annotations

import base64
from datetime import date
from typing import Any

import altair as alt
import streamlit as st

from nbastats.metrics import load_matchup_rules, load_projection_params, matchup_report
from nbastats.metrics.linhas import attach_lines, fair_odd, lines_for, prob_over, save_line

GREEN, RED, GREY = "#22c55e", "#ef4444", "#8b98a9"

MARKETS = {
    "pts": "Pontos", "reb": "Rebotes", "ast": "Assist.", "pra": "PRA", "pr": "PR", "pa": "PA",
    "ra": "RA", "fg3m": "3FM", "fg3a": "3FA", "fg2m": "2FM", "fg2a": "2FA", "ftm": "FTM",
    "fta": "FTA", "stl": "Roubos", "blk": "Tocos", "turnover": "Turnovers",
    "dd": "Duplo-duplo", "td": "Triplo-duplo",
}
WINDOWS = {"L5": 5, "L10": 10, "L20": 20, "Temp.": None}
SORTS = {
    "Maior vantagem (over ou under)": lambda p: max(p["p_over"] or 0, p["p_under"] or 0),
    "Chance de over": lambda p: p["p_over"] or 0,
    "Chance de under": lambda p: p["p_under"] or 0,
    "Projeção acima da linha": lambda p: p["proj_vs_linha"] or -99,
    "Valor esperado (com odd)": lambda p: max(p["ev_over"] or -9, p["ev_under"] or -9),
}


def headshot(player_id: int) -> str:
    return f"https://cdn.nba.com/headshots/nba/latest/260x190/{player_id}.png"


def bars_svg(values: list[float], line: float | None, width: int = 160, height: int = 44) -> str:
    """Barras dos jogos (mais antigo à esquerda) em verde (over) e vermelho (under)."""
    if not values:
        return ""
    top = max(max(values), (line or 0) * 1.4, 1)
    n = len(values)
    gap = 2
    w = max((width - gap * (n - 1)) / n, 2)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}">']
    for i, v in enumerate(values):
        h = max(height * v / top, 2)
        color = GREEN if line is not None and v > line else RED if line is not None else GREY
        parts.append(f'<rect x="{i * (w + gap):.1f}" y="{height - h:.1f}" width="{w:.1f}" '
                     f'height="{h:.1f}" rx="1.5" fill="{color}"/>')
    if line is not None:
        y = height - height * line / top
        parts.append(f'<line x1="0" x2="{width}" y1="{y:.1f}" y2="{y:.1f}" stroke="#e6edf3" '
                     'stroke-width="1" stroke-dasharray="3,2" opacity="0.7"/>')
    parts.append("</svg>")
    return "data:image/svg+xml;base64," + base64.b64encode("".join(parts).encode()).decode()


@st.cache_data(ttl=600, show_spinner="Calculando projeções...")
def _report(_conn, day: str, stat: str, version: str | None) -> list[dict[str, Any]]:
    """Relatório do dia (sem as linhas, que mudam a cada digitação).
    ``version`` = última atualização dos dados: muda e o cache é refeito."""
    return matchup_report(_conn, day, stat, load_matchup_rules(), load_projection_params())


def _fmt_line(p: dict[str, Any]) -> str:
    if p["linha"] is None:
        return "—"
    txt = f"{p['linha']:g}"
    if p["linha_ref"]:
        return txt + " ref"
    odds = " · ".join(f"{o:.2f}" for o in (p["odd_over"], p["odd_under"]) if o)
    return f"{txt}  ({odds})" if odds else txt


def _rows(players: list[dict[str, Any]], stat: str, window: int | None) -> list[dict[str, Any]]:
    out = []
    for p in players:
        hist = p.get("historico") or []
        recent = hist[:window] if window else hist
        values = [g[stat] for g in reversed(recent)]
        hits = sum(1 for v in values if p["linha"] is not None and v > p["linha"])
        side = None
        if p["p_over"] is not None:
            side = "▲ Over" if p["p_over"] >= 0.5 else "▼ Under"
        out.append({
            "Foto": headshot(p["player_id"]),
            "Jogador": f"{p['jogador']} · {p['time']} x {p['adversario']}"
                       + (f"  [{p['lesao']}]" if p.get("lesao") else ""),
            "Linha": _fmt_line(p),
            "Projeção": p.get("proj"),
            "Lado": side,
            "Chance": max(p["p_over"] or 0, p["p_under"] or 0) if p["p_over"] is not None else None,
            "Últimos jogos": bars_svg(values, p["linha"]),
            "Acerto": f"{hits}/{len(values)}" if values else "",
            "_over": p["proj_vs_linha"] is not None and p["proj_vs_linha"] > 0,
        })
    return out


def _style(df):
    def color(row):
        c = GREEN if row["_over"] else RED
        styles = [""] * len(row)
        for col in ("Projeção", "Lado"):
            styles[row.index.get_loc(col)] = f"color: {c}; font-weight: 600"
        return styles
    return df.style.apply(color, axis=1).format({"Projeção": "{:.1f}"}, na_rep="—")


def _detail(conn, p: dict[str, Any], stat: str, day: str, market_cfg: dict[str, Any]) -> None:
    c1, c2 = st.columns([1, 3])
    c1.image(headshot(p["player_id"]), width=120)
    with c2:
        st.markdown(f"### {p['jogador']}")
        st.caption(f"{p['time']} x {p['adversario']} · {MARKETS.get(stat, stat)} · "
                   f"posição {p.get('grupo') or '?'} / {p.get('posicao_est') or '?'} (estimada)")
        if p.get("lesao"):
            st.warning(f"Injury report: {p['lesao']} — {p.get('lesao_motivo') or ''}")

    with st.form(f"linha_{p['player_id']}_{stat}"):
        st.markdown("**Linha da casa**")
        f1, f2, f3 = st.columns(3)
        line = f1.number_input("Linha", value=float(p["linha"] or 0.5), step=0.5, format="%.1f")
        odd_o = f2.number_input("Odd over", value=float(p["odd_over"] or 0.0), step=0.01, format="%.2f")
        odd_u = f3.number_input("Odd under", value=float(p["odd_under"] or 0.0), step=0.01, format="%.2f")
        b1, b2 = st.columns(2)
        if b1.form_submit_button("Salvar linha", type="primary"):
            save_line(conn, day, p["player_id"], stat, line, odd_o or None, odd_u or None)
            st.rerun()
        if not p["linha_ref"] and b2.form_submit_button("Apagar linha"):
            save_line(conn, day, p["player_id"], stat, None)
            st.rerun()

    po = prob_over(p.get("proj"), line, market_cfg)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Projeção", f"{p['proj']:.1f}" if p.get("proj") is not None else "—",
              f"{p['proj'] - line:+.1f} vs linha" if p.get("proj") is not None else None)
    if po is not None:
        m2.metric("Chance de over", f"{100 * po:.0f}%", f"odd justa {fair_odd(po):.2f}",
                  delta_color="off")
        m3.metric("Chance de under", f"{100 * (1 - po):.0f}%", f"odd justa {fair_odd(1 - po):.2f}",
                  delta_color="off")
    ev = [(lbl, prob * odd - 1) for lbl, prob, odd in (("over", po, odd_o), ("under", 1 - (po or 0), odd_u))
          if po is not None and odd]
    if ev:
        best = max(ev, key=lambda x: x[1])
        m4.metric("Valor esperado", f"{100 * best[1]:+.1f}%", f"no {best[0]}", delta_color="off")
    if p.get("proj_detalhe", {}).get("erro_tipico"):
        st.caption(f"Erro típico da projeção neste mercado: ±{p['proj_detalhe']['erro_tipico']}. "
                   "Valor esperado positivo = a odd paga mais do que a chance calculada.")

    hist = p.get("historico") or []
    if hist:
        data = [{"jogo": f"{g['data'][5:]} {'vs' if g['em_casa'] else '@'}", "valor": g[stat],
                 "over": "Over" if g[stat] > line else "Under", "ordem": i}
                for i, g in enumerate(reversed(hist[:20]))]
        bars = alt.Chart(alt.Data(values=data)).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
            x=alt.X("ordem:O", axis=alt.Axis(title=None, labels=False, ticks=False)),
            y=alt.Y("valor:Q", title=None),
            color=alt.Color("over:N", scale=alt.Scale(domain=["Over", "Under"], range=[GREEN, RED]),
                            legend=None),
            tooltip=["jogo:N", "valor:Q"])
        rule = alt.Chart(alt.Data(values=[{"linha": line}])).mark_rule(
            strokeDash=[4, 3], color="#e6edf3").encode(y="linha:Q")
        st.markdown(f"**Últimos {len(data)} jogos contra a linha {line:g}**")
        st.altair_chart(bars + rule, width="stretch")

        from nbastats.metrics.linhas import hit_rates
        rates = hit_rates(hist, stat, line, p.get("adversario_id"))
        st.dataframe([{"Janela": k, "Over": f"{v['over']}/{v['jogos']}",
                       "%": v["pct"]} for k, v in rates.items() if v["jogos"]],
                     hide_index=True, width="stretch",
                     column_config={"%": st.column_config.ProgressColumn("%", min_value=0, max_value=100,
                                                                         format="%d%%")})

    d = p.get("proj_detalhe")
    if d:
        with st.expander("De onde vem a projeção"):
            st.markdown(
                f"- Base **{d['base']}** = taxa por minuto × **{d['minutos']} min** esperados\n"
                f"- Defesa adversária na posição (DvP rank {p.get('dvp_rank') or '—'}º): ×{d['f_dvp']}\n"
                f"- Ritmo do jogo: ×{d['f_ritmo']}\n"
                f"- Ajuste calibrado ({100 * d['ausencia']:.0f}% da produção do time fora): ×{d['f_ajuste']}")
            for c in p.get("com_sem") or []:
                st.markdown(f"- Com **{c['companheiro']}**: {c['com']} em {c['jogos_com']} jogos · "
                            f"sem: {c['sem'] if c['sem'] is not None else '—'} em {c['jogos_sem']}")
    zm = p.get("zonas")
    if zm:
        with st.expander(f"Zonas de arremesso · encaixe {zm['encaixe_pp']:+.1f} p.p."):
            st.dataframe([{"Zona": z["zona"], "% dele": z["arremessos_dele_pct"], "FG% dele": z["fg_dele"],
                           "FG% cedido": z["fg_cedido"], "FG% liga": z["fg_liga"]} for z in zm["zonas"]],
                         hide_index=True, width="stretch")
            st.caption("Fotografia da temporada até a última carga; ainda sem validação retroativa.")


def render(conn, version: str | None) -> None:
    params = load_projection_params()
    top1, top2 = st.columns([3, 1])
    top1.markdown("## Props do dia")
    day = top2.date_input("Data", date.today(), format="DD/MM/YYYY", label_visibility="collapsed")
    stat = st.pills("Mercado", list(MARKETS), default="pts", format_func=MARKETS.get,
                    label_visibility="collapsed") or "pts"

    report = _report(conn, day.isoformat(), stat, version)
    if not report:
        st.info("Nenhum jogo nesta data. Use \"Atualizar agora\" na barra lateral para buscar a agenda.")
        return
    report = attach_lines(report, stat, lines_for(conn, day.isoformat(), stat), params)

    labels = {}
    for g in report:
        j = g["jogo"]
        when = (f"{j['visitor_team_score']}-{j['home_team_score']}" if j["home_team_score"] is not None
                else (j["status"] or "").replace(" ET", ""))
        blow = f" · blowout {100 * g['risco_blowout']:.0f}%" if g.get("risco_blowout") is not None else ""
        labels[j["id"]] = f"{j['visitor']} @ {j['home']} · {when}{blow}"
    chosen_games = st.pills("Jogos", list(labels), format_func=labels.get, selection_mode="multi",
                            label_visibility="collapsed")

    f1, f2, f3, f4 = st.columns([1.2, 1.6, 1.6, 1])
    win_label = f1.segmented_control("Janela", list(WINDOWS), default="L10",
                                     label_visibility="collapsed") or "L10"
    sort_label = f2.selectbox("Ordenar", list(SORTS), label_visibility="collapsed")
    search = f3.text_input("Buscar", placeholder="Buscar jogador", label_visibility="collapsed")
    only_lines = f4.toggle("Só com linha", help="Só jogadores com linha da casa informada")

    players = [p for g in report if not chosen_games or g["jogo"]["id"] in chosen_games
               for p in g["jogadores"]]
    if search:
        players = [p for p in players if search.lower() in p["jogador"].lower()]
    if only_lines:
        players = [p for p in players if not p["linha_ref"]]
    players.sort(key=SORTS[sort_label], reverse=True)

    reports_at = {g["injury_report"] for g in report if g.get("injury_report")}
    st.caption(
        f"{len(players)} jogadores · {len(report)} jogos"
        + (f" · injury report {max(reports_at)[11:]} ET" if reports_at else "")
        + " · toque no jogador para detalhar")
    if all(p["linha_ref"] for p in players):
        st.caption("Sem linha da casa, a referência (\"ref\") é o L10 arredondado. Médias recentes "
                   "altas tendem a voltar, então a referência favorece o under; informe a linha real "
                   "(no detalhe do jogador ou na página Linhas) para a chance valer de verdade.")
    if not players:
        st.info("Nenhum jogador com esses filtros.")
        return

    import pandas as pd
    df = pd.DataFrame(_rows(players, stat, WINDOWS[win_label]))
    event = st.dataframe(
        _style(df), hide_index=True, width="stretch", height=min(70 + 52 * len(df), 900),
        row_height=52, on_select="rerun", selection_mode="single-row", key=f"props_{stat}",
        column_order=["Foto", "Jogador", "Linha", "Projeção", "Lado", "Chance", "Últimos jogos", "Acerto"],
        column_config={
            "Foto": st.column_config.ImageColumn("", width="small"),
            "Jogador": st.column_config.TextColumn("Jogador", width="medium"),
            "Linha": st.column_config.TextColumn("Linha"),
            "Projeção": st.column_config.NumberColumn("Proj."),
            "Lado": st.column_config.TextColumn("Lado"),
            "Chance": st.column_config.ProgressColumn("Chance", min_value=0, max_value=1, format="percent"),
            "Últimos jogos": st.column_config.ImageColumn(f"{win_label} vs linha", width="medium"),
            "Acerto": st.column_config.TextColumn(f"Over {win_label}"),
        },
    )
    rows = event.selection.rows if event and event.selection else []
    key = (stat, day.isoformat(), players[rows[0]]["player_id"]) if rows else None
    if key and st.session_state.get("_props_open") != key:
        st.session_state["_props_open"] = key
        market_cfg = (params.get("mercados") or {}).get(stat) or {}

        @st.dialog(MARKETS.get(stat, stat), width="large")
        def _open():
            _detail(conn, players[rows[0]], stat, day.isoformat(), market_cfg)

        _open()
    elif not rows:
        st.session_state.pop("_props_open", None)
