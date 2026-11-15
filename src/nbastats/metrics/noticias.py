"""Notícias de lesão a partir dos dados que o site já guarda.

- **mudanças**: o injury report mais recente do dia contra o anterior
  (entrou na lista, mudou de status, saiu da lista);
- **retornos**: quem não jogou a última partida do time e hoje não está
  como Out/Doubtful (volta provável), com os minutos que vinha jogando, para
  responder "com tantos minutos, o que ele faz";
- **linha do tempo**: os relatórios do dia, com o horário e quantos nomes.
"""

from __future__ import annotations

import sqlite3
from statistics import mean
from typing import Any

from .matchup import _player_rows, games_on

ORDER = {"Out": 0, "Doubtful": 1, "Questionable": 2, "Probable": 3, "Available": 4, None: 5}


def reports_for(conn: sqlite3.Connection, day: str) -> list[dict[str, Any]]:
    """Relatórios que cobrem o dia, do mais recente ao mais antigo."""
    sql = """
        SELECT r.id, r.published_at, COUNT(i.id) AS nomes
        FROM injury_reports r JOIN injuries i ON i.report_id = r.id AND i.game_date = ?
        GROUP BY r.id ORDER BY r.id DESC
    """
    return [dict(r) for r in conn.execute(sql, (day,))]


def _entries(conn: sqlite3.Connection, report_id: int, day: str) -> dict[str, dict[str, Any]]:
    sql = """
        SELECT i.player_id, COALESCE(TRIM(p.first_name || ' ' || p.last_name), i.player_name) AS player_name,
               i.status, i.reason, i.team_id, t.abbreviation AS time
        FROM injuries i LEFT JOIN teams t ON t.id = i.team_id LEFT JOIN players p ON p.id = i.player_id
        WHERE i.report_id = ? AND i.game_date = ?
    """
    return {str(r["player_id"] or r["player_name"]): dict(r) for r in conn.execute(sql, (report_id, day))}


def changes(conn: sqlite3.Connection, day: str) -> dict[str, Any]:
    """Mudanças entre os dois últimos injury reports do dia."""
    reps = reports_for(conn, day)
    if not reps:
        return {"atual": None, "anterior": None, "mudancas": []}
    new = _entries(conn, reps[0]["id"], day)
    old = _entries(conn, reps[1]["id"], day) if len(reps) > 1 else {}
    out = []
    for key in set(new) | set(old):
        a, b = old.get(key), new.get(key)
        if a and b and a["status"] == b["status"]:
            continue
        if not old:  # primeiro relatório do dia: tudo é novidade, sem "antes"
            tipo = "lista"
        elif a is None:
            tipo = "entrou"
        elif b is None:
            tipo = "saiu"
        else:
            tipo = "piorou" if ORDER.get(b["status"], 5) < ORDER.get(a["status"], 5) else "melhorou"
        ref = b or a
        out.append({"tipo": tipo, "player_id": ref["player_id"], "jogador": ref["player_name"],
                    "time": ref["time"], "antes": a["status"] if a else None,
                    "agora": b["status"] if b else None, "motivo": ref["reason"]})
    out.sort(key=lambda c: (ORDER.get(c["agora"], 5), c["time"] or "", c["jogador"] or ""))
    return {"atual": reps[0]["published_at"],
            "anterior": reps[1]["published_at"] if len(reps) > 1 else None, "mudancas": out}


def returns(conn: sqlite3.Connection, day: str, min_minutes: float = 15.0,
            n_recent: int = 5) -> list[dict[str, Any]]:
    """Quem ficou fora do último jogo do time e hoje pode voltar.

    Considera jogadores que vinham jogando ``min_minutes``+ nos últimos
    ``n_recent`` jogos que disputaram. Mostra o status no último relatório
    (sem status = não está na lista, ou seja, liberado).
    """
    games = games_on(conn, day)
    if not games:
        return []
    playing = {g["home_team_id"] for g in games} | {g["visitor_team_id"] for g in games}
    reps = reports_for(conn, day)
    status = {}
    if reps:
        for e in _entries(conn, reps[0]["id"], day).values():
            if e["player_id"]:
                status[e["player_id"]] = e
    abbr = {r["id"]: r["abbreviation"] for r in conn.execute("SELECT id, abbreviation FROM teams")}
    out = []
    for season in {g["season"] for g in games}:
        rows = _player_rows(conn, season, day)
        last_game: dict[int, int] = {}
        team_games: dict[int, list[int]] = {}
        for r in rows:
            last_game.setdefault(r["team_id"], r["game_id"])
            lst = team_games.setdefault(r["team_id"], [])
            if r["game_id"] not in lst:
                lst.append(r["game_id"])
        by_player: dict[int, list[dict[str, Any]]] = {}
        for r in rows:
            by_player.setdefault(r["player_id"], []).append(r)
        for pid, played in by_player.items():
            team = played[0]["team_id"]
            if team not in playing or played[0]["game_id"] == last_game.get(team):
                continue
            recent = played[:n_recent]
            mins = mean(g["minutes"] for g in recent)
            if mins < min_minutes:
                continue
            st = status.get(pid) or {}
            if st.get("status") in ("Out", "Doubtful"):
                continue
            missed = team_games[team].index(played[0]["game_id"]) if played[0]["game_id"] in team_games[team] else None
            out.append({
                "player_id": pid, "jogador": played[0]["jogador"], "time": abbr.get(team),
                "jogos_fora": missed, "ultimo_jogo": played[0]["date"],
                "status": st.get("status") or "fora da lista", "motivo": st.get("reason"),
                "minutos_antes": round(mins, 1),
                "pts": round(mean(g["pts"] for g in recent), 1),
                "reb": round(mean(g["reb"] for g in recent), 1),
                "ast": round(mean(g["ast"] for g in recent), 1),
                "pra": round(mean(g["pra"] for g in recent), 1),
                "pra_por_min": round(sum(g["pra"] for g in recent) / max(sum(g["minutes"] for g in recent), 1), 3),
            })
    out.sort(key=lambda r: r["minutos_antes"], reverse=True)
    return out
