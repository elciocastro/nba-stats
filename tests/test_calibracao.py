from datetime import datetime

from nbastats.metrics import calibracao as cb


def test_resumo_por_faixa_do_lado_escolhido():
    # 60% de over que bateu, 30% de over (=70% under) que não bateu (under acertou), 55% que errou
    r = cb.resumo([(0.6, True), (0.3, False), (0.55, False), (0.5, None)])
    assert r["n"] == 3 and r["acerto_pct"] == round(100 * 2 / 3, 1)
    faixas = {f["faixa"]: f for f in r["faixas"]}
    assert faixas["70–80%"]["acerto_pct"] == 100.0 and faixas["55–60%"]["acerto_pct"] == 0.0
    assert r["brier"] == round(((0.6 - 1) ** 2 + 0.3 ** 2 + 0.55 ** 2) / 3, 4)
    assert cb.resumo([])["n"] == 0


def test_backtest_points_usa_linha_de_referencia():
    data = [{"proj_base": {"pts": 20.0}, "l10": {"pts": 18.2}, "ausencia": 0.0, "real": {"pts": 25}},
            {"proj_base": {"pts": 20.0}, "l10": {"pts": 18.2}, "ausencia": 0.0, "real": {"pts": 18}},
            {"proj_base": {"pts": None}, "l10": {"pts": 18.2}, "ausencia": 0.0, "real": {"pts": 18}}]
    params = {"mercados": {"pts": {"nivel": 1.0, "ausencia": 0.0, "dist": "normal", "sd_k": 3.0, "sd_e": 0.3}}}
    pts = cb.backtest_points(data, params, "pts")
    assert len(pts) == 2 and pts[0][0] > 0.5 and pts[0][1] is True and pts[1][1] is False


def _report(score=None, status="7:30 pm ET"):
    return [{"jogo": {"id": 1, "date": "2026-11-15", "status": status, "home_team_score": score},
             "jogadores": [{"player_id": 7, "game_id": 1, "linha": 20.5, "linha_ref": False, "proj": 22.0, "p_over": 0.62},
                           {"player_id": 8, "game_id": 1, "linha": None, "p_over": None}]}]


def test_guarda_previsao_ate_o_inicio_e_confere(conn):
    from nbastats.metrics.betaniag import tipoff
    antes, depois = datetime(2026, 11, 15, 18), datetime(2026, 11, 15, 20)
    assert cb.save_predictions(conn, "2026-11-15", "pts", _report(), antes, tipoff) == 1
    rep = _report(); rep[0]["jogadores"][0]["p_over"] = 0.9
    assert cb.save_predictions(conn, "2026-11-15", "pts", rep, depois, tipoff) == 0  # já começou
    assert conn.execute("SELECT p_over FROM predictions").fetchone()[0] == 0.62
    assert cb.save_predictions(conn, "2026-11-15", "pts", _report(score=100), antes, tipoff) == 0
    conn.execute("INSERT INTO player_game_stats (id, game_id, player_id, minutes, pts) VALUES (1, 1, 7, 30, 25)")
    pts = cb.prediction_points(conn)
    assert pts == {"pts": [(0.62, True)]}
    assert cb.prediction_points(conn, so_casa=True)["pts"]
    rep = cb.report(conn)
    assert rep["previsoes"]["geral"]["n"] == 1 and rep["apostas"]["n"] == 0


def test_backtest_salvo_e_lido(conn):
    cb.save_backtest(conn, 2026, "2026-11-01", {"pts": cb.resumo([(0.6, True)])})
    cb.save_backtest(conn, 2026, "2026-11-02", {"pts": cb.resumo([(0.6, True), (0.7, True)])})
    bt = cb.load_backtest(conn)
    assert len(bt) == 1 and bt[0]["desde"] == "2026-11-02" and bt[0]["mercados"]["pts"]["n"] == 2
