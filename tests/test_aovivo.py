"""Ao Vivo: normalização do placar da NBA (resposta real gravada) e projeção."""

import json
from pathlib import Path

import pytest

from nbastats.metrics import aovivo as av
from nbastats.sources.nba_live import NbaLiveSource, duration_seconds

FIX = json.loads((Path(__file__).parent / "fixtures" / "live_2026-11-14.json").read_text())


def _source():
    return NbaLiveSource(scoreboard=lambda: {"scoreboard": FIX["scoreboard"]},
                         boxscore=lambda gid: FIX["boxscore"] if gid == FIX["boxscore"]["_gameId"] else None)


def test_normaliza_placar_e_jogadores():
    games = _source().live_games()
    assert len(games) == 5 and games[0]["data"] == "2026-11-14"
    final = games[0]
    assert final["status"] == 3 and final["casa"] == "NOP" and final["jogadores"] == []  # sem box gravado
    live = next(g for g in games if g["game_id"] == int(FIX["boxscore"]["_gameId"]))
    assert live["status"] == 2 and live["periodo"] == 4 and live["relogio_seg"] == 451.0
    klay = next(p for p in live["jogadores"] if p["player_id"] == 202691)
    assert klay["minutos"] == 16.0 and klay["pts"] == 17 and klay["fg3m"] == 3 and klay["em_quadra"]
    assert duration_seconds("PT40M33.00S") == 2433 and duration_seconds("") == 0
    # o box score mais atual tem prioridade sobre o placar geral
    from nbastats.sources.nba_live import normalize_game
    sbg = next(g for g in FIX["scoreboard"]["games"] if g["gameStatus"] == 2)
    box = {"game": {**FIX["boxscore"]["game"], "gameClock": "PT02M00.00S", "period": 4,
                    "homeTeam": {**FIX["boxscore"]["game"]["homeTeam"], "score": 120}}}
    n = normalize_game(sbg, box, "2026-11-14")
    assert n["relogio_seg"] == 120 and n["placar_casa"] == 120


def test_minutos_que_faltam():
    assert av.game_minutes_left(1, 0, 0) == 48
    assert av.game_minutes_left(2, 2, 6 * 60) == 30           # 2º quarto, 6 min: 6 + 24
    assert av.game_minutes_left(2, 5, 120) == 2               # prorrogação
    assert av.game_minutes_left(3, 4, 0) == 0


MARKET = {"dist": "normal", "sd_k": 3.0, "sd_e": 0.3}
G = {"status": 2, "periodo": 3, "relogio_seg": 0, "placar_casa": 80, "placar_fora": 75}


def test_projecao_ao_vivo():
    pre = {"proj": 24.0, "min_esperado": 32.0}
    # fim do 3º: faltam 12 min de jogo, ele joga 2/3 do tempo -> 8 min restantes
    r = av.player_live(18, 24, 2, pre, 24.5, G, MARKET, {})
    assert r["restante"] == 8.0 and r["status"] in ("a caminho", "precisa acelerar")
    assert r["final"] == pytest.approx(18 + 8 * (0.7 * 0.75 + 0.3 * 0.75))
    assert av.player_live(25, 24, 2, pre, 24.5, G, MARKET, {})["status"] == "bateu"
    longe = av.player_live(5, 24, 2, pre, 24.5, G, MARKET, {})
    assert longe["status"] == "longe" and longe["chance"] < 0.2
    # blowout no 4º e faltas cortam os minutos
    blow = {**G, "periodo": 4, "relogio_seg": 600, "placar_casa": 110, "placar_fora": 85}
    r = av.player_live(18, 30, 5, pre, 24.5, blow, MARKET, {})
    assert set(r["alertas"]) == {"blowout", "faltas"} and r["restante"] < 2
    fim = av.player_live(18, 30, 2, pre, 24.5, {**G, "status": 3}, MARKET, {})
    assert fim["chance"] == 0 and fim["restante"] == 0


def test_relatorio_ao_vivo_por_mercado_e_alvo():
    games = _source().live_games()
    live = next(g for g in games if g["status"] == 2 and g["jogadores"])
    pid = live["jogadores"][0]["player_id"]
    pre = {pid: {"proj": 20.0, "min_esperado": 30.0, "linha": 25.5, "media": 15.0, "jogador": "X", "time": "MIA"}}
    out = av.live_report(games, pre, "pra", {"mercados": {"pra": MARKET}}, "media")
    row = next(g for g in out if g["game_id"] == live["game_id"])["jogadores"][0]
    assert row["alvo"] == 15.0 and row["atual"] == 17 + 0 + 2 and row["status"] == "bateu"


def test_api_ao_vivo(monkeypatch):
    from fastapi.testclient import TestClient
    from nbastats.api import app as api
    from nbastats import db
    conn = db.connect(":memory:", threads=True)
    db.init_db(conn)
    api._LIVE.update(t=0.0, dados=None)
    api.app.dependency_overrides[api.get_conn] = lambda: conn
    api.app.dependency_overrides[api.get_live] = _source
    monkeypatch.setenv("NBASTATS_PASSWORD", "")
    try:
        r = TestClient(api.app).get("/api/aovivo", params={"mercado": "pts"}).json()
        assert r["data"] == "2026-11-14" and len(r["jogos"]) == 5 and r["destaques"] == []  # base vazia
        assert TestClient(api.app).get("/api/aovivo", params={"alvo": "x"}).status_code == 400
    finally:
        api.app.dependency_overrides.clear()
