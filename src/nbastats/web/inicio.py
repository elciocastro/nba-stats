"""Página inicial: destaques do dia (jogos, jogadores em alta, oportunidades)."""

from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from nbastats.metrics import destaques as dq
from nbastats.metrics import load_projection_params
from nbastats.web import props

CSS = """
<style>
.gc { background: #121821; border: 1px solid #263040; border-radius: 12px; padding: 12px 14px; height: 100%; }
.gc .tm { display: flex; justify-content: space-between; align-items: center; font-weight: 700; font-size: 1.15rem; }
.gc .tm small { color: #8b98a9; font-weight: 500; font-size: .8rem; }
.gc .row { display: flex; gap: 6px; flex-wrap: wrap; margin: 8px 0 6px; }
.gc .ch { font-size: .72rem; padding: 2px 8px; border-radius: 999px; background: #1c2532; color: #cbd5e1; }
.gc .ch.hot { background: #3b2a12; color: #f5b041; } .gc .ch.ok { background: #14532d; color: #bbf7d0; }
.gc .ch.bad { background: #4c1d1d; color: #fecaca; }
.gc .ds { color: #8b98a9; font-size: .75rem; line-height: 1.35; }
.gc .bp { margin-top: 6px; font-size: .8rem; color: #e6edf3; }
.gg { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; }
.hd { font-size: .78rem; color: #8b98a9; letter-spacing: .05em; text-transform: uppercase; margin: 6px 0 2px; }
</style>
"""


@st.cache_data(ttl=600, show_spinner="Montando os destaques...")
def _reports(_conn, day: str, version: str | None, bet_on: bool) -> dict[str, list[dict[str, Any]]]:
    params = load_projection_params()
    return {s: props._prepare(_conn, day, s, version, params) for s in dq.HOME_MARKETS}


def go_player(pid: int, stat: str) -> None:
    """Abre o jogador na página Props, já no mercado."""
    st.session_state["pagina"] = "Props"
    st.session_state["mercado"] = stat
    st.session_state["_player"] = pid


def _game_card(c: dict[str, Any]) -> str:
    when = c["placar"] or (c["status"] or "").replace(" ET", " ET")
    chips = []
    if c["margem"] is not None:
        chips.append(f'<span class="ch">{c["favorito"]} por {c["margem"]:.1f}</span>')
    if c["blowout"] is not None:
        cls = "bad" if c["blowout"] >= .4 else ""
        chips.append(f'<span class="ch {cls}">blowout {100 * c["blowout"]:.0f}%</span>')
    if c["ritmo_vs_liga"] is not None:
        cls = "hot" if c["ritmo_vs_liga"] >= 1.5 else ""
        chips.append(f'<span class="ch {cls}">ritmo {c["ritmo_vs_liga"]:+.1f}</span>')
    if c["props_boas"]:
        chips.append(f'<span class="ch ok">{c["props_boas"]} props boas</span>')
    v = c.get("validacao") or {}
    if v.get("status") == "validada":
        chips.append('<span class="ch ok">validada</span>')
    d = c["desfalques"]
    best = c["melhor"]
    best_txt = ""
    if best:
        best_txt = (f'<div class="bp">Maior chance: <b>{best["jogador"]}</b> {best["lado"]} '
                    f'{best["linha"]:g} {props.MARKETS[best["mercado"]]} · {100 * best["chance"]:.0f}%</div>')
    return (f'<div class="gc"><div class="tm">{c["fora"]} @ {c["casa"]}<small>{when}</small></div>'
            f'<div class="row">{"".join(chips)}</div>'
            f'<div class="ds">{c["fora"]}: {", ".join(d["fora"]) or "—"}<br>'
            f'{c["casa"]}: {", ".join(d["casa"]) or "—"}</div>{best_txt}</div>')


def _row(html: str, key: str, pid: int, stat: str) -> None:
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        st.html(html, width="stretch")
        st.button("›", key=key, type="tertiary", help="Abrir o jogador", on_click=go_player, args=(pid, stat))


def _opp_html(o: dict[str, Any]) -> str:
    arrow = "▲" if o["lado"] == "over" else "▼"
    s = o.get("selo")
    chance = f"{arrow} {100 * o['chance']:.0f}%"
    if s:
        chance = (f'<span class="sl sm" style="background:{s["cor"]};color:{s["texto"]}">{chance}</span>')
    ev = f" · EV {100 * o['ev']:+.0f}%" if o["ev"] is not None else ""
    odd = f" @ {o['odd']:.2f}" if o.get("odd") else ""
    ref = " ref" if o["linha_ref"] else ""
    vals = [g[o["mercado"]] for g in reversed(o["historico"][:10])]
    proj = "—" if o["proj"] is None else f"{o['proj']:.1f}"
    cls = "over" if o["lado"] == "over" else "under"
    return (f'<div class="pc"><img class="ph" src="{props.headshot(o["player_id"])}" loading="lazy" alt="">'
            f'<div class="who"><div class="nm">{o["jogador"]}<small>{o["time"]} x {o["adversario"]}</small></div>'
            f'<div class="ln">{o["lado"].capitalize()} {o["linha"]:g}{ref} {props.MARKETS[o["mercado"]]}{odd}{ev}</div></div>'
            f'<div class="ed"><div class="lb">PROJ</div><div class="v {cls}">{proj}</div>'
            f'<div class="pr">{chance}</div></div>'
            f'<img class="bars" src="{props.bars_svg(vals, o["linha"], 150, 36)}" alt=""></div>')


def _rise_html(r: dict[str, Any]) -> str:
    tag = f'<span class="tag">{r["lesao"]}</span>' if r.get("lesao") else ""
    mins = f"min {r['min_l5']:.0f} (L10 {r['min_l10']:.0f})"
    use = f" · uso {r['uso_l5']:.0f}%" if r.get("uso_l5") else ""
    return (f'<div class="pc"><img class="ph" src="{props.headshot(r["player_id"])}" loading="lazy" alt="">'
            f'<div class="who"><div class="nm">{r["jogador"]}<small>{r["time"]} x {r["adversario"]}</small>{tag}</div>'
            f'<div class="ln">PRA L5 {r["l5"]} · temp. {r["temporada"]} · {mins}{use}</div></div>'
            f'<div class="ed"><div class="lb">ALTA</div><div class="v over">{r["alta_pct"]:+d}%</div>'
            f'<div class="pr">proj {r["proj"] or 0:.1f}</div></div>'
            f'<img class="bars" src="{props.bars_svg(r["valores"], r["temporada"], 150, 36)}" alt=""></div>')


def render(conn, version: str | None) -> None:
    st.html(props.CSS + CSS)
    with st.container(horizontal=True, vertical_alignment="center"):
        st.markdown("### Destaques do dia")
        day = st.date_input("Data", date.today(), format="DD/MM/YYYY", label_visibility="collapsed",
                            width=140, key="home_day")
    cfg = props.betaniag_cfg()
    reports = _reports(conn, day.isoformat(), version, cfg is not None)
    if not next(iter(reports.values()), None):
        st.info("Nenhum jogo nesta data. Use \"Atualizar agora\" na barra lateral para buscar a agenda.")
        return

    mins = ((props.bt.load_betaniag().get("destaques") or {}).get("min_media")) or dq.MIN_MEDIA
    cards = dq.game_cards(reports, cfg, mins)
    opp = dq.opportunities(reports, cfg, min_media=mins)
    hot = dq.rising(reports["pra"])
    n_players = len({p["player_id"] for g in reports["pra"] for p in g["jogadores"]})
    good = sum(c["props_boas"] for c in cards)
    with st.container(horizontal=True, gap="small"):
        st.metric("Jogos", len(cards), border=True)
        st.metric("Jogadores analisados", n_players, border=True)
        st.metric("Linhas da casa", sum(1 for rep in reports.values() for g in rep
                                        for p in g["jogadores"] if not p["linha_ref"]), border=True)
        if cfg:
            st.metric("Props Forte/Boa", good, border=True)

    st.html('<div class="hd">Jogos do dia</div><div class="gg">' + "".join(_game_card(c) for c in cards) + "</div>")
    st.caption("Ritmo = posses do jogo acima (+) ou abaixo (−) da média da liga. Blowout = chance de "
               "decisão por 15+ (titulares saem mais cedo).")

    mobile = props.is_mobile()
    left, right = (st.container(), st.container()) if mobile else st.columns(2, gap="large")
    with left:
        st.html('<div class="hd">Melhores oportunidades</div>')
        if opp["com_odd"]:
            st.caption("Com odd da casa, pelo valor esperado (quanto a odd paga acima da chance).")
            for i, o in enumerate(opp["com_odd"]):
                _row(_opp_html(o), f"opp_o_{i}", o["player_id"], o["mercado"])
        st.caption("Pela chance do modelo, em Pontos, Rebotes, Assist., PRA e 3FM. Sem odd da casa a linha "
                   "é a referência (L10), que favorece o under: informe a linha real para confirmar.")
        for i, o in enumerate(opp["sem_odd"]):
            _row(_opp_html(o), f"opp_r_{i}", o["player_id"], o["mercado"])
    with right:
        st.html('<div class="hd">Em alta: vale acompanhar</div>')
        st.caption("Jogam hoje e vêm acima da própria temporada no PRA dos últimos 5 jogos "
                   "(barras: últimos 10, verde = acima da média da temporada).")
        for i, r in enumerate(hot):
            _row(_rise_html(r), f"hot_{i}", r["player_id"], "pra")
