"""Teste de contrato contra as fontes reais (stats.nba.com, CDN e injury report).

Fora do CI e do ``pytest`` normal: só roda com ``NBASTATS_CONTRATO=1``
(``NBASTATS_CONTRATO=1 pytest -m contrato``). Serve para descobrir cedo quando
a NBA muda o formato de uma resposta, antes de a carga das 06h quebrar.
"""

import os
from datetime import date, timedelta

import pytest

pytestmark = [
    pytest.mark.contrato,
    pytest.mark.skipif(os.environ.get("NBASTATS_CONTRATO") != "1",
                       reason="contrato com APIs reais: use NBASTATS_CONTRATO=1"),
]

TEMPORADA = int(os.environ.get("NBASTATS_CONTRATO_TEMPORADA", "2025"))


def test_times():
    from nbastats.sources.nba_api_source import NbaApiSource
    teams = list(NbaApiSource().teams())
    assert len(teams) == 30
    assert {"id", "abbreviation", "full_name"} <= set(teams[0])


def test_jogos_e_stats_de_um_dia():
    from nbastats.sources.nba_api_source import NbaApiSource
    src = NbaApiSource()
    dia = f"{TEMPORADA + 1}-01-15"
    games = list(src.games(season=TEMPORADA, start_date=dia, end_date=dia))
    assert games, "esperava jogos em 15/jan"
    assert {"id", "date", "home_team", "visitor_team"} <= set(games[0])
    stats = list(src.stats(season=TEMPORADA, start_date=dia, end_date=dia))
    assert stats
    assert {"pts", "reb", "ast", "min", "fg3m", "player", "game"} <= set(stats[0])


def test_agenda():
    from nbastats.sources.nba_api_source import NbaApiSource
    dia = (date.today() + timedelta(days=1)).isoformat()
    for g in NbaApiSource().schedule(date=dia):   # pode vir vazio fora da temporada
        assert {"id", "date", "home_team", "visitor_team"} <= set(g)


def test_ao_vivo():
    from nbastats.sources.nba_live import NbaLiveSource
    for g in NbaLiveSource().live_games():
        assert {"game_id", "status"} <= set(g)


def test_injury_report():
    from nbastats.sources.injury_report import NbaInjuryReport
    rep = NbaInjuryReport(TEMPORADA).latest()
    assert rep is not None
    assert rep["url"].endswith(".pdf")
    assert rep["rows"], "relatório sem linhas"
