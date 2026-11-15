"""Saúde da carga de dados e dos backups, para o aviso no topo do site e o
painel de administração."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_HORAS = 36  # sem carga boa há mais que isso: avisa
CARGAS = ("refresh", "range", "daily", "season")


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def status_carga(conn: sqlite3.Connection, now: datetime | None = None,
                 max_horas: float = MAX_HORAS) -> dict[str, Any]:
    """Última carga boa, falhas depois dela e o aviso (ou None)."""
    now = now or datetime.now(timezone.utc)
    marks = ",".join("?" * len(CARGAS))
    ok = conn.execute(f"SELECT MAX(finished_at) FROM sync_log WHERE status = 'ok' AND kind IN ({marks})",
                      CARGAS).fetchone()[0]
    falhas = [dict(r) for r in conn.execute(
        "SELECT kind, started_at, error FROM sync_log WHERE status = 'error' AND started_at > ? ORDER BY id DESC LIMIT 5",
        (ok or "",))]
    ultima = _dt(ok)
    horas = None if ultima is None else round((now - ultima).total_seconds() / 3600, 1)
    alerta = None
    if ultima is None:
        alerta = "Nenhuma carga de dados concluída ainda."
    elif horas is not None and horas > max_horas:
        alerta = f"Dados desatualizados: a última carga boa foi há {horas:.0f} h."
    if falhas:
        erro = (falhas[0]["error"] or "").splitlines()[0][:160]
        alerta = (alerta + " " if alerta else "") + f"Última tentativa ({falhas[0]['kind']}) falhou: {erro}"
    return {"ultima_ok": ok, "horas": horas, "falhas": falhas, "alerta": alerta}


def status_backup(pasta: str | Path, now: datetime | None = None) -> dict[str, Any]:
    """Backups em ``pasta`` (arquivos nba-*.db): quantos, o último e o tamanho."""
    now = now or datetime.now(timezone.utc)
    files = sorted(Path(pasta).glob("nba-*.db")) if Path(pasta).exists() else []
    if not files:
        return {"quantidade": 0, "ultimo": None, "horas": None, "tamanho_mb": None,
                "alerta": "Nenhum backup do banco ainda."}
    last = files[-1]
    when = datetime.fromtimestamp(last.stat().st_mtime, timezone.utc)
    horas = round((now - when).total_seconds() / 3600, 1)
    return {"quantidade": len(files), "ultimo": last.name, "horas": horas,
            "tamanho_mb": round(last.stat().st_size / 1e6, 1),
            "alerta": f"Último backup há {horas:.0f} h." if horas > 48 else None}


def backup(conn: sqlite3.Connection, pasta: str | Path, manter: int = 14,
           now: datetime | None = None) -> Path:
    """Cópia consistente do banco (API de backup do SQLite, funciona com o
    site aberto) em ``pasta/nba-AAAAMMDD.db``; mantém as ``manter`` mais novas."""
    now = now or datetime.now(timezone.utc)
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    dest = pasta / f"nba-{now:%Y%m%d}.db"
    tmp = dest.with_suffix(".tmp")
    out = sqlite3.connect(tmp)
    try:
        conn.backup(out)
    finally:
        out.close()
    tmp.replace(dest)
    for old in sorted(pasta.glob("nba-*.db"))[:-manter] if manter > 0 else []:
        old.unlink()
    return dest

