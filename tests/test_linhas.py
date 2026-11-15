"""Linhas: chance de over/under, valor esperado, taxa de acerto, gravação e tela."""

import base64
import math

import pytest

from nbastats.metrics.linhas import (
    attach_lines,
    expected_value,
    fair_odd,
    find_player,
    hit_rates,
    lines_for,
    prob_over,
    reference_line,
    save_line,
)
from nbastats.metrics.projecao import _dispersion


def test_poisson_e_binomial_negativa():
    # r enorme = Poisson: P(X > 0,5) = 1 - e^-mu
    assert prob_over(2.0, 0.5, {"dist": "nb", "r": 1e9}) == pytest.approx(1 - math.exp(-2))
    # mais dispersão (r menor) espalha a cauda: P(X > 4,5) cresce
    assert prob_over(2.0, 4.5, {"dist": "nb", "r": 2}) > prob_over(2.0, 4.5, {"dist": "nb", "r": 50})
    assert prob_over(2.0, -0.5, {"dist": "nb", "r": 5}) == 1.0


def test_normal():
    m = {"dist": "normal", "sd_k": 3.0, "sd_e": 0.0}  # desvio 3 fixo
    assert prob_over(20.0, 20.0, m) == pytest.approx(0.5)
    assert prob_over(20.0, 23.0, m) == pytest.approx(1 - 0.8413, abs=1e-3)  # +1 desvio
    assert prob_over(None, 20.0, m) is None and prob_over(20.0, None, m) is None


def test_linha_de_referencia_ev_e_odd_justa():
    assert reference_line(24.3) == 24.5 and reference_line(24.0) == 24.5 and reference_line(None) is None
    assert expected_value(0.55, 1.90) == pytest.approx(0.045)
    assert expected_value(0.5, None) is None
    assert fair_odd(0.5) == 2.0


def test_taxa_de_acerto_por_janela():
    hist = [{"pts": v, "em_casa": i % 2 == 0, "opp_id": 7 if i < 2 else 8}
            for i, v in enumerate([30, 10, 25, 26, 5, 30, 30, 1, 2, 3, 40, 40])]
    r = hit_rates(hist, "pts", 20.5, opp_id=7)
    assert r["L5"] == {"over": 3, "jogos": 5, "pct": 60}
    assert r["L10"]["over"] == 5 and r["Temporada"]["over"] == 7
    assert r["Casa"]["jogos"] == 6 and r["Contra o adversário"] == {"over": 1, "jogos": 2, "pct": 50}


def test_gravar_atualizar_e_apagar_linha(conn):
    save_line(conn, "2026-11-14", 1, "pts", 24.5, 1.9, None)
    save_line(conn, "2026-11-14", 1, "pts", 25.5, 1.85, 1.95)
    save_line(conn, "2026-11-14", 1, "reb", 8.5)
    got = lines_for(conn, "2026-11-14", "pts")
    assert got[1]["line"] == 25.5 and got[1]["odd_under"] == 1.95 and got[1]["source"] == "manual"
    save_line(conn, "2026-11-14", 1, "pts", None)
    assert lines_for(conn, "2026-11-14", "pts") == {}
    assert len(lines_for(conn, "2026-11-14", "reb")) == 1


def test_busca_de_jogador(conn):
    conn.execute("INSERT INTO players (id, first_name, last_name) VALUES (1, 'Egor', 'Dëmin'), "
                 "(2, 'Jamal', 'Murray'), (3, 'Dejounte', 'Murray')")
    assert [p["id"] for p in find_player(conn, "demin")] == [1]
    assert len(find_player(conn, "murray")) == 2
    assert [p["id"] for p in find_player(conn, "Jamal Mur")] == [2]


def _report(player_extra=None):
    hist = [{"pts": v, "em_casa": True, "opp_id": 9} for v in (30, 20, 22, 18, 26)]
    p = {"player_id": 1, "jogador": "X", "l10": 23.2, "proj": 25.0, "historico": hist,
         "adversario_id": 9, **(player_extra or {})}
    return [{"jogadores": [p]}]


def test_juntar_linha_com_o_relatorio():
    params = {"mercados": {"pts": {"dist": "normal", "sd_k": 5.0, "sd_e": 0.0}}}
    [g] = attach_lines(_report(), "pts", {}, params)
    p = g["jogadores"][0]
    assert p["linha"] == 23.5 and p["linha_ref"] is True        # sem linha: referência
    assert p["p_over"] > 0.5 and p["p_over"] + p["p_under"] == pytest.approx(1)
    assert p["proj_vs_linha"] == 1.5 and p["acertos"]["L5"]["over"] == 2

    saved = {1: {"line": 27.5, "odd_over": 2.1, "odd_under": 1.7}}
    p = attach_lines(_report(), "pts", saved, params)[0]["jogadores"][0]
    assert p["linha"] == 27.5 and p["linha_ref"] is False and p["p_over"] < 0.5
    assert p["ev_over"] == pytest.approx(p["p_over"] * 2.1 - 1, abs=0.002)


def test_calibracao_escolhe_a_distribuicao():
    # contagens baixas e assimétricas: a binomial negativa deve ganhar
    import random
    rnd = random.Random(1)
    pts = []
    for _ in range(600):
        mu = rnd.choice([0.8, 1.5, 2.5])
        lam = rnd.gammavariate(2.0, mu / 2.0)       # mistura gama-Poisson = binomial negativa
        y, p, k = 0, math.exp(-lam), 0
        u = rnd.random()
        while u > p:
            k += 1
            p += math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1)) if lam > 0 else 1
        y = k
        pts.append((mu, y, mu * rnd.uniform(0.7, 1.4)))
    d = _dispersion(pts)
    assert d["dist"] == "nb" and 0.5 < d["r"] < 6


def test_barras_svg():
    from nbastats.web.props import bars_svg
    uri = bars_svg([10, 30, 20], 19.5)
    svg = base64.b64decode(uri.split(",")[1]).decode()
    assert svg.count("<rect") == 3 and svg.count("#22c55e") == 2 and svg.count("#ef4444") == 1
    assert "<line" in svg and bars_svg([], 1) == ""


def test_encolhimento_aproxima_de_50():
    from nbastats.metrics.linhas import prob_over, shrink
    assert shrink(0.5, 0.8) == 0.5 and shrink(0.75, 1.0) == 0.75
    assert 0.5 < shrink(0.75, 0.8) < 0.75 and 0.25 < shrink(0.25, 0.8) < 0.5
    m = {"dist": "normal", "sd_k": 3.0, "sd_e": 0.3}
    assert prob_over(30, 20.5, {**m, "encolhimento": 0.8}) < prob_over(30, 20.5, m)
