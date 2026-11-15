"""Página "Props do dia" e página do jogador.

- Celular: cartões compactos (foto, linha, projeção, selo, barras).
- Computador: tabela de calor no estilo das planilhas de props (temporada,
  H2H, L5, L10, L20, temporada anterior, projeção, DvP).
- Tocar/clicar num jogador abre a página dele: gráfico grande com rótulos,
  janelas e recortes (casa/fora/vitória/derrota/sem descanso), minutos e
  uso, "e se jogar X minutos", H2H, checklist BetânIAG, lesões e aposta.

Só apresentação: números vêm de nbastats.metrics.
"""

from __future__ import annotations

import base64
from datetime import date
from typing import Any

import altair as alt
import streamlit as st

from nbastats.metrics import load_matchup_rules, load_projection_params, matchup_report
from nbastats.metrics import betaniag as bt
from nbastats.metrics import historico as hs
from nbastats.metrics.apostas import add_bet, load_bet_config
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
    "Projeção acima da linha": lambda p: p["proj_vs_linha"] if p["proj_vs_linha"] is not None else -99,
    "Valor esperado (com odd)": lambda p: max(p["ev_over"] or -9, p["ev_under"] or -9),
    "Melhor H2H": lambda p: ((p.get("janelas") or {}).get("H2H") or {}).get("pct") or -1,
}
# pares de feito x tentado para o gráfico de arremessos
MADE_TRIED = {"fg3m": ("fg3m", "fg3a", "Bolas de 3"), "fg3a": ("fg3m", "fg3a", "Bolas de 3"),
              "ftm": ("ftm", "fta", "Lances livres"), "fta": ("ftm", "fta", "Lances livres"),
              "fg2m": ("fg2m", "fg2a", "Bolas de 2"), "fg2a": ("fg2m", "fg2a", "Bolas de 2"),
              "pts": ("fg3m", "fg3a", "Bolas de 3")}


def headshot(player_id: int) -> str:
    return f"https://cdn.nba.com/headshots/nba/latest/260x190/{player_id}.png"


# ---------- preferências da sessão ----------

def is_mobile() -> bool:
    """Layout: escolha da barra lateral; no automático, pelo navegador."""
    choice = st.session_state.get("layout", "Automático")
    if choice != "Automático":
        return choice == "Celular"
    try:
        ua = (st.context.headers.get("User-Agent") or "").lower()
    except Exception:  # sem contexto (testes)
        return False
    return any(k in ua for k in ("mobi", "android", "iphone", "ipod"))


def betaniag_cfg() -> dict[str, Any] | None:
    """Configuração do protocolo se ligado (YAML ou botão da barra lateral)."""
    cfg = bt.load_betaniag()
    on = st.session_state.get("betaniag", bool(cfg.get("habilitado")))
    return cfg if on else None


# ---------- desenho ----------

def bars_svg(values: list[float], line: float | None, width: int = 160, height: int = 44) -> str:
    """Barras dos jogos (mais antigo à esquerda) em verde (over) e vermelho (under)."""
    if not values:
        return ""
    top = max(max(values), (line or 0) * 1.4, 1)
    n = len(values)
    gap = 2
    w = max((width - gap * (n - 1)) / n, 2)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}" preserveAspectRatio="none">']
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


def heat(pct: float | None) -> tuple[str, str]:
    """(fundo, texto) para uma taxa de over: verde forte a vermelho forte."""
    if pct is None or pct != pct:  # None ou NaN
        return "transparent", "#5b6676"
    for lo, bg, fg in ((70, "#15803d", "#ffffff"), (58, "#166534", "#dcfce7"), (43, "#273241", "#cbd5e1"),
                       (31, "#7f1d1d", "#fee2e2")):
        if pct >= lo:
            return bg, fg
    return "#b91c1c", "#ffffff"


def seal_html(s: dict[str, Any] | None, small: bool = False) -> str:
    if not s:
        return ""
    unit = f" · {s['unidade']:g}u" if s.get("unidade") is not None else ""
    cls = "sl sm" if small else "sl"
    return (f'<span class="{cls}" style="background:{s["cor"]};color:{s["texto"]}" '
            f'title="BetânIAG: {s["nivel"]}">{s["nivel"]}{unit}</span>')


@st.cache_data(ttl=600, show_spinner="Calculando projeções...")
def _report(_conn, day: str, stat: str, version: str | None) -> list[dict[str, Any]]:
    """Relatório do dia (sem as linhas, que mudam a cada digitação).
    ``version`` = última atualização dos dados: muda e o cache é refeito."""
    return matchup_report(_conn, day, stat, load_matchup_rules(), load_projection_params())


@st.cache_data(ttl=600, show_spinner=False)
def _logs(_conn, day: str, ids: tuple[int, ...], version: str | None) -> dict[int, list[dict[str, Any]]]:
    return hs.player_logs(_conn, ids, day)


def _fmt_line(p: dict[str, Any]) -> str:
    if p["linha"] is None:
        return "—"
    return f"{p['linha']:g}" + (" ref" if p["linha_ref"] else "")


CSS = """
<style>
[data-testid="stButtonGroup"] > div:last-child {
  flex-wrap: nowrap !important; overflow-x: auto; scrollbar-width: none; padding-bottom: 2px;
}
[data-testid="stButtonGroup"] > div:last-child::-webkit-scrollbar { display: none; }
[data-testid="stButtonGroup"] button { flex-shrink: 0; }
.block-container { padding-top: 3rem; }
[data-testid="stHorizontalBlock"]:has(.pc) { flex-wrap: nowrap !important; gap: 4px !important; }
[data-testid="stHorizontalBlock"]:has(.pc) > [data-testid="stElementContainer"]:has(.pc) {
  flex: 1 1 0 !important; min-width: 0 !important; }
[data-testid="stHorizontalBlock"]:has(.pc) button { padding: 0 10px; font-size: 1.4rem; color: #8b98a9; }
.pc { display: flex; align-items: center; gap: 8px; padding: 7px 2px; min-width: 0; }
[data-testid="stHorizontalBlock"]:has(.pc) { border-bottom: 1px solid #1d2632; }
.pc img.ph { width: 44px; height: 44px; border-radius: 50%; object-fit: cover; object-position: top;
  background: #1c2430; flex-shrink: 0; }
.pc .who { flex: 1; min-width: 0; line-height: 1.2; }
.pc .nm { font-weight: 600; font-size: 0.9rem; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; }
.pc .nm small { color: #8b98a9; font-weight: 500; margin-left: 4px; }
.pc .ln { color: #b8c2cf; font-size: 0.8rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pc .tag { font-size: 0.7rem; padding: 0 5px; border-radius: 6px; background: #3b2a12; color: #f5b041;
  margin-left: 4px; }
.pc .ed { text-align: right; flex-shrink: 0; width: 52px; line-height: 1.1; }
.pc .ed .lb { color: #8b98a9; font-size: 0.62rem; letter-spacing: .04em; }
.pc .ed .v { font-weight: 700; font-size: 1.05rem; }
.pc .ed .pr { font-size: 0.7rem; color: #b8c2cf; }
.pc img.bars { flex-shrink: 0; width: 84px; height: 32px; }
.sl { display: inline-block; font-size: .72rem; font-weight: 700; padding: 1px 7px; border-radius: 999px;
  white-space: nowrap; }
.sl.sm { font-size: .66rem; padding: 0 5px; }
.over { color: #22c55e; } .under { color: #ef4444; }
@media (max-width: 360px) { .pc img.bars { width: 64px; } }
@media (min-width: 700px) { .pc img.bars { width: 150px; height: 36px; } .pc .ed { width: 64px; } }
</style>
"""

DETAIL_CSS = """
<style>
.dh { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.dh img { width: 84px; height: 84px; border-radius: 50%; object-fit: cover; object-position: top;
  background: #1c2430; }
.dh .n { font-size: 1.45rem; font-weight: 700; line-height: 1.1; }
.dh .t { color: #b8c2cf; font-size: .85rem; }
.kp { display: grid; grid-template-columns: repeat(auto-fit, minmax(84px, 1fr)); gap: 8px; margin: 4px 0 8px; }
.kp > div { background: #151b23; border: 1px solid #263040; border-radius: 10px; padding: 8px; text-align: center; }
.kp .l { color: #8b98a9; font-size: .68rem; letter-spacing: .03em; }
.kp .v { font-size: 1.25rem; font-weight: 700; line-height: 1.2; }
.kp .s { color: #8b98a9; font-size: .7rem; }
.hr { display: grid; grid-template-columns: repeat(6, 1fr); gap: 6px; margin: 6px 0 10px; }
.hr > div { border-radius: 8px; padding: 6px 4px; text-align: center; }
.hr .l { font-size: .68rem; opacity: .85; } .hr .v { font-size: 1.05rem; font-weight: 700; }
.hr .s { font-size: .66rem; opacity: .8; }
.ck { width: 100%; border-collapse: collapse; font-size: .85rem; }
.ck td { padding: 5px 6px; border-bottom: 1px solid #1d2632; vertical-align: top; }
.ck td.v { font-weight: 600; white-space: nowrap; } .ck td.n { color: #8b98a9; font-size: .75rem; }
.ck .ok { color: #22c55e; } .ck .no { color: #ef4444; } .ck .ctx { color: #8b98a9; }
.vs { display: inline-block; font-size: .72rem; padding: 2px 8px; border-radius: 999px; margin-left: 6px; }
.vs.ok { background: #14532d; color: #bbf7d0; } .vs.pre { background: #422006; color: #fde68a; }
.vs.end { background: #1f2937; color: #cbd5e1; }
.over { color: #22c55e; } .under { color: #ef4444; }
@media (max-width: 640px) { .hr { grid-template-columns: repeat(3, 1fr); } }
</style>
"""

PAGE_SIZE = 30


def card_html(p: dict[str, Any], stat: str, window: int | None) -> str:
    """Um jogador numa linha: foto, nome, linha, projeção, chance, selo e barras."""
    hist = p.get("historico") or []
    values = [g[stat] for g in reversed(hist[:window] if window else hist)]
    over = p["proj_vs_linha"] is not None and p["proj_vs_linha"] > 0
    cls = "over" if over else "under"
    line = "—" if p["linha"] is None else f"{p['linha']:g}"
    ref = " ref" if p["linha_ref"] else ""
    odds = "" if p["linha_ref"] or not p["odd_over"] else f" · {p['odd_over']:.2f}"
    chance = ""
    if p["p_over"] is not None:
        side = "▲" if p["p_over"] >= 0.5 else "▼"
        chance = f"{side} {100 * max(p['p_over'], p['p_under']):.0f}%"
        s = p.get("selo")
        if s:  # BetânIAG: a chance ganha a cor do nível
            chance = (f'<span class="sl sm" style="background:{s["cor"]};color:{s["texto"]}" '
                      f'title="BetânIAG: {s["nivel"]}">{chance}</span>')
    tag = f'<span class="tag">{p["lesao"]}</span>' if p.get("lesao") else ""
    proj = "—" if p.get("proj") is None else f"{p['proj']:.1f}"
    h2h = ((p.get("janelas") or {}).get("H2H") or {})
    h2h_txt = f" · H2H {h2h['over']}/{h2h['jogos']}" if h2h.get("jogos") else ""
    return (
        f'<div class="pc"><img class="ph" src="{headshot(p["player_id"])}" loading="lazy" alt="">'
        f'<div class="who"><div class="nm">{p["jogador"]}<small>{p["time"]}</small>{tag}</div>'
        f'<div class="ln">{line}{ref} {MARKETS.get(stat, stat)}{odds} · x {p["adversario"]}{h2h_txt}</div></div>'
        f'<div class="ed"><div class="lb">PROJ</div><div class="v {cls}">{proj}</div>'
        f'<div class="pr">{chance}</div></div>'
        f'<img class="bars" src="{bars_svg(values, p["linha"], 150, 36)}" alt=""></div>'
    )


# ---------- lista ----------

def _prepare(conn, day: str, stat: str, version: str | None, params: dict[str, Any]) -> list[dict[str, Any]]:
    from nbastats.metrics.painel import day_report
    base = (_report(conn, day, stat, version), None)
    ids = tuple(sorted({p["player_id"] for g in base[0] for p in g["jogadores"]}))
    return day_report(conn, day, stat, version, betaniag_cfg(), params,
                      base=(base[0], _logs(conn, day, ids, version)))


def open_player(pid: int) -> None:
    st.session_state["_player"] = pid


def close_player() -> None:
    st.session_state.pop("_player", None)
    for k in [k for k in st.session_state if str(k).startswith("props_tbl_")]:
        del st.session_state[k]  # senão a linha continua selecionada e reabre o jogador


def render(conn, version: str | None) -> None:
    params = load_projection_params()
    st.html(CSS)
    with st.container(horizontal=True, vertical_alignment="center"):
        st.markdown("### Props do dia")
        day = st.date_input("Data", date.today(), format="DD/MM/YYYY", label_visibility="collapsed",
                            width=140)
    stat = st.pills("Mercado", list(MARKETS), default="pts", format_func=MARKETS.get,
                    label_visibility="collapsed", key="mercado") or "pts"

    report = _prepare(conn, day.isoformat(), stat, version, params)
    if not report:
        st.info("Nenhum jogo nesta data. Use \"Atualizar agora\" na barra lateral para buscar a agenda.")
        return

    pid = st.session_state.get("_player")
    if pid is not None:
        found = next(((g, p) for g in report for p in g["jogadores"] if p["player_id"] == pid), None)
        if found:
            player_page(conn, found[1], found[0], stat, day.isoformat(), params)
            return
        st.session_state.pop("_player", None)
        st.info("Esse jogador não tem projeção neste mercado/data.")

    labels = {}
    for g in report:
        j = g["jogo"]
        when = (f"{j['visitor_team_score']}-{j['home_team_score']}" if j["home_team_score"] is not None
                else (j["status"] or "").replace(" ET", "").replace(" pm", "p").replace(" am", "a"))
        blow = f" · {100 * g['risco_blowout']:.0f}% blowout" if g.get("risco_blowout") is not None else ""
        labels[j["id"]] = f"{j['visitor']} @ {j['home']} {when}{blow}"
    chosen_games = st.pills("Jogos", list(labels), format_func=labels.get, selection_mode="multi",
                            label_visibility="collapsed")

    mobile = is_mobile()
    with st.container(horizontal=True, vertical_alignment="center"):
        win_label = st.segmented_control("Janela", list(WINDOWS), default="L10",
                                         label_visibility="collapsed") or "L10"
        with st.popover("Filtros", icon=":material/tune:"):
            sort_label = st.selectbox("Ordenar por", list(SORTS))
            search = st.text_input("Buscar jogador")
            only_lines = st.toggle("Só com linha da casa")
            only_good = st.toggle("Só selos Forte/Boa (BetânIAG)") if betaniag_cfg() else False

    players = [p for g in report if not chosen_games or g["jogo"]["id"] in chosen_games
               for p in g["jogadores"]]
    if search:
        players = [p for p in players if search.lower() in p["jogador"].lower()]
    if only_lines:
        players = [p for p in players if not p["linha_ref"]]
    if only_good:
        players = [p for p in players if (p.get("selo") or {}).get("nivel") in ("Forte", "Boa")]
    players.sort(key=SORTS[sort_label], reverse=True)

    reports_at = {g["injury_report"] for g in report if g.get("injury_report")}
    st.caption(
        f"{len(players)} jogadores · {len(report)} jogos"
        + (f" · injury report {max(reports_at)[11:]} ET" if reports_at else "")
        + (" · toque em › para a página do jogador" if mobile else " · clique numa linha para abrir o jogador"))
    if players and all(p["linha_ref"] for p in players):
        with st.expander("Sem linha da casa: a linha \"ref\" é o L10 arredondado"):
            st.caption("Médias recentes altas tendem a voltar, então a referência favorece o under. "
                       "Informe a linha real (na página do jogador ou na página Linhas) para a chance "
                       "valer de verdade.")
    if not players:
        st.info("Nenhum jogador com esses filtros.")
        return

    if not mobile:
        _table_view(players, stat, report, win_label)
        return

    shown = st.session_state.get("_props_n", PAGE_SIZE)
    with st.container(gap=None):
        for p in players[:shown]:
            with st.container(horizontal=True, vertical_alignment="center", gap="small"):
                st.html(card_html(p, stat, WINDOWS[win_label]), width="stretch")
                st.button("›", key=f"open_{stat}_{p['player_id']}", help="Página do jogador",
                          type="tertiary", on_click=open_player, args=(p["player_id"],))
    if len(players) > shown and st.button(f"Mostrar mais ({len(players) - shown})", width="stretch"):
        st.session_state["_props_n"] = shown + PAGE_SIZE
        st.rerun()


def _table_view(players, stat, report, win_label) -> None:
    """Tabela de calor para o computador."""
    import pandas as pd

    season = report[0]["jogo"]["season"]
    cur, prev = hs.season_label(season), hs.season_label(season - 1)
    rate_cols = [cur, "H2H", "L5", "L10", "L20", prev]
    rows = []
    for p in players:
        jan = p.get("janelas") or {}
        hist = p.get("historico") or []
        window = WINDOWS[win_label]
        values = [g[stat] for g in reversed(hist[:window] if window else hist)]
        s = p.get("selo")
        side = None
        if p["p_over"] is not None:
            side = ("▲ " if p["p_over"] >= .5 else "▼ ") + f"{100 * max(p['p_over'], p['p_under']):.0f}%"
        rows.append({
            "Foto": headshot(p["player_id"]),
            "Jogador": f"{p['jogador']} · {p['time']} x {p['adversario']}"
                       + (f"  [{p['lesao']}]" if p.get("lesao") else ""),
            "Selo": s["nivel"] + (f" {s['unidade']:g}u" if s.get("unidade") is not None else "") if s else "",
            "Linha": _fmt_line(p),
            "O": f"{p['odd_over']:.2f}" if p["odd_over"] else "—",
            "U": f"{p['odd_under']:.2f}" if p["odd_under"] else "—",
            "Proj": "—" if p.get("proj") is None else f"{p['proj']:.1f}",
            "Diff": "—" if p.get("proj_vs_linha") is None else f"{p['proj_vs_linha']:+.1f}",
            "Chance": side or "—",
            **{c: "—" if (jan.get(c) or {}).get("pct") is None else f"{jan[c]['pct']}%" for c in rate_cols},
            **{f"_{c}": (jan.get(c) or {}).get("pct") for c in rate_cols},
            "DvP": "—" if not p.get("dvp_rank") else f"{p['dvp_rank']}º",
            "_diff": p.get("proj_vs_linha"), "_dvp": p.get("dvp_rank"),
            "Últimos": bars_svg(values, p["linha"], 150, 36),
            "_cor": s["cor"] if s else None, "_txt": s["texto"] if s else None,
            "_n": {c: (jan.get(c) or {}).get("jogos") for c in rate_cols},
        })
    df = pd.DataFrame(rows)

    def style_row(row):
        out = [""] * len(row)
        idx = row.index.get_loc
        if row["_cor"]:
            out[idx("Selo")] = f"background-color: {row['_cor']}; color: {row['_txt']}; font-weight: 700"
        for c in rate_cols:
            bg, fg = heat(row[f"_{c}"])
            out[idx(c)] = f"background-color: {bg}; color: {fg}; font-weight: 600"
        d = row["_diff"]
        if d == d and d is not None:
            out[idx("Diff")] = f"color: {GREEN if d > 0 else RED}; font-weight: 600"
            out[idx("Proj")] = f"color: {GREEN if d > 0 else RED}; font-weight: 700"
        r = row["_dvp"]
        if r == r and r is not None:
            out[idx("DvP")] = f"color: {GREEN if r >= 21 else RED if r <= 10 else '#cbd5e1'}; font-weight: 600"
        return out

    styled = df.style.apply(style_row, axis=1)
    col_cfg = {
        "Foto": st.column_config.ImageColumn("", width=48),
        "Jogador": st.column_config.TextColumn("Jogador", width=210),
        "Selo": st.column_config.TextColumn("BetânIAG", width=92),
        "Linha": st.column_config.TextColumn("Linha", width=62),
        "O": st.column_config.TextColumn("O", width=46, help="Odd over"),
        "U": st.column_config.TextColumn("U", width=46, help="Odd under"),
        "Proj": st.column_config.TextColumn("Proj", width=50),
        "Diff": st.column_config.TextColumn("Diff", width=50, help="Projeção − linha"),
        "Chance": st.column_config.TextColumn("Chance", width=64, help="Lado do modelo e chance calibrada"),
        "DvP": st.column_config.TextColumn("DvP", width=46, help="Rank da defesa na posição (30 = cede mais)"),
        "Últimos": st.column_config.ImageColumn(f"{win_label} vs linha", width=160),
        cur: st.column_config.TextColumn(cur, width=52, help="Over na temporada atual"),
        "H2H": st.column_config.TextColumn("H2H", width=52, help="Over contra este adversário, todas as temporadas"),
        "L5": st.column_config.TextColumn("L5", width=52), "L10": st.column_config.TextColumn("L10", width=52),
        "L20": st.column_config.TextColumn("L20", width=52),
        prev: st.column_config.TextColumn(prev, width=52, help="Over na temporada anterior"),
    }
    order = ["Foto", "Jogador", *(["Selo"] if betaniag_cfg() else []), "Linha", "O", "U", *rate_cols,
             "Proj", "Diff", "Chance", "DvP", "Últimos"]
    event = st.dataframe(styled, hide_index=True, width="stretch", height=min(70 + 46 * len(df), 1100),
                         row_height=46, on_select="rerun", selection_mode="single-row",
                         key=f"props_tbl_{stat}", column_order=order, column_config=col_cfg)
    st.caption("% = vezes que passou da linha na janela. Verde ≥ 58%, vermelho ≤ 42%. "
               "H2H junta todas as temporadas contra o adversário de hoje (poucos jogos: contexto).")
    rows_sel = event.selection.rows if event and event.selection else []
    if rows_sel:
        open_player(players[rows_sel[0]]["player_id"])
        st.rerun()


# ---------- página do jogador ----------

def _kpis(p: dict[str, Any], line: float, proj: float | None, po: float | None,
          odd_o: float, odd_u: float) -> str:
    cells = []
    if proj is not None:
        diff = proj - line
        cls = "over" if diff > 0 else "under"
        cells.append(("PROJEÇÃO", f'<span class="{cls}">{proj:.1f}</span>', f"{diff:+.1f} vs linha"))
    if po is not None:
        cells.append(("OVER", f'<span class="{"over" if po >= .5 else ""}">{100 * po:.0f}%</span>',
                      f"odd justa {fair_odd(po):.2f}"))
        cells.append(("UNDER", f'<span class="{"under" if po < .5 else ""}">{100 * (1 - po):.0f}%</span>',
                      f"odd justa {fair_odd(1 - po):.2f}"))
        ev = [(lbl, prob * odd - 1) for lbl, prob, odd in (("over", po, odd_o), ("under", 1 - po, odd_u)) if odd]
        if ev:
            lbl, val = max(ev, key=lambda x: x[1])
            cells.append(("VALOR ESP.", f'<span class="{"over" if val > 0 else "under"}">{100 * val:+.1f}%</span>',
                          f"no {lbl}"))
    if p.get("min_l10") is not None:
        exp = (p.get("proj_detalhe") or {}).get("minutos")
        cells.append(("MINUTOS", f"{exp:.0f}" if exp else "—", f"L5 {p['min_l5']:.0f} · L10 {p['min_l10']:.0f}"))
    if p.get("dvp_rank"):
        r = p["dvp_rank"]
        cls = "over" if r >= 21 else "under" if r <= 10 else ""
        cells.append(("DvP", f'<span class="{cls}">{r}º</span>', "30 = cede mais"))
    return '<div class="kp">' + "".join(
        f'<div><div class="l">{a}</div><div class="v">{b}</div><div class="s">{c}</div></div>'
        for a, b, c in cells) + "</div>"


def _rates_html(jan: dict[str, dict[str, Any]]) -> str:
    cells = []
    for k, w in jan.items():
        bg, fg = heat(w.get("pct"))
        pct = "—" if w.get("pct") is None else f"{w['pct']}%"
        sub = f"{w['over']}/{w['jogos']} · méd {w['media']}" if w.get("jogos") else "sem jogos"
        cells.append(f'<div style="background:{bg};color:{fg};border:1px solid #263040">'
                     f'<div class="l">{k}</div><div class="v">{pct}</div><div class="s">{sub}</div></div>')
    return '<div class="hr">' + "".join(cells) + "</div>"


def _checklist_html(items: list[dict[str, Any]]) -> str:
    rows = []
    for i in items:
        mark = ('<span class="ok">✓</span>' if i["ok"] else '<span class="no">✗</span>' if i["ok"] is False
                else '<span class="ctx">•</span>')
        rows.append(f'<tr><td>{mark}</td><td>{i["item"]}</td><td class="v">{i["valor"]}</td>'
                    f'<td class="n">{i["nota"]}</td></tr>')
    return '<table class="ck">' + "".join(rows) + "</table>"


def _game_chart(games: list[dict[str, Any]], stat: str, line: float) -> alt.Chart:
    data = [{"jogo": f"{g['data'][8:]}/{g['data'][5:7]} {'vs' if g['em_casa'] else '@'}{g.get('adv', '')}",
             "valor": g[stat], "minutos": round(g["minutes"]), "res": g.get("resultado") or "",
             "over": "Over" if g[stat] > line else "Under", "ordem": i}
            for i, g in enumerate(reversed(games))]
    base = alt.Chart(alt.Data(values=data)).encode(
        x=alt.X("jogo:N", sort=None, title=None, axis=alt.Axis(labelAngle=-50, labelFontSize=10)))
    bars = base.mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        y=alt.Y("valor:Q", title=None),
        color=alt.Color("over:N", scale=alt.Scale(domain=["Over", "Under"], range=[GREEN, RED]), legend=None),
        tooltip=["jogo:N", "valor:Q", "minutos:Q", "res:N"])
    labels = base.mark_text(dy=-7, color="#e6edf3", fontSize=11, fontWeight="bold").encode(
        y="valor:Q", text="valor:Q")
    rule = alt.Chart(alt.Data(values=[{"linha": line}])).mark_rule(
        strokeDash=[5, 3], color="#e6edf3", strokeWidth=1.5).encode(y="linha:Q")
    return (bars + labels + rule).properties(height=300)


def _minutes_chart(games: list[dict[str, Any]], minutes_exp: float | None) -> alt.Chart:
    data = [{"jogo": f"{g['data'][8:]}/{g['data'][5:7]}", "Minutos": round(g["minutes"], 1),
             "Posses usadas": g["usadas"], "ordem": i} for i, g in enumerate(reversed(games))]
    base = alt.Chart(alt.Data(values=data)).encode(x=alt.X("jogo:N", sort=None, title=None,
                                                          axis=alt.Axis(labelAngle=-50, labelFontSize=10)))
    mins = base.mark_bar(color="#3b82f6", opacity=.75, cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
        y=alt.Y("Minutos:Q", title="minutos"), tooltip=["jogo:N", "Minutos:Q", "Posses usadas:Q"])
    use = base.mark_line(color="#f59e0b", point=True).encode(y=alt.Y("Posses usadas:Q", title="posses usadas"))
    left = mins
    if minutes_exp:  # minutos esperados na projeção, no mesmo eixo dos minutos
        rule = alt.Chart(alt.Data(values=[{"Minutos": minutes_exp}])).mark_rule(
            strokeDash=[4, 3], color="#93c5fd").encode(y="Minutos:Q")
        left = alt.layer(mins, rule)
    return alt.layer(left, use).resolve_scale(y="independent").properties(height=200)


def _made_chart(games: list[dict[str, Any]], made: str, tried: str) -> alt.Chart:
    data = []
    for i, g in enumerate(reversed(games)):
        lbl = f"{g['data'][8:]}/{g['data'][5:7]}"
        data += [{"jogo": lbl, "tipo": "Tentadas", "n": g[tried], "o": i},
                 {"jogo": lbl, "tipo": "Certas", "n": g[made], "o": i}]
    return alt.Chart(alt.Data(values=data)).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
        x=alt.X("jogo:N", sort=None, title=None, axis=alt.Axis(labelAngle=-50, labelFontSize=10)),
        xOffset="tipo:N", y=alt.Y("n:Q", title=None),
        color=alt.Color("tipo:N", scale=alt.Scale(domain=["Tentadas", "Certas"], range=["#475569", GREEN]),
                        legend=alt.Legend(orient="top", title=None)),
        tooltip=["jogo:N", "tipo:N", "n:Q"]).properties(height=180)


LOG_STATS = ("minutes", "pts", "reb", "ast", "pra", "fg3m", "stl", "blk")
BAND_COLORS = {"acima": ("#14532d", "#bbf7d0"), "perto": ("#713f12", "#fde68a"),
               "abaixo": ("#7f1d1d", "#fecaca")}


def _log_table(games: list[dict[str, Any]], stat: str, line: float, avgs: dict[str, float],
               with_season: bool = False):
    """Jogos com cada valor colorido contra a média dele (o mercado, contra a linha)."""
    import pandas as pd

    names = {"minutes": "Min", "pts": "PTS", "reb": "REB", "ast": "AST", "pra": "PRA", "fg3m": "3PM",
             "stl": "ROU", "blk": "TOC"}
    cols = [s for s in LOG_STATS] + ([stat] if stat not in LOG_STATS else [])
    rows = []
    for g in games:
        r = {"Data": f"{g['data'][8:]}/{g['data'][5:7]}" + (f"/{g['data'][2:4]}" if with_season else ""),
             "Adv.": ("vs " if g["em_casa"] else "@ ") + g.get("adv", ""),
             "Res.": f"{g['resultado'] or ''} {g['margem']:+d}" if g["margem"] is not None else ""}
        for c in cols:
            r[names.get(c, MARKETS.get(c, c))] = round(g[c]) if c == "minutes" else g[c]
        rows.append(r)
    df = pd.DataFrame(rows)

    def color(col):
        key = next((c for c in cols if names.get(c, MARKETS.get(c, c)) == col.name), None)
        if key is None:
            return [""] * len(col)
        ref = line if key == stat else avgs.get(key)
        out = []
        for v in col:
            b = hs.band(v, ref)
            out.append("" if b is None else
                       f"background-color: {BAND_COLORS[b][0]}; color: {BAND_COLORS[b][1]}; font-weight: 600")
        return out

    styled = df.style.apply(color, axis=0)
    mk = names.get(stat, MARKETS.get(stat, stat))
    return styled.set_properties(subset=[mk], **{"border-left": "2px solid #e6edf3"})


def _bet_form(conn, p, stat, day, line, po, odd_o, odd_u, seal) -> None:
    cfg = load_bet_config()
    with st.expander("Registrar aposta", icon=":material/receipt_long:"):
        with st.form(f"aposta_{p['player_id']}_{stat}", border=False):
            default_side = "over" if (po or 0) >= 0.5 else "under"
            unit_default = (seal or {}).get("unidade") or 1.0
            with st.container(horizontal=True, gap="small"):
                side = st.segmented_control("Lado", ["over", "under"], default=default_side,
                                            format_func=str.capitalize)
                units = st.segmented_control("Unidades", cfg.get("unidades", [0.5, 1.0, 2.0]),
                                             default=unit_default, format_func=lambda u: f"{u:g} u")
            with st.container(horizontal=True, gap="small"):
                odd_default = (odd_o if side == "over" else odd_u) or 1.90
                odd = st.number_input("Odd", value=float(odd_default), min_value=1.01, step=0.01,
                                      format="%.2f", width=96)
                book = st.text_input("Casa", width=150)
            note = st.text_input("Observação (opcional)")
            if st.form_submit_button("Registrar", type="primary"):
                prob = None if po is None else (po if side == "over" else 1 - po)
                add_bet(conn, day=day, player_id=p["player_id"], market=stat, side=side or default_side,
                        line=line, odd=odd, units=units or 1.0, game_id=p.get("game_id"),
                        bookmaker=book or None, prob=prob, proj=p.get("proj"), note=note or None)
                st.success("Aposta registrada. Ela é conferida sozinha depois do jogo (página Apostas).")


def _validation_badge(v: dict[str, Any] | None) -> str:
    if not v:
        return ""
    cls = {"validada": "ok", "pré-análise": "pre"}.get(v["status"], "end")
    return f'<span class="vs {cls}" title="{v["motivo"]}">{v["status"]}</span>'


def player_page(conn, p: dict[str, Any], game_item: dict[str, Any], stat: str, day: str,
                params: dict[str, Any]) -> None:
    """Página do jogador (substitui o antigo diálogo)."""
    market_cfg = (params.get("mercados") or {}).get(stat) or {}
    cfg = betaniag_cfg()
    mobile = is_mobile()
    abbr = {r["id"]: r["abbreviation"] for r in conn.execute("SELECT id, abbreviation FROM teams")}
    log = [{**g, "adv": abbr.get(g["opp_id"], "")} for g in (p.get("historico_total") or [])]
    season = p.get("temporada_atual") or game_item["jogo"]["season"]

    st.button("← Voltar à lista", type="tertiary", on_click=close_player)
    st.html(DETAIL_CSS + (
        f'<div class="dh"><img src="{headshot(p["player_id"])}" alt="">'
        f'<div><div class="n">{p["jogador"]} {seal_html(p.get("selo"))}</div>'
        f'<div class="t">{p["time"]} x {p["adversario"]} · {MARKETS.get(stat, stat)} · '
        f'{p.get("grupo") or "?"} / {p.get("posicao_est") or "?"} (estimada) · '
        f'{(game_item["jogo"].get("status") or "")}'
        f'{_validation_badge(game_item.get("validacao")) if cfg else ""}</div></div></div>'))
    if p.get("lesao"):
        st.warning(f"Injury report: {p['lesao']} — {p.get('lesao_motivo') or ''}")

    if mobile:  # celular: linha, chance e checklist primeiro; gráficos depois
        side, main = st.container(), st.container()
    else:
        main, side = st.columns([3, 2], gap="large")

    with side:
        with st.form(f"linha_{p['player_id']}_{stat}", border=True):
            st.markdown("**Linha da casa**")
            with st.container(horizontal=True, gap="small"):
                line = st.number_input("Linha", value=float(p["linha"] or 0.5), step=0.5, format="%.1f",
                                       width=96)
                odd_o = st.number_input("Odd over", value=float(p["odd_over"] or 0.0), step=0.01,
                                        format="%.2f", width=96)
                odd_u = st.number_input("Odd under", value=float(p["odd_under"] or 0.0), step=0.01,
                                        format="%.2f", width=96)
            with st.container(horizontal=True, gap="small"):
                if st.form_submit_button("Salvar linha", type="primary"):
                    save_line(conn, day, p["player_id"], stat, line, odd_o or None, odd_u or None)
                    st.rerun()
                if not p["linha_ref"] and st.form_submit_button("Apagar linha"):
                    save_line(conn, day, p["player_id"], stat, None)
                    st.rerun()
            if p["linha_ref"]:
                st.caption("Linha \"ref\" = L10 arredondado (não é da casa).")

        d = p.get("proj_detalhe") or {}
        minutes = None
        if d.get("minutos"):
            lo, hi = 10, 44
            minutes = st.slider("E se jogar quantos minutos?", lo, hi, int(round(d["minutos"])),
                                help="Mesma produção por minuto e mesmos ajustes; muda só o tempo em quadra.")
        proj = hs.scale_to_minutes(d, minutes) if minutes else p.get("proj")
        po = prob_over(proj, line, market_cfg)
        st.html(DETAIL_CSS + _kpis(p, line, proj, po, odd_o, odd_u))
        if minutes and d.get("minutos") and abs(minutes - d["minutos"]) >= 1:
            st.caption(f"Com {minutes} min (esperado {d['minutos']:.0f}): projeção {proj:.1f}.")
        if d.get("erro_tipico"):
            st.caption(f"Erro típico da projeção: ±{d['erro_tipico']}. "
                       "Valor esperado positivo = a odd paga mais do que a chance calculada.")

        if cfg:
            live = {**p, "linha": line, "p_over": po, "p_under": None if po is None else 1 - po,
                    "odd_over": odd_o or None, "odd_under": odd_u or None,
                    "janelas": hs.windows(log, stat, line, p.get("adversario_id"), season)}
            s = bt.seal(live, cfg)
            st.markdown("**Checklist BetânIAG** " + (f"· {s['nivel']}" if s else ""))
            st.html(DETAIL_CSS + _checklist_html(bt.checklist(live, cfg, game_item.get("validacao"))))
            _ai_box(cfg, live, stat, s, game_item.get("validacao"))
        else:
            s = None
        _bet_form(conn, p, stat, day, line, po, odd_o, odd_u, s)
        _injury_panel(game_item, p)

    with main:
        jan = hs.windows(log, stat, line, p.get("adversario_id"), season)
        avgs = hs.season_averages(log, season, LOG_STATS)
        st.html(DETAIL_CSS + _rates_html(jan))
        cur, prev = hs.season_label(season), hs.season_label(season - 1)
        with st.container(horizontal=True, vertical_alignment="center"):
            win = st.segmented_control("Jogos", ["L5", "L10", "L20", cur, "H2H", prev], default="L10",
                                       key=f"win_{p['player_id']}", label_visibility="collapsed") or "L10"
            spl = st.pills("Recorte", list(hs.SPLITS), format_func=hs.SPLITS.get,
                           key=f"split_{p['player_id']}", label_visibility="collapsed")
        pool = hs.split(log, spl)
        if win == "H2H":
            games = hs.h2h_games(pool, p.get("adversario_id"), limit=20)
        elif win == prev:
            games = [g for g in pool if g["season"] == season - 1][:41]
        else:
            cur_games = [g for g in pool if g["season"] == season]
            games = cur_games if win == cur else cur_games[:int(win[1:])]
        if games:
            over = sum(1 for g in games if g[stat] > line)
            avg = sum(g[stat] for g in games) / len(games)
            st.markdown(f"**{over}/{len(games)} acima de {line:g}** · média {avg:.1f}"
                        + (f" · recorte: {hs.SPLITS[spl]}" if spl else ""))
            st.altair_chart(_game_chart(games, stat, line), width="stretch")
            st.markdown("**Minutos e posses usadas** (FGA + 0,44·FTA + TOV)")
            st.altair_chart(_minutes_chart(games, (p.get("proj_detalhe") or {}).get("minutos")), width="stretch")
            made, tried, title = MADE_TRIED.get(stat, (None, None, None))
            tot_m = sum(g[made] for g in games) if made else 0
            tot_t = sum(g[tried] for g in games) if tried else 0
            if made and tot_t >= len(games):  # só se ele arremessa isso com frequência
                st.markdown(f"**{title}: certas x tentadas** · {tot_m}/{tot_t}"
                            + (f" ({100 * tot_m / tot_t:.0f}%)" if tot_t else ""))
                st.altair_chart(_made_chart(games, made, tried), width="stretch")
            st.markdown("**Jogo a jogo**")
            st.dataframe(_log_table(games, stat, line, avgs), hide_index=True, width="stretch",
                         height=min(40 + 35 * len(games), 420))
            st.caption(f"Verde = atingiu a média dele na temporada (no {MARKETS.get(stat, stat)}, a linha "
                       f"{line:g}); âmbar = chegou a 80%; vermelho = abaixo.")
        else:
            st.info("Sem jogos nesse recorte.")

        h2h = hs.h2h_games(log, p.get("adversario_id"))
        with st.expander(f"H2H contra {p['adversario']} ({len(h2h)} jogos, todas as temporadas)",
                         expanded=bool(h2h) and not mobile):
            if h2h:
                st.dataframe(_log_table(h2h, stat, line, avgs, with_season=True), hide_index=True,
                             width="stretch")
                st.caption("H2H tem poucos jogos por temporada: serve de contexto, não de critério.")
            else:
                st.caption("Nenhum jogo contra esse adversário na base.")

        if d:
            with st.expander("De onde vem a projeção"):
                st.markdown(
                    f"- Base **{d['base']}** = taxa por minuto × **{d['minutos']} min** esperados\n"
                    f"- Defesa adversária na posição (DvP rank {p.get('dvp_rank') or '—'}º): ×{d['f_dvp']}\n"
                    f"- Ritmo do jogo: ×{d['f_ritmo']}\n"
                    f"- Ajuste calibrado ({100 * d['ausencia']:.0f}% da produção do time fora): ×{d['f_ajuste']}")
        zm = p.get("zonas")
        if zm:
            with st.expander(f"Zonas de arremesso · encaixe {zm['encaixe_pp']:+.1f} p.p."):
                st.dataframe([{"Zona": z["zona"], "% dele": z["arremessos_dele_pct"], "FG% dele": z["fg_dele"],
                               "FG% cedido": z["fg_cedido"], "FG% liga": z["fg_liga"]} for z in zm["zonas"]],
                             hide_index=True, width="stretch")
                st.caption("Fotografia da temporada até a última carga; ainda sem validação retroativa.")


def _injury_panel(game_item: dict[str, Any], p: dict[str, Any]) -> None:
    g = game_item["jogo"]
    d = game_item["desfalques"]
    when = (f"injury report {game_item['injury_report'][11:]} ET" if game_item.get("injury_report")
            else "fora no último jogo")
    with st.container(border=True):
        st.markdown(f"**Desfalques** · {when}")
        st.markdown(f"{g['visitor']}: {', '.join(d['fora']) or '—'}  \n{g['home']}: {', '.join(d['casa']) or '—'}")
        for c in p.get("com_sem") or []:
            st.markdown(f"- Com **{c['companheiro']}**: {c['com']} em {c['jogos_com']} j · "
                        f"sem: {c['sem'] if c['sem'] is not None else '—'} em {c['jogos_sem']} j")
        if game_item.get("margem_esperada") is not None:
            m = game_item["margem_esperada"]
            fav = g["home"] if m >= 0 else g["visitor"]
            st.caption(f"Margem esperada: {fav} por {abs(m):.1f} · risco de blowout "
                       f"{100 * game_item['risco_blowout']:.0f}%")


def _ai_box(cfg, p, stat, seal, valid) -> None:
    from nbastats import ia

    ok, why = ia.status(cfg)
    with st.expander("Relatório BetânIAG com IA", icon=":material/auto_awesome:"):
        if not ok:
            st.caption(why)
            return
        q = st.text_input("Pergunta (opcional)", key=f"ia_q_{p['player_id']}")
        if st.button("Gerar relatório", key=f"ia_{p['player_id']}"):
            with st.spinner("Escrevendo..."):
                try:
                    st.markdown(ia.report(cfg, {"props": [ia.player_payload(p, stat, seal, valid)]}, q or None))
                except Exception as exc:
                    st.error(f"Falhou: {exc}")
