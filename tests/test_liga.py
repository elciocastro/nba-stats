"""Panorama da liga (página inicial): fonte de notícias, ingestão e métricas."""

from datetime import date

import pytest
from test_injury_report import FakeInjuries

from nbastats.ingest import refresh, sync_news, sync_season
from nbastats.metrics import liga
from nbastats.sources.noticias import ESPN_NEWS, NBA_MOVEMENT, NbaNewsFeed

ESPN = {"articles": [
    {"id": 1, "type": "Recap", "published": "2026-11-06T03:00:00Z", "headline": "Warriors beat Bulls ",
     "description": "— Novato Sobe had 25 points.", "links": {"web": {"href": "http://www.espn.com/nba/recap?gameId=1"}},
     "images": [{"url": "https://a.espncdn.com/x.jpg"}],
     "categories": [{"type": "league", "description": "NBA"}, {"type": "team", "description": "Chicago Bulls"}]},
    {"id": 2, "type": "Media", "published": "2026-11-06T04:00:00Z", "headline": "Highlights",
     "links": {"web": {"href": "https://www.espn.com/video/2"}}},
    {"id": 3, "type": "Story", "headline": "Sem link"},
]}
MOV = {"NBA_Player_Movement": {"rows": [
    {"Transaction_Type": "Signing", "TRANSACTION_DATE": "2026-11-04T00:00:00", "TEAM_ID": 5.0, "PLAYER_ID": 2.0,
     "GroupSort": "Signing 1", "TRANSACTION_DESCRIPTION": "Chicago Bulls signed forward Novato Cai to a Two-Way Contract."},
    {"Transaction_Type": "Trade", "TRANSACTION_DATE": "2026-11-03T00:00:00", "TEAM_ID": 10.0, "PLAYER_ID": 9.0,
     "GroupSort": "Trade 7", "TRANSACTION_DESCRIPTION": "Golden State Warriors received guard Fulano de Tal from Chicago Bulls."},
    {"Transaction_Type": "Trade", "TRANSACTION_DATE": "2026-11-03T00:00:00", "TEAM_ID": 5.0, "PLAYER_ID": 0.0,
     "GroupSort": "Trade 7", "TRANSACTION_DESCRIPTION": "Chicago Bulls received draft consideration from Golden State Warriors."},
    {"Transaction_Type": "Waive", "TRANSACTION_DATE": "2026-06-30T00:00:00", "TEAM_ID": 5.0, "PLAYER_ID": 8.0,
     "GroupSort": "Waive 0", "TRANSACTION_DESCRIPTION": "Chicago Bulls waived center Velho Demais."},
]}}


def fake_get(url):
    return {ESPN_NEWS: ESPN, NBA_MOVEMENT: MOV}[url]


class Falha:
    def news(self):
        raise RuntimeError("ESPN fora do ar")

    def transactions(self, *, since):
        raise RuntimeError("fora")


@pytest.fixture
def loaded(conn, source):
    sync_season(conn, source, 2026)
    return conn


def test_fonte_normaliza_noticias_e_transacoes():
    feed = NbaNewsFeed(get=fake_get)
    news = feed.news()
    assert [n["id"] for n in news] == ["1", "2"]  # sem link fica de fora
    n = news[0]
    assert n["titulo"] == "Warriors beat Bulls" and n["resumo"] == "Novato Sobe had 25 points."
    assert n["url"].startswith("https://") and n["times"] == ["Chicago Bulls"]
    tx = feed.transactions(since="2026-07-01")
    assert len(tx) == 3  # a de junho é da temporada passada
    assert tx[0]["team_id"] == 5 and tx[0]["player_id"] == 2 and tx[0]["date"] == "2026-11-04"
    assert tx[2]["player_id"] is None


def test_sync_news_idempotente(conn):
    feed = NbaNewsFeed(get=fake_get)
    first = sync_news(conn, feed, today=date(2026, 11, 6))
    again = sync_news(conn, feed, today=date(2026, 11, 6))
    assert (first["noticias"], first["transacoes"]) == (again["noticias"], again["transacoes"]) == (2, 3)
    assert conn.execute("SELECT COUNT(*) FROM news").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 3


def test_refresh_nao_cai_se_noticias_falham(conn, source):
    res = refresh(conn, source, FakeInjuries([]), news_source=Falha(), today=date(2026, 11, 6))
    assert res["pulado"] is False and res["games"] > 0
    assert conn.execute("SELECT status FROM sync_log WHERE kind = 'news'").fetchone()[0] == "error"


def test_refresh_baixa_transacoes_so_a_cada_3h(conn, source):
    calls = []

    def get(url):
        calls.append(url)
        return fake_get(url)

    feed = NbaNewsFeed(get=get)
    refresh(conn, source, None, news_source=feed, today=date(2026, 11, 6))
    refresh(conn, source, None, news_source=feed, today=date(2026, 11, 6), force=True)
    assert calls.count(ESPN_NEWS) == 2 and calls.count(NBA_MOVEMENT) == 1


@pytest.mark.parametrize("tipo, desc, player, esperado", [
    ("Waive", "Chicago Bulls waived center Velho Demais.", None, "Chicago Bulls dispensou o pivô Velho Demais"),
    ("Signing", "Chicago Bulls signed forward Novato Cai to a Two-Way Contract.", "Novato Cai",
     "Chicago Bulls contratou o ala Novato Cai (contrato two-way)"),
    ("Signing", "Chicago Bulls re-signed guard Fulano Jr. to a Contract.", None, "Chicago Bulls renovou com o armador Fulano Jr"),
    ("Trade", "Chicago Bulls received guard Fulano from Golden State Warriors.", "Fulano",
     "Chicago Bulls recebeu o armador Fulano do Golden State Warriors"),
    ("Trade", "Chicago Bulls received draft consideration from Golden State Warriors.", None,
     "Chicago Bulls recebeu compensação de draft do Golden State Warriors"),
    ("Outro", "Something new happened.", None, "Something new happened."),
])
def test_traduz_transacoes(tipo, desc, player, esperado):
    assert liga.translate(tipo, desc, "Chicago Bulls", player) == esperado


def test_troca_vira_um_item(conn, loaded):
    sync_news(loaded, NbaNewsFeed(get=fake_get), today=date(2026, 11, 6))
    items = liga.transactions(loaded)
    assert [i["tipo"] for i in items] == ["Contratação", "Troca"]
    troca = items[1]
    assert sorted(troca["times"]) == ["CHI", "GSW"] and len(troca["linhas"]) == 2
    assert items[0]["jogadores"] == [{"player_id": 2, "jogador": "Novato Cai"}]


def test_rodada_classificacao_e_lideres(loaded):
    assert liga.last_round_date(loaded, "2026-11-06") == "2026-11-05"
    [r] = liga.results(loaded, "2026-11-05")
    assert (r["vencedor"], r["margem"]) == ("GSW", 10)
    assert r["cestinha_casa"]["pts"] == 25 and r["cestinha_fora"]["jogador"] == "Novato Cai"

    top = liga.top_performances(loaded, "2026-11-05", limit=2)
    assert top[0]["pts"] == 25 and top[0]["venceu"] is True

    st = liga.standings(loaded, 2026)
    gsw, chi = st["West"][0], st["East"][0]
    assert (gsw["v"], gsw["d"], gsw["sequencia"], gsw["atras"], gsw["zona"]) == (3, 0, "V3", "—", "playoff")
    assert (chi["v"], chi["d"], chi["ult10"]) == (0, 3, "0-3")
    assert liga.standings(loaded, 2026, until="2026-11-01")["West"][0]["v"] == 1

    ld = liga.leaders(loaded, 2026)
    assert ld["min_jogos"] == 3  # 70% de 3 jogos
    assert ld["categorias"]["pts"]["jogadores"][0]["media"] == 15.0


def test_overview_sem_jogos(conn):
    o = liga.overview(conn, "2026-11-06")
    assert o["rodada"] is None and o["resultados"] == [] and o["noticias"] == []
