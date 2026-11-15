"""Registro de apostas: resultado, conferência automática e desempenho."""

import pytest

from nbastats.ingest import sync_season
from nbastats.metrics.apostas import (
    add_bet, delete_bet, list_bets, outcome, performance, profit, settle_bets,
)


@pytest.mark.parametrize("side,line,actual,played,expected", [
    ("over", 24.5, 25, True, "ganha"), ("over", 24.5, 24, True, "perdida"),
    ("under", 5.5, 5, True, "ganha"), ("under", 5.5, 6, True, "perdida"),
    ("over", 25.0, 25, True, "devolvida"), ("under", 25.0, 25, True, "devolvida"),
    ("over", 24.5, None, False, "anulada"),
])
def test_resultado(side, line, actual, played, expected):
    assert outcome(side, line, actual, played) == expected


def test_jogador_que_nao_jogou_pode_contar_como_perdida():
    assert outcome("over", 10.5, None, False, void_if_dnp=False) == "perdida"


def test_lucro():
    assert profit("ganha", 1.90, 2) == pytest.approx(1.8)
    assert profit("perdida", 1.90, 2) == -2
    assert profit("devolvida", 1.90, 2) == 0 and profit("anulada", 1.90, 2) == 0


def test_validacao(conn):
    with pytest.raises(ValueError):
        add_bet(conn, day="2026-11-05", player_id=1, market="pts", side="acima", line=1, odd=1.9, units=1)
    with pytest.raises(ValueError):
        add_bet(conn, day="2026-11-05", player_id=1, market="pts", side="over", line=1, odd=1.0, units=1)


@pytest.fixture
def loaded(conn, source):
    sync_season(conn, source, 2026)
    return conn


def test_confere_sozinho_e_mede(loaded):
    # 11-05 (jogo 102): Novato Sobe 25 pts, 8 reb; Novato Cai 5 pts; Nao Jogou 0 min
    a = add_bet(loaded, day="2026-11-05", player_id=1, market="pts", side="over", line=19.5,
                odd=2.0, units=1, prob=0.6, proj=21.0)
    b = add_bet(loaded, day="2026-11-05", player_id=2, market="pts", side="over", line=10.5,
                odd=1.9, units=2, prob=0.55, game_id=102)
    c = add_bet(loaded, day="2026-11-05", player_id=4, market="pts", side="over", line=0.5,
                odd=1.9, units=1, game_id=102)
    d = add_bet(loaded, day="2026-11-05", player_id=1, market="pra", side="under", line=41.0,
                odd=1.9, units=1, game_id=102)  # 25 + 8 + 8 = 41: devolvida
    e = add_bet(loaded, day="2026-11-09", player_id=1, market="pts", side="over", line=1, odd=1.9,
                units=1)  # sem jogo: fica pendente
    assert settle_bets(loaded) == {"ganha": 1, "perdida": 1, "anulada": 1, "devolvida": 1}
    bets = {x["id"]: x for x in list_bets(loaded)}
    assert (bets[a]["status"], bets[a]["actual"], bets[a]["profit_units"], bets[a]["game_id"]) == ("ganha", 25, 1.0, 102)
    assert (bets[b]["status"], bets[b]["profit_units"]) == ("perdida", -2)
    assert bets[c]["status"] == "anulada" and bets[d]["status"] == "devolvida"
    assert bets[e]["status"] == "pendente"
    assert bets[a]["ev"] == pytest.approx(0.2) and bets[a]["jogador"] == "Novato Sobe"
    assert settle_bets(loaded) == {}  # idempotente: só confere pendentes

    perf = performance(loaded)
    g = perf["geral"]
    assert (g["apostas"], g["pendentes"], g["conferidas"], g["ganhas"]) == (5, 1, 3, 1)
    assert g["acerto_pct"] == 50.0 and g["lucro_unidades"] == -1.0
    assert g["roi_pct"] == pytest.approx(-100 / 4)          # -1 u em 4 u apostadas
    assert g["chance_media_pct"] == pytest.approx(57.5)
    assert perf["unidades"]["2 u"]["lucro_unidades"] == -2
    assert perf["faixa_chance"]["60–65%"]["ganhas"] == 1
    assert perf["curva"] == [{"data": "2026-11-05", "lucro_acumulado": -1.0}]

    delete_bet(loaded, e)
    assert len(list_bets(loaded)) == 4
    assert len(list_bets(loaded, status="ganha")) == 1
