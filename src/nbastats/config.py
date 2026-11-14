"""Configuração por variáveis de ambiente (com suporte a um .env simples)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: str | Path = ".env") -> None:
    """Carrega pares CHAVE=valor do .env sem sobrescrever o ambiente."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


@dataclass(frozen=True)
class Settings:
    fonte: str
    api_key: str
    rpm: int
    db_path: str
    password: str


def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        fonte=os.getenv("NBASTATS_FONTE", "nba_api"),
        api_key=os.getenv("BALLDONTLIE_API_KEY", ""),
        rpm=int(os.getenv("BALLDONTLIE_RPM", "60")),
        db_path=os.getenv("NBASTATS_DB", "data/nba.db"),
        password=os.getenv("NBASTATS_PASSWORD", ""),
    )
