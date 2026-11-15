"""Projeção, margem esperada, blowout, com/sem companheiro, zonas e calibração."""

import math

import pytest

from nbastats.metrics.projecao import (
    _lstsq,
    absence_share,
    blowout_probability,
    calibrate,
    evaluate,
    expected_margin,
    project,
    recent_players,
    with_without,
)
from nbastats.metrics.zonas import load_zones, zone_matchup


def _form(**kw):
    base = {"jogos": 20, "minutes_l5": 30.0, "minutes_l10": 30.0, "minutes_temp": 30.0,
            "pts_l5": 20.0, "pts_l10": 20.0, "pts_temp": 20.0, "pra_l10": 30.0}
    return {**base, **kw}


PARAMS = {"pesos_taxa": {"l5": 0, "l10": 1, "temporada": 1},
          "pesos_minutos": {"l5": 1, "l10": 1, "temporada": 1},
          "temporada_anterior_jogos": 5, "dvp_encolhimento_jogos": 20, "ritmo_peso": 1.0}


def test_projecao_sem_ajustes_e_a_media():
    p = project(_form(), "pts", PARAMS)
    assert (p["valor"], p["base"], p["minutos"]) == (20.0, 20.0, 30.0)


def test_mais_minutos_recentes_aumentam_a_projecao():
    # mesma taxa por minuto (2/3 de ponto), minutos subindo
    f = _form(minutes_l5=36.0, minutes_l10=33.0, pts_l5=24.0, pts_l10=22.0)
    p = project(f, "pts", PARAMS)
    assert p["minutos"] == 33.0 and p["valor"] == pytest.approx(22.0, abs=0.01)


def test_temporada_anterior_pesa_no_comeco():
    f = _form(jogos=5)
    prior = {"jogos": 70, "minutes": 2100.0, "pts": 2100.0}  # 1 ponto por minuto antes
    p = project(f, "pts", PARAMS, prior=prior)
    # (5 * 2/3 + 5 * 1) / 10 = 0,8333 por minuto × 30 min
    assert p["valor"] == pytest.approx(25.0, abs=0.01)
    assert project(f, "pts", {**PARAMS, "temporada_anterior_jogos": 0}, prior=prior)["valor"] == 20.0


def test_fatores_dvp_ritmo_e_ajuste():
    params = {**PARAMS, "mercados": {"pts": {"nivel": 0.9, "ausencia": 0.5}}}
    p = project(_form(), "pts", params, dvp_media=60.0, liga_media=50.0, opp_games=20,
                ritmo_time=100.0, ritmo_adv=110.0, ausencia=0.2)
    assert p["f_dvp"] == pytest.approx(1 + 0.5 * 0.2)       # amostra 20/(20+20)
    assert p["f_ritmo"] == pytest.approx(1.05)               # ritmo médio 105 vs 100
    assert p["f_ajuste"] == pytest.approx(1.0)               # 0,9 + 0,5 × 0,2
    assert p["valor"] == pytest.approx(20 * 1.1 * 1.05, abs=0.01)


def test_sem_minutos_nao_projeta():
    assert project(_form(minutes_l5=0.0), "pts", PARAMS) is None


def test_margem_e_blowout():
    params = {"margem": {"intercepto": 0, "saldo": 0.8, "casa": 2, "pra_ausente_time": -0.1,
                         "pra_ausente_adv": 0.1},
              "blowout": {"a": -1.0, "b": 0.08}}
    m = expected_margin(8.0, -2.0, True, 0.0, 30.0, params)
    assert m == pytest.approx(0.8 * 10 + 2 + 3)
    assert expected_margin(None, 1.0, True, 0, 0, params) is None
    assert blowout_probability(m, params) == pytest.approx(1 / (1 + math.exp(-(-1 + 0.08 * 13))))
    assert blowout_probability(-m, params) == blowout_probability(m, params)


def _row(game, team, pid, pts=10):
    return {"game_id": game, "team_id": team, "player_id": pid, "pts": pts}


def test_jogadores_recentes_e_fracao_ausente():
    # mais recente primeiro; jogador 3 só jogou o jogo mais antigo
    rows = [_row(4, 1, 1), _row(4, 1, 2), _row(3, 1, 1), _row(2, 1, 2), _row(1, 1, 3)]
    assert recent_players(rows, 3)[1] == {1, 2}
    form = {1: {"pra_l10": 30.0}, 2: {"pra_l10": 10.0}, 3: {"pra_l10": 20.0}}
    assert absence_share(form, {1, 2}, [2]) == pytest.approx(0.25)


def test_com_e_sem_companheiro():
    rows = [_row(1, 1, 10, 20), _row(1, 1, 11), _row(2, 1, 10, 30), _row(3, 1, 10, 26), _row(3, 1, 11)]
    ww = with_without(rows, 10, [11], "pts")[11]
    assert (ww["com"], ww["jogos_com"], ww["sem"], ww["jogos_sem"]) == (23.0, 2, 30.0, 1)


def test_lstsq_resolve_sistema_simples():
    xs = [[1.0, x] for x in range(10)]
    assert _lstsq(xs, [3 + 2 * x for x in range(10)]) == pytest.approx([3, 2])


def test_calibracao_recupera_nivel_e_ausencia():
    # real = proj × (0,9 + 0,5 × fração), com fração variando
    data = []
    for i in range(200):
        frac = (i % 5) / 10
        proj = 10 + i % 7
        real = proj * (0.9 + 0.5 * frac)
        data.append({"proj_base": {"pts": proj}, "ausencia": frac, "real": {"pts": real},
                     "l10": {"pts": proj}, "saldo_time": None, "saldo_adv": None})
    out = calibrate(data, {})
    assert out["mercados"]["pts"]["nivel"] == pytest.approx(0.9, abs=1e-3)
    assert out["mercados"]["pts"]["ausencia"] == pytest.approx(0.5, abs=1e-3)
    [ev] = evaluate(data, out, ["pts"])
    assert ev["erro_projecao"] == pytest.approx(0, abs=1e-6) and ev["ganho_pct"] > 0


def test_calibracao_de_evento_raro_so_corrige_escala():
    data = [{"proj_base": {"td": 0.1}, "ausencia": (i % 3) / 10, "real": {"td": 1 if i % 50 == 0 else 0},
             "l10": {"td": 0.1}, "saldo_time": None, "saldo_adv": None} for i in range(200)]
    m = calibrate(data, {})["mercados"]["td"]
    assert m["ausencia"] == 0.0 and m["nivel"] == pytest.approx(0.2)


def test_zonas_encaixe(conn):
    rows = [  # jogador 1: 25% no aro, 75% de 3 de frente; defesa 5 cede mais de 3
        ("player", 1, "aro", 5, 10), ("player", 1, "frente3", 12, 30),
        ("team_opp", 5, "aro", 60, 100), ("team_opp", 5, "frente3", 40, 100),
        ("team_opp", 6, "aro", 70, 100), ("team_opp", 6, "frente3", 30, 100),
    ]
    for kind, ent, zone, m, a in rows:
        conn.execute("INSERT INTO shot_zones (id, season, kind, entity_id, zone, fgm, fga)"
                     " VALUES (?, 2026, ?, ?, ?, ?, ?)", (f"{kind}{ent}{zone}", kind, ent, zone, m, a))
    zones = load_zones(conn, 2026)
    zm = zone_matchup(zones, 1, 5)
    # liga: aro 65%, frente3 35%. Defesa 5: aro 60 (-5), frente3 40 (+5)
    assert zm["encaixe_pp"] == pytest.approx(0.25 * -5 + 0.75 * 5)
    assert zone_matchup(zones, 1, 5, only=("frente3",))["encaixe_pp"] == pytest.approx(5.0)
    assert zone_matchup(zones, 99, 5) is None
