import pytest

from nbastats.ingest import sync_season
from nbastats.metrics import boxscore, load_rules, player_gamelog, player_trends, rank_potenciais

RULES = {
    "ultimos_jogos": 1,
    "filtros": {"min_jogos": 3, "min_minutos": 15, "max_anos_de_liga": 4},
    "pesos": {"pts": 1.0, "reb": 1.0, "ast": 1.0},
}


@pytest.fixture
def loaded(conn, source):
    sync_season(conn, source, 2026)
    return conn


def test_trends_media_temporada_e_recente(loaded):
    rows = {r["jogador"]: r for r in player_trends(loaded, 2026, last_n=1)}
    sobe = rows["Novato Sobe"]
    assert sobe["jogos"] == 3
    assert sobe["pts"] == 15.0      # (10 + 10 + 25) / 3
    assert sobe["pts_n"] == 25.0    # só o último jogo
    assert sobe["minutes"] == 31.5  # (30 + 30 + 34.5) / 3
    assert "Nao Jogou" not in rows  # 0 minuto não conta


def test_potencial_filtra_veterano_e_ordena(loaded):
    ranked = rank_potenciais(loaded, 2026, RULES)
    assert [r["jogador"] for r in ranked] == ["Novato Sobe", "Novato Cai"]
    assert ranked[0]["nota"] > 0 > ranked[1]["nota"]
    assert ranked[0]["anos_de_liga"] == 1


def test_potencial_sem_limite_de_anos_inclui_veterano(loaded):
    rules = {**RULES, "filtros": {**RULES["filtros"], "max_anos_de_liga": None}}
    assert "Veterano Sobe" in [r["jogador"] for r in rank_potenciais(loaded, 2026, rules)]


def test_mudar_peso_muda_o_ranking(loaded):
    invertido = {**RULES, "pesos": {"pts": -1.0, "reb": -1.0, "ast": -1.0}}
    assert rank_potenciais(loaded, 2026, invertido)[0]["jogador"] == "Novato Cai"


def test_boxscore_por_siglas_em_qualquer_ordem(loaded):
    found = boxscore(loaded, "chi", "gsw")
    assert found["jogo"]["date"] == "2026-11-05"  # o mais recente
    assert len(found["jogadores"]) == 3
    assert boxscore(loaded, "GSW", "CHI", "2026-11-01")["jogo"]["id"] == 100
    assert boxscore(loaded, "GSW", "LAL") is None


def test_gamelog(loaded):
    log = player_gamelog(loaded, 1, 2026)
    assert [g["pts"] for g in log] == [10, 10, 25]
    assert log[0]["adversario"] == "vs CHI"


def test_regras_do_repositorio_sao_validas(loaded):
    rules = load_rules("config/potencial.yaml")
    assert isinstance(rank_potenciais(loaded, 2026, rules), list)


def test_peso_desconhecido_e_rejeitado(tmp_path):
    f = tmp_path / "r.yaml"
    f.write_text("pesos:\n  enterradas: 1.0\n")
    with pytest.raises(ValueError):
        load_rules(f)
