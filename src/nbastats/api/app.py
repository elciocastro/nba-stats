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

from nbastats import db
from nbastats.config import get_settings
from nbastats.ingest import last_refresh
from nbastats.metrics import betaniag as bt
from nbastats.metrics import aovivo as av
from nbastats.metrics import destaques as dq
from nbastats.metrics import favoritos as fv
from nbastats.metrics.comparar import _season_of
from nbastats.metrics.matchup import dvp_table, load_matchup_rules
from nbastats.metrics.potencial import load_rules, rank_potenciais
from nbastats.metrics import historico as hs
from nbastats.metrics.linhas import prob_over, save_line
from nbastats.metrics.painel import day_report
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


@app.middleware("http")
async def password(request: Request, call_next):
    """Senha única (NBASTATS_PASSWORD) no cabeçalho X-Senha para /api/*."""
    pw = os.getenv("NBASTATS_PASSWORD", settings.password)
    path = request.url.path
    if pw and path.startswith("/api/") and path not in ("/api/login", "/api/saude"):
        sent = request.headers.get("x-senha", "")
        if not hmac.compare_digest(sent, pw):
            return JSONResponse({"detail": "senha"}, status_code=401)
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
def health():
    return {"ok": True}


class Login(BaseModel):
    senha: str


@app.post("/api/login")
def login(body: Login):
    pw = os.getenv("NBASTATS_PASSWORD", settings.password)
    if pw and not hmac.compare_digest(body.senha, pw):
        raise HTTPException(401, "Senha incorreta")
    return {"ok": True}


@app.get("/api/meta")
def meta(conn=Depends(get_conn)):
    cfg = bt.load_betaniag()
    return {"mercados": MARKETS, "hoje": date.today().isoformat(), "atualizado": last_refresh(conn),
            "betaniag": bool(cfg.get("habilitado")), "esportes": bt.active_sports(cfg)}


@app.get("/api/props")
def props(data: str | None = None, mercado: str = "pts", betaniag: bool | None = None,
          conn=Depends(get_conn)):
    if mercado not in MARKETS:
        raise HTTPException(400, "mercado inválido")
    day = _day(data)
    report = day_report(conn, day, mercado, last_refresh(conn), _cfg(betaniag))
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
def favorites(conn=Depends(get_conn)):
    return fv.list_favorites(conn)


@app.post("/api/favoritos")
def add_fav(body: Favorito, conn=Depends(get_conn)):
    try:
        fv.add_favorite(conn, body.tipo, body.id, body.nome)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return fv.list_favorites(conn)


@app.delete("/api/favoritos/{tipo}/{entity_id}")
def del_fav(tipo: str, entity_id: int, conn=Depends(get_conn)):
    try:
        fv.remove_favorite(conn, tipo, entity_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return fv.list_favorites(conn)


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
    pre = {p["player_id"]: {"proj": p.get("proj"), "min_esperado": (p.get("proj_detalhe") or {}).get("minutos"),
                            "linha": p.get("linha"), "linha_ref": p.get("linha_ref"), "media": p.get("temporada"),
                            "l10": p.get("l10"), "jogador": p["jogador"], "time": p["time"]}
           for g in report for p in g["jogadores"]}
    out = av.live_report(games, pre, mercado, load_projection_params(), alvo)
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
