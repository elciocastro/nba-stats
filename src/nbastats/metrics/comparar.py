"""Comparações: jogador × jogador, time × time e tendências da liga."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any

from .matchup import (
    _player_rows, _team_games, dvp, player_form, player_groups, team_context,
)

COMPARE_STATS = ("pts", "reb", "ast", "pra", "fg3m")


def compare_players(a: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
    """Linhas lado a lado de dois jogadores do relatório (mesmo mercado, com linha)."""
    def pct(p, key):
        return None if p.get(key) is None else round(100 * p[key])

    def jan(p, k):
        w = (p.get("janelas") or {}).get(k) or {}
        return None if w.get("pct") is None else f"{w['pct']}% ({w['jogos']})"

    fields = [
        ("Jogo", lambda p: f"{p['time']} x {p['adversario']}"),
        ("Linha", lambda p: p.get("linha")),
        ("Projeção", lambda p: p.get("proj")),
        ("Proj. − linha", lambda p: p.get("proj_vs_linha")),
        ("Chance over %", lambda p: pct(p, "p_over")),
        ("L5", lambda p: p.get("l5")), ("L10", lambda p: p.get("l10")),
        ("Temporada", lambda p: p.get("temporada")),
        ("Over L10", lambda p: jan(p, "L10")), ("H2H", lambda p: jan(p, "H2H")),
        ("Minutos L5/L10", lambda p: f"{p.get('min_l5') or 0:.0f} / {p.get('min_l10') or 0:.0f}"),
        ("Uso L5/L10 %", lambda p: f"{p.get('usg_l5') or 0:.0f} / {p.get('usg_l10') or 0:.0f}"),
        ("DvP rank", lambda p: p.get("dvp_rank")),
        ("Lesão", lambda p: p.get("lesao") or "—"),
    ]
    return [{"Item": name, a["jogador"]: f(a), b["jogador"]: f(b)} for name, f in fields]


def _season_of(conn: sqlite3.Connection, day: str) -> int | None:
    row = conn.execute("SELECT MAX(season) AS s FROM games WHERE date <= ?", (day,)).fetchone()
    return row["s"] if row else None


def team_compare(conn: sqlite3.Connection, day: str, team_a: int, team_b: int,
                 rules: dict[str, Any], stats: tuple[str, ...] = COMPARE_STATS) -> dict[str, Any]:
    """Ritmo, saldo, pontos feitos/cedidos e DvP por posição de dois times,
    temporada inteira e últimos ``dvp_recente_dias`` dias."""
    season = _season_of(conn, day)
    if season is None:
        return {}
    rows = _player_rows(conn, season, day)
    teams = _team_games(rows)
    ctx = team_context(teams)
    groups = player_groups(player_form(rows, teams), rules)
    since = (date.fromisoformat(day) - timedelta(days=rules.get("dvp_recente_dias", 15))).isoformat()
    d_all, d_rec = dvp(rows, teams, groups), dvp(rows, teams, groups, since=since)
    abbr = {r["id"]: r["abbreviation"] for r in conn.execute("SELECT id, abbreviation FROM teams")}

    def side(t: int) -> dict[str, Any]:
        mine = [v for (g, tid), v in teams.items() if tid == t]
        opp = [v for (g, tid), v in teams.items() if v["opp_id"] == t]
        out = {"time": abbr.get(t), "jogos": len(mine), "ritmo": ctx["ritmo"].get(t),
               "saldo": ctx["saldo"].get(t),
               "pts_feitos": round(sum(v["pts"] for v in mine) / len(mine), 1) if mine else None,
               "pts_cedidos": round(sum(v["pts"] for v in opp) / len(opp), 1) if opp else None,
               "dvp": []}
        for grp in sorted({g for g in groups.values() if g}):
            for s in stats:
                a = (d_all.get(t, {}).get(grp) or {}).get(s) or {}
                r = (d_rec.get(t, {}).get(grp) or {}).get(s) or {}
                out["dvp"].append({"grupo": grp, "stat": s, "media": a.get("media"), "rank": a.get("rank"),
                                   "media_rec": r.get("media"), "rank_rec": r.get("rank")})
        return out

    return {"temporada": season, "liga_ritmo": ctx["ritmo_liga"], "a": side(team_a), "b": side(team_b)}


def trends(conn: sqlite3.Connection, day: str, rules: dict[str, Any], top: int = 15,
           min_minutes: float = 15.0) -> dict[str, list[dict[str, Any]]]:
    """Quem ganhou (ou perdeu) minutos e uso no L5 contra a temporada, e as
    defesas que mais pioraram nos últimos ``dvp_recente_dias`` dias."""
    season = _season_of(conn, day)
    if season is None:
        return {"minutos": [], "uso": [], "defesas": []}
    rows = _player_rows(conn, season, day)
    teams = _team_games(rows)
    form = player_form(rows, teams)
    abbr = {r["id"]: r["abbreviation"] for r in conn.execute("SELECT id, abbreviation FROM teams")}
    players = [f for f in form.values() if f["jogos"] >= 8 and (f["minutes_l5"] or 0) >= min_minutes]

    def row(f, key_l5, key_t):
        return {"player_id": f["player_id"], "jogador": f["jogador"], "time": abbr.get(f["team_id"]),
                "l5": f[key_l5], "temporada": f[key_t], "dif": round(f[key_l5] - f[key_t], 1),
                "pra_l5": f["pra_l5"], "pra_temp": f["pra_temp"]}

    mins = sorted((row(f, "minutes_l5", "minutes_temp") for f in players), key=lambda r: r["dif"], reverse=True)
    uso = sorted((row(f, "usg_l5", "usg_temp") for f in players if f["usg_l5"] and f["usg_temp"]),
                 key=lambda r: r["dif"], reverse=True)

    groups = player_groups(form, rules)
    since = (date.fromisoformat(day) - timedelta(days=rules.get("dvp_recente_dias", 15))).isoformat()
    d_all, d_rec = dvp(rows, teams, groups), dvp(rows, teams, groups, since=since)
    worse = []
    for t, by_group in d_rec.items():
        for grp, by_stat in by_group.items():
            rec = by_stat["pra"]["media"]
            full = d_all.get(t, {}).get(grp, {}).get("pra", {}).get("media")
            if full:
                worse.append({"time": abbr.get(t), "grupo": grp, "pra_temporada": full, "pra_recente": rec,
                              "dif": round(rec - full, 1), "rank_recente": by_stat["pra"]["rank"]})
    worse.sort(key=lambda r: r["dif"], reverse=True)
    return {"minutos": mins[:top], "minutos_queda": mins[::-1][:top], "uso": uso[:top], "defesas": worse[:top]}
