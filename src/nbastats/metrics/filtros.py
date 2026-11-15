"""Filtros salvos da página Props, por usuário (sem login: um conjunto só).

Salvar com o mesmo nome substitui (upsert). Só guarda as chaves conhecidas,
para o banco não virar depósito de qualquer coisa vinda da tela.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

CHAVES = {"aba": str, "mercado": str, "chance_min": (int, float), "lado": str, "so_casa": bool,
          "so_fav": bool, "sem_duvida": bool, "diff_min": (int, float)}
MAX_POR_USUARIO = 30


def _clean(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if k in CHAVES and isinstance(v, CHAVES[k]) and v is not None}


def save_filter(conn: sqlite3.Connection, nome: str, params: dict[str, Any], user_id: int | None = None) -> int:
    nome = (nome or "").strip()[:40]
    if not nome:
        raise ValueError("Dê um nome ao filtro.")
    n = conn.execute("SELECT COUNT(*) FROM saved_filters WHERE COALESCE(user_id, 0) = ?", (user_id or 0,)).fetchone()[0]
    exists = conn.execute("SELECT id FROM saved_filters WHERE COALESCE(user_id, 0) = ? AND nome = ?",
                          (user_id or 0, nome)).fetchone()
    if exists is None and n >= MAX_POR_USUARIO:
        raise ValueError(f"Limite de {MAX_POR_USUARIO} filtros.")
    body = json.dumps(_clean(params), ensure_ascii=False)
    if exists:
        conn.execute("UPDATE saved_filters SET params = ? WHERE id = ?", (body, exists[0]))
        conn.commit()
        return int(exists[0])
    cur = conn.execute("INSERT INTO saved_filters (user_id, nome, params, criado_em) VALUES (?, ?, ?, ?)",
                       (user_id, nome, body, datetime.now(timezone.utc).isoformat(timespec="seconds")))
    conn.commit()
    return int(cur.lastrowid)


def list_filters(conn: sqlite3.Connection, user_id: int | None = None) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT id, nome, params FROM saved_filters WHERE COALESCE(user_id, 0) = ? ORDER BY nome",
                        (user_id or 0,))
    return [{"id": r["id"], "nome": r["nome"], "params": json.loads(r["params"])} for r in rows]


def delete_filter(conn: sqlite3.Connection, filter_id: int, user_id: int | None = None) -> None:
    conn.execute("DELETE FROM saved_filters WHERE id = ? AND COALESCE(user_id, 0) = ?", (filter_id, user_id or 0))
    conn.commit()
