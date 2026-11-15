"""Conexão e schema do banco (SQLite)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA = Path(__file__).with_name("schema.sql")


def connect(path: str = "data/nba.db", threads: bool = False) -> sqlite3.Connection:
    """``threads=True`` permite usar a conexão em outra thread (API)."""
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=not threads)
    conn.row_factory = sqlite3.Row
    return conn


# Colunas novas em tabelas que já existiam. O schema.sql só cria tabelas
# (CREATE IF NOT EXISTS); bancos antigos ganham as colunas aqui, uma vez.
COLUMNS = [
    ("bets", "tags", "TEXT"),          # etiquetas/motivos da aposta, separadas por vírgula
    ("bets", "user_id", "INTEGER"),    # quem registrou (NULL = antes dos usuários)
]


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Adiciona as colunas que faltam. Idempotente; devolve o que fez."""
    done = []
    for table, col, kind in COLUMNS:
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if have and col not in have:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {kind}")
            done.append(f"{table}.{col}")
    conn.commit()
    return done


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
    migrate(conn)
    conn.commit()
