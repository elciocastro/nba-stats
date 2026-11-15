"""API: contrato das rotas com uma base pequena (a mesma da fase 5)."""

import pytest
from fastapi.testclient import TestClient

from nbastats import db
from nbastats.api import app as api
from test_fase5 import base  # noqa: F401  (fixture: liga pequena com 2 temporadas)


@pytest.fixture
def client(base, monkeypatch):
    shared = db.connect(":memory:", threads=True)
    base.commit()
    base.backup(shared)
    api.app.dependency_overrides[api.get_conn] = lambda: shared
    monkeypatch.setenv("NBASTATS_PASSWORD", "")
    monkeypatch.setenv("NBASTATS_AQUECER", "0")
    from nbastats.metrics import painel
    painel._CACHE.clear()
    rules = {"posicoes": {"G": "G", "C": "C"}, "filtros": {"min_jogos": 1, "min_minutos_l10": 0}}
    monkeypatch.setattr(painel, "load_matchup_rules", lambda: rules)
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()


def test_props_e_jogador(client):
    r = client.get("/api/props", params={"data": "2026-11-07", "mercado": "pts"})
    assert r.status_code == 200
    body = r.json()
    assert body["temporada"] == "26/27" and len(body["jogos"]) == 1
    ana = next(p for p in body["jogadores"] if p["jogador"].strip() == "Ana")
    assert ana["janelas"]["H2H"]["jogos"] == 2 and ana["valores"]
    d = client.get(f"/api/jogador/{ana['player_id']}", params={"data": "2026-11-07", "mercado": "pts",
                                                              "betaniag": True}).json()
    assert len(d["log"]) == 4 and d["log"][0]["adv"] == "CCC" and d["checklist"]
    assert client.get("/api/jogador/999", params={"data": "2026-11-07"}).status_code == 404
    assert client.get("/api/props", params={"mercado": "xyz"}).status_code == 400


def test_linha_muda_a_chance(client):
    q = {"data": "2026-11-07", "mercado": "pts"}
    pid = client.get("/api/props", params=q).json()["jogadores"][0]["player_id"]
    assert client.put("/api/linhas", json={**q, "player_id": pid, "linha": 99.5, "odd_over": 2.0,
                                           "odd_under": 1.8}).json() == {"ok": True}
    p = next(x for x in client.get("/api/props", params=q).json()["jogadores"] if x["player_id"] == pid)
    assert p["linha"] == 99.5 and not p["linha_ref"] and p["p_over"] < 0.01


def test_inicio_e_chance(client):
    r = client.get("/api/inicio", params={"data": "2026-11-07"}).json()
    assert len(r["jogos"]) == 1 and "em_alta" in r
    c = client.get("/api/chance", params={"mercado": "pts", "proj": 20, "linha": 19.5}).json()
    assert 0 < c["p_over"] < 1


def test_senha(client, monkeypatch):
    monkeypatch.setenv("NBASTATS_PASSWORD", "x")
    assert client.get("/api/meta").status_code == 401
    assert client.get("/api/meta", headers={"X-Senha": "x"}).status_code == 200
    assert client.post("/api/login", json={"senha": "y"}).status_code == 401
    assert client.get("/api/saude").status_code == 200


def test_favoritos(client):
    assert client.get("/api/favoritos").json() == {"jogador": [], "time": [], "jogo": []}
    client.post("/api/favoritos", json={"tipo": "jogador", "id": 10, "nome": "Ana"})
    r = client.post("/api/favoritos", json={"tipo": "jogador", "id": 10})   # idempotente, mantém o nome
    assert r.json()["jogador"][0]["label"] == "Ana" and len(r.json()["jogador"]) == 1
    assert client.post("/api/favoritos", json={"tipo": "xpto", "id": 1}).status_code == 400
    assert client.delete("/api/favoritos/jogador/10").json()["jogador"] == []
    assert client.delete("/api/favoritos/jogador/10").status_code == 200


def test_favorito_por_time_ou_jogo():
    from nbastats.metrics.favoritos import is_favorite
    favs = {"jogador": [], "time": [{"entity_id": 5}], "jogo": [{"entity_id": 9}]}
    assert is_favorite(favs, {"player_id": 1, "time_id": 5, "game_id": 1})
    assert is_favorite(favs, {"player_id": 1, "time_id": 2, "game_id": 9})
    assert not is_favorite(favs, {"player_id": 1, "time_id": 2, "game_id": 1})


def test_linhas_em_lote_dvp_e_potenciais(client):
    q = {"data": "2026-11-07", "mercado": "pts"}
    ids = [p["player_id"] for p in client.get("/api/props", params=q).json()["jogadores"]][:2]
    body = [{**q, "player_id": i, "linha": 10.5} for i in ids]
    assert client.put("/api/linhas/lote", json=body).json()["salvas"] == 2
    assert all(not p["linha_ref"] for p in client.get("/api/props", params=q).json()["jogadores"]
               if p["player_id"] in ids)
    d = client.get("/api/dvp", params=q).json()
    assert d["grupos"] and any(r["joga_hoje"] for r in d["linhas"])
    assert "jogadores" in client.get("/api/potenciais", params={"data": "2026-11-07"}).json()
