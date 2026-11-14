"""Injury report: leitura do PDF (pelas palavras e posições), ingestão e uso na análise."""

from datetime import datetime, timedelta, timezone

import pytest

from nbastats.ingest import refresh, sync_injuries
from nbastats.ingest.sync import sync_season
from nbastats.metrics import matchup_report
from nbastats.sources.injury_report import latest_pdf_url, normalize_name, parse_pages

# x de cada coluna, como no PDF real de 14/11/2026
X = {"GameDate": 23, "GameTime": 120, "Matchup": 200, "Team": 264,
     "PlayerName": 425, "CurrentStatus": 586, "Reason": 666}


def _w(col, top, text):
    return {"x0": X[col] + 1, "top": top, "text": text}


def _header(top=108):
    return [{"x0": x, "top": top, "text": c} for c, x in X.items()]


PAGE_1 = [
    {"x0": 289, "top": 46, "text": "Injury"}, {"x0": 356, "top": 46, "text": "Report:"},
    *_header(),
    _w("GameDate", 129, "11/14/2026"), _w("GameTime", 129, "07:00(ET)"),
    _w("Matchup", 129, "DEN@NOP"), _w("Team", 129, "DenverNuggets"),
    _w("PlayerName", 129, "Strawther,Julian"), _w("CurrentStatus", 129, "Out"),
    _w("Reason", 129, "Injury/Illness-LeftKneeSprain"),
    _w("Team", 218, "NewOrleansPelicans"),
    _w("PlayerName", 218, "Dia,Malik"), _w("CurrentStatus", 218, "Questionable"),
    _w("Reason", 218, "GLeague-Two-Way"),
    # motivo quebrado em duas linhas, centralizado na altura do jogador
    _w("Reason", 262, "Injury/Illness-LeftKneeContusion/"),
    _w("PlayerName", 269, "Missi,Yves"), _w("CurrentStatus", 269, "Probable"),
    _w("Reason", 276, "BoneBruise"),
    _w("Reason", 298, "Injury/Illness-BilateralPatellar"),
    _w("PlayerName", 305, "MurphyIII,Trey"), _w("CurrentStatus", 305, "Out"),
    _w("Reason", 312, "Tendinopathy"),
    {"x0": 23, "top": 560, "text": "Page1of2"},
]
PAGE_2 = [  # sem cabeçalho: usa as colunas da página anterior; novo dia
    _w("GameDate", 129, "11/15/2026"), _w("GameTime", 129, "01:00(ET)"),
    _w("Matchup", 129, "CHI@GSW"), _w("Team", 129, "ChicagoBulls"),
    _w("PlayerName", 129, "Giddey,Josh"), _w("CurrentStatus", 129, "Doubtful"),
    _w("Reason", 129, "Injury/Illness-Back"),
    # time que ainda não enviou: sem jogador, não vira linha nem gruda em ninguém
    _w("Team", 200, "GoldenStateWarriors"), _w("Reason", 200, "NOTYETSUBMITTED"),
]


def test_le_colunas_repete_celulas_e_junta_motivo_quebrado():
    report = parse_pages([PAGE_1, PAGE_2], "Injury Report: 11/14/26 03:00 PM")
    assert report["published_at"] == "2026-11-14T15:00"
    rows = {r["player_name"]: r for r in report["rows"]}
    assert list(rows) == ["Strawther,Julian", "Dia,Malik", "Missi,Yves", "MurphyIII,Trey", "Giddey,Josh"]
    assert rows["Dia,Malik"]["team"] == "NewOrleansPelicans"
    assert rows["Dia,Malik"]["matchup"] == "DEN@NOP"  # repetido da linha de cima
    assert rows["Missi,Yves"]["reason"] == "Injury/Illness-LeftKneeContusion/BoneBruise"
    assert rows["MurphyIII,Trey"]["reason"] == "Injury/Illness-BilateralPatellarTendinopathy"
    assert rows["Giddey,Josh"]["game_date"] == "2026-11-15"
    assert rows["Giddey,Josh"]["team"] == "ChicagoBulls"
    assert all("NOTYET" not in (r["reason"] or "") for r in report["rows"])


def test_pdf_mais_recente_da_pagina():
    html = """
      <a href="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_11_45AM.pdf">
      <a href="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_12_00PM.pdf">
      <a href="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-14_03_00PM.pdf">
      <a href="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_11_30PM.pdf">
    """
    url, stamp = latest_pdf_url(html)
    assert stamp == "2026-11-14T15:00" and url.endswith("03_00PM.pdf")
    assert latest_pdf_url("<html></html>") is None


@pytest.mark.parametrize("a,b", [("MurphyIII,Trey", "Murphy III Trey"),
                                 ("Dëmin,Egor", "Demin, Egor"),
                                 ("NewOrleansPelicans", "New Orleans Pelicans")])
def test_normaliza_nomes(a, b):
    assert normalize_name(a) == normalize_name(b)


class FakeInjuries:
    def __init__(self, rows, published="2026-11-07T15:00"):
        self.report = {"published_at": published, "url": "x", "rows": rows}

    def latest(self):
        return self.report


def _inj(name, status, team="Golden State Warriors", day="2026-11-07"):
    return {"game_date": day, "matchup": "CHI@GSW", "team": team,
            "player_name": name, "status": status, "reason": "Injury/Illness-Knee"}


@pytest.fixture
def loaded(conn, source):
    sync_season(conn, source, 2026)
    from nbastats.ingest import sync_schedule
    sync_schedule(conn, source, ["2026-11-07"])  # CHI @ GSW agendado (id 103)
    return conn


def test_ingestao_liga_nomes_e_e_idempotente(loaded):
    src = FakeInjuries([_inj("Sobe,Veterano", "Out"), _inj("Sobe,Novato", "Questionable"),
                        _inj("Desconhecido,Fulano", "Out")])
    res = sync_injuries(loaded, src)
    assert (res["injuries"], res["unmatched"]) == (3, 1)
    sync_injuries(loaded, src)
    assert loaded.execute("SELECT COUNT(*) FROM injuries").fetchone()[0] == 3
    row = loaded.execute("SELECT player_id, team_id FROM injuries WHERE player_name='Sobe,Veterano'").fetchone()
    assert (row["player_id"], row["team_id"]) == (3, 10)


RULES = {"posicoes": {"G": "G", "F": "F", "C": "C"},
         "filtros": {"min_jogos": 1, "min_minutos_l10": 0},
         "lesoes": {"tirar": ["Out"], "desfalque_min_minutos": 15},
         "criterios": {"forma": {}}}


def test_out_sai_da_lista_e_questionable_fica_marcado(loaded):
    sync_injuries(loaded, FakeInjuries([_inj("Sobe,Veterano", "Out"),
                                        _inj("Sobe,Novato", "Questionable")]))
    [game] = matchup_report(loaded, "2026-11-07", "pts", RULES)
    players = {p["jogador"]: p for p in game["jogadores"]}
    assert "Veterano Sobe" not in players
    assert players["Novato Sobe"]["lesao"] == "Questionable"
    assert players["Novato Cai"]["lesao"] is None
    assert game["injury_report"] == "2026-11-07T15:00"
    assert game["desfalques"]["fora"] == ["Novato Sobe (Questionable)", "Veterano Sobe (Out)"]


def test_vale_o_relatorio_mais_recente(loaded):
    sync_injuries(loaded, FakeInjuries([_inj("Sobe,Veterano", "Out")], "2026-11-07T12:00"))
    sync_injuries(loaded, FakeInjuries([_inj("Sobe,Veterano", "Available")], "2026-11-07T17:00"))
    [game] = matchup_report(loaded, "2026-11-07", "pts", RULES)
    veterano = next(p for p in game["jogadores"] if p["jogador"] == "Veterano Sobe")
    assert veterano["lesao"] == "Available"


def test_sem_relatorio_usa_quem_nao_jogou(loaded):
    [game] = matchup_report(loaded, "2026-11-07", "pts", RULES)
    assert game["injury_report"] is None
    assert all(p["lesao"] is None for p in game["jogadores"])


def test_atualizar_respeita_intervalo(conn, source):
    inj = FakeInjuries([])
    first = refresh(conn, source, inj, min_interval_min=15)
    assert first["pulado"] is False
    feito = datetime.fromisoformat(first["ultima"])

    cedo = refresh(conn, source, inj, min_interval_min=15, now=feito + timedelta(minutes=5))
    assert (cedo["pulado"], cedo["minutos"]) == (True, 5)
    assert refresh(conn, source, inj, min_interval_min=15, force=True)["pulado"] is False
    depois = datetime.now(timezone.utc) + timedelta(minutes=20)
    assert refresh(conn, source, inj, min_interval_min=15, now=depois)["pulado"] is False
    kinds = [r[0] for r in conn.execute("SELECT kind FROM sync_log WHERE kind='refresh'")]
    assert len(kinds) == 3  # o pulado não registra nada
