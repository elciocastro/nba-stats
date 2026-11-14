"""Cruzamento L5/L10 x DvP com um cenário pequeno, calculado à mão.

3 times (A, B, C), cada um com um armador (G) e um pivô (C), 30 min cada.
  11-01  A x B   pts: a_g 20, a_c 10 | b_g 30, b_c 6   (+ a_x, ala de A, só neste jogo)
  11-03  A x C   pts: a_g 24, a_c 12 | c_g 10, c_c 20
  11-05  B x C   pts: b_g 28, b_c 8  | c_g 14, c_c 16
  11-07  A x B   agendado (sem estatística)

Pontos cedidos a armadores (DvP G): A 20,0 · B 17,0 · C 26,0
  -> ranking (1 = cede menos): B 1º, A 2º, C 3º
"""

import pytest

from nbastats.metrics import load_matchup_rules, matchup_report, position_group
from nbastats.metrics.matchup import dvp_table

A, B, C = 1, 2, 3
PLAYERS = {  # id: (nome, posição)
    11: ("a_g", "G"), 12: ("a_c", "C"), 13: ("a_x", "F"),
    21: ("b_g", "G-F"), 22: ("b_c", "C"),
    31: ("c_g", "G"), 32: ("c_c", "C-F"),
}
GAMES = [  # id, data, casa, fora, linhas (jogador, time, pts)
    (1, "2026-11-01", A, B, [(11, A, 20), (12, A, 10), (13, A, 0), (21, B, 30), (22, B, 6)]),
    (2, "2026-11-03", A, C, [(11, A, 24), (12, A, 12), (31, C, 10), (32, C, 20)]),
    (3, "2026-11-05", B, C, [(21, B, 28), (22, B, 8), (31, C, 14), (32, C, 16)]),
    (4, "2026-11-07", A, B, []),
]
RULES = {
    "posicoes": {"G": "G", "G-F": "G", "F": "F", "C": "C", "C-F": "C"},
    "filtros": {"min_jogos": 1, "min_minutos_l10": 0},
    "dvp_recente_dias": 3,
    "desfalque_min_minutos": 25,
    "criterios": {"forma": {}, "minutos": {}, "uso": {},
                  "dvp_temporada": {"rank_min": 3}, "dvp_recente": {"rank_min": 3}},
    "classificacao": {"forte": 5, "bom": 3},
}


def _insert_stat(conn, game_id, pid, team, pts, minutes=30):
    conn.execute(
        "INSERT INTO player_game_stats (id, game_id, player_id, team_id, minutes, pts, reb, ast,"
        " fga, fta, turnover, oreb, fgm, fg3m, stl, blk)"
        " VALUES (?, ?, ?, ?, ?, ?, 0, 0, 10, 0, 0, 0, 5, 0, 0, 0)",
        (game_id * 1000 + pid, game_id, pid, team, minutes, pts))


@pytest.fixture
def base(conn):
    for tid, abbr in ((A, "AAA"), (B, "BBB"), (C, "CCC")):
        conn.execute("INSERT INTO teams (id, abbreviation) VALUES (?, ?)", (tid, abbr))
    for pid, (name, pos) in PLAYERS.items():
        conn.execute("INSERT INTO players (id, first_name, last_name, position) VALUES (?, ?, '', ?)",
                     (pid, name, pos))
    for gid, day, home, away, rows in GAMES:
        conn.execute("INSERT INTO games (id, date, season, postseason, status, home_team_id,"
                     " visitor_team_id) VALUES (?, ?, 2026, 0, 'Final', ?, ?)", (gid, day, home, away))
        for pid, team, pts in rows:
            _insert_stat(conn, gid, pid, team, pts)
    conn.commit()
    return conn


def _player(report, name):
    return next(p for p in report[0]["jogadores"] if p["jogador"] == f"{name} ")


def test_grupo_de_posicao():
    assert position_group("G-F", RULES["posicoes"]) == "G"
    assert position_group(None, RULES["posicoes"]) is None
    assert position_group("X", RULES["posicoes"]) is None


def test_dvp_e_ranking(base):
    table = {r["time"]: r for r in dvp_table(base, 2026, "2026-11-07", "pts", RULES)}
    assert (table["AAA"]["G"], table["BBB"]["G"], table["CCC"]["G"]) == (20.0, 17.0, 26.0)
    assert (table["BBB"]["G_rank"], table["AAA"]["G_rank"], table["CCC"]["G_rank"]) == (1, 2, 3)
    assert table["CCC"]["C"] == 10.0  # (12 + 8) / 2


def test_cruzamento_do_jogo_agendado(base):
    report = matchup_report(base, "2026-11-07", "pts", RULES)
    assert len(report) == 1 and report[0]["jogo"]["home"] == "AAA"
    a_g = _player(report, "a_g")
    assert (a_g["adversario"], a_g["grupo"]) == ("BBB", "G")
    assert (a_g["l5"], a_g["l10"], a_g["temporada"]) == (22.0, 22.0, 22.0)
    assert (a_g["dvp"], a_g["dvp_rank"]) == (17.0, 1)  # B é a melhor defesa contra armador
    assert a_g["criterios"]["dvp_temporada"] is False
    assert a_g["real"] is None  # jogo ainda não aconteceu

    b_g = _player(report, "b_g")  # 'G-F' entra como armador
    assert (b_g["grupo"], b_g["dvp"], b_g["dvp_rank"]) == ("G", 20.0, 2)


def test_taxa_de_uso(base):
    # dois jogadores com o mesmo volume e minutos em 60 min de time: 20% cada
    a_c = _player(matchup_report(base, "2026-11-07", "pts", RULES), "a_c")
    assert a_c["usg_l5"] == pytest.approx(20.0, abs=0.1)


def test_dvp_recente_usa_so_a_janela(base):
    # janela de 3 dias antes de 11-07: só o jogo de 11-05 (B x C)
    report = matchup_report(base, "2026-11-07", "pts", RULES)
    a_g = _player(report, "a_g")
    assert (a_g["dvp_rec"], a_g["dvp_rec_rank"]) == (14.0, 1)  # B cedeu 14 ao c_g


def test_nao_usa_o_proprio_jogo_nem_o_futuro(base):
    # analisando 11-05, o jogo B x C desse dia não entra nas médias
    report = matchup_report(base, "2026-11-05", "pts", RULES)
    b_g = _player(report, "b_g")
    assert (b_g["l5"], b_g["jogos"]) == (30.0, 1)
    assert b_g["real"] == 28  # mas o resultado real aparece para conferir


def test_resultado_real_nao_muda_a_analise(base):
    antes = _player(matchup_report(base, "2026-11-07", "pts", RULES), "a_g")
    _insert_stat(base, 4, 11, A, 40)
    depois = _player(matchup_report(base, "2026-11-07", "pts", RULES), "a_g")
    assert depois["real"] == 40
    assert {k: v for k, v in depois.items() if k not in ("real", "min_real")} == \
           {k: v for k, v in antes.items() if k not in ("real", "min_real")}


def test_desfalque_no_ultimo_jogo(base):
    report = matchup_report(base, "2026-11-07", "pts", RULES)
    assert report[0]["desfalques"]["casa"] == ["a_x "]  # jogou 30 min em 11-01, fora em 11-03
    assert report[0]["desfalques"]["fora"] == []


def test_nota_e_classificacao(base):
    for p in matchup_report(base, "2026-11-07", "pts", RULES)[0]["jogadores"]:
        assert p["nota"] == sum(1 for v in p["criterios"].values() if v)
        assert set(p["criterios"]) == set(RULES["criterios"])  # só os configurados
        assert p["classificacao"] == ("forte" if p["nota"] >= 5 else "bom" if p["nota"] >= 3 else "fraco")


def test_dia_sem_jogo_e_stat_invalida(base):
    assert matchup_report(base, "2026-12-25", "pts", RULES) == []
    with pytest.raises(ValueError):
        matchup_report(base, "2026-11-07", "enterradas", RULES)


def test_regras_do_repositorio_sao_validas(base):
    rules = load_matchup_rules("config/matchup.yaml")
    assert set(rules["posicoes"].values()) == {"G", "F", "C"}
    assert isinstance(matchup_report(base, "2026-11-07", "pts", rules), list)


def test_criterio_desconhecido_e_rejeitado(tmp_path):
    f = tmp_path / "m.yaml"
    f.write_text("criterios:\n  horoscopo: {}\n")
    with pytest.raises(ValueError):
        load_matchup_rules(f)


def test_jogador_fora_do_ultimo_jogo_e_marcado(base):
    a_x = _player(matchup_report(base, "2026-11-07", "pts", RULES), "a_x")
    assert a_x["fora_ultimo_jogo"] is True


def test_backtest_compara_com_o_real(base):
    from nbastats.metrics import backtest
    res = backtest(base, 2026, "pts", RULES)
    total = sum(v["n"] for v in res["classificacao"].values())
    # 4 dias com jogo (o de 11-07 sem resultado ainda). Com resultado e
    # histórico: 11-03 a_g, a_c (C ainda não jogou) e 11-05 b_g, b_c, c_g, c_c
    assert res["dias"] == 4 and total == 6


@pytest.mark.parametrize("pos,height,ast36,reb36,expected", [
    ("G", "6-1", 9.0, 3.0, "PG"), ("G", "6-4", 3.5, 5.0, "SG"),
    ("G-F", "6-8", 3.0, 6.0, "SF"), ("G-F", "6-5", 2.0, 4.0, "SG"), ("F-G", "6-6", 3, 5, "SF"),
    ("F", "6-7", 3.0, 6.0, "SF"), ("F", "6-10", 3.0, 6.0, "PF"), ("F", "6-7", 2.0, 9.5, "PF"),
    ("F-C", "6-9", 2.0, 9.0, "PF"), ("F-C", "7-4", 3.7, 14.0, "C"), ("C-F", "6-11", 2, 12, "C"),
    (None, "6-5", 1, 1, None),
])
def test_estimativa_de_posicao(pos, height, ast36, reb36, expected):
    from nbastats.metrics.matchup import estimate_position
    cfg = {"pg_min_ast36": 5.0, "sf_min_altura_pol": 79, "pf_min_altura_pol": 82,
           "pf_min_reb36": 8.5, "c_min_altura_pol": 84}
    assert estimate_position(pos, height, ast36, reb36, cfg) == expected


def test_mercados_calculados():
    from nbastats.metrics.matchup import _derive
    r = _derive({"pts": 25, "reb": 11, "ast": 9, "stl": 1, "blk": 0,
                 "fgm": 10, "fga": 20, "fg3m": 3, "fg3a": 8})
    assert (r["pra"], r["pr"], r["pa"], r["ra"]) == (45, 36, 34, 20)
    assert (r["fg2m"], r["fg2a"]) == (7, 12)
    assert (r["dd"], r["td"]) == (1, 0)
    assert _derive({"pts": 12, "reb": 10, "ast": 10})["td"] == 1


def test_todos_os_mercados_no_relatorio(base):
    from nbastats.metrics import MATCHUP_STATS
    for stat in MATCHUP_STATS:
        assert isinstance(matchup_report(base, "2026-11-07", stat, RULES), list)
    # pivô: 10 pts, 0 reb -> PRA = pts aqui; a_g tem 22 de média
    assert _player(matchup_report(base, "2026-11-07", "pra", RULES), "a_g")["l10"] == 22.0


def test_dvp_com_cinco_posicoes(base):
    # sem altura nem assistências: G -> SG, 'G-F' -> SG, F -> SF, C -> C
    rules = {**RULES, "posicao_modo": "estimada", "posicao_estimada": {}}
    a_g = _player(matchup_report(base, "2026-11-07", "pts", rules), "a_g")
    assert (a_g["grupo"], a_g["posicao_est"]) == ("SG", "SG")
    assert (a_g["dvp"], a_g["dvp_rank"]) == (17.0, 1)


def test_relatorio_com_projecao(base):
    params = {"pesos_taxa": {"l5": 0, "l10": 1, "temporada": 1}, "ausencia": {"min_minutos_l10": 15}}
    report = matchup_report(base, "2026-11-07", "pts", RULES, params)
    game = report[0]
    a_g = _player(report, "a_g")
    assert a_g["proj"] is not None and a_g["proj_detalhe"]["minutos"] == 30.0
    # sem relatório e jogo não disputado: ausência = quem jogou algum dos 3 últimos
    # jogos do time e ficou fora do último. a_x (30 min em 11-01, fora em 11-03) conta,
    # mas não produziu nada, então a fração da produção fora é zero
    assert game["producao_fora"] == {"casa": 0.0, "fora": 0.0}
    assert game["margem_esperada"] is not None and 0 < game["risco_blowout"] < 1
    assert any(c["companheiro"] == "a_x " for c in a_g["com_sem"])
    assert matchup_report(base, "2026-11-07", "pts", RULES)[0].get("margem_esperada") is None
