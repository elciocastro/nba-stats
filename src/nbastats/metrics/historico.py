"""Histórico do jogador em várias temporadas: H2H, recortes e minutos.

O relatório de matchups usa só a temporada atual. Aqui o histórico junta as
temporadas da base para responder:

- **H2H**: o jogador contra o adversário de hoje, em todas as temporadas;
- **janelas** no estilo das planilhas de props: temporada atual, H2H, L5,
  L10, L20 e temporada anterior, com a taxa de over contra a linha;
- **recortes**: casa/fora, vitória/derrota, sem descanso (back-to-back);
- **minutos**: "e se jogar X minutos" escala a projeção pela taxa por minuto.

H2H tem poucos jogos (1 a 4 por temporada): é contexto, não critério (0008).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import date
from statistics import mean
from typing import Any

from .matchup import _COLS, MATCHUP_STATS, _derive

SPLITS = {
    "casa": "Casa", "fora": "Fora", "vitoria": "Vitória", "derrota": "Derrota",
    "b2b": "Sem descanso",
}


def season_label(season: int) -> str:
    """2026 -> '26/27'."""
    return f"{season % 100:02d}/{(season + 1) % 100:02d}"


def player_logs(conn: sqlite3.Connection, player_ids: Iterable[int], before: str,
                seasons: Iterable[int] | None = None, playoffs: bool = False) -> dict[int, list[dict[str, Any]]]:
    """Jogos de cada jogador (mais recente primeiro) antes da data, em todas as
    temporadas da base (ou só nas pedidas), sem playoffs (``playoffs=True``:
    só os jogos de playoffs).

    Cada jogo traz adversário, mando, resultado (V/D), margem, dias de
    descanso e todos os mercados (MATCHUP_STATS).
    """
    ids = sorted(set(player_ids))
    if not ids:
        return {}
    cols = ", ".join(f"COALESCE(s.{c}, 0) AS {c}" for c in _COLS)
    marks = ",".join("?" * len(ids))
    params: list[Any] = [*ids, before]
    season_sql = ""
    if seasons is not None:
        ss = sorted(set(seasons))
        season_sql = f" AND g.season IN ({','.join('?' * len(ss))})"
        params += ss
    sql = f"""
        SELECT s.player_id, s.game_id, g.date, g.season, s.team_id,
               CASE WHEN s.team_id = g.home_team_id THEN g.visitor_team_id
                    ELSE g.home_team_id END AS opp_id,
               CASE WHEN s.team_id = g.home_team_id THEN 1 ELSE 0 END AS em_casa,
               CASE WHEN s.team_id = g.home_team_id THEN g.home_team_score - g.visitor_team_score
                    ELSE g.visitor_team_score - g.home_team_score END AS margem,
               {cols}
        FROM player_game_stats s
        JOIN games g ON g.id = s.game_id
        WHERE s.player_id IN ({marks}) AND g.date < ? AND s.minutes > 0
              AND g.postseason = {1 if playoffs else 0}{season_sql}
        ORDER BY g.date DESC, g.id DESC
    """
    out: dict[int, list[dict[str, Any]]] = {pid: [] for pid in ids}
    for r in conn.execute(sql, params):
        g = _derive(dict(r))
        g["em_casa"] = bool(g["em_casa"])
        g["data"] = g["date"]
        g["resultado"] = None if g["margem"] is None else ("V" if g["margem"] > 0 else "D")
        g["usadas"] = round(g["fga"] + 0.44 * g["fta"] + g["turnover"], 1)
        out[g["player_id"]].append(g)
    for games in out.values():
        for cur, prev in zip(games, games[1:]):
            gap = (date.fromisoformat(cur["date"]) - date.fromisoformat(prev["date"])).days - 1
            # mais de 10 dias: pausa (lesão, intervalo de temporada), não "descanso"
            cur["descanso"] = gap if gap <= 10 else None
        if games:
            games[-1]["descanso"] = None
    return out


def split(log: list[dict[str, Any]], name: str | None) -> list[dict[str, Any]]:
    """Recorte do histórico: casa, fora, vitoria, derrota ou b2b (0 dias de descanso)."""
    if not name:
        return log
    test = {
        "casa": lambda g: g["em_casa"], "fora": lambda g: not g["em_casa"],
        "vitoria": lambda g: g["resultado"] == "V", "derrota": lambda g: g["resultado"] == "D",
        "b2b": lambda g: g.get("descanso") == 0,
    }[name]
    return [g for g in log if test(g)]


def _rate(games: list[dict[str, Any]], stat: str, line: float | None) -> dict[str, Any]:
    vals = [g[stat] for g in games]
    over = sum(1 for v in vals if line is not None and v > line)
    return {
        "jogos": len(vals),
        "over": over,
        "pct": round(100 * over / len(vals)) if vals and line is not None else None,
        "media": round(mean(vals), 1) if vals else None,
    }


def windows(log: list[dict[str, Any]], stat: str, line: float | None, opp_id: int | None,
            season: int) -> dict[str, dict[str, Any]]:
    """Taxa de over e média por janela, na ordem das planilhas de props:
    temporada atual, H2H (todas as temporadas), L5, L10, L20, temporada anterior."""
    cur = [g for g in log if g["season"] == season]
    prev = [g for g in log if g["season"] == season - 1]
    h2h = [g for g in log if opp_id is not None and g["opp_id"] == opp_id]
    return {
        season_label(season): _rate(cur, stat, line),
        "H2H": _rate(h2h, stat, line),
        "L5": _rate(cur[:5], stat, line),
        "L10": _rate(cur[:10], stat, line),
        "L20": _rate(cur[:20], stat, line),
        season_label(season - 1): _rate(prev, stat, line),
    }


def h2h_games(log: list[dict[str, Any]], opp_id: int | None, limit: int = 10) -> list[dict[str, Any]]:
    """Os últimos jogos contra o adversário, de qualquer temporada."""
    return [g for g in log if opp_id is not None and g["opp_id"] == opp_id][:limit]


def scale_to_minutes(proj: dict[str, Any] | None, minutes: float) -> float | None:
    """Projeção se o jogador atuar ``minutes`` minutos: mesma taxa por minuto,
    mesmos ajustes (defesa, ritmo, desfalques). Aproximação linear: não mexe na
    taxa quando o jogador ganha uso com companheiros fora."""
    if not proj or not proj.get("minutos"):
        return None
    return round(proj["valor"] * minutes / proj["minutos"], 2)


def band(value: float | None, ref: float | None, near: float = 0.8) -> str | None:
    """Faixa de um valor contra uma referência (linha ou média do jogador):
    'acima' (atingiu), 'perto' (até ``near`` da referência) ou 'abaixo'."""
    if value is None or not ref:
        return None
    if value >= ref:
        return "acima"
    return "perto" if value >= near * ref else "abaixo"


def season_averages(log: list[dict[str, Any]], season: int,
                    stats: Iterable[str]) -> dict[str, float]:
    """Média do jogador na temporada (ou em todo o histórico, se ainda não jogou)."""
    games = [g for g in log if g["season"] == season] or log
    if not games:
        return {}
    return {s: round(mean(g[s] for g in games), 1) for s in stats}


def minutes_profile(log: list[dict[str, Any]], season: int, n: int = 10) -> dict[str, Any]:
    """Minutos e posses usadas: L5, L10, temporada e o mínimo/máximo recente."""
    cur = [g for g in log if g["season"] == season]
    if not cur:
        return {}
    recent = cur[:n]
    return {
        "l5": round(mean(g["minutes"] for g in cur[:5]), 1),
        "l10": round(mean(g["minutes"] for g in recent), 1),
        "temporada": round(mean(g["minutes"] for g in cur), 1),
        "min": round(min(g["minutes"] for g in recent), 1),
        "max": round(max(g["minutes"] for g in recent), 1),
        "usadas_l10": round(mean(g["usadas"] for g in recent), 1),
        "usadas_temp": round(mean(g["usadas"] for g in cur), 1),
    }


def attach_history(report: list[dict[str, Any]], conn: sqlite3.Connection | None, day: str,
                   stat: str, logs: dict[int, list[dict[str, Any]]] | None = None) -> list[dict[str, Any]]:
    """Acrescenta a cada jogador (com linha já calculada) o histórico de todas as
    temporadas e as janelas contra a linha (``p['janelas']``). ``logs`` evita
    reler a base quando já se tem o resultado de player_logs."""
    if logs is None:
        ids = [p["player_id"] for g in report for p in g["jogadores"]]
        logs = player_logs(conn, ids, day)
    for g in report:
        season = g["jogo"]["season"]
        for p in g["jogadores"]:
            log = logs.get(p["player_id"], [])
            p["historico_total"] = log
            p["janelas"] = windows(log, stat, p.get("linha"), p.get("adversario_id"), season)
            p["temporada_atual"] = season
    return report


__all__ = [
    "SPLITS", "MATCHUP_STATS", "attach_history", "h2h_games", "minutes_profile", "player_logs",
    "scale_to_minutes", "season_label", "split", "windows",
]
