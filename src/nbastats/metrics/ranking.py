"""Ranking de jogadores e box score de um jogo, para o site novo.

Ranking: médias da temporada e dos últimos N jogos, porcentagens de
arremesso (FG%, 3P%, FT%, TS%) e, opcionalmente, por 36 minutos. O time sai
de cada jogo (``player_game_stats.team_id``), então quem foi trocado aparece
como "GSW/CHI" (do mais recente ao mais antigo).
"""

from __future__ import annotations

import sqlite3
from typing import Any

COUNTING = ("pts", "reb", "ast", "stl", "blk", "fg3m", "turnover", "oreb", "dreb", "pf")


def _pct(made: float, att: float) -> float | None:
    return round(100 * made / att, 1) if att else None


def _ts(pts: float, fga: float, fta: float) -> float | None:
    den = 2 * (fga + 0.44 * fta)
    return round(100 * pts / den, 1) if den else None


def ranking(conn: sqlite3.Connection, season: int, last_n: int = 10, min_games: int = 1,
            per36: bool = False, postseason: bool = False) -> list[dict[str, Any]]:
    """Uma linha por jogador. Com ``per36`` as contagens viram por 36 minutos."""
    sql = """
        SELECT s.player_id, s.team_id, s.minutes, s.pts, s.reb, s.ast, s.stl, s.blk, s.fg3m,
               s.turnover, s.oreb, s.dreb, s.pf, s.fgm, s.fga, s.fg3a, s.ftm, s.fta, s.plus_minus,
               g.date, t.abbreviation AS time
        FROM player_game_stats s JOIN games g ON g.id = s.game_id
        LEFT JOIN teams t ON t.id = s.team_id
        WHERE g.season = ? AND g.postseason = ? AND s.minutes > 0
        ORDER BY s.player_id, g.date DESC, g.id DESC
    """
    by: dict[int, list[sqlite3.Row]] = {}
    for r in conn.execute(sql, (season, int(postseason))):
        by.setdefault(r["player_id"], []).append(r)
    names = {r["id"]: (f"{r['first_name'] or ''} {r['last_name'] or ''}".strip(), r["position"])
             for r in conn.execute("SELECT id, first_name, last_name, position FROM players")}
    out = []
    for pid, rows in by.items():
        if len(rows) < min_games:
            continue
        teams: list[str] = []
        for r in rows:
            if r["time"] and r["time"] not in teams:
                teams.append(r["time"])
        row: dict[str, Any] = {"player_id": pid, "jogador": names.get(pid, (str(pid), None))[0],
                               "posicao": names.get(pid, (None, None))[1], "time": "/".join(teams),
                               "jogos": len(rows)}
        row |= _block(rows, per36, "")
        row |= _block(rows[:last_n], per36, "_n")
        out.append(row)
    out.sort(key=lambda r: r["pts"] or 0, reverse=True)
    return out


def _block(rows: list[sqlite3.Row], per36: bool, suffix: str) -> dict[str, Any]:
    n = len(rows)
    tot = {k: sum((r[k] or 0) for r in rows) for k in (*COUNTING, "minutes", "fgm", "fga", "fg3a",
                                                        "ftm", "fta", "plus_minus")}
    mins = tot["minutes"]
    scale = (36 / mins if mins else 0) if per36 else 1 / n
    b = {f"{k}{suffix}": round(tot[k] * scale, 1) for k in COUNTING}
    b[f"pra{suffix}"] = round((tot["pts"] + tot["reb"] + tot["ast"]) * scale, 1)
    b[f"min{suffix}"] = round(mins / n, 1)
    b[f"pm{suffix}"] = round(tot["plus_minus"] / n, 1)
    if not suffix:  # porcentagens só na temporada (na janela curta o ruído é grande)
        b |= {"fg_pct": _pct(tot["fgm"], tot["fga"]), "fg3_pct": _pct(tot["fg3m"], tot["fg3a"]),
              "ft_pct": _pct(tot["ftm"], tot["fta"]), "ts_pct": _ts(tot["pts"], tot["fga"], tot["fta"]),
              "fga": round(tot["fga"] / n, 1), "fg3a": round(tot["fg3a"] / n, 1), "fta": round(tot["fta"] / n, 1)}
    return b


def games_by_date(conn: sqlite3.Connection, day: str) -> list[dict[str, Any]]:
    """Jogos de uma data com placar e se já tem box score."""
    sql = """
        SELECT g.id, g.date, g.status, g.home_team_score AS placar_casa, g.visitor_team_score AS placar_fora,
               h.abbreviation AS casa, v.abbreviation AS fora, g.home_team_id AS casa_id, g.visitor_team_id AS fora_id,
               EXISTS (SELECT 1 FROM player_game_stats s WHERE s.game_id = g.id) AS tem_box
        FROM games g JOIN teams h ON h.id = g.home_team_id JOIN teams v ON v.id = g.visitor_team_id
        WHERE g.date = ? ORDER BY g.id
    """
    return [dict(r) | {"tem_box": bool(r["tem_box"])} for r in conn.execute(sql, (day,))]


def last_game_date(conn: sqlite3.Connection, before: str) -> str | None:
    """Última data (até ``before``, inclusive) com algum box score."""
    r = conn.execute("""SELECT MAX(g.date) FROM games g WHERE g.date <= ?
                        AND EXISTS (SELECT 1 FROM player_game_stats s WHERE s.game_id = g.id)""", (before,)).fetchone()
    return r[0] if r else None


def boxscore_game(conn: sqlite3.Connection, game_id: int) -> dict[str, Any] | None:
    """Box score completo: jogadores de cada time (mais minutos primeiro) e totais."""
    g = conn.execute("""
        SELECT g.*, h.abbreviation AS casa, v.abbreviation AS fora, h.full_name AS casa_nome, v.full_name AS fora_nome
        FROM games g JOIN teams h ON h.id = g.home_team_id JOIN teams v ON v.id = g.visitor_team_id
        WHERE g.id = ?""", (game_id,)).fetchone()
    if g is None:
        return None
    rows = conn.execute("""
        SELECT s.*, TRIM(COALESCE(p.first_name, '') || ' ' || COALESCE(p.last_name, '')) AS jogador, p.position AS posicao
        FROM player_game_stats s LEFT JOIN players p ON p.id = s.player_id
        WHERE s.game_id = ? ORDER BY s.minutes DESC""", (game_id,)).fetchall()
    teams = []
    for side, tid, abbr, name, score in (("fora", g["visitor_team_id"], g["fora"], g["fora_nome"], g["visitor_team_score"]),
                                         ("casa", g["home_team_id"], g["casa"], g["casa_nome"], g["home_team_score"])):
        ps = [_box_row(r) for r in rows if r["team_id"] == tid]
        played = [p for p in ps if p["min"] > 0]
        tot = {k: sum(p[k] or 0 for p in played) for k in ("pts", "reb", "ast", "stl", "blk", "turnover", "pf",
                                                           "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb")}
        tot |= {"fg_pct": _pct(tot["fgm"], tot["fga"]), "fg3_pct": _pct(tot["fg3m"], tot["fg3a"]),
                "ft_pct": _pct(tot["ftm"], tot["fta"])}
        teams.append({"lado": side, "time_id": tid, "time": abbr, "nome": name, "placar": score,
                      "jogadores": played, "nao_jogaram": [p["jogador"] for p in ps if p["min"] <= 0], "totais": tot})
    return {"id": g["id"], "data": g["date"], "status": g["status"], "temporada": g["season"],
            "playoffs": bool(g["postseason"]), "times": teams}


def _box_row(r: sqlite3.Row) -> dict[str, Any]:
    keys = ("pts", "reb", "ast", "stl", "blk", "turnover", "pf", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta",
            "oreb", "dreb", "plus_minus")
    d = {k: r[k] for k in keys}
    d |= {"player_id": r["player_id"], "jogador": r["jogador"] or str(r["player_id"]), "posicao": r["posicao"],
          "min": round(r["minutes"] or 0, 1), "pra": (r["pts"] or 0) + (r["reb"] or 0) + (r["ast"] or 0)}
    return d
