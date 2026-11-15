"""API JSON do nba-stats (FastAPI) para o site novo.

Só expõe o que `nbastats.metrics` já calcula; nenhuma regra mora aqui.
Rodar: uvicorn nbastats.api.app:app --port 8000
Com o front montado (frontend/dist), serve o site na mesma porta.
"""

from __future__ import annotations

import hmac
import os
import threading
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from nbastats import ajustes as aj
from nbastats import auth, db
from nbastats.config import get_settings
from nbastats.ingest import last_refresh
from nbastats.metrics import aovivo as av
from nbastats.metrics import apostas as ap
from nbastats.metrics import betaniag as bt
from nbastats.metrics import calibracao as cb
from nbastats.metrics import cascata as cs
from nbastats.metrics import comparar as cp
from nbastats.metrics import destaques as dq
from nbastats.metrics import favoritos as fv
from nbastats.metrics import filtros as fl
from nbastats.metrics import historico as hs
from nbastats.metrics import liga as lg
from nbastats.metrics import noticias as nt
from nbastats.metrics import ranking as rk
from nbastats.metrics import sistema as si
from nbastats.metrics.comparar import _season_of
from nbastats.metrics.linhas import prob_over, save_line
from nbastats.metrics.matchup import dvp_table, load_matchup_rules
from nbastats.metrics.painel import day_report
from nbastats.metrics.potencial import load_rules, rank_potenciais
from nbastats.metrics.projecao import load_projection_params

MARKETS = {
    "pts": "Pontos", "reb": "Rebotes", "ast": "Assist.", "pra": "PRA", "pr": "PR", "pa": "PA",
    "ra": "RA", "fg3m": "3FM", "fg3a": "3FA", "fg2m": "2FM", "fg2a": "2FA", "ftm": "FTM",
    "fta": "FTA", "stl": "Roubos", "blk": "Tocos", "turnover": "Turnovers",
    "dd": "Duplo-duplo", "td": "Triplo-duplo",
}
LOG_FIELDS = ("data", "season", "game_id", "opp_id", "em_casa", "resultado", "margem", "descanso",
              "minutes", "usadas", "pts", "reb", "ast", "pra", "pr", "pa", "ra", "fg3m", "fg3a",
              "fg2m", "fg2a", "ftm", "fta", "stl", "blk", "turnover", "dd", "td")

settings = get_settings()


def _warm() -> None:
    """Calcula os destaques de hoje ao subir (a 1ª conta leva ~15 s)."""
    try:
        conn = db.connect(settings.db_path, threads=True)
        inicio(None, None, conn)
        conn.close()
    except Exception:  # base vazia etc.: a 1ª requisição calcula
        pass


@asynccontextmanager
async def lifespan(_app):
    if os.getenv("NBASTATS_AQUECER", "1") == "1":
        threading.Thread(target=_warm, daemon=True).start()
    yield


app = FastAPI(title="nba-stats", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)


_SCHEMA_OK = False


def get_conn():
    global _SCHEMA_OK
    conn = db.connect(settings.db_path, threads=True)
    if not _SCHEMA_OK:  # tabelas novas (ex.: favorites) em bancos antigos
        db.init_db(conn)
        _SCHEMA_OK = True
    try:
        yield conn
    finally:
        conn.close()


PUBLICAS = ("/api/login", "/api/saude", "/api/primeiro-admin")
# com a senha provisória, só dá para ver quem é, trocar a senha e sair
TROCA_SENHA = ("/api/meta", "/api/eu", "/api/eu/senha", "/api/sair")


def _senha_unica() -> str:
    return os.getenv("NBASTATS_PASSWORD", settings.password) or ""


def _token(request: Request) -> str | None:
    h = request.headers.get("authorization", "")
    return h[7:] if h.lower().startswith("bearer ") else None


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@app.middleware("http")
async def acesso(request: Request, call_next):
    """Usuários com sessão (painel de administração) ou, sem usuários, a
    senha única ``NBASTATS_PASSWORD`` no cabeçalho X-Senha."""
    path = request.url.path
    request.state.usuario = None
    if not path.startswith("/api/") or path in PUBLICAS:
        return await call_next(request)
    dep = app.dependency_overrides.get(get_conn, get_conn)()  # respeita o override dos testes
    conn = next(dep) if hasattr(dep, "__next__") else dep
    try:
        modo = auth.modo(conn, _senha_unica())
        if modo == "usuarios":
            u = auth.sessao(conn, _token(request))
            if u is None:
                return JSONResponse({"detail": "login", "modo": modo}, status_code=401)
            if u["trocar_senha"] and path not in TROCA_SENHA:
                return JSONResponse({"detail": "trocar_senha"}, status_code=403)
            if path.startswith("/api/admin/") and u["papel"] != "admin":
                return JSONResponse({"detail": "Só para administradores."}, status_code=403)
            request.state.usuario = u
        elif modo == "senha":
            if not hmac.compare_digest(request.headers.get("x-senha", ""), _senha_unica()):
                return JSONResponse({"detail": "login", "modo": modo}, status_code=401)
    finally:
        if hasattr(dep, "__next__"):
            dep.close()  # roda o finally de get_conn (fecha a conexão)
    return await call_next(request)


def _cfg(betaniag: bool | None) -> dict[str, Any] | None:
    cfg = bt.load_betaniag()
    on = cfg.get("habilitado") if betaniag is None else betaniag
    return cfg if on else None


def _abbr(conn) -> dict[int, str]:
    return {r["id"]: r["abbreviation"] for r in conn.execute("SELECT id, abbreviation FROM teams")}


def _day(d: str | None) -> str:
    return d or date.today().isoformat()


def _player_row(p: dict[str, Any], stat: str, n: int = 20) -> dict[str, Any]:
    """Jogador da lista: só o que a tela usa (sem o histórico completo)."""
    hist = p.get("historico") or []
    side = bt.best_side(p)
    return {
        "player_id": p["player_id"], "jogador": p["jogador"], "time": p["time"],
        "adversario": p["adversario"], "game_id": p["game_id"], "grupo": p.get("grupo"),
        "posicao_est": p.get("posicao_est"), "lesao": p.get("lesao"), "lesao_motivo": p.get("lesao_motivo"),
        "linha": p.get("linha"), "linha_ref": p.get("linha_ref"),
        "odd_over": p.get("odd_over"), "odd_under": p.get("odd_under"),
        "proj": p.get("proj"), "diff": p.get("proj_vs_linha"),
        "p_over": p.get("p_over"), "p_under": p.get("p_under"),
        "ev": None if side is None else side["ev"], "lado": None if side is None else side["lado"],
        "chance": None if side is None else side["chance"],
        "l5": p.get("l5"), "l10": p.get("l10"), "temporada": p.get("temporada"),
        "min_l5": p.get("min_l5"), "min_l10": p.get("min_l10"),
        "usg_l5": p.get("usg_l5"), "usg_l10": p.get("usg_l10"),
        "dvp_rank": p.get("dvp_rank"), "dvp_rec_rank": p.get("dvp_rec_rank"),
        "selo": p.get("selo"), "janelas": p.get("janelas"), "time_id": p.get("time_id"),
        "jogos": p.get("jogos"), "proj_vs_l10": p.get("proj_vs_l10"),
        "encaixe_zonas": p.get("encaixe_zonas"), "com_sem": p.get("com_sem"),
        "fora_ultimo_jogo": p.get("fora_ultimo_jogo"), "real": p.get("real"),
        "valores": [{"data": g["data"], "valor": g[stat], "casa": g["em_casa"]} for g in reversed(hist[:n])],
    }


def _game(g: dict[str, Any]) -> dict[str, Any]:
    j = g["jogo"]
    return {
        "id": j["id"], "casa": j["home"], "fora": j["visitor"], "status": j.get("status"),
        "casa_id": j["home_team_id"], "fora_id": j["visitor_team_id"],
        "placar_casa": j["home_team_score"], "placar_fora": j["visitor_team_score"],
        "margem_esperada": g.get("margem_esperada"), "risco_blowout": g.get("risco_blowout"),
        "ritmo": g.get("ritmo"), "desfalques": g.get("desfalques"),
        "injury_report": g.get("injury_report"), "validacao": g.get("validacao"),
    }


@app.get("/api/saude")
def health(conn=Depends(get_conn)):
    site = aj.load_site()  # público: o login mostra o nome e a cor do site
    return {"ok": True, "modo": auth.modo(conn, _senha_unica()),
            "site": {k: site.get(k) for k in ("nome", "subtitulo", "cor_destaque", "tema_padrao")}}


class Login(BaseModel):
    login: str | None = None
    senha: str


@app.post("/api/login")
def login(body: Login, request: Request, conn=Depends(get_conn)):
    modo = auth.modo(conn, _senha_unica())
    if modo == "usuarios":
        try:
            return {"ok": True, "modo": modo, **auth.entrar(conn, body.login or "", body.senha, _ip(request),
                                                            request.headers.get("user-agent"))}
        except auth.AcessoNegado as exc:
            raise HTTPException(401, str(exc))
    if modo == "senha" and not hmac.compare_digest(body.senha, _senha_unica()):
        raise HTTPException(401, "Senha incorreta")
    return {"ok": True, "modo": modo}


class PrimeiroAdmin(BaseModel):
    login: str
    nome: str | None = None
    senha: str
    senha_atual: str | None = None  # a senha única, se houver


@app.post("/api/primeiro-admin")
def first_admin(body: PrimeiroAdmin, request: Request, conn=Depends(get_conn)):
    """Cria o 1º administrador. Só funciona enquanto não há usuários; com
    senha única, exige a senha única (quem já tinha acesso)."""
    modo = auth.modo(conn, _senha_unica())
    if modo == "usuarios":
        raise HTTPException(409, "Já existe administrador.")
    if modo == "senha" and not hmac.compare_digest(body.senha_atual or "", _senha_unica()):
        raise HTTPException(401, "Senha do site incorreta")
    try:
        auth.criar_usuario(conn, body.login, body.senha, body.nome, papel="admin")
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return {"ok": True, **auth.entrar(conn, body.login, body.senha, _ip(request), request.headers.get("user-agent"))}


@app.post("/api/sair")
def logout(request: Request, conn=Depends(get_conn)):
    if (tok := _token(request)):
        auth.sair(conn, tok)
    return {"ok": True}


@app.get("/api/eu")
def me(request: Request):
    return {"usuario": request.state.usuario}


class TrocaSenha(BaseModel):
    atual: str
    nova: str


@app.post("/api/eu/senha")
def change_password(body: TrocaSenha, request: Request, conn=Depends(get_conn)):
    u = request.state.usuario
    if u is None:
        raise HTTPException(400, "Sem usuário (modo de senha única).")
    try:
        auth.trocar_propria_senha(conn, u["id"], body.atual, body.nova)
    except auth.AcessoNegado as exc:
        raise HTTPException(401, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return {"ok": True}


@app.get("/api/meta")
def meta(request: Request, conn=Depends(get_conn)):
    cfg = bt.load_betaniag()
    return {"mercados": MARKETS, "hoje": date.today().isoformat(), "atualizado": last_refresh(conn),
            "betaniag": bool(cfg.get("habilitado")), "esportes": bt.active_sports(cfg),
            "modo": auth.modo(conn, _senha_unica()), "usuario": request.state.usuario, "lavada": _lavada(),
            "etiquetas": ap.load_bet_config().get("etiquetas") or [], "site": aj.load_site(),
            "alerta": si.status_carga(conn)["alerta"]}


@app.get("/api/props")
def props(data: str | None = None, mercado: str = "pts", betaniag: bool | None = None,
          conn=Depends(get_conn)):
    if mercado not in MARKETS:
        raise HTTPException(400, "mercado inválido")
    day = _day(data)
    report = day_report(conn, day, mercado, last_refresh(conn), _cfg(betaniag))
    if day == date.today().isoformat():  # foto antes do jogo, para a calibração pública
        _guardar_previsoes(conn, day, mercado, report)
    season = report[0]["jogo"]["season"] if report else None
    return {
        "data": day, "mercado": mercado,
        "temporada": None if season is None else hs.season_label(season),
        "anterior": None if season is None else hs.season_label(season - 1),
        "jogos": [_game(g) for g in report],
        "jogadores": [_player_row(p, mercado) for g in report for p in g["jogadores"]],
    }


@app.get("/api/inicio")
def inicio(data: str | None = None, betaniag: bool | None = None, conn=Depends(get_conn)):
    day = _day(data)
    cfg = _cfg(betaniag)
    version = last_refresh(conn)
    reports = {s: day_report(conn, day, s, version, cfg) for s in dq.HOME_MARKETS}
    if not reports["pts"]:
        return {"data": day, "jogos": [], "oportunidades": {"com_odd": [], "sem_odd": []}, "em_alta": []}
    mins = (bt.load_betaniag().get("destaques") or {}).get("min_media") or dq.MIN_MEDIA
    opp = dq.opportunities(reports, cfg, min_media=mins)
    for k in opp:
        for o in opp[k]:
            o["valores"] = [g[o["mercado"]] for g in reversed(o.pop("historico")[:10])]
    return {"data": day, "jogos": dq.game_cards(reports, cfg, mins), "oportunidades": opp,
            "em_alta": dq.rising(reports["pra"])}


@app.get("/api/jogador/{player_id}")
def jogador(player_id: int, data: str | None = None, mercado: str = "pts",
            betaniag: bool | None = None, conn=Depends(get_conn)):
    day = _day(data)
    cfg = _cfg(betaniag)
    report = day_report(conn, day, mercado, last_refresh(conn), cfg)
    found = next(((g, p) for g in report for p in g["jogadores"] if p["player_id"] == player_id), None)
    if not found:
        raise HTTPException(404, "Jogador sem jogo/projeção nesta data")
    g, p = found
    abbr = _abbr(conn)
    season = g["jogo"]["season"]
    log = p.get("historico_total") or []
    medias = hs.season_averages(log, season, ("minutes", "pts", "reb", "ast", "pra", "fg3m",
                                              "stl", "blk", mercado))
    out = _player_row(p, mercado)
    out.update({
        "jogo": _game(g), "temporada_atual": season,
        "rotulos": {"atual": hs.season_label(season), "anterior": hs.season_label(season - 1)},
        "proj_detalhe": p.get("proj_detalhe"), "com_sem": p.get("com_sem"), "zonas": p.get("zonas"),
        "adversario_id": p.get("adversario_id"),
        "medias": medias,
        "log": [{**{k: x.get(k) for k in LOG_FIELDS}, "adv": abbr.get(x["opp_id"], ""),
                 # cor de cada valor: contra a média dele; o mercado, contra a linha
                 "faixas": {k: hs.band(x[k], p.get("linha") if k == mercado else medias.get(k))
                            for k in medias}} for x in log],
        "checklist": bt.checklist(p, cfg, g.get("validacao")) if cfg else None,
        "minutos": hs.minutes_profile(log, season),
        # playoffs ficam fora das janelas e da projeção; aparecem como janela própria
        "playoffs": [{**{k: x.get(k) for k in LOG_FIELDS}, "adv": abbr.get(x["opp_id"], ""),
                      "faixas": {k: hs.band(x[k], p.get("linha") if k == mercado else medias.get(k)) for k in medias}}
                     for x in hs.player_logs(conn, [player_id], day, playoffs=True).get(player_id, [])],
    })
    return out


@app.get("/api/chance")
def chance(mercado: str, proj: float, linha: float):
    """Chance de over para uma projeção e linha (usada no 'e se jogar X minutos')."""
    market = (load_projection_params().get("mercados") or {}).get(mercado) or {}
    po = prob_over(proj, linha, market)
    return {"p_over": po, "p_under": None if po is None else 1 - po}


class Linha(BaseModel):
    data: str
    player_id: int
    mercado: str
    linha: float | None = None
    odd_over: float | None = None
    odd_under: float | None = None


@app.put("/api/linhas")
def put_line(body: Linha, conn=Depends(get_conn)):
    if body.mercado not in MARKETS:
        raise HTTPException(400, "mercado inválido")
    save_line(conn, body.data, body.player_id, body.mercado, body.linha, body.odd_over, body.odd_under)
    return {"ok": True}


@app.put("/api/linhas/lote")
def put_lines(body: list[Linha], conn=Depends(get_conn)):
    for b in body:
        if b.mercado not in MARKETS:
            raise HTTPException(400, f"mercado inválido: {b.mercado}")
    for b in body:
        save_line(conn, b.data, b.player_id, b.mercado, b.linha, b.odd_over, b.odd_under)
    return {"ok": True, "salvas": len(body)}


@app.get("/api/dvp")
def dvp(data: str | None = None, mercado: str = "pts", recente: bool = False, conn=Depends(get_conn)):
    day = _day(data)
    season = _season_of(conn, day)
    if season is None:
        return {"grupos": [], "linhas": []}
    rules = load_matchup_rules()
    rows = dvp_table(conn, season, day, mercado, rules, recent=recente)
    groups = sorted(set((rules.get("posicoes") or {}).values()))
    playing = {r["abbreviation"] for r in conn.execute(
        "SELECT t.abbreviation FROM games g JOIN teams t ON t.id IN (g.home_team_id, g.visitor_team_id)"
        " WHERE g.date = ?", (day,))}
    return {"grupos": groups, "dias_recente": rules.get("dvp_recente_dias", 15),
            "linhas": [{**r, "joga_hoje": r["time"] in playing} for r in rows]}


@app.get("/api/potenciais")
def potenciais(data: str | None = None, conn=Depends(get_conn)):
    day = _day(data)
    season = _season_of(conn, day)
    if season is None:
        return {"regras": {}, "jogadores": []}
    rules = load_rules()
    playing = {r["id"] for r in conn.execute(
        "SELECT p.id FROM players p JOIN games g ON p.team_id IN (g.home_team_id, g.visitor_team_id)"
        " WHERE g.date = ?", (day,))}
    rows = rank_potenciais(conn, season, rules)
    return {"regras": rules, "jogadores": [{**r, "joga_hoje": r["player_id"] in playing} for r in rows]}


class Favorito(BaseModel):
    tipo: str
    id: int
    nome: str | None = None


@app.get("/api/favoritos")
def favorites(request: Request, conn=Depends(get_conn)):
    return fv.list_favorites(conn, _uid(request))


@app.post("/api/favoritos")
def add_fav(body: Favorito, request: Request, conn=Depends(get_conn)):
    try:
        fv.add_favorite(conn, body.tipo, body.id, body.nome, _uid(request))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return fv.list_favorites(conn, _uid(request))


@app.delete("/api/favoritos/{tipo}/{entity_id}")
def del_fav(tipo: str, entity_id: int, request: Request, conn=Depends(get_conn)):
    try:
        fv.remove_favorite(conn, tipo, entity_id, _uid(request))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return fv.list_favorites(conn, _uid(request))


# ---------- apostas ----------

class Aposta(BaseModel):
    data: str
    player_id: int
    mercado: str
    lado: str
    linha: float
    odd: float
    unidades: float = 1.0
    casa: str | None = None
    obs: str | None = None
    etiquetas: list[str] = []
    confirmar: bool = False  # registra mesmo passando dos limites do jogo responsável


def _uid(request: Request) -> int | None:
    u = request.state.usuario
    return u["id"] if u else None


@app.get("/api/apostas")
def bets(request: Request, status: str | None = None, todas: bool = False, conn=Depends(get_conn)):
    """Com login, mostra as apostas da pessoa (``todas=true`` mostra as de todos)."""
    cfg = ap.load_bet_config()
    uid = None if todas else _uid(request)
    return {"apostas": ap.list_bets(conn, status=status, user_id=uid), "desempenho": ap.performance(conn, user_id=uid),
            "limites": ap.limits(conn, date.today().isoformat(), cfg, _uid(request)),
            "por_usuario": request.state.usuario is not None,
            "config": {k: cfg.get(k) for k in ("valor_unidade", "moeda", "unidades", "etiquetas")}}


@app.post("/api/apostas")
def add_bet(body: Aposta, request: Request, conn=Depends(get_conn)):
    """Registra com a fotografia do momento: chance e projeção calculadas agora.
    Passando dos limites do jogo responsável, responde 409 com os avisos; o
    site pergunta e reenvia com ``confirmar``."""
    if body.mercado not in MARKETS:
        raise HTTPException(400, "mercado inválido")
    cfg = ap.load_bet_config()
    lim = ap.limits(conn, body.data, cfg, _uid(request), extra_units=body.unidades)
    if lim["avisos"] and not body.confirmar:
        return JSONResponse({"detail": " ".join(lim["avisos"]), "avisos": lim["avisos"], "limites": lim}, status_code=409)
    report = day_report(conn, body.data, body.mercado, last_refresh(conn), None)
    p = next((p for g in report for p in g["jogadores"] if p["player_id"] == body.player_id), None)
    prob = proj = None
    if p is not None:
        market = (load_projection_params().get("mercados") or {}).get(body.mercado) or {}
        po = prob_over(p.get("proj"), body.linha, market)
        prob = None if po is None else (po if body.lado == "over" else 1 - po)
        proj = p.get("proj")
    try:
        bet_id = ap.add_bet(conn, day=body.data, player_id=body.player_id, market=body.mercado, side=body.lado,
                            line=body.linha, odd=body.odd, units=body.unidades,
                            game_id=p.get("game_id") if p else None, bookmaker=body.casa, prob=prob, proj=proj,
                            note=body.obs, tags=body.etiquetas, user_id=_uid(request))
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"id": bet_id, "chance": prob, "avisos": lim["avisos"]}


@app.delete("/api/apostas/{bet_id}")
def del_bet(bet_id: int, conn=Depends(get_conn)):
    ap.delete_bet(conn, bet_id)
    return {"ok": True}


@app.post("/api/apostas/conferir")
def settle(conn=Depends(get_conn)):
    return {"conferidas": ap.settle_bets(conn, ap.load_bet_config())}


# ---------- comparar e notícias ----------

@app.get("/api/times")
def teams(conn=Depends(get_conn)):
    return [dict(r) for r in conn.execute(
        "SELECT id, abbreviation AS sigla, full_name AS nome FROM teams WHERE abbreviation IS NOT NULL ORDER BY abbreviation")]


@app.get("/api/comparar/times")
def compare_teams(a: int, b: int, data: str | None = None, conn=Depends(get_conn)):
    res = cp.team_compare(conn, _day(data), a, b, load_matchup_rules())
    if not res:
        raise HTTPException(404, "Sem dados para a data")
    return res


@app.get("/api/tendencias")
def trends(data: str | None = None, conn=Depends(get_conn)):
    return cp.trends(conn, _day(data), load_matchup_rules())


@app.get("/api/lesoes")
@app.get("/api/noticias", include_in_schema=False)  # nome antigo
def news(data: str | None = None, conn=Depends(get_conn)):
    """Mudanças entre os dois últimos injury reports e quem pode voltar."""
    day = _day(data)
    return {**nt.changes(conn, day), "relatorios": nt.reports_for(conn, day), "retornos": nt.returns(conn, day)}


@app.post("/api/atualizar")
def update(forcar: bool = False, conn=Depends(get_conn)):
    """Estatísticas recentes, agenda e injury report (como o botão do Streamlit)."""
    from nbastats.ingest import refresh
    from nbastats.sources import build_injury_source, build_news_source, build_source
    try:
        res = refresh(conn, build_source(settings.fonte, settings), build_injury_source(), force=forcar,
                      news_source=build_news_source())
    except Exception as exc:
        raise HTTPException(502, f"Falhou: {exc}")
    ap.settle_bets(conn, ap.load_bet_config())
    return {**res, "atualizado": last_refresh(conn)}


def _guardar_previsoes(conn, day: str, mercado: str, report) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    try:
        cb.save_predictions(conn, day, mercado, report,
                            datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None), bt.tipoff)
    except Exception:  # a foto é um extra; nunca derruba a página
        pass


class Filtro(BaseModel):
    nome: str
    params: dict[str, Any]


@app.get("/api/liga")
def league(data: str | None = None, conn=Depends(get_conn)):
    """Última rodada, destaques, classificação, líderes, manchetes e transações."""
    return lg.overview(conn, _day(data))


@app.get("/api/filtros")
def filters(request: Request, conn=Depends(get_conn)):
    return {"filtros": fl.list_filters(conn, _uid(request))}


@app.post("/api/filtros")
def save_filter(body: Filtro, request: Request, conn=Depends(get_conn)):
    try:
        fl.save_filter(conn, body.nome, body.params, _uid(request))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return {"filtros": fl.list_filters(conn, _uid(request))}


@app.delete("/api/filtros/{filter_id}")
def delete_filter(filter_id: int, request: Request, conn=Depends(get_conn)):
    fl.delete_filter(conn, filter_id, _uid(request))
    return {"filtros": fl.list_filters(conn, _uid(request))}


@app.get("/api/cascata")
def cascade(data: str | None = None, mercado: str = "pra", conn=Depends(get_conn)):
    """Quem ganha com cada desfalque do dia; novidades do último injury report primeiro."""
    if mercado not in MARKETS:
        raise HTTPException(400, "mercado inválido")
    day = _day(data)
    report = day_report(conn, day, mercado, last_refresh(conn), None)
    novos = [c["jogador"] for c in nt.changes(conn, day)["mudancas"]
             if c["tipo"] in ("entrou", "piorou", "lista") and c["agora"] in ("Out", "Doubtful")]
    return {"data": day, "mercado": mercado, "desfalques": cs.cascata(report, novos)}


@app.get("/api/calibracao")
def calibration(desde: str | None = None, conn=Depends(get_conn)):
    return cb.report(conn, desde)


# ---------- ranking e jogo (box score) ----------

@app.get("/api/ranking")
def ranking_route(data: str | None = None, janela: int = Query(10, ge=1, le=82), min_jogos: int = Query(5, ge=1),
                  por36: bool = False, playoffs: bool = False, sem_lavadas: bool = False, conn=Depends(get_conn)):
    season = _season_of(conn, _day(data))
    corte = _lavada() if sem_lavadas else None
    return {"temporada": season, "janela": janela, "lavada": _lavada(),
            "jogadores": rk.ranking(conn, season, janela, min_jogos, por36, playoffs, corte)}


def _lavada() -> int:
    """Diferença final a partir da qual o jogo conta como lavada (config/projecao.yaml)."""
    return int((load_projection_params().get("lavada") or {}).get("margem", 20))


@app.get("/api/jogos")
def games_route(data: str | None = None, conn=Depends(get_conn)):
    """Jogos de uma data; sem jogos com box score nela, a última data que tem."""
    day = _day(data)
    jogos = rk.games_by_date(conn, day)
    if not any(j["tem_box"] for j in jogos):
        last = rk.last_game_date(conn, day)
        if last and last != day:
            return {"data": last, "pedida": day, "jogos": rk.games_by_date(conn, last)}
    return {"data": day, "pedida": day, "jogos": jogos}


@app.get("/api/jogo/{game_id}")
def game_route(game_id: int, conn=Depends(get_conn)):
    box = rk.boxscore_game(conn, game_id)
    if box is None:
        raise HTTPException(404, "Jogo não encontrado.")
    return box


# ---------- administração ----------

BACKUP_DIR = os.getenv("NBASTATS_BACKUP_DIR", str(Path(settings.db_path).parent / "backup"))


class NovoUsuario(BaseModel):
    login: str
    nome: str | None = None
    papel: str = "usuario"
    expira_em: str | None = None


class MudaUsuario(BaseModel):
    nome: str | None = None
    papel: str | None = None
    ativo: bool | None = None
    expira_em: str | None = None
    mudar_validade: bool = False  # expira_em só é aplicado com isto (None = sem validade)


def _admin_call(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.get("/api/admin/usuarios")
def admin_users(conn=Depends(get_conn)):
    return {"usuarios": auth.listar_usuarios(conn), "papeis": auth.PAPEIS}


@app.post("/api/admin/usuarios")
def admin_create(body: NovoUsuario, conn=Depends(get_conn)):
    """Cria com senha provisória (mostrada uma vez ao admin; troca no 1º acesso)."""
    if auth.modo(conn, _senha_unica()) != "usuarios":
        raise HTTPException(409, "Crie primeiro o administrador.")
    senha = auth.gerar_senha()
    uid = _admin_call(auth.criar_usuario, conn, body.login, senha, body.nome, body.papel, body.expira_em, True)
    return {"id": uid, "senha_provisoria": senha}


@app.patch("/api/admin/usuarios/{user_id}")
def admin_update(user_id: int, body: MudaUsuario, conn=Depends(get_conn)):
    _admin_call(auth.alterar_usuario, conn, user_id, nome=body.nome, papel=body.papel, ativo=body.ativo,
                expira_em=body.expira_em if body.mudar_validade else False)
    return {"ok": True}


@app.post("/api/admin/usuarios/{user_id}/senha")
def admin_reset(user_id: int, conn=Depends(get_conn)):
    senha = auth.gerar_senha()
    _admin_call(auth.definir_senha, conn, user_id, senha, True)
    auth.encerrar_sessoes(conn, user_id)
    return {"senha_provisoria": senha}


@app.post("/api/admin/usuarios/{user_id}/sair")
def admin_kick(user_id: int, conn=Depends(get_conn)):
    return {"encerradas": auth.encerrar_sessoes(conn, user_id)}


@app.delete("/api/admin/usuarios/{user_id}")
def admin_delete(user_id: int, request: Request, conn=Depends(get_conn)):
    if request.state.usuario and request.state.usuario["id"] == user_id:
        raise HTTPException(422, "Você não pode apagar o próprio usuário.")
    _admin_call(auth.apagar_usuario, conn, user_id)
    return {"ok": True}


class Ajuste(BaseModel):
    arquivo: str
    caminho: str
    valor: Any = None


def _bases() -> dict[str, dict[str, Any]]:
    from nbastats.metrics.matchup import load_matchup_rules as mr
    return {"site": {**aj.SITE_PADRAO, **_site_base()},
            "apostas": ap.load_bet_config(ajustes=False), "alertas": _alert_cfg(False),
            "betaniag": bt.load_betaniag(ajustes=False), "projecao": load_projection_params(ajustes=False),
            "matchup": mr(ajustes=False), "potencial": load_rules(ajustes=False)}


def _site_base() -> dict[str, Any]:
    import yaml as _y
    p = Path("config/site.yaml")
    return (_y.safe_load(p.read_text(encoding="utf-8")) or {}) if p.exists() else {}


def _alert_cfg(ajustes: bool = True) -> dict[str, Any]:
    from nbastats.metrics.alertas import load_alert_config
    return load_alert_config(ajustes=ajustes)


def _limpar_caches() -> None:
    from nbastats.metrics import painel
    painel._CACHE.clear()


@app.get("/api/admin/config")
def admin_config():
    return {"secoes": aj.painel(_bases())}


@app.put("/api/admin/config")
def admin_config_set(body: Ajuste):
    try:
        v = aj.definir(body.arquivo, body.caminho, body.valor)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    _limpar_caches()
    return {"ok": True, "valor": v}


@app.delete("/api/admin/config")
def admin_config_reset(arquivo: str, caminho: str):
    try:
        aj.restaurar(arquivo, caminho)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    _limpar_caches()
    return {"ok": True}


@app.get("/api/admin/acessos")
def admin_log(limite: int = Query(100, le=500), conn=Depends(get_conn)):
    return {"acessos": auth.acessos(conn, limite)}


@app.get("/api/admin/sistema")
def admin_system(conn=Depends(get_conn)):
    db_file = Path(settings.db_path)
    syncs = [dict(r) for r in conn.execute(
        "SELECT kind, started_at, finished_at, status, games, stats, substr(error, 1, 200) AS error"
        " FROM sync_log ORDER BY id DESC LIMIT 15")]
    from nbastats.metrics.alertas import load_alert_config
    tg = bool(os.getenv("NBASTATS_TELEGRAM_TOKEN") and os.getenv("NBASTATS_TELEGRAM_CHAT"))
    return {"carga": si.status_carga(conn), "backup": si.status_backup(BACKUP_DIR), "cargas": syncs,
            "alertas": {"habilitado": bool(load_alert_config().get("habilitado")), "telegram": tg},
            "banco_mb": round(db_file.stat().st_size / 1e6, 1) if db_file.exists() else None}


@app.post("/api/admin/backup")
def admin_backup(conn=Depends(get_conn)):
    dest = si.backup(conn, BACKUP_DIR)
    return {"arquivo": dest.name, **si.status_backup(BACKUP_DIR)}


# ---------- ao vivo ----------

_LIVE: dict[str, Any] = {"t": 0.0, "dados": None}
LIVE_TTL = 20  # segundos: o placar da NBA atualiza a cada ~10-20 s


def get_live():
    from nbastats.sources.nba_live import NbaLiveSource
    return NbaLiveSource()


def _live_games(source) -> list[dict[str, Any]]:
    import time
    if _LIVE["dados"] is None or time.time() - _LIVE["t"] > LIVE_TTL:
        _LIVE["dados"], _LIVE["t"] = source.live_games(), time.time()
    return _LIVE["dados"]


@app.get("/api/aovivo")
def ao_vivo(mercado: str = "pts", alvo: str = "linha", conn=Depends(get_conn), live=Depends(get_live)):
    if mercado not in MARKETS or alvo not in ("linha", "media"):
        raise HTTPException(400, "mercado ou alvo inválido")
    try:
        games = _live_games(live)
    except Exception as exc:  # NBA fora do ar, rede etc.
        raise HTTPException(502, f"Placar ao vivo indisponível: {exc}")
    if not games:
        return {"data": None, "jogos": [], "destaques": []}
    day = games[0]["data"]
    report = day_report(conn, day, mercado, last_refresh(conn), None)
    out = av.live_report(games, av.pre_from_report(report), mercado, load_projection_params(), alvo)
    top = [{**p, "jogo": f"{g['fora']} @ {g['casa']}", "game_id": g["game_id"]}
           for g in out if g["status"] == 2 for p in g["jogadores"]
           if p["status"] in ("a caminho", "precisa acelerar")]
    top.sort(key=lambda r: r["chance"] or 0, reverse=True)
    return {"data": day, "jogos": out, "destaques": top[:15], "atualizado_ha": round(__import__("time").time() - _LIVE["t"])}


# ---------- site (frontend/dist), se montado ----------

DIST = Path(os.getenv("NBASTATS_FRONT", "frontend/dist"))
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
