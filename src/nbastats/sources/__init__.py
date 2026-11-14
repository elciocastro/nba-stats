from .balldontlie import BallDontLie
from .base import DataSource
from .nba_api_source import NbaApiSource

FONTES = ("nba_api", "balldontlie")


def build_source(name: str, settings) -> DataSource:
    """Cria a fonte de dados pelo nome (NBASTATS_FONTE ou --fonte)."""
    if name == "nba_api":
        return NbaApiSource()
    if name == "balldontlie":
        return BallDontLie(settings.api_key, rpm=settings.rpm)
    raise ValueError(f"Fonte desconhecida: {name}. Use uma de {FONTES}")


__all__ = ["DataSource", "BallDontLie", "NbaApiSource", "FONTES", "build_source"]
