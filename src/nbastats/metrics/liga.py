"""Panorama da liga para a página inicial: última rodada, destaques
individuais, classificação, líderes, manchetes e transações.

Tudo sai do banco (consultas rápidas), sem a projeção do dia: a página
inicial mostra isto na hora enquanto o relatório de props é montado.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import defaultdict
from typing import Any

FINAL = "home_team_score IS NOT NULL AND visitor_team_score IS NOT NULL"

# ---------- última rodada ----------

def last_round_date(conn: sqlite3.Connection, before: str) -> str | None:
    """Última data antes de ``before`` com jogos encerrados e box score."""
    r = conn.execute(f"""SELECT MAX(g.date) FROM games g WHERE g.date < ? AND {FINAL}
                         AND EXISTS (SELECT 1 FROM player_game_stats s WHERE s.game_id = g.id)""", (before,)).fetchone()
    return r[0] if r else None


def results(conn: sqlite3.Connection, day: str) -> list[dict[str, Any]]:
    """Placar de cada jogo da data e o cestinha de cada lado."""
    games = conn.execute(f"""
        SELECT g.id, g.home_team_id, g.visitor_team_id, g.home_team_score, g.visitor_team_score,
               h.abbreviation AS casa, v.abbreviation AS fora
        FROM games g JOIN teams h ON h.id = g.home_team_id JOIN teams v ON v.id = g.visitor_team_id
        WHERE g.date = ? AND {FINAL} ORDER BY g.id""", (day,)).fetchall()
    tops: dict[tuple[int, int], dict[str, Any]] = {}
    for r in conn.execute("""
        SELECT s.game_id, s.team_id, s.player_id, s.pts, s.reb, s.ast, p.first_name, p.last_name
        FROM player_game_stats s JOIN games g ON g.id = s.game_id LEFT JOIN players p ON p.id = s.player_id
        WHERE g.date = ? AND s.minutes > 0 ORDER BY s.pts DESC, s.reb + s.ast DESC""", (day,)):
        tops.setdefault((r["game_id"], r["team_id"]), {
            "player_id": r["player_id"], "jogador": _nome(r), "pts": r["pts"], "reb": r["reb"], "ast": r["ast"]})
    out = []
    for g in games:
        casa_venceu = g["home_team_score"] > g["visitor_team_score"]
        out.append({"game_id": g["id"], "casa": g["casa"], "fora": g["fora"],
                    "casa_id": g["home_team_id"], "fora_id": g["visitor_team_id"],
                    "placar_casa": g["home_team_score"], "placar_fora": g["visitor_team_score"],
                    "vencedor": g["casa"] if casa_venceu else g["fora"],
                    "margem": abs(g["home_team_score"] - g["visitor_team_score"]),
                    "cestinha_casa": tops.get((g["id"], g["home_team_id"])),
                    "cestinha_fora": tops.get((g["id"], g["visitor_team_id"]))})
    return out


def game_score(s: sqlite3.Row | dict[str, Any]) -> float:
    """Game Score de John Hollinger: resume a atuação num número (~10 = média)."""
    v = {k: (s[k] or 0) for k in ("pts", "fgm", "fga", "fta", "ftm", "oreb", "dreb", "stl", "ast", "blk", "pf", "turnover")}
    return (v["pts"] + 0.4 * v["fgm"] - 0.7 * v["fga"] - 0.4 * (v["fta"] - v["ftm"]) + 0.7 * v["oreb"]
            + 0.3 * v["dreb"] + v["stl"] + 0.7 * v["ast"] + 0.7 * v["blk"] - 0.4 * v["pf"] - v["turnover"])


def top_performances(conn: sqlite3.Connection, day: str, limit: int = 8) -> list[dict[str, Any]]:
    """Melhores atuações da data pelo Game Score, com marcas (duplo-duplo,
    triplo-duplo, recorde do jogador na temporada)."""
    rows = conn.execute("""
        SELECT s.*, g.season, p.first_name, p.last_name, t.abbreviation AS time,
               CASE WHEN s.team_id = g.home_team_id THEN v.abbreviation ELSE h.abbreviation END AS adversario,
               CASE WHEN s.team_id = g.home_team_id THEN g.home_team_score ELSE g.visitor_team_score END AS pf_time,
               CASE WHEN s.team_id = g.home_team_id THEN g.visitor_team_score ELSE g.home_team_score END AS pf_adv
        FROM player_game_stats s JOIN games g ON g.id = s.game_id
        JOIN teams h ON h.id = g.home_team_id JOIN teams v ON v.id = g.visitor_team_id
        LEFT JOIN teams t ON t.id = s.team_id LEFT JOIN players p ON p.id = s.player_id
        WHERE g.date = ? AND s.minutes > 0""", (day,)).fetchall()
    ranked = sorted(rows, key=game_score, reverse=True)[:limit]
    out = []
    for r in ranked:
        dez = sum((r[k] or 0) >= 10 for k in ("pts", "reb", "ast", "stl", "blk"))
        marcas = ["triplo-duplo"] if dez >= 3 else ["duplo-duplo"] if dez == 2 else []
        prev = conn.execute("""SELECT MAX(s.pts) AS pts, COUNT(*) AS n FROM player_game_stats s JOIN games g ON g.id = s.game_id
                               WHERE s.player_id = ? AND g.season = ? AND g.date < ? AND s.minutes > 0""",
                            (r["player_id"], r["season"], day)).fetchone()
        if prev["n"] >= 3 and r["pts"] > (prev["pts"] or 0):
            marcas.append("recorde na temporada")
        venceu = None if r["pf_time"] is None else r["pf_time"] > r["pf_adv"]
        out.append({"player_id": r["player_id"], "jogador": _nome(r), "time": r["time"], "team_id": r["team_id"],
                    "adversario": r["adversario"], "game_id": r["game_id"],
                    "venceu": venceu, "min": round(r["minutes"]), "pts": r["pts"], "reb": r["reb"], "ast": r["ast"],
                    "fg3m": r["fg3m"], "stl": r["stl"], "blk": r["blk"], "fgm": r["fgm"], "fga": r["fga"],
                    "game_score": round(game_score(r), 1), "marcas": marcas})
    return out


# ---------- classificação e líderes ----------

def standings(conn: sqlite3.Connection, season: int, until: str | None = None) -> dict[str, list[dict[str, Any]]]:
    """Classificação por conferência: V-D, aproveitamento, jogos atrás do
    líder, últimos 10 e sequência. Só temporada regular."""
    teams = {r["id"]: dict(r) for r in conn.execute("SELECT id, abbreviation, full_name, conference FROM teams")}
    seq: dict[int, list[bool]] = defaultdict(list)
    sql = f"""SELECT home_team_id, visitor_team_id, home_team_score, visitor_team_score FROM games
              WHERE season = ? AND postseason = 0 AND {FINAL} {"AND date <= ?" if until else ""} ORDER BY date, id"""
    for g in conn.execute(sql, (season, until) if until else (season,)):
        home_win = g["home_team_score"] > g["visitor_team_score"]
        seq[g["home_team_id"]].append(home_win)
        seq[g["visitor_team_id"]].append(not home_win)
    out: dict[str, list[dict[str, Any]]] = {"East": [], "West": []}
    for tid, t in teams.items():
        conf = t.get("conference")
        if conf not in out:
            continue
        res = seq.get(tid, [])
        w = sum(res)
        lst = res[-10:]
        streak = 0
        for x in reversed(res):
            if x != res[-1]:
                break
            streak += 1
        out[conf].append({"team_id": tid, "time": t["abbreviation"], "nome": t["full_name"], "v": w, "d": len(res) - w,
                          "pct": round(w / len(res), 3) if res else None,
                          "ult10": f"{sum(lst)}-{len(lst) - sum(lst)}",
                          "sequencia": f"{'V' if res[-1] else 'D'}{streak}" if res else "—"})
    for rows in out.values():
        rows.sort(key=lambda r: (-(r["pct"] or 0), -r["v"], r["d"], r["time"]))
        if rows:
            lw, ll = rows[0]["v"], rows[0]["d"]
            for i, r in enumerate(rows, 1):
                r["pos"] = i
                gb = ((lw - r["v"]) + (r["d"] - ll)) / 2
                r["atras"] = "—" if gb == 0 else f"{gb:g}"
                r["zona"] = "playoff" if i <= 6 else "play-in" if i <= 10 else None
    return out


LIDER_STATS = {"pts": "Pontos", "reb": "Rebotes", "ast": "Assistências", "fg3m": "Bolas de 3", "stl": "Roubos",
               "blk": "Tocos"}


def leaders(conn: sqlite3.Connection, season: int, top: int = 5) -> dict[str, Any]:
    """Médias por jogo; entra quem jogou 70% dos jogos do time (regra da NBA)."""
    team_games = [r[0] for r in conn.execute(f"""
        SELECT COUNT(*) FROM (SELECT home_team_id AS t FROM games WHERE season = ? AND postseason = 0 AND {FINAL}
                              UNION ALL SELECT visitor_team_id FROM games WHERE season = ? AND postseason = 0 AND {FINAL})
        GROUP BY t""", (season, season))]
    if not team_games:
        return {"min_jogos": 0, "categorias": {}}
    team_games.sort()
    min_games = max(1, math.ceil(0.7 * team_games[len(team_games) // 2]))
    cols = ", ".join(f"AVG(s.{k}) AS {k}" for k in LIDER_STATS)
    rows = conn.execute(f"""
        SELECT s.player_id, p.first_name, p.last_name, t.abbreviation AS time, COUNT(*) AS jogos, {cols}
        FROM player_game_stats s JOIN games g ON g.id = s.game_id
        LEFT JOIN players p ON p.id = s.player_id LEFT JOIN teams t ON t.id = p.team_id
        WHERE g.season = ? AND g.postseason = 0 AND s.minutes > 0
        GROUP BY s.player_id HAVING COUNT(*) >= ?""", (season, min_games)).fetchall()
    cats = {}
    for k, label in LIDER_STATS.items():
        best = sorted(rows, key=lambda r, k=k: r[k] or 0, reverse=True)[:top]
        cats[k] = {"nome": label, "jogadores": [{"player_id": r["player_id"], "jogador": _nome(r), "time": r["time"],
                                                 "jogos": r["jogos"], "media": round(r[k] or 0, 1)} for r in best]}
    return {"min_jogos": min_games, "categorias": cats}


# ---------- manchetes e transações ----------

TIPO_NOTICIA = {"Story": "Matéria", "HeadlineNews": "Notícia", "Recap": "Resumo do jogo", "Preview": "Prévia",
                "Media": "Vídeo"}


def news(conn: sqlite3.Connection, limit: int = 12, videos: bool = False) -> list[dict[str, Any]]:
    sql = "SELECT * FROM news" + ("" if videos else " WHERE COALESCE(tipo, '') != 'Media'") + \
          " ORDER BY published_at DESC LIMIT ?"
    return [{"id": r["id"], "publicado": r["published_at"], "tipo": TIPO_NOTICIA.get(r["tipo"], r["tipo"]),
             "titulo": r["titulo"], "resumo": r["resumo"], "url": r["url"], "imagem": r["imagem"],
             "times": json.loads(r["times"] or "[]")} for r in conn.execute(sql, (limit,))]


POSICAO = {"guard": "o armador", "forward": "o ala", "center": "o pivô", "guard-forward": "o ala-armador",
           "forward-guard": "o ala-armador", "forward-center": "o ala-pivô", "center-forward": "o pivô"}
CONTRATO = {"Two-Way Contract": "contrato two-way", "Contract": "", "Rookie Scale Contract": "contrato de novato",
            "Veteran Extension": "extensão de contrato", "Rookie Scale Extension": "extensão de contrato de novato",
            "Rest-of-Season Contract": "até o fim da temporada", "10-Day Contract": "contrato de 10 dias",
            "Exhibit 10 Contract": "contrato Exhibit 10", "Multi-Year Contract": "contrato de vários anos"}
TIPO_TX = {"Signing": "Contratação", "Waive": "Dispensa", "Trade": "Troca", "ContractConverted": "Contrato",
           "AwardOnWaivers": "Contratação"}


def translate(tipo: str | None, desc: str, team: str | None, player: str | None) -> str:
    """Frase em português a partir do tipo e do texto original; se não
    reconhecer o modelo, devolve o original."""
    m_pos = re.search(r"(?:signed|waived|received|converted the contract of|claimed) "
                      r"(guard-forward|forward-guard|forward-center|center-forward|guard|forward|center) ", desc)
    pos = POSICAO.get(m_pos.group(1), "") if m_pos else ""
    if not player:  # jogador fora do banco: o nome vem do texto
        m_nome = re.search(r"(?:signed|waived|received|converted the contract of|claimed) (?:[a-z-]+ )?\s*"
                           r"([A-Z][^\s].*?)\.?(?: to an? | from | off waivers|\.?$)", desc)
        player = m_nome.group(1).rstrip(".") if m_nome and "draft" not in m_nome.group(1) else None
    quem = f"{pos} {player}".strip() if player else None
    m_from = re.search(r" from (.+?)\.?$", desc)
    m_contr = re.search(r" to an? (.+?)\.?$", desc)
    contrato = CONTRATO.get(m_contr.group(1).strip(), m_contr.group(1)) if m_contr else ""
    extra = f" ({contrato})" if contrato else ""
    if not team:
        return desc
    if tipo == "Waive" and quem:
        return f"{team} dispensou {quem}"
    if tipo == "Signing" and quem:
        verbo = "renovou com" if " re-signed " in desc else "contratou"
        return f"{team} {verbo} {quem}{extra}"
    if tipo == "ContractConverted" and quem:
        return f"{team} mudou o contrato de {quem}{f' para {contrato}' if contrato else ''}"
    if tipo == "AwardOnWaivers" and quem:
        return f"{team} pegou {quem} na lista de dispensas"
    if tipo == "Trade" and m_from:
        origem = m_from.group(1)
        if "draft consideration" in desc:
            return f"{team} recebeu compensação de draft do {origem}"
        if quem:
            return f"{team} recebeu {quem} do {origem}"
        m_pick = re.search(r"received (?:a |the )?(\d{4}) (1st|2nd|first|second) round", desc, re.I)
        if m_pick:
            rodada = "1ª" if m_pick.group(2).lower() in ("1st", "first") else "2ª"
            return f"{team} recebeu escolha de {rodada} rodada de {m_pick.group(1)} do {origem}"
    return desc


def transactions(conn: sqlite3.Connection, limit: int = 15, tipos: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    """Movimentações mais recentes; as linhas de uma mesma troca viram um item."""
    sql = """SELECT x.*, t.abbreviation AS time, t.full_name AS time_nome, p.first_name, p.last_name
             FROM transactions x LEFT JOIN teams t ON t.id = x.team_id LEFT JOIN players p ON p.id = x.player_id"""
    args: list[Any] = []
    if tipos:
        sql += f" WHERE x.tipo IN ({','.join('?' * len(tipos))})"
        args += list(tipos)
    sql += " ORDER BY x.date DESC, x.grupo, x.id"
    items: dict[str, dict[str, Any]] = {}
    for r in conn.execute(sql, args):
        key = r["grupo"] if r["tipo"] == "Trade" and r["grupo"] else r["id"]
        if key not in items:
            if len(items) >= limit:
                break
            items[key] = {"id": key, "data": r["date"], "tipo": TIPO_TX.get(r["tipo"], r["tipo"]), "times": [],
                          "jogadores": [], "linhas": []}
        it = items[key]
        player = _nome(r) if r["first_name"] or r["last_name"] else None
        if r["time"] and r["time"] not in it["times"]:
            it["times"].append(r["time"])
        if r["player_id"] and player:
            it["jogadores"].append({"player_id": r["player_id"], "jogador": player})
        it["linhas"].append(translate(r["tipo"], r["descricao"] or "", r["time_nome"], player))
    return list(items.values())


def overview(conn: sqlite3.Connection, day: str) -> dict[str, Any]:
    """Tudo o que a página inicial mostra sobre a liga para a data."""
    rodada = last_round_date(conn, day)
    season = conn.execute("SELECT MAX(season) FROM games WHERE date <= ?", (day,)).fetchone()[0]
    return {"data": day, "rodada": rodada,
            "resultados": results(conn, rodada) if rodada else [],
            "destaques": top_performances(conn, rodada) if rodada else [],
            "classificacao": standings(conn, season, day) if season else {"East": [], "West": []},
            "lideres": leaders(conn, season) if season else {"min_jogos": 0, "categorias": {}},
            "noticias": news(conn), "transacoes": transactions(conn)}


def _nome(r: Any) -> str:
    return f"{r['first_name'] or ''} {r['last_name'] or ''}".strip()
