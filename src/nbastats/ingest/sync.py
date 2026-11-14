"""Ingestão: lê de um DataSource e grava no banco com upsert.

Tudo aqui é idempotente: rodar de novo o mesmo período atualiza as
linhas existentes (placar final, estatística corrigida) sem duplicar.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable

from ..sources.base import DataSource

BATCH = 500


def parse_minutes(value: Any) -> float:
    """'34:30' -> 34.5, '34' -> 34.0, None/'' -> 0.0."""
    if value in (None, ""):
        return 0.0
    text = str(value)
    try:
        if ":" in text:
            mins, secs = text.split(":", 1)
            return int(mins) + int(secs) / 60
        return float(text)
    except ValueError:
        return 0.0


def _upsert(conn: sqlite3.Connection, table: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    cols = list(rows[0])
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "id")
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) "
        f"VALUES ({', '.join(':' + c for c in cols)}) "
        f"ON CONFLICT(id) DO UPDATE SET {updates}"
    )
    conn.executemany(sql, rows)
    return len(rows)


def _team_row(t: dict[str, Any]) -> dict[str, Any]:
    keys = ("id", "abbreviation", "city", "name", "full_name", "conference", "division")
    return {k: t.get(k) for k in keys}


def _player_row(p: dict[str, Any], team_id: int | None) -> dict[str, Any]:
    keys = (
        "id", "first_name", "last_name", "position", "height", "weight",
        "country", "college", "draft_year", "draft_round", "draft_number",
    )
    row = {k: p.get(k) for k in keys}
    row["team_id"] = p.get("team_id") or team_id
    return row


def _game_row(g: dict[str, Any]) -> dict[str, Any]:
    home = g.get("home_team") or {}
    visitor = g.get("visitor_team") or {}
    return {
        "id": g["id"],
        "date": str(g.get("date", ""))[:10],
        "season": g.get("season"),
        "postseason": int(bool(g.get("postseason"))),
        "status": g.get("status"),
        "home_team_id": home.get("id") or g.get("home_team_id"),
        "visitor_team_id": visitor.get("id") or g.get("visitor_team_id"),
        "home_team_score": g.get("home_team_score"),
        "visitor_team_score": g.get("visitor_team_score"),
    }


_STAT_KEYS = (
    "pts", "reb", "ast", "oreb", "dreb", "stl", "blk", "turnover", "pf",
    "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "plus_minus",
)


def _stat_row(s: dict[str, Any]) -> dict[str, Any]:
    row = {
        "id": s["id"],
        "game_id": s["game"]["id"],
        "player_id": s["player"]["id"],
        "team_id": (s.get("team") or {}).get("id"),
        "minutes": parse_minutes(s.get("min")),
    }
    row.update({k: s.get(k) for k in _STAT_KEYS})
    return row


def _load_games(conn: sqlite3.Connection, games: Iterable[dict[str, Any]]) -> int:
    total, batch = 0, []
    for g in games:
        batch.append(_game_row(g))
        if len(batch) >= BATCH:
            total += _upsert(conn, "games", batch)
            batch = []
    return total + _upsert(conn, "games", batch)


def _load_stats(conn: sqlite3.Connection, stats: Iterable[dict[str, Any]]) -> int:
    total = 0
    stat_rows: list[dict[str, Any]] = []
    players: dict[int, dict[str, Any]] = {}

    def flush() -> int:
        _upsert(conn, "players", list(players.values()))
        n = _upsert(conn, "player_game_stats", stat_rows)
        players.clear()
        stat_rows.clear()
        return n

    for s in stats:
        if not s.get("player") or not s.get("game"):
            continue  # linha sem jogador/jogo não serve para nada
        row = _stat_row(s)
        stat_rows.append(row)
        players[row["player_id"]] = _player_row(s["player"], row["team_id"])
        if len(stat_rows) >= BATCH:
            total += flush()
    return total + flush()


def _run(conn, source: DataSource, kind: str, params: dict[str, Any]) -> dict[str, int]:
    now = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")  # noqa: E731
    cur = conn.execute(
        "INSERT INTO sync_log (started_at, kind, params) VALUES (?, ?, ?)",
        (now(), kind, json.dumps(params)),
    )
    log_id = cur.lastrowid
    conn.commit()
    try:
        _upsert(conn, "teams", [_team_row(t) for t in source.teams()])
        games = _load_games(conn, source.games(**params))
        stats = _load_stats(conn, source.stats(**params))
        conn.execute(
            "UPDATE sync_log SET finished_at=?, games=?, stats=?, status='ok' WHERE id=?",
            (now(), games, stats, log_id),
        )
        conn.commit()
        return {"games": games, "stats": stats}
    except Exception as exc:
        conn.rollback()
        conn.execute(
            "UPDATE sync_log SET finished_at=?, status='error', error=? WHERE id=?",
            (now(), str(exc)[:500], log_id),
        )
        conn.commit()
        raise


def sync_season(conn, source: DataSource, season: int) -> dict[str, int]:
    """Carga completa de uma temporada (2025 = temporada 2025-26)."""
    return _run(conn, source, "season", {"season": season})


def sync_range(conn, source: DataSource, start_date: str, end_date: str) -> dict[str, int]:
    """Carga incremental por intervalo de datas (AAAA-MM-DD)."""
    return _run(conn, source, "range", {"start_date": start_date, "end_date": end_date})
