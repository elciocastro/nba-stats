"""Ingestão: lê de um DataSource e grava no banco com upsert.

Tudo aqui é idempotente: rodar de novo o mesmo período atualiza as
linhas existentes (placar final, estatística corrigida) sem duplicar.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from typing import Any

from ..sources.base import DataSource, InjurySource
from ..sources.injury_report import normalize_name

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


def _upsert(conn: sqlite3.Connection, table: str, rows: list[dict[str, Any]],
            keep: tuple[str, ...] = ()) -> int:
    """INSERT ... ON CONFLICT DO UPDATE. Colunas em ``keep`` não são apagadas
    por um valor vazio: a linha nova só as troca se trouxer algo."""
    if not rows:
        return 0
    cols = list(rows[0])
    updates = ", ".join(
        f"{c}=COALESCE(excluded.{c}, {table}.{c})" if c in keep else f"{c}=excluded.{c}"
        for c in cols if c != "id"
    )
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


# Perfil que pode chegar vazio numa fonte e cheio em outra (o LeagueGameLog
# não traz posição; o PlayerIndex traz). Vazio nunca apaga o que já existe.
_PLAYER_PROFILE = (
    "position", "height", "weight", "country", "college",
    "draft_year", "draft_round", "draft_number",
)


def _player_row(p: dict[str, Any], team_id: int | None) -> dict[str, Any]:
    keys = ("id", "first_name", "last_name", *_PLAYER_PROFILE)
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
        _upsert(conn, "players", list(players.values()), keep=_PLAYER_PROFILE)
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


def _load_players(conn: sqlite3.Connection, players: Iterable[dict[str, Any]]) -> int:
    rows = [_player_row(p, p.get("team_id")) for p in players if p.get("id")]
    return _upsert(conn, "players", rows, keep=(*_PLAYER_PROFILE, "team_id"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _logged(conn, kind: str, params: dict[str, Any], work) -> dict[str, int]:
    """Roda ``work()`` registrando início, fim e erro em sync_log."""
    cur = conn.execute(
        "INSERT INTO sync_log (started_at, kind, params) VALUES (?, ?, ?)",
        (_now(), kind, json.dumps(params)),
    )
    log_id = cur.lastrowid
    conn.commit()
    try:
        result = work()
        conn.execute(
            "UPDATE sync_log SET finished_at=?, games=?, stats=?, status='ok' WHERE id=?",
            (_now(), result.get("games", 0), result.get("stats", 0), log_id),
        )
        conn.commit()
        return result
    except Exception as exc:
        conn.rollback()
        conn.execute(
            "UPDATE sync_log SET finished_at=?, status='error', error=? WHERE id=?",
            (_now(), str(exc)[:500], log_id),
        )
        conn.commit()
        raise


def _run(conn, source: DataSource, kind: str, params: dict[str, Any]) -> dict[str, int]:
    def work() -> dict[str, int]:
        _upsert(conn, "teams", [_team_row(t) for t in source.teams()])
        players = _load_players(conn, source.players(**params))
        games = _load_games(conn, source.games(**params))
        stats = _load_stats(conn, source.stats(**params))
        return {"games": games, "stats": stats, "players": players}

    return _logged(conn, kind, params, work)


def sync_season(conn, source: DataSource, season: int) -> dict[str, int]:
    """Carga completa de uma temporada (2025 = temporada 2025-26)."""
    return _run(conn, source, "season", {"season": season})


def sync_range(conn, source: DataSource, start_date: str, end_date: str) -> dict[str, int]:
    """Carga incremental por intervalo de datas (AAAA-MM-DD)."""
    return _run(conn, source, "range", {"start_date": start_date, "end_date": end_date})


def sync_schedule(conn, source: DataSource, dates: list[str]) -> dict[str, int]:
    """Grava os jogos dos dias pedidos, inclusive os que ainda vão acontecer.

    O placar só é gravado quando vem preenchido: um jogo já finalizado na base
    não perde o placar se o calendário vier sem ele.
    """
    def work() -> dict[str, int]:
        _upsert(conn, "teams", [_team_row(t) for t in source.teams()])
        rows = [_game_row(g) for day in dates for g in source.schedule(date=day)]
        n = _upsert(conn, "games", rows, keep=("home_team_score", "visitor_team_score"))
        return {"games": n, "stats": 0}

    return _logged(conn, "schedule", {"dates": dates}, work)


def _name_index(conn) -> tuple[dict[str, int], dict[str, int]]:
    """Chaves normalizadas -> id. Jogador: 'sobrenome,nome'; time: nome completo."""
    players = {normalize_name(f"{r['last_name']}{r['first_name']}"): r["id"]
               for r in conn.execute("SELECT id, first_name, last_name FROM players")}
    teams = {normalize_name(r["full_name"]): r["id"]
             for r in conn.execute("SELECT id, full_name FROM teams") if r["full_name"]}
    return players, teams


def sync_injuries(conn, source: InjurySource) -> dict[str, int]:
    """Grava o injury report mais recente. Rodar de novo o mesmo relatório não duplica."""
    def work() -> dict[str, int]:
        report = source.latest()
        if not report or not report.get("published_at"):
            return {"games": 0, "stats": 0, "injuries": 0, "unmatched": 0}
        report_id = int(report["published_at"].replace("-", "").replace("T", "").replace(":", ""))
        _upsert(conn, "injury_reports", [{
            "id": report_id, "published_at": report["published_at"],
            "url": report.get("url"), "fetched_at": _now(),
        }])
        players, teams = _name_index(conn)
        rows = []
        for i, r in enumerate(report["rows"]):
            rows.append({
                "id": report_id * 1000 + i,
                "report_id": report_id,
                "game_date": r.get("game_date"),
                "matchup": r.get("matchup"),
                "team_id": teams.get(normalize_name(r.get("team"))),
                "player_id": players.get(normalize_name(r.get("player_name"))),
                "player_name": r.get("player_name"),
                "status": r.get("status"),
                "reason": r.get("reason"),
            })
        n = _upsert(conn, "injuries", rows)
        unmatched = sum(1 for r in rows if r["player_id"] is None)
        return {"games": 0, "stats": n, "injuries": n, "unmatched": unmatched,
                "report": report["published_at"]}

    return _logged(conn, "injury", {}, work)


def last_refresh(conn) -> str | None:
    """Quando terminou a última atualização completa bem-sucedida (UTC, ISO)."""
    row = conn.execute(
        "SELECT finished_at FROM sync_log WHERE kind = 'refresh' AND status = 'ok'"
        " ORDER BY id DESC LIMIT 1").fetchone()
    return row[0] if row else None


def refresh(conn, source: DataSource, injury_source: InjurySource | None,
            min_interval_min: float = 15, force: bool = False,
            today: date | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Atualização do dia: estatísticas dos últimos 2 dias, agenda de hoje e
    amanhã e o injury report. Se a última foi há menos de ``min_interval_min``
    minutos, não refaz (a menos que ``force``) e diz quando foi.
    """
    now = now or datetime.now(timezone.utc)
    last = last_refresh(conn)
    if last and not force:
        age = (now - datetime.fromisoformat(last)).total_seconds() / 60
        if age < min_interval_min:
            return {"pulado": True, "ultima": last, "minutos": round(age)}

    today = today or date.today()

    def work() -> dict[str, Any]:
        stats = sync_range(conn, source, (today - timedelta(days=2)).isoformat(), today.isoformat())
        agenda = sync_schedule(conn, source, [today.isoformat(), (today + timedelta(days=1)).isoformat()])
        inj = sync_injuries(conn, injury_source) if injury_source else {"injuries": 0}
        # zonas de arremesso: fotografia da temporada, basta uma vez a cada 12 h
        season = today.year if today.month >= 10 else today.year - 1
        recent_zones = conn.execute(
            "SELECT 1 FROM sync_log WHERE kind = 'zones' AND status = 'ok' AND finished_at >= ?",
            ((now - timedelta(hours=12)).isoformat(timespec="seconds"),)).fetchone()
        if not recent_zones:
            sync_shot_zones(conn, source, season)
        return {"games": stats["games"] + agenda["games"], "stats": stats["stats"],
                "lesoes": inj.get("injuries", 0), "relatorio": inj.get("report")}

    result = _logged(conn, "refresh", {"today": today.isoformat()}, work)
    return {"pulado": False, "ultima": last_refresh(conn), **result}


def sync_shot_zones(conn, source: DataSource, season: int, today: date | None = None) -> dict[str, int]:
    """Fotografia das zonas de arremesso da temporada (substitui a anterior) e
    uma cópia por dia em ``shot_zones_daily``."""
    def work() -> dict[str, int]:
        stamp = _now()
        rows = [{"id": f"{season}:{z['kind']}:{z['entity_id']}:{z['zone']}", "season": season,
                 "kind": z["kind"], "entity_id": z["entity_id"], "zone": z["zone"],
                 "fgm": z["fgm"], "fga": z["fga"], "updated_at": stamp}
                for z in source.shot_zones(season=season)]
        n = _upsert(conn, "shot_zones", rows)
        # foto do dia (a tabela acima só guarda a mais recente)
        day = (today or date.today()).isoformat()
        _upsert(conn, "shot_zones_daily", [{"id": f"{day}:{r['id']}", "date": day, "season": season, "kind": r["kind"],
                                            "entity_id": r["entity_id"], "zone": r["zone"], "fgm": r["fgm"],
                                            "fga": r["fga"]} for r in rows])
        return {"games": 0, "stats": n}

    return _logged(conn, "zones", {"season": season}, work)
