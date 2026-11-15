from nbastats.metrics.cascata import cascata


def _p(pid, nome, com_sem, proj=None, linha=None):
    return {"player_id": pid, "jogador": nome, "time": "PHI", "adversario": "IND", "l10": 30, "proj": proj,
            "linha": linha, "linha_ref": False, "p_over": 0.6, "com_sem": com_sem}


def test_agrupa_por_desfalque_e_ordena_por_ganho():
    report = [{"jogo": {"id": 1}, "jogadores": [
        _p(1, "Maxey", [{"companheiro": "Joel Embiid", "com": 30.0, "jogos_com": 5, "sem": 36.0, "jogos_sem": 4}], 38.2, 35.5),
        _p(2, "Oubre", [{"companheiro": "Joel Embiid", "com": 20.0, "jogos_com": 5, "sem": 19.0, "jogos_sem": 4}]),
        _p(3, "Drummond", [{"companheiro": "Joel Embiid", "com": 10.0, "jogos_com": 5, "sem": 25.0, "jogos_sem": 1}]),
        _p(4, "Grimes", [{"companheiro": "Kelly Oubre", "com": 15.0, "jogos_com": 6, "sem": 16.0, "jogos_sem": 3}]),
    ]}]
    out = cascata(report, novidades=["Kelly Oubre"])
    assert [i["fora"] for i in out] == ["Kelly Oubre", "Joel Embiid"]  # novidade primeiro
    embiid = out[1]
    assert [c["jogador"] for c in embiid["companheiros"]] == ["Maxey", "Oubre"]  # Drummond: 1 jogo sem, fica de fora
    assert embiid["companheiros"][0]["ganho"] == 6.0 and embiid["companheiros"][0]["diff"] == 2.7
    assert embiid["ganho_total"] == 6.0 and out[0]["novo"]
    assert cascata([]) == []
