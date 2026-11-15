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
    ("favorites", "user_id", "INTEGER"),  # dono (NULL = lista compartilhada, sem login)
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


# Tabelas que vêm das fontes públicas (ou são calculadas a partir delas) e
# podem ser espelhadas de outra máquina. As demais (usuários, sessões,
# apostas, linhas digitadas, favoritos, filtros, alertas enviados) são do uso
# do site e nunca são tocadas pela importação.
DATA_TABLES = ("teams", "players", "games", "player_game_stats", "injury_reports", "injuries",
               "shot_zones_daily", "news", "transactions", "predictions", "calibration", "sync_log")
SNAPSHOT_TABLES = ("shot_zones",)  # fotografia: a nova substitui a anterior inteira


def import_data(conn: sqlite3.Connection, source_path: str | Path) -> dict[str, int]:
    """Traz as estatísticas de outro banco (ex.: o do computador para a VPS).

    Upsert por chave primária, numa transação só: rodar de novo com o mesmo
    arquivo não muda nada, e as tabelas de uso do site ficam como estão.
    """
    init_db(conn)
    conn.execute("ATTACH DATABASE ? AS src", (str(source_path),))
    try:
        have = {r[0] for r in conn.execute("SELECT name FROM src.sqlite_master WHERE type = 'table'")}
        out: dict[str, int] = {}
        conn.execute("BEGIN")
        for table in DATA_TABLES + SNAPSHOT_TABLES:
            if table not in have:
                continue
            mine = [r[1] for r in conn.execute(f"PRAGMA main.table_info({table})")]
            theirs = {r[1] for r in conn.execute(f"PRAGMA src.table_info({table})")}
            cols = ", ".join(c for c in mine if c in theirs)
            if table in SNAPSHOT_TABLES:
                conn.execute(f"DELETE FROM main.{table}")
            cur = conn.execute(f"INSERT OR REPLACE INTO main.{table} ({cols}) SELECT {cols} FROM src.{table}")
            out[table] = cur.rowcount
        conn.commit()
        return out
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("DETACH DATABASE src")
