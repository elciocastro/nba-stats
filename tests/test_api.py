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


def test_apostas_pela_api(client):
    q = {"data": "2026-11-07", "mercado": "pts"}
    pid = client.get("/api/props", params=q).json()["jogadores"][0]["player_id"]
    r = client.post("/api/apostas", json={**q, "player_id": pid, "lado": "over", "linha": 10.5, "odd": 1.9,
                                          "unidades": 1, "casa": "X"}).json()
    assert r["id"] and 0 < r["chance"] < 1                       # fotografia da chance no momento
    assert client.post("/api/apostas", json={**q, "player_id": pid, "lado": "x", "linha": 1, "odd": 1.9}).status_code == 400
    body = client.get("/api/apostas").json()
    assert body["desempenho"]["geral"]["apostas"] == 1 and body["apostas"][0]["status"] == "pendente"
    assert client.post("/api/apostas/conferir").json() == {"conferidas": {}}   # jogo ainda não aconteceu
    client.delete(f"/api/apostas/{r['id']}")
    assert client.get("/api/apostas").json()["apostas"] == []


def test_comparar_tendencias_e_noticias(client):
    ts = client.get("/api/times").json()
    assert {t["sigla"] for t in ts} == {"AAA", "BBB", "CCC"}
    r = client.get("/api/comparar/times", params={"a": 1, "b": 3, "data": "2026-11-07"}).json()
    assert r["a"]["time"] == "AAA" and r["b"]["time"] == "CCC"
    assert set(client.get("/api/tendencias", params={"data": "2026-11-07"}).json()) >= {"minutos", "defesas"}
    n = client.get("/api/noticias", params={"data": "2026-11-07"}).json()
    assert n["atual"] is None and n["relatorios"] == [] and "retornos" in n


def test_ranking_e_box_score(client):
    r = client.get("/api/ranking", params={"data": "2026-11-07", "min_jogos": 1}).json()
    assert r["jogadores"] and {"pts", "pts_n", "ts_pct", "time"} <= set(r["jogadores"][0])
    p36 = client.get("/api/ranking", params={"data": "2026-11-07", "min_jogos": 1, "por36": True}).json()
    assert p36["jogadores"]
    j = client.get("/api/jogos", params={"data": "2026-11-30"}).json()
    assert j["pedida"] == "2026-11-30" and j["data"] != j["pedida"] and j["jogos"]
    gid = next(x["id"] for x in j["jogos"] if x["tem_box"])
    box = client.get(f"/api/jogo/{gid}").json()
    assert len(box["times"]) == 2 and box["times"][0]["jogadores"]
    assert client.get("/api/jogo/987654").status_code == 404


def test_usuarios_admin_e_sessao(client, monkeypatch):
    monkeypatch.setenv("NBASTATS_PASSWORD", "unica")
    assert client.get("/api/saude").json()["modo"] == "senha"
    assert client.post("/api/admin/usuarios", headers={"X-Senha": "unica"}, json={"login": "a"}).status_code == 409
    # 1º admin exige a senha única
    assert client.post("/api/primeiro-admin", json={"login": "chefe", "senha": "senha-forte"}).status_code == 401
    r = client.post("/api/primeiro-admin", json={"login": "chefe", "senha": "senha-forte", "senha_atual": "unica"})
    adm = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.post("/api/primeiro-admin", json={"login": "x", "senha": "senha-forte"}).status_code == 409
    # agora só com sessão (a senha única deixa de valer)
    assert client.get("/api/meta", headers={"X-Senha": "unica"}).status_code == 401
    meta = client.get("/api/meta", headers=adm).json()
    assert meta["modo"] == "usuarios" and meta["usuario"]["papel"] == "admin"
    novo = client.post("/api/admin/usuarios", headers=adm, json={"login": "coni", "nome": "Coni"}).json()
    login = client.post("/api/login", json={"login": "coni", "senha": novo["senha_provisoria"]}).json()
    coni = {"Authorization": f"Bearer {login['token']}"}
    assert login["usuario"]["trocar_senha"]
    assert client.get("/api/props", headers=coni).status_code == 403  # troca a senha antes
    assert client.post("/api/eu/senha", headers=coni,
                       json={"atual": novo["senha_provisoria"], "nova": "minha-senha"}).json() == {"ok": True}
    assert client.get("/api/ranking", headers=coni, params={"data": "2026-11-07"}).status_code == 200
    assert client.get("/api/admin/usuarios", headers=coni).status_code == 403
    users = client.get("/api/admin/usuarios", headers=adm).json()["usuarios"]
    cid = next(u["id"] for u in users if u["login"] == "coni")
    assert client.patch(f"/api/admin/usuarios/{cid}", headers=adm, json={"ativo": False}).json() == {"ok": True}
    assert client.get("/api/meta", headers=coni).status_code == 401
    acessos = client.get("/api/admin/acessos", headers=adm).json()["acessos"]
    assert {a["login"] for a in acessos} == {"chefe", "coni"}
    assert client.post("/api/login", json={"login": "coni", "senha": "errada"}).status_code == 401
    assert client.delete(f"/api/admin/usuarios/{users[0]['id']}", headers=adm).status_code == 422  # a si mesmo


def test_sistema_e_backup(client, monkeypatch, tmp_path):
    monkeypatch.setattr(api, "BACKUP_DIR", str(tmp_path))
    st = client.get("/api/admin/sistema").json()
    assert {"carga", "backup", "cargas"} <= set(st)
    assert client.post("/api/admin/backup").json()["quantidade"] == 1
    assert "alerta" in client.get("/api/meta").json()
