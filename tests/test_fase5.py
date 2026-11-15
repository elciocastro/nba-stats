"""Fase 5: histórico multitemporada (H2H), BetânIAG, notícias, comparação e IA."""

import sys
import types

import pytest

from nbastats.metrics import betaniag as bt
from nbastats.metrics import comparar, historico as hs, noticias
from nbastats import ia

A, B, C = 1, 2, 3
RULES = {"posicoes": {"G": "G", "C": "C"}, "dvp_recente_dias": 15}


def _game(conn, gid, day, season, home, away, hs_, vs_, rows):
    conn.execute("INSERT INTO games (id, date, season, postseason, status, home_team_id, visitor_team_id,"
                 " home_team_score, visitor_team_score) VALUES (?, ?, ?, 0, 'Final', ?, ?, ?, ?)",
                 (gid, day, season, home, away, hs_, vs_))
    for pid, team, pts, mins in rows:
        conn.execute("INSERT INTO player_game_stats (id, game_id, player_id, team_id, minutes, pts, reb, ast,"
                     " fga, fta, turnover, oreb, fgm, fg3m, fg3a, stl, blk, ftm)"
                     " VALUES (?, ?, ?, ?, ?, ?, 5, 5, 10, 2, 1, 0, 5, 1, 3, 0, 0, 2)",
                     (gid * 100 + pid, gid, pid, team, mins, pts))


@pytest.fixture
def base(conn):
    for tid, ab in ((A, "AAA"), (B, "BBB"), (C, "CCC")):
        conn.execute("INSERT INTO teams (id, abbreviation) VALUES (?, ?)", (tid, ab))
    for pid, name, pos, team in ((10, "Ana", "G", A), (11, "Beto", "C", A), (20, "Caio", "G", B),
                                 (30, "Duda", "G", C)):
        conn.execute("INSERT INTO players (id, first_name, last_name, position, team_id)"
                     " VALUES (?, ?, '', ?, ?)", (pid, name, pos, team))
    # temporada passada: Ana x B duas vezes (H2H em outra temporada)
    _game(conn, 1, "2026-02-01", 2025, A, B, 100, 90, [(10, A, 30, 34), (11, A, 10, 30), (20, B, 12, 30)])
    _game(conn, 2, "2026-03-01", 2025, B, A, 95, 99, [(10, A, 26, 33), (11, A, 12, 30), (20, B, 14, 30)])
    # temporada atual
    _game(conn, 3, "2026-11-01", 2026, A, C, 110, 100, [(10, A, 20, 32), (11, A, 8, 28), (30, C, 18, 30)])
    _game(conn, 4, "2026-11-02", 2026, C, A, 105, 101, [(10, A, 15, 30), (30, C, 22, 30)])  # Beto fora
    _game(conn, 5, "2026-11-05", 2026, B, C, 100, 104, [(20, B, 25, 34), (30, C, 16, 31)])
    # hoje: A x B, agendado
    conn.execute("INSERT INTO games (id, date, season, postseason, status, home_team_id, visitor_team_id)"
                 " VALUES (6, '2026-11-07', 2026, 0, '7:30 pm ET', ?, ?)", (A, B))
    return conn


def test_historico_junta_temporadas_h2h_e_descanso(base):
    log = hs.player_logs(base, [10], "2026-11-07")[10]
    assert [g["game_id"] for g in log] == [4, 3, 2, 1]
    assert log[0]["descanso"] == 0 and log[0]["resultado"] == "D" and log[0]["margem"] == -4
    assert log[1]["descanso"] is None            # 8 meses: pausa, não descanso
    assert log[2]["resultado"] == "V" and not log[2]["em_casa"]
    w = hs.windows(log, "pts", 21.5, B, 2026)
    assert list(w) == ["26/27", "H2H", "L5", "L10", "L20", "25/26"]
    assert w["H2H"] == {"jogos": 2, "over": 2, "pct": 100, "media": 28.0}
    assert w["26/27"]["jogos"] == 2 and w["26/27"]["over"] == 0
    assert w["25/26"]["media"] == 28.0
    assert [g["game_id"] for g in hs.split(log, "b2b")] == [4]
    assert [g["game_id"] for g in hs.split(log, "derrota")] == [4]
    assert hs.h2h_games(log, B, limit=1)[0]["game_id"] == 2


def test_minutos_escalam_a_projecao():
    assert hs.scale_to_minutes({"valor": 20.0, "minutos": 30.0}, 36) == 24.0
    assert hs.scale_to_minutes(None, 30) is None
    assert hs.season_label(2026) == "26/27"


CFG = {
    "niveis": [{"nome": "Forte", "cor": "g", "chance_min": 0.62, "ev_min": 0.08},
               {"nome": "Boa", "cor": "lg", "chance_min": 0.57, "ev_min": 0.04},
               {"nome": "Especulativa", "cor": "a", "chance_min": 0.53, "ev_min": 0.0},
               {"nome": "Neutra", "cor": "c", "chance_min": 0.0, "ev_min": None}],
    "sem_valor": {"nome": "Sem valor", "cor": "r"},
    "unidades": {"habilitado": False, "por_nivel": {"Forte": 2, "Boa": 1, "Especulativa": 0.5}},
    "validacao": {"minutos_antes_do_jogo": 90, "min_minutos_l10": 20},
}


def test_mercado_sem_margem():
    m = bt.no_vig(1.87, 1.93)
    assert m["p_over"] == pytest.approx(0.508, abs=0.001) and m["margem"] == pytest.approx(0.0529, abs=0.001)
    assert bt.no_vig(None, 1.9) is None


def test_selo_por_chance_e_valor():
    p = {"p_over": 0.64, "p_under": 0.36, "odd_over": 1.80, "odd_under": 2.0, "linha": 20.5}
    s = bt.seal(p, CFG)                       # EV = 0,64*1,80-1 = +15%
    assert s["nivel"] == "Forte" and s["lado"] == "over" and s["unidade"] is None
    assert s["vantagem"] == pytest.approx(0.64 - (1 / 1.8) / (1 / 1.8 + 0.5), abs=1e-6)
    p["odd_over"] = 1.70                      # EV +8,8% ainda forte; 1,60 -> +2,4%: especulativa
    p["odd_over"] = 1.60
    assert bt.seal(p, CFG)["nivel"] == "Especulativa"
    p["odd_over"] = 1.50                      # EV negativo
    assert bt.seal(p, CFG)["nivel"] == "Sem valor"
    sem_odd = {"p_over": 0.42, "p_under": 0.58, "linha_ref": True}
    s = bt.seal(sem_odd, CFG)
    assert s["lado"] == "under" and s["nivel"] == "Boa" and s["sem_odd"] and s["linha_ref"]
    on = {**CFG, "unidades": {**CFG["unidades"], "habilitado": True}}
    assert bt.seal(sem_odd, on)["unidade"] == 1
    capped = {**CFG, "linha_ref_max": "Especulativa"}
    assert bt.seal(sem_odd, capped)["nivel"] == "Especulativa"
    assert bt.seal({**sem_odd, "linha_ref": False}, capped)["nivel"] == "Boa"
    assert bt.seal({"p_over": None}, CFG) is None


def test_validacao_do_jogo():
    game = {"date": "2026-11-07", "status": "7:30 pm ET", "home_team_score": None}
    p = {"player_id": 1, "jogador": "X", "lesao": None, "min_l10": 30}
    item = {"jogo": game, "injury_report": None, "jogadores": [p]}
    assert bt.tipoff(game).strftime("%H:%M") == "19:30"
    assert bt.validation(item, CFG)["status"] == "pré-análise"
    item["injury_report"] = "2026-11-07T13:30"
    assert "último injury report" in bt.validation(item, CFG)["motivo"]
    item["injury_report"] = "2026-11-07T18:30"
    assert bt.validation(item, CFG)["status"] == "validada"
    p["lesao"] = "Questionable"
    assert bt.validation(item, CFG)["motivo"] == "em dúvida: X"


def test_checklist_traz_os_itens_do_protocolo():
    p = {"p_over": 0.6, "p_under": 0.4, "odd_over": 1.9, "odd_under": 1.9, "linha": 20.5,
         "linha_ref": False, "dvp_rank": 28,
         "janelas": {"L5": {"pct": 40, "jogos": 5}, "L10": {"pct": 60, "jogos": 10},
                     "H2H": {"pct": 100, "jogos": 2, "media": 25.0}}}
    items = {i["item"]: i for i in bt.checklist(p, CFG, {"status": "validada", "motivo": "ok"})}
    assert items["Valor esperado"]["valor"] == "+14.0%" and items["Valor esperado"]["ok"]
    assert items["Vantagem sobre o mercado"]["valor"] == "+10.0 p.p."
    assert items["L5 a favor do lado"]["nota"] == "alerta: o L5 vai contra"
    assert items["H2H a favor do lado"]["nota"] == "poucos jogos: só curiosidade"
    assert "Unidade sugerida" not in items


def _report(conn, rid, when, rows):
    conn.execute("INSERT INTO injury_reports (id, published_at) VALUES (?, ?)", (rid, when))
    for i, (pid, name, team, status) in enumerate(rows):
        conn.execute("INSERT INTO injuries (id, report_id, game_date, team_id, player_id, player_name,"
                     " status, reason) VALUES (?, ?, '2026-11-07', ?, ?, ?, ?, 'x')",
                     (rid * 1000 + i, rid, team, pid, name, status))


def test_noticias_mudancas_e_retornos(base):
    _report(base, 1, "2026-11-07T12:00", [(11, "Beto", A, "Out"), (20, "Caio", B, "Questionable")])
    _report(base, 2, "2026-11-07T17:00", [(11, "Beto", A, "Questionable"), (10, "Ana", A, "Probable")])
    ch = noticias.changes(base, "2026-11-07")
    by = {c["jogador"]: c for c in ch["mudancas"]}
    assert ch["atual"] == "2026-11-07T17:00" and ch["anterior"] == "2026-11-07T12:00"
    assert by["Beto"]["tipo"] == "melhorou" and by["Beto"]["antes"] == "Out"
    assert by["Caio"]["tipo"] == "saiu" and by["Ana"]["tipo"] == "entrou"
    ret = noticias.returns(base, "2026-11-07")
    assert [r["jogador"].strip() for r in ret] == ["Beto"]
    assert ret[0]["jogos_fora"] == 1 and ret[0]["minutos_antes"] == 28.0 and ret[0]["status"] == "Questionable"


def test_comparacao_de_times_e_tendencias(base):
    tc = comparar.team_compare(base, "2026-11-07", A, C, RULES)
    assert tc["a"]["time"] == "AAA" and tc["a"]["jogos"] == 2 and tc["a"]["pts_feitos"] == 21.5
    assert {d["grupo"] for d in tc["a"]["dvp"]} == {"G", "C"}
    tr = comparar.trends(base, "2026-11-07", RULES, min_minutes=0)
    assert set(tr) == {"minutos", "minutos_queda", "uso", "defesas"}
    rows = comparar.compare_players(
        {"jogador": "Ana", "time": "AAA", "adversario": "BBB", "linha": 20.5, "p_over": 0.6},
        {"jogador": "Caio", "time": "BBB", "adversario": "AAA", "linha": 18.5, "p_over": 0.4})
    assert rows[1] == {"Item": "Linha", "Ana": 20.5, "Caio": 18.5}


def test_ia_desligada_nao_chama_nada(monkeypatch):
    ok, why = ia.status({"ia": {"habilitado": False}})
    assert not ok and "desligada" in why
    with pytest.raises(ia.IADesligada):
        ia.report({}, {"x": 1})
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert "ANTHROPIC_API_KEY" in ia.status({"ia": {"habilitado": True}})[1]


def test_ia_ligada_manda_so_os_dados(monkeypatch):
    sent = {}

    class Block:
        type, text = "text", "Análise"

    class Messages:
        def create(self, **kw):
            sent.update(kw)
            return types.SimpleNamespace(stop_reason="end_turn", content=[Block()])

    fake = types.ModuleType("anthropic")
    fake.Anthropic = lambda: types.SimpleNamespace(beta=types.SimpleNamespace(messages=Messages()))
    monkeypatch.setitem(sys.modules, "anthropic", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "teste")
    cfg = {"ia": {"habilitado": True, "modelo": "claude-opus-5-5"}}
    assert ia.report(cfg, {"jogador": "Ana", "chance": 0.6}, "compare") == "Análise"
    assert sent["model"] == "claude-opus-5-5" and sent["fallbacks"] == "default"
    assert '"chance": 0.6' in sent["messages"][0]["content"] and "compare" in sent["messages"][0]["content"]


def test_faixa_de_cor_contra_a_media_ou_linha():
    assert hs.band(20, 20) == "acima" and hs.band(16, 20) == "perto" and hs.band(15.9, 20) == "abaixo"
    assert hs.band(None, 20) is None and hs.band(5, 0) is None
    log = [{"season": 2026, "pts": 10}, {"season": 2026, "pts": 20}, {"season": 2025, "pts": 99}]
    assert hs.season_averages(log, 2026, ["pts"]) == {"pts": 15.0}
    assert hs.season_averages(log, 2027, ["pts"]) == {"pts": 43.0}   # sem jogos: histórico todo


def _p(pid, name, **kw):
    base = {"player_id": pid, "jogador": name, "time": "AAA", "adversario": "BBB", "jogos": 10,
            "l5": 20.0, "temporada": 20.0, "min_l5": 30, "min_l10": 30, "usg_l5": 20, "usg_l10": 20,
            "proj": 20.0, "linha": 19.5, "l10": 20.0, "linha_ref": True, "p_over": .55, "p_under": .45,
            "odd_over": None, "odd_under": None, "historico": [{"pra": 20, "pts": 20}] * 3}
    return {**base, **kw}


def test_destaques_do_dia():
    from nbastats.metrics import destaques as dq
    game = {"id": 6, "home": "AAA", "visitor": "BBB", "status": "7:30 pm ET", "home_team_score": None,
            "visitor_team_score": None}
    players = [_p(1, "Sobe", l5=30.0), _p(2, "Cai", l5=15.0, p_over=.3, p_under=.7),
               _p(3, "Com odd", odd_over=2.2, odd_under=1.7, p_over=.5, p_under=.5),
               _p(4, "Poucos jogos", jogos=3, l5=50.0)]
    item = {"jogo": game, "ritmo": {"casa": 101, "fora": 103, "liga": 100}, "desfalques": {"casa": [], "fora": []},
            "margem_esperada": -3.2, "risco_blowout": .3, "jogadores": players}
    reports = {"pra": [item], "pts": [item]}
    hot = dq.rising(reports["pra"])
    assert [h["jogador"] for h in hot][:1] == ["Sobe"] and hot[0]["alta_pct"] == 50
    assert "Poucos jogos" not in [h["jogador"] for h in hot]
    opp = dq.opportunities(reports, CFG)
    assert opp["com_odd"][0]["jogador"] == "Com odd" and opp["com_odd"][0]["ev"] == pytest.approx(.1)
    assert opp["sem_odd"][0]["jogador"] == "Cai" and opp["sem_odd"][0]["lado"] == "under"
    [card] = dq.game_cards(reports, CFG)
    assert card["favorito"] == "BBB" and card["margem"] == 3.2 and card["ritmo_vs_liga"] == 2.0
    assert card["melhor"]["jogador"] == "Cai" and card["props_boas"] == 2   # Cai é Boa em 2 mercados
    assert len([o for o in opp["sem_odd"] if o["jogador"] == "Cai"]) == 1   # um destaque por jogador
    assert dq.opportunities(reports, CFG, min_media={"pra": 25, "pts": 25})["sem_odd"] == []
