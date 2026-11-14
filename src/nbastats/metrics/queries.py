"""Consultas sobre a base. Sem lógica de tela aqui: só dados."""

from __future__ import annotations

import sqlite3
from typing import Any

# Estatísticas com média na temporada e na janela recente
STATS = ("minutes", "pts", "reb", "ast", "stl", "blk", "fg3m", "turnover")


def _rows(cur: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(r) for r in cur.fetchall()]


def seasons(conn: sqlite3.Connection) -> list[int]:
    cur = conn.execute("SELECT DISTINCT season FROM games ORDER BY season DESC")
    return [r[0] for r in cur.fetchall()]


def player_trends(
    conn: sqlite3.Connection, season: int, last_n: int = 10, min_games: int = 1
) -> list[dict[str, Any]]:
    """Uma linha por jogador: média da temporada (pts) e dos últimos N jogos (pts_n).

    Conta só temporada regular e jogos em que o jogador entrou em quadra.
    """
    season_avgs = ", ".join(f"ROUND(AVG(b.{s}), 2) AS {s}" for s in STATS)
    recent_avgs = ", ".join(
        f"ROUND(AVG(CASE WHEN b.rn <= :n THEN b.{s} END), 2) AS {s}_n" for s in STATS
    )
    sql = f"""
        WITH b AS (
            SELECT s.*, ROW_NUMBER() OVER (
                       PARTITION BY s.player_id ORDER BY g.date DESC, g.id DESC
                   ) AS rn
            FROM player_game_stats s
            JOIN games g ON g.id = s.game_id
            WHERE g.season = :season AND g.postseason = 0 AND s.minutes > 0
        )
        SELECT p.id AS player_id,
               p.first_name || ' ' || p.last_name AS jogador,
               t.abbreviation AS time,
               p.position AS posicao,
               p.draft_year,
               COUNT(*) AS jogos,
               {season_avgs},
               {recent_avgs}
        FROM b
        JOIN players p ON p.id = b.player_id
        LEFT JOIN teams t ON t.id = p.team_id
        GROUP BY p.id
        HAVING COUNT(*) >= :min_games
        ORDER BY pts DESC
    """
    return _rows(conn.execute(sql, {"season": season, "n": last_n, "min_games": min_games}))


def player_gamelog(conn: sqlite3.Connection, player_id: int, season: int) -> list[dict[str, Any]]:
    sql = """
        SELECT g.date AS data,
               CASE WHEN s.team_id = g.home_team_id THEN 'vs ' || v.abbreviation
                    ELSE '@ ' || h.abbreviation END AS adversario,
               s.minutes AS min, s.pts, s.reb, s.ast, s.stl, s.blk, s.fg3m, s.turnover
        FROM player_game_stats s
        JOIN games g ON g.id = s.game_id
        LEFT JOIN teams h ON h.id = g.home_team_id
        LEFT JOIN teams v ON v.id = g.visitor_team_id
        WHERE s.player_id = ? AND g.season = ? AND s.minutes > 0
        ORDER BY g.date
    """
    return _rows(conn.execute(sql, (player_id, season)))


def boxscore(
    conn: sqlite3.Connection, team_a: str, team_b: str, date: str | None = None
) -> dict[str, Any] | None:
    """Jogo entre dois times (siglas, ex.: GSW e CHI). Sem data, pega o mais recente."""
    sql = """
        SELECT g.*, h.abbreviation AS home, v.abbreviation AS visitor
        FROM games g
        JOIN teams h ON h.id = g.home_team_id
        JOIN teams v ON v.id = g.visitor_team_id
        WHERE ((h.abbreviation = :a AND v.abbreviation = :b)
            OR (h.abbreviation = :b AND v.abbreviation = :a))
          AND (:date IS NULL OR g.date = :date)
        ORDER BY g.date DESC
        LIMIT 1
    """
    params = {"a": team_a.upper(), "b": team_b.upper(), "date": date}
    game = conn.execute(sql, params).fetchone()
    if game is None:
        return None
    players = _rows(conn.execute(
        """
        SELECT t.abbreviation AS time,
               p.first_name || ' ' || p.last_name AS jogador,
               ROUND(s.minutes, 1) AS min, s.pts, s.reb, s.ast, s.stl, s.blk,
               s.fg3m, s.turnover, s.plus_minus
        FROM player_game_stats s
        JOIN players p ON p.id = s.player_id
        LEFT JOIN teams t ON t.id = s.team_id
        WHERE s.game_id = ? AND s.minutes > 0
        ORDER BY t.abbreviation, s.pts DESC
        """,
        (game["id"],),
    ))
    return {"jogo": dict(game), "jogadores": players}
