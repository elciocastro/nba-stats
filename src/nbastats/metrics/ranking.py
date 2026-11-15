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
            per36: bool = False, postseason: bool = False, max_margem: int | None = None) -> list[dict[str, Any]]:
    """Uma linha por jogador. Com ``per36`` as contagens viram por 36 minutos.
    ``max_margem``: tira os jogos decididos por essa diferença ou mais (lavadas,
    em que os titulares saem cedo)."""
    sql = """
        SELECT s.player_id, s.team_id, s.minutes, s.pts, s.reb, s.ast, s.stl, s.blk, s.fg3m,
               s.turnover, s.oreb, s.dreb, s.pf, s.fgm, s.fga, s.fg3a, s.ftm, s.fta, s.plus_minus,
               g.date, t.abbreviation AS time
        FROM player_game_stats s JOIN games g ON g.id = s.game_id
        LEFT JOIN teams t ON t.id = s.team_id
        WHERE g.season = ? AND g.postseason = ? AND s.minutes > 0
          AND (:m IS NULL OR ABS(COALESCE(g.home_team_score, 0) - COALESCE(g.visitor_team_score, 0)) < :m)
        ORDER BY s.player_id, g.date DESC, g.id DESC
    """
    by: dict[int, list[sqlite3.Row]] = {}
    for r in conn.execute(sql.replace("= ? AND g.postseason = ?", "= :s AND g.postseason = :p"),
                          {"s": season, "p": int(postseason), "m": max_margem}):
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


# ---------- jogos ao vivo e por time ----------

def overlay_live(jogos: list[dict[str, Any]], live: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Placar e situação do placar ao vivo da NBA por cima dos jogos do banco
    (o box score do banco só chega depois do jogo, pela atualização)."""
    by_id = {g["game_id"]: g for g in live}
    out = []
    for j in jogos:
        g = by_id.get(j["id"])
        if g is None:
            out.append({**j, "ao_vivo": False})
            continue
        out.append({**j, "status": g["status_texto"] or j["status"], "ao_vivo": g["status"] == 2,
                    "placar_casa": g["placar_casa"] if g["status"] >= 2 else j["placar_casa"],
                    "placar_fora": g["placar_fora"] if g["status"] >= 2 else j["placar_fora"],
                    "tem_box": j["tem_box"] or (g["status"] >= 2 and bool(g["jogadores"]))})
    return out


def live_boxscore(g: dict[str, Any], names: dict[str, str] | None = None) -> dict[str, Any]:
    """Box score no formato de ``boxscore_game`` a partir do placar ao vivo."""
    names = names or {}
    teams = []
    for side, tid, abbr, score in (("fora", g["fora_id"], g["fora"], g["placar_fora"]),
                                   ("casa", g["casa_id"], g["casa"], g["placar_casa"])):
        ps = []
        for p in (x for x in g["jogadores"] if x["team_id"] == tid):
            ps.append({"player_id": p["player_id"], "jogador": p.get("nome") or str(p["player_id"]), "posicao": None,
                       "min": p["minutos"], "pts": p["pts"], "reb": p["reb"], "ast": p["ast"], "stl": p["stl"],
                       "blk": p["blk"], "turnover": p["turnover"], "pf": p.get("faltas"), "fgm": p.get("fgm"),
                       "fga": p.get("fga"), "fg3m": p["fg3m"], "fg3a": p["fg3a"], "ftm": p["ftm"], "fta": p["fta"],
                       "oreb": None, "dreb": None, "plus_minus": None, "pra": p["pts"] + p["reb"] + p["ast"],
                       "em_quadra": p.get("em_quadra", False)})
        ps.sort(key=lambda p: p["min"], reverse=True)
        played = [p for p in ps if p["min"] > 0]
        tot = {k: sum(p[k] or 0 for p in played) for k in ("pts", "reb", "ast", "stl", "blk", "turnover", "pf",
                                                           "fgm", "fga", "fg3m", "fg3a", "ftm", "fta")}
        tot |= {"oreb": None, "fg_pct": _pct(tot["fgm"], tot["fga"]), "fg3_pct": _pct(tot["fg3m"], tot["fg3a"]),
                "ft_pct": _pct(tot["ftm"], tot["fta"])}
        teams.append({"lado": side, "time_id": tid, "time": abbr, "nome": names.get(abbr, abbr), "placar": score,
                      "jogadores": played, "nao_jogaram": [p["jogador"] for p in ps if p["min"] <= 0], "totais": tot})
    return {"id": g["game_id"], "data": g["data"], "status": g["status_texto"], "temporada": None, "playoffs": False,
            "times": teams, "ao_vivo": g["status"] == 2, "periodo": g.get("periodo")}


def team_games(conn: sqlite3.Connection, team_id: int, season: int) -> list[dict[str, Any]]:
    """Jogos do time na temporada (mais recente primeiro), com placar e resultado."""
    rows = conn.execute("""
        SELECT g.id, g.date, g.status, g.postseason, g.home_team_id, g.home_team_score, g.visitor_team_score,
               h.abbreviation AS casa, v.abbreviation AS fora,
               EXISTS (SELECT 1 FROM player_game_stats s WHERE s.game_id = g.id) AS tem_box
        FROM games g JOIN teams h ON h.id = g.home_team_id JOIN teams v ON v.id = g.visitor_team_id
        WHERE g.season = ? AND (g.home_team_id = ? OR g.visitor_team_id = ?)
        ORDER BY g.date DESC, g.id DESC""", (season, team_id, team_id)).fetchall()
    out = []
    for r in rows:
        casa = r["home_team_id"] == team_id
        pro, contra = (r["home_team_score"], r["visitor_team_score"]) if casa else (r["visitor_team_score"], r["home_team_score"])
        out.append({"id": r["id"], "data": r["date"], "em_casa": casa, "adversario": r["fora"] if casa else r["casa"],
                    "pro": pro, "contra": contra, "status": r["status"], "playoffs": bool(r["postseason"]),
                    "resultado": None if pro is None or contra is None else ("V" if pro > contra else "D"),
                    "tem_box": bool(r["tem_box"])})
    return out
