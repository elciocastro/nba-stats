from nbastats.metrics import valor as vl


def _p(pid, p_over, odd_over=None, odd_under=None, linha_ref=False, l10=20, lesao=None):
    return {"player_id": pid, "jogador": f"J{pid}", "time": "AAA", "adversario": "BBB", "linha": 19.5,
            "linha_ref": linha_ref, "proj": 21, "l10": l10, "lesao": lesao, "p_over": p_over,
            "p_under": round(1 - p_over, 3), "odd_over": odd_over, "odd_under": odd_under}


def test_conta_do_edge():
    assert vl.implied(2.0) == 0.5 and vl.implied(1.0) is None
    assert abs(vl.edge(0.6, 2.0) - 0.10) < 1e-9          # o exemplo: 60% numa odd 2,00
    assert abs(vl.min_odd(0.6, 0.05) - 1 / 0.55) < 1e-9
    assert vl.min_odd(0.03, 0.05) is None


def test_listas_com_e_sem_odd():
    rep = {"pts": [{"jogadores": [
        _p(1, 0.60, odd_over=2.0, odd_under=1.8),        # over com +10 p.p.
        _p(2, 0.52, odd_over=1.85, odd_under=1.95),      # sem valor nos dois lados
        _p(3, 0.30, odd_under=1.9),                      # under 70% numa 1,90: +17 p.p.
        _p(4, 0.66, linha_ref=True),                     # sem odd: vai para a odd mínima
        _p(5, 0.80, odd_over=2.0, lesao="Out"),          # fora
        _p(6, 0.70, l10=3),                              # média baixa demais
    ]}]}
    out = vl.value_bets(rep, {"edge_minimo": 0.03}, {"pts": 10})
    assert [(r["player_id"], r["lado"]) for r in out["com_odd"]] == [(3, "under"), (1, "over")]
    assert out["avaliadas"] == 5
    o = out["com_odd"][1]
    assert abs(o["ev"] - 0.2) < 1e-9 and o["odd_justa"] == 1 / 0.6 and o["chance_mercado"] is not None
    assert [r["player_id"] for r in out["sem_odd"]] == [4]
    assert abs(out["sem_odd"][0]["odd_minima"] - 1 / 0.63) < 1e-9
