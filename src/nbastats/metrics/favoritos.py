"""Favoritos: jogadores, times e jogos marcados com estrela.

O site tem senha única, então a lista é uma só (compartilhada). Gravar é
upsert idempotente; apagar não falha se não existir.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

KINDS = ("jogador", "time", "jogo")


def _id(kind: str, entity_id: int) -> str:
    if kind not in KINDS:
        raise ValueError(f"Tipo inválido: {kind}. Use {KINDS}.")
    return f"{kind}:{entity_id}"


def add_favorite(conn: sqlite3.Connection, kind: str, entity_id: int, label: str | None = None) -> None:
    conn.execute(
        "INSERT INTO favorites (id, kind, entity_id, label, created_at) VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(id) DO UPDATE SET label = COALESCE(excluded.label, favorites.label)",
        (_id(kind, entity_id), kind, entity_id, label,
         datetime.now(timezone.utc).isoformat(timespec="seconds")))
    conn.commit()


def remove_favorite(conn: sqlite3.Connection, kind: str, entity_id: int) -> None:
    conn.execute("DELETE FROM favorites WHERE id = ?", (_id(kind, entity_id),))
    conn.commit()


def list_favorites(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {k: [] for k in KINDS}
    for r in conn.execute("SELECT kind, entity_id, label, created_at FROM favorites ORDER BY created_at"):
        out[r["kind"]].append(dict(r))
    return out


def is_favorite(favs: dict[str, list[dict[str, Any]]], player: dict[str, Any]) -> bool:
    """Jogador favorito, ou do time favorito, ou no jogo favorito."""
    ids = {k: {f["entity_id"] for f in v} for k, v in favs.items()}
    return (player.get("player_id") in ids["jogador"] or player.get("time_id") in ids["time"]
            or player.get("game_id") in ids["jogo"])
