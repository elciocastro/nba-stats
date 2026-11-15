from datetime import date

from .balldontlie import BallDontLie
from .base import DataSource, InjurySource, NewsSource
from .injury_report import NbaInjuryReport
from .nba_api_source import NbaApiSource, season_of
from .noticias import NbaNewsFeed

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


def build_news_source() -> NewsSource:
    """Manchetes (ESPN) e transações (NBA)."""
    return NbaNewsFeed()


__all__ = [
    "DataSource", "InjurySource", "NewsSource", "NbaNewsFeed", "build_news_source",
    "BallDontLie", "NbaApiSource", "NbaInjuryReport",
    "FONTES", "build_source", "build_injury_source",
]
