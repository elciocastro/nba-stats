"""API: contrato das rotas com uma base pequena (a mesma da fase 5)."""

import pytest
from fastapi.testclient import TestClient
from test_fase5 import base  # noqa: F401  (fixture: liga pequena com 2 temporadas)

from nbastats import db
from nbastats.api import app as api


class AoVivoFalso:
    def __init__(self, jogos):
        self.jogos = jogos

    def live_games(self):
        return self.jogos


@pytest.fixture
def client(base, monkeypatch):  # noqa: F811 (fixture importada de test_fase5)
    shared = db.connect(":memory:", threads=True)
    base.commit()
    base.backup(shared)
    api.app.dependency_overrides[api.get_conn] = lambda: shared
    api._LIVE.update(t=0.0, dados=None)
    api.app.dependency_overrides[api.get_live] = lambda: AoVivoFalso([])
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
    assert d["playoffs"] == []
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


def test_aposta_com_etiqueta_e_limite(client, monkeypatch):
    from nbastats.metrics import apostas as ap
    monkeypatch.setattr(ap, "load_bet_config", lambda *a: {"jogo_responsavel": {"limite_unidades_dia": 1},
                                                           "etiquetas": ["H2H"]})
    q = {"data": "2026-11-07", "mercado": "pts"}
    pid = client.get("/api/props", params=q).json()["jogadores"][0]["player_id"]
    corpo = {**q, "player_id": pid, "lado": "over", "linha": 10.5, "odd": 1.9, "etiquetas": ["H2H"]}
    assert client.post("/api/apostas", json={**corpo, "unidades": 1}).status_code == 200
    r = client.post("/api/apostas", json={**corpo, "unidades": 1})
    assert r.status_code == 409 and "limite do dia" in r.json()["avisos"][0]
    assert client.post("/api/apostas", json={**corpo, "unidades": 1, "confirmar": True}).status_code == 200
    body = client.get("/api/apostas").json()
    assert body["apostas"][0]["etiquetas"] == ["H2H"] and body["config"]["etiquetas"] == ["H2H"]
    assert "H2H" in body["desempenho"]["etiqueta"]


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


def test_calibracao(client):
    r = client.get("/api/calibracao").json()
    assert {"backtest", "previsoes", "apostas"} <= set(r)
    assert r["previsoes"]["geral"]["n"] == 0


def test_cascata(client):
    r = client.get("/api/cascata", params={"data": "2026-11-07"}).json()
    assert r["mercado"] == "pra" and isinstance(r["desfalques"], list)
    assert client.get("/api/cascata", params={"mercado": "x"}).status_code == 400


def test_filtros_salvos(client):
    r = client.post("/api/filtros", json={"nome": "PRA 60", "params": {"mercado": "pra", "chance_min": 60}}).json()
    fid = r["filtros"][0]["id"]
    assert client.get("/api/filtros").json()["filtros"][0]["params"]["chance_min"] == 60
    assert client.delete(f"/api/filtros/{fid}").json()["filtros"] == []
    assert client.post("/api/filtros", json={"nome": "", "params": {}}).status_code == 422


def test_configuracoes_pela_administracao(client):
    secoes = {s["arquivo"]: s for s in client.get("/api/admin/config").json()["secoes"]}
    assert {"site", "apostas", "alertas", "projecao"} <= set(secoes)
    r = client.put("/api/admin/config", json={"arquivo": "site", "caminho": "nome", "valor": "Teste"})
    assert r.json()["valor"] == "Teste" and client.get("/api/meta").json()["site"]["nome"] == "Teste"
    assert client.put("/api/admin/config", json={"arquivo": "site", "caminho": "cor_destaque", "valor": "x"}).status_code == 422
    assert client.put("/api/admin/config", json={"arquivo": "projecao", "caminho": "mercados", "valor": 1}).status_code == 422
    campo = next(c for c in client.get("/api/admin/config").json()["secoes"][0]["campos"] if c["caminho"] == "nome")
    assert campo["mudado"] and campo["valor"] == "Teste"
    client.delete("/api/admin/config", params={"arquivo": "site", "caminho": "nome"})
    assert client.get("/api/meta").json()["site"]["nome"] != "Teste"


def test_favoritos_por_usuario():
    from nbastats import db as _db
    from nbastats.metrics import favoritos as fv
    c = _db.connect(":memory:"); _db.init_db(c)
    fv.add_favorite(c, "jogador", 1, "Ana")                 # lista compartilhada (sem login)
    assert [f["entity_id"] for f in fv.list_favorites(c, 7)["jogador"]] == [1]   # 1º acesso copia
    fv.add_favorite(c, "jogador", 2, "Beto", user_id=7)
    fv.remove_favorite(c, "jogador", 1, user_id=7)
    assert [f["entity_id"] for f in fv.list_favorites(c, 7)["jogador"]] == [2]
    assert [f["entity_id"] for f in fv.list_favorites(c)["jogador"]] == [1]      # compartilhada intacta
    assert [f["entity_id"] for f in fv.list_favorites(c, 8)["jogador"]] == [1]   # outra pessoa
    fv.remove_favorite(c, "jogador", 2, user_id=7)
    assert fv.list_favorites(c, 7)["jogador"] == []                              # não recopia
    assert {f["entity_id"] for f in fv.list_favorites(c, todos=True)["jogador"]} == {1}


def test_liga_e_lesoes(client):
    d = client.get("/api/liga", params={"data": "2026-11-07"}).json()
    assert {"rodada", "resultados", "destaques", "classificacao", "lideres", "noticias", "transacoes"} <= set(d)
    assert d["rodada"] and d["resultados"] and set(d["classificacao"]) == {"East", "West"}
    les = client.get("/api/lesoes", params={"data": "2026-11-07"}).json()
    assert les == client.get("/api/noticias", params={"data": "2026-11-07"}).json()


def test_jogador_sem_jogo_na_data_mostra_o_perfil(client):
    # 2026-12-25: nenhum jogo na base pequena
    d = client.get("/api/jogador/10", params={"data": "2026-12-25", "mercado": "pts"}).json()
    assert d["sem_jogo"] is True and d["jogador"] == "Ana" and d["time"] == "AAA"
    assert d["proj"] is None and d["jogo"] is None and d["log"] and d["janelas"]
    assert d["linha_ref"] is True and d["linha"] == int(d["l10"]) + 0.5
    assert d["proximo_jogo"] is None


def test_perfil_usa_a_transacao_mais_recente(base):  # noqa: F811
    from nbastats.metrics import historico as hs
    base.execute("INSERT INTO transactions (id, date, tipo, team_id, player_id, descricao)"
                 " VALUES ('t1', '2026-12-01', 'Signing', 3, 10, 'x')")
    p = hs.player_profile(base, 10, "2026-12-25", "pts")
    assert p["time_id"] == 3 and p["time"] == "CCC" and p["ultima_transacao"]["tipo"] == "Signing"
    base.execute("INSERT INTO transactions (id, date, tipo, team_id, player_id, descricao)"
                 " VALUES ('t2', '2026-12-10', 'Waive', 3, 10, 'x')")
    p = hs.player_profile(base, 10, "2026-12-25", "pts")
    assert p["sem_time"] is True and p["time"] is None and p["proximo_jogo"] is None


def _ao_vivo(game_id, casa_id, fora_id, day="2026-11-07"):
    return {"game_id": game_id, "data": day, "status": 2, "status_texto": "Q3 5:12", "periodo": 3, "relogio_seg": 312,
            "casa": "AAA", "fora": "BBB", "casa_id": casa_id, "fora_id": fora_id, "placar_casa": 70, "placar_fora": 66,
            "jogadores": [{"player_id": 10, "team_id": casa_id, "nome": "Ana", "minutos": 24.0, "pts": 18, "reb": 4,
                           "ast": 3, "fg3m": 2, "fg3a": 5, "ftm": 2, "fta": 2, "fgm": 7, "fga": 12, "stl": 1, "blk": 0,
                           "turnover": 1, "faltas": 2, "em_quadra": True},
                          {"player_id": 20, "team_id": fora_id, "nome": "Caio", "minutos": 0.0, "pts": 0, "reb": 0,
                           "ast": 0, "fg3m": 0, "fg3a": 0, "ftm": 0, "fta": 0, "fgm": 0, "fga": 0, "stl": 0, "blk": 0,
                           "turnover": 0, "faltas": 0}]}


def test_jogos_ao_vivo_e_por_time(client, base):  # noqa: F811
    from nbastats.metrics import ranking as rk
    g = base.execute("SELECT id, home_team_id, visitor_team_id FROM games WHERE date = '2026-11-07'").fetchone()
    if g is None:  # a base pequena: usa o jogo mais recente
        g = base.execute("SELECT id, home_team_id, visitor_team_id, date FROM games ORDER BY date DESC").fetchone()
    vivo = _ao_vivo(g["id"], g["home_team_id"], g["visitor_team_id"])
    jogos = rk.overlay_live([{"id": g["id"], "status": "8:00 pm", "placar_casa": None, "placar_fora": None,
                              "tem_box": False}], [vivo])
    assert jogos[0]["ao_vivo"] and jogos[0]["placar_casa"] == 70 and jogos[0]["tem_box"]
    box = rk.live_boxscore(vivo)
    assert box["ao_vivo"] and box["times"][1]["jogadores"][0]["pra"] == 25 and box["times"][0]["nao_jogaram"] == ["Caio"]

    tid = g["home_team_id"]
    t = client.get(f"/api/jogos/time/{tid}", params={"data": "2026-11-07"}).json()
    assert t["jogos"] and {"adversario", "pro", "contra", "resultado"} <= set(t["jogos"][0])
    assert t["v"] + t["d"] == sum(1 for j in t["jogos"] if j["resultado"] and not j["playoffs"])
    assert client.get("/api/jogos/time/999999").status_code == 404
