"""Favoritos: jogadores, times e jogos marcados com estrela.

Com login, cada pessoa tem a sua lista (``user_id``); sem login, a lista é
uma só (``user_id`` nulo). No primeiro acesso, quem ainda não tem favoritos
começa com uma cópia da lista compartilhada. Gravar é upsert idempotente;
apagar não falha se não existir.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

KINDS = ("jogador", "time", "jogo")


def _id(kind: str, entity_id: int, user_id: int | None = None) -> str:
    if kind not in KINDS:
        raise ValueError(f"Tipo inválido: {kind}. Use {KINDS}.")
    return f"{kind}:{entity_id}" if user_id is None else f"u{user_id}:{kind}:{entity_id}"


def add_favorite(conn: sqlite3.Connection, kind: str, entity_id: int, label: str | None = None,
                 user_id: int | None = None) -> None:
    _seed(conn, user_id)
    conn.execute(
        "INSERT INTO favorites (id, kind, entity_id, label, created_at, user_id) VALUES (?, ?, ?, ?, ?, ?)"
        " ON CONFLICT(id) DO UPDATE SET label = COALESCE(excluded.label, favorites.label)",
        (_id(kind, entity_id, user_id), kind, entity_id, label,
         datetime.now(timezone.utc).isoformat(timespec="seconds"), user_id))
    conn.commit()


def remove_favorite(conn: sqlite3.Connection, kind: str, entity_id: int, user_id: int | None = None) -> None:
    _seed(conn, user_id)
    conn.execute("DELETE FROM favorites WHERE id = ?", (_id(kind, entity_id, user_id),))
    conn.commit()


def _seed(conn: sqlite3.Connection, user_id: int | None) -> None:
    """1º acesso de um usuário sem favoritos: copia a lista compartilhada."""
    if user_id is None or conn.execute("SELECT 1 FROM favorites WHERE user_id = ? LIMIT 1", (user_id,)).fetchone():
        return
    if conn.execute("SELECT 1 FROM user_seeds WHERE user_id = ?", (user_id,)).fetchone():
        return  # já copiou uma vez (e a pessoa apagou tudo depois): não recopia
    rows = conn.execute("SELECT kind, entity_id, label, created_at FROM favorites WHERE user_id IS NULL").fetchall()
    conn.executemany(
        "INSERT OR IGNORE INTO favorites (id, kind, entity_id, label, created_at, user_id) VALUES (?, ?, ?, ?, ?, ?)",
        [(_id(r["kind"], r["entity_id"], user_id), r["kind"], r["entity_id"], r["label"], r["created_at"], user_id)
         for r in rows])
    conn.execute("INSERT OR IGNORE INTO user_seeds (user_id) VALUES (?)", (user_id,))
    conn.commit()


def list_favorites(conn: sqlite3.Connection, user_id: int | None = None,
                   todos: bool = False) -> dict[str, list[dict[str, Any]]]:
    """Lista da pessoa (ou a compartilhada). ``todos``: união de todas as listas
    (alertas do Telegram, que vão para um chat só)."""
    out: dict[str, list[dict[str, Any]]] = {k: [] for k in KINDS}
    if todos:
        sql, args = ("SELECT kind, entity_id, MAX(label) AS label, MIN(created_at) AS created_at FROM favorites"
                     " GROUP BY kind, entity_id ORDER BY created_at"), ()
    else:
        _seed(conn, user_id)
        sql = ("SELECT kind, entity_id, label, created_at FROM favorites WHERE "
               + ("user_id IS NULL" if user_id is None else "user_id = ?") + " ORDER BY created_at")
        args = () if user_id is None else (user_id,)
    for r in conn.execute(sql, args):
        out[r["kind"]].append(dict(r))
    return out


def is_favorite(favs: dict[str, list[dict[str, Any]]], player: dict[str, Any]) -> bool:
    """Jogador favorito, ou do time favorito, ou no jogo favorito."""
    ids = {k: {f["entity_id"] for f in v} for k, v in favs.items()}
    return (player.get("player_id") in ids["jogador"] or player.get("time_id") in ids["time"]
            or player.get("game_id") in ids["jogo"])
