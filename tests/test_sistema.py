import os
from datetime import datetime, timezone

from nbastats.metrics import sistema

NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)


def _log(conn, kind, start, status, error=None):
    conn.execute("INSERT INTO sync_log (started_at, finished_at, kind, status, error) VALUES (?, ?, ?, ?, ?)",
                 (start, start, kind, status, error))


def test_sem_carga_avisa(conn):
    assert sistema.status_carga(conn, NOW)["alerta"].startswith("Nenhuma carga")


def test_carga_recente_sem_aviso_e_antiga_com_aviso(conn):
    _log(conn, "refresh", "2026-11-15T02:00:00+00:00", "ok")
    st = sistema.status_carga(conn, NOW)
    assert st["alerta"] is None and st["horas"] == 10.0
    assert "há 46 h" in sistema.status_carga(conn, datetime(2026, 11, 17, tzinfo=timezone.utc))["alerta"]


def test_falha_depois_da_ultima_carga_boa_avisa(conn):
    _log(conn, "refresh", "2026-11-15T02:00:00+00:00", "ok")
    _log(conn, "range", "2026-11-15T03:00:00+00:00", "error", "HTTP 403\ntraceback...")
    st = sistema.status_carga(conn, NOW)
    assert "falhou: HTTP 403" in st["alerta"] and len(st["falhas"]) == 1
    _log(conn, "refresh", "2026-11-15T04:00:00+00:00", "ok")  # voltou a funcionar
    assert sistema.status_carga(conn, NOW)["alerta"] is None


def test_backup_copia_e_mantem_os_mais_novos(conn, tmp_path):
    conn.execute("INSERT INTO teams (id, abbreviation) VALUES (1, 'AAA')")
    conn.commit()
    for day in range(1, 5):
        sistema.backup(conn, tmp_path, manter=2, now=datetime(2026, 11, day, tzinfo=timezone.utc))
    assert sorted(p.name for p in tmp_path.glob("nba-*.db")) == ["nba-20261103.db", "nba-20261104.db"]
    import sqlite3
    copy = sqlite3.connect(tmp_path / "nba-20261104.db")
    assert copy.execute("SELECT abbreviation FROM teams").fetchone()[0] == "AAA"
    st = sistema.status_backup(tmp_path)
    assert st["quantidade"] == 2 and st["ultimo"] == "nba-20261104.db"
    assert sistema.status_backup(tmp_path / "nada")["alerta"]
    assert not list(tmp_path.glob("*.tmp")) and os.path.exists(tmp_path / "nba-20261104.db")
