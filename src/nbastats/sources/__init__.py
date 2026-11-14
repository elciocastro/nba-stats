from .balldontlie import BallDontLie
from datetime import date

from .base import DataSource, InjurySource
from .injury_report import NbaInjuryReport
from .nba_api_source import NbaApiSource, season_of

FONTES = ("nba_api", "balldontlie")


def build_source(name: str, settings) -> DataSource:
    """Cria a fonte de dados pelo nome (NBASTATS_FONTE ou --fonte)."""
    if name == "nba_api":
        return NbaApiSource()
    if name == "balldontlie":
        return BallDontLie(settings.api_key, rpm=settings.rpm)
    raise ValueError(f"Fonte desconhecida: {name}. Use uma de {FONTES}")


def build_injury_source(day: date | None = None) -> InjurySource:
    """Injury report oficial da temporada do dia (padrão: hoje)."""
    return NbaInjuryReport(season_of((day or date.today()).isoformat()))


__all__ = [
    "DataSource", "InjurySource", "BallDontLie", "NbaApiSource", "NbaInjuryReport",
    "FONTES", "build_source", "build_injury_source",
]
