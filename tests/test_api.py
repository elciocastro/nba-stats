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
