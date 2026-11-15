import pytest

from nbastats.ingest import sync_season
from nbastats.metrics import ranking as rk


@pytest.fixture
def loaded(conn, source):
    sync_season(conn, source, 2026)
    return conn


def test_ranking_medias_janela_e_por_36(loaded):
    rows = {r["jogador"]: r for r in rk.ranking(loaded, 2026, last_n=1)}
    sobe = rows["Novato Sobe"]
    assert sobe["jogos"] == 3 and sobe["time"] == "GSW"
    assert sobe["pts"] == 15.0 and sobe["pts_n"] == 25.0
    assert sobe["pra"] == round((45 + 16 + 16) / 3, 1)
    assert "Nao Jogou" not in rows
    p36 = {r["jogador"]: r for r in rk.ranking(loaded, 2026, per36=True)}["Novato Cai"]
    assert p36["pts"] == round(45 * 36 / 90, 1)  # 45 pontos em 90 minutos


def test_ranking_mostra_os_times_de_quem_foi_trocado(loaded):
    # o veterano jogou o último jogo pelo CHI
    loaded.execute("UPDATE player_game_stats SET team_id = 5 WHERE id = 9")
    rows = {r["jogador"]: r for r in rk.ranking(loaded, 2026)}
    assert rows["Veterano Sobe"]["time"] == "CHI/GSW"


def test_porcentagens_e_true_shooting():
    assert rk._pct(5, 10) == 50.0 and rk._pct(0, 0) is None
    assert rk._ts(20, 15, 5) == round(100 * 20 / (2 * (15 + 2.2)), 1)


def test_jogos_da_data_e_box_score(loaded):
    jogos = rk.games_by_date(loaded, "2026-11-05")
    assert len(jogos) == 1 and jogos[0]["casa"] == "GSW" and jogos[0]["tem_box"]
    assert rk.last_game_date(loaded, "2026-11-30") == "2026-11-05"
    box = rk.boxscore_game(loaded, jogos[0]["id"])
    fora, casa = box["times"]
    assert (fora["time"], casa["time"]) == ("CHI", "GSW")
    assert casa["totais"]["pts"] == 50 and [p["jogador"] for p in casa["jogadores"]][0] == "Novato Sobe"
    assert casa["nao_jogaram"] == ["Nao Jogou"]
    assert rk.boxscore_game(loaded, 999) is None
