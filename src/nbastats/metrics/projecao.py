"""Projeção com número para cada mercado, margem esperada e risco de blowout.

A projeção de um jogador para um mercado é:

    taxa por minuto (L5/L10/temporada, misturada com a temporada anterior
    no começo da temporada) × minutos esperados × fator DvP × fator ritmo
    × (nível + ausência × fração da produção do time que está fora)

"nível" e "ausência" são calibrados por mercado com `nbastats calibrar`,
que também mede o erro contra o simples L10. Parâmetros em
config/projecao.yaml; método em docs/decisoes/0005-projecao.md.

Tudo usa só jogos ANTERIORES à data analisada.
"""

from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from statistics import mean
from typing import Any

import yaml

from .. import ajustes as _aj
from .matchup import (
    _COLS,
    MATCHUP_STATS,
    _derive,
    _player_rows,
    _team_games,
    dvp,
    player_form,
    player_groups,
    team_context,
)

DEFAULT_PROJECTION_PARAMS = Path("config/projecao.yaml")


def load_projection_params(path: str | Path = DEFAULT_PROJECTION_PARAMS, ajustes: bool = True) -> dict[str, Any]:
    """``ajustes=False``: só o arquivo (para o ``calibrar`` regravar sem levar os
    ajustes da Administração para o config/)."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return _aj.aplicar("projecao", data) if ajustes and Path(path) == Path(DEFAULT_PROJECTION_PARAMS) else data


# ---------- peças ----------

def previous_season(conn: sqlite3.Connection, season: int) -> dict[int, dict[str, float]]:
    """Totais de cada jogador na temporada anterior (jogos, minutos e mercados)."""
    out: dict[int, dict[str, float]] = {}
    for r in _player_rows(conn, season - 1, f"{season}-09-01"):
        p = out.setdefault(r["player_id"], {"jogos": 0, "minutes": 0.0,
                                            **{s: 0.0 for s in MATCHUP_STATS}})
        p["jogos"] += 1
        p["minutes"] += r["minutes"]
        for s in MATCHUP_STATS:
            p[s] += r[s]
    return out


def recent_players(rows: list[dict[str, Any]], n_games: int = 3) -> dict[int, set[int]]:
    """Quem entrou em algum dos últimos ``n_games`` jogos de cada time.

    Uma ausência só conta como "nova" se o jogador estava jogando: quem está
    fora há semanas já está refletido no L10 dos companheiros.
    """
    last: dict[int, list[int]] = defaultdict(list)
    for r in rows:  # do mais recente ao mais antigo
        games = last[r["team_id"]]
        if r["game_id"] not in games and len(games) < n_games:
            games.append(r["game_id"])
    out: dict[int, set[int]] = defaultdict(set)
    for r in rows:
        if r["game_id"] in last[r["team_id"]]:
            out[r["team_id"]].add(r["player_id"])
    return out


def league_allowed(table: dict[int, dict[str, dict[str, dict[str, float]]]]) -> dict[str, dict[str, float]]:
    """Média da liga do que se cede a cada grupo de posição, por mercado."""
    groups = {g for t in table.values() for g in t}
    return {g: {s: mean(t[g][s]["media"] for t in table.values() if g in t) for s in MATCHUP_STATS}
            for g in groups}


def absence_share(form: dict[int, dict[str, Any]], recent: set[int], absent: Iterable[int]) -> float:
    """Fração da produção recente do time (soma do PRA no L10) que está fora."""
    total = sum(form[p]["pra_l10"] or 0 for p in recent if p in form)
    lost = sum(form[p]["pra_l10"] or 0 for p in absent if p in form)
    return lost / total if total else 0.0


def absent_production(form: dict[int, dict[str, Any]], absent: Iterable[int]) -> float:
    return sum(form[p]["pra_l10"] or 0 for p in absent if p in form)


def _blend(values: list[float | None], weights: list[float]) -> float | None:
    pairs = [(v, w) for v, w in zip(values, weights) if v is not None and w]
    total = sum(w for _, w in pairs)
    return sum(v * w for v, w in pairs) / total if total else None


def _weights(cfg: dict[str, Any], key: str, default: tuple[float, float, float]) -> list[float]:
    w = cfg.get(key) or {}
    return [w.get("l5", default[0]), w.get("l10", default[1]), w.get("temporada", default[2])]


def project(f: dict[str, Any], stat: str, params: dict[str, Any], *,
            prior: dict[str, float] | None = None, dvp_media: float | None = None,
            liga_media: float | None = None, opp_games: int = 0,
            ritmo_time: float | None = None, ritmo_adv: float | None = None,
            ausencia: float = 0.0) -> dict[str, Any] | None:
    """Projeção de ``stat`` para um jogador (``f`` vem de player_form).

    Devolve o valor e cada componente, para a tela mostrar de onde veio o número.
    """
    mins = [f["minutes_l5"], f["minutes_l10"], f["minutes_temp"]]
    if not all(mins):
        return None
    rates = [f[f"{stat}_l5"] / mins[0], f[f"{stat}_l10"] / mins[1], f[f"{stat}_temp"] / mins[2]]
    rate = _blend(rates, _weights(params, "pesos_taxa", (0, 1, 3)))
    k = params.get("temporada_anterior_jogos", 5)
    if prior and k and prior.get("jogos", 0) >= 10 and prior.get("minutes"):
        # começo da temporada: a anterior vale como k jogos a mais
        rate = (f["jogos"] * rate + k * prior[stat] / prior["minutes"]) / (f["jogos"] + k)
    minutes = _blend(mins, _weights(params, "pesos_minutos", (2, 1, 1)))
    base = rate * minutes

    f_dvp = 1.0
    if dvp_media is not None and liga_media:
        shrink = opp_games / (opp_games + params.get("dvp_encolhimento_jogos", 80))
        f_dvp = 1 + shrink * (dvp_media / liga_media - 1)
    f_ritmo = 1.0
    if ritmo_time and ritmo_adv:
        f_ritmo = 1 + params.get("ritmo_peso", 0.5) * ((ritmo_time + ritmo_adv) / 2 / ritmo_time - 1)
    m = (params.get("mercados") or {}).get(stat) or {}
    f_ajuste = m.get("nivel", 1.0) + m.get("ausencia", 0.0) * ausencia
    value = base * f_dvp * f_ritmo * f_ajuste
    return {
        "valor": round(value, 2), "base": round(base, 2), "minutos": round(minutes, 1),
        "f_dvp": round(f_dvp, 3), "f_ritmo": round(f_ritmo, 3), "f_ajuste": round(f_ajuste, 3),
        "ausencia": round(ausencia, 3), "erro_tipico": m.get("erro_tipico"),
    }


def expected_margin(saldo_time: float | None, saldo_adv: float | None, casa: bool,
                    ausente_time: float, ausente_adv: float, params: dict[str, Any]) -> float | None:
    """Margem esperada para o time (positivo = vence por tanto)."""
    if saldo_time is None or saldo_adv is None:
        return None
    c = params.get("margem") or {}
    return (c.get("intercepto", 0.0) + c.get("saldo", 0.57) * (saldo_time - saldo_adv)
            + c.get("casa", 1.25) * (1 if casa else -1)
            + c.get("pra_ausente_time", -0.11) * ausente_time
            + c.get("pra_ausente_adv", 0.11) * ausente_adv)


def blowout_probability(margin: float | None, params: dict[str, Any]) -> float | None:
    """Chance de o jogo ser decidido por ``blowout.pontos`` ou mais."""
    if margin is None:
        return None
    b = params.get("blowout") or {}
    z = b.get("a", -1.03) + b.get("b", 0.084) * abs(margin)
    return 1 / (1 + math.exp(-z))


def with_without(rows: list[dict[str, Any]], player_id: int, teammates: Iterable[int],
                 stat: str) -> dict[int, dict[str, Any]]:
    """Média do jogador nos jogos com e sem cada companheiro (mesmo time)."""
    games = {r["game_id"]: r for r in rows if r["player_id"] == player_id}
    if not games:
        return {}
    team = next(iter(games.values()))["team_id"]
    played: dict[int, set[int]] = defaultdict(set)
    for r in rows:
        if r["game_id"] in games and r["team_id"] == team:
            played[r["player_id"]].add(r["game_id"])
    out = {}
    for t in teammates:
        com = [games[g][stat] for g in games if g in played.get(t, set())]
        sem = [games[g][stat] for g in games if g not in played.get(t, set())]
        out[t] = {"com": round(mean(com), 1) if com else None, "jogos_com": len(com),
                  "sem": round(mean(sem), 1) if sem else None, "jogos_sem": len(sem)}
    return out


# ---------- calibração ----------

def build_dataset(conn: sqlite3.Connection, season: int, rules: dict[str, Any],
                  params: dict[str, Any], start: str | None = None, step: int = 1,
                  min_jogos: int = 5, min_minutos: float = 20) -> list[dict[str, Any]]:
    """Para cada jogador em cada jogo já disputado: o que se sabia antes e o real.

    As ausências vêm do próprio box score (quem estava jogando e não entrou),
    o equivalente a ter o injury report final do dia.
    """
    sql = "SELECT DISTINCT date FROM games WHERE season = ? AND postseason = 0"
    days = [r[0] for r in conn.execute(sql + " ORDER BY date", (season,))
            if not start or r[0] >= start][::max(step, 1)]
    prior = previous_season(conn, season)
    aus_cfg = params.get("ausencia") or {}
    min_aus = aus_cfg.get("min_minutos_l10", 15)
    data = []
    for day in days:
        rows = _player_rows(conn, season, day)
        if not rows:
            continue
        teams = _team_games(rows)
        form = player_form(rows, teams)
        groups = player_groups(form, rules)
        table = dvp(rows, teams, groups)
        league = league_allowed(table)
        ctx = team_context(teams)
        recent = recent_players(rows, aus_cfg.get("jogos_recentes", 3))
        n_games = defaultdict(int)
        for (_, t) in teams:
            n_games[t] += 1
        cols = ", ".join(f"COALESCE(s.{c}, 0) AS {c}" for c in _COLS)
        today = conn.execute(
            f"SELECT s.game_id, s.player_id, s.team_id, g.home_team_id, g.visitor_team_id,"
            f" g.home_team_score, g.visitor_team_score, {cols}"
            " FROM player_game_stats s JOIN games g ON g.id = s.game_id"
            " WHERE g.date = ? AND g.postseason = 0 AND g.season = ?", (day, season)).fetchall()
        by_game: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for r in today:
            by_game[r["game_id"]].append(dict(r))
        for game_rows in by_game.values():
            g0 = game_rows[0]
            home, away = g0["home_team_id"], g0["visitor_team_id"]
            if g0["home_team_score"] is None:
                continue
            played = {r["player_id"] for r in game_rows if r["minutes"] > 0}
            absent = {t: [p for p in recent[t] if p not in played and p in form
                          and (form[p]["minutes_l10"] or 0) >= min_aus]
                      for t in (home, away)}
            margin_home = g0["home_team_score"] - g0["visitor_team_score"]
            for r in game_rows:
                pid, team = r["player_id"], r["team_id"]
                f = form.get(pid)
                if not f or r["minutes"] <= 0 or f["jogos"] < min_jogos or (f["minutes_l10"] or 0) < min_minutos:
                    continue
                opp = away if team == home else home
                real = _derive(r)
                share = absence_share(form, recent[team], absent[team])
                rec = {"day": day, "player_id": pid, "real": real, "l10": {},
                       "margem_real": margin_home if team == home else -margin_home,
                       "saldo_time": ctx["saldo"].get(team), "saldo_adv": ctx["saldo"].get(opp),
                       "casa": team == home,
                       "ausente_time": absent_production(form, absent[team]),
                       "ausente_adv": absent_production(form, absent[opp]),
                       "proj_base": {}, "ausencia": share, "min_l10": f["minutes_l10"]}
                margin = expected_margin(rec["saldo_time"], rec["saldo_adv"], rec["casa"],
                                         rec["ausente_time"], rec["ausente_adv"], params)
                rec["risco_blowout"] = blowout_probability(margin, params)
                group = groups.get(pid)
                for s in MATCHUP_STATS:
                    d = table.get(opp, {}).get(group, {}).get(s) if group else None
                    neutral = {**params, "mercados": {}}  # sem nível/ausência: é o que se calibra
                    p = project(f, s, neutral, prior=prior.get(pid),
                                dvp_media=d["media"] if d else None,
                                liga_media=league.get(group, {}).get(s) if group else None,
                                opp_games=n_games[opp], ritmo_time=ctx["ritmo"].get(team),
                                ritmo_adv=ctx["ritmo"].get(opp), ausencia=share)
                    rec["proj_base"][s] = p["valor"] if p else None
                    rec["l10"][s] = f[f"{s}_l10"]
                data.append(rec)
    return data


def _lstsq(xs: list[list[float]], ys: list[float]) -> list[float]:
    """Mínimos quadrados pelas equações normais (poucas variáveis)."""
    n = len(xs[0])
    a = [[sum(x[i] * x[j] for x in xs) for j in range(n)] for i in range(n)]
    b = [sum(x[i] * y for x, y in zip(xs, ys)) for i in range(n)]
    for i in range(n):  # eliminação de Gauss
        piv = max(range(i, n), key=lambda r: abs(a[r][i]))
        a[i], a[piv], b[i], b[piv] = a[piv], a[i], b[piv], b[i]
        if abs(a[i][i]) < 1e-12:
            return [0.0] * n
        for r in range(i + 1, n):
            k = a[r][i] / a[i][i]
            a[r] = [x - k * y for x, y in zip(a[r], a[i])]
            b[r] -= k * b[i]
    sol = [0.0] * n
    for i in reversed(range(n)):
        sol[i] = (b[i] - sum(a[i][j] * sol[j] for j in range(i + 1, n))) / a[i][i]
    return sol


def _dispersion(pts: list[tuple[float, float, float]]) -> dict[str, Any]:
    """Escolhe a distribuição da chance de over: binomial negativa ou normal.

    ``pts``: (média projetada, real, L10). Testa as duas contra uma linha de
    referência (L10 arredondado para x,5) e fica com a de menor erro de
    probabilidade (Brier).
    """
    from .linhas import prob_over, reference_line, shrink

    mus = [m for m, _, _ in pts]
    excess = mean((y - m) ** 2 for m, y, _ in pts) - mean(mus)
    r = mean(m * m for m in mus) / excess if excess > 0 else 1e6
    # normal: desvio = k × média^e (ajuste em log dos desvios absolutos)
    xs = [[1.0, math.log(m)] for m, _, _ in pts]
    ys = [math.log(abs(y - m) * math.sqrt(math.pi / 2) + 0.5) for m, y, _ in pts]
    c0, e = _lstsq(xs, ys)
    k = math.exp(c0)
    scale = mean(abs(y - m) * math.sqrt(math.pi / 2) for m, y, _ in pts) / mean(k * m ** e for m in mus)
    k *= scale
    cand = {"nb": {"dist": "nb", "r": round(min(r, 1e6), 2)},
            "normal": {"dist": "normal", "sd_k": round(k, 3), "sd_e": round(e, 3)}}
    brier = {}
    for name, cfg in cand.items():
        errs = []
        for m, y, l10 in pts:
            line = reference_line(l10)
            errs.append((prob_over(m, line, cfg) - (1.0 if y > line else 0.0)) ** 2)
        brier[name] = mean(errs)
    best = min(brier, key=brier.get)
    out = {**cand[best], "brier": round(brier[best], 4)}
    # encolhimento: corrige excesso de confiança nas pontas (Brier mínimo em b)
    raw = [(prob_over(m, reference_line(l10), cand[best]), 1.0 if y > reference_line(l10) else 0.0) for m, y, l10 in pts]
    def brier_b(b: float) -> float:
        return mean((shrink(p, b) - y) ** 2 for p, y in raw)
    b = min((x / 100 for x in range(50, 131)), key=brier_b)
    if b != 1.0:
        out |= {"encolhimento": b, "brier": round(brier_b(b), 4)}
    return out


def calibrate(data: list[dict[str, Any]], params: dict[str, Any]) -> dict[str, Any]:
    """Ajusta nível/ausência por mercado, a margem esperada e o risco de blowout."""
    out = dict(params)
    mercados = {}
    for s in MATCHUP_STATS:
        full = [(r["proj_base"][s], r["ausencia"], r["real"][s], r["l10"][s]) for r in data
                if r["proj_base"].get(s) is not None]
        pts = [(p, a, y) for p, a, y, _ in full]
        if len(pts) < 50 or not sum(p for p, _, _ in pts):
            mercados[s] = {"nivel": 1.0, "ausencia": 0.0}
            continue
        # real ≈ proj × (nível + ausência × fração)  ->  colunas proj e proj × fração
        nivel, aus = _lstsq([[p, p * a] for p, a, _ in pts], [y for _, _, y in pts])
        if not 0.5 <= nivel <= 1.5 or not -1 <= aus <= 2:
            # evento raro (ex.: triplo-duplo): o ajuste não se sustenta; só corrige a escala
            nivel, aus = sum(y for _, _, y in pts) / sum(p for p, _, _ in pts), 0.0
        erro = mean(abs(p * (nivel + aus * a) - y) for p, a, y in pts)
        mercados[s] = {"nivel": round(nivel, 3), "ausencia": round(aus, 3),
                       "erro_tipico": round(erro, 2),
                       **_dispersion([(max(p * (nivel + aus * a), 0.05), y, l10)
                                      for p, a, y, l10 in full])}
    out["mercados"] = mercados

    games = [r for r in data if r["saldo_time"] is not None and r["saldo_adv"] is not None]
    if len(games) >= 50:
        xs = [[1.0, r["saldo_time"] - r["saldo_adv"], 1.0 if r["casa"] else -1.0,
               r["ausente_time"], r["ausente_adv"]] for r in games]
        c = _lstsq(xs, [r["margem_real"] for r in games])
        out["margem"] = {"intercepto": round(c[0], 3), "saldo": round(c[1], 3), "casa": round(c[2], 3),
                         "pra_ausente_time": round(c[3], 4), "pra_ausente_adv": round(c[4], 4)}
        pontos = (params.get("blowout") or {}).get("pontos", 15)
        x = [abs(sum(a * b for a, b in zip(row, c))) for row in xs]
        y = [1.0 if abs(r["margem_real"]) >= pontos else 0.0 for r in games]
        a, b = -1.0, 0.08
        for _ in range(2000):  # regressão logística por gradiente
            p = [1 / (1 + math.exp(-(a + b * xi))) for xi in x]
            a -= 0.05 * mean(pi - yi for pi, yi in zip(p, y))
            b -= 0.005 * mean((pi - yi) * xi for pi, yi, xi in zip(p, y, x))
        out["blowout"] = {"pontos": pontos, "a": round(a, 3), "b": round(b, 4)}
    return out


def evaluate(data: list[dict[str, Any]], params: dict[str, Any],
             stats: Iterable[str] = MATCHUP_STATS) -> list[dict[str, Any]]:
    """Erro médio (MAE) da projeção contra o L10, por mercado."""
    rows = []
    for s in stats:
        m = (params.get("mercados") or {}).get(s) or {}
        pts = [(r["proj_base"][s] * (m.get("nivel", 1) + m.get("ausencia", 0) * r["ausencia"]),
                r["l10"][s], r["real"][s]) for r in data if r["proj_base"].get(s) is not None]
        if not pts:
            continue
        e_proj = mean(abs(p - y) for p, _, y in pts)
        e_l10 = mean(abs(l10 - y) for _, l10, y in pts)
        rows.append({"mercado": s, "n": len(pts), "erro_l10": round(e_l10, 3),
                     "erro_projecao": round(e_proj, 3),
                     "ganho_pct": round(100 * (e_l10 - e_proj) / e_l10, 1) if e_l10 else None})
    return rows


def save_projection_params(params: dict[str, Any], path: str | Path = DEFAULT_PROJECTION_PARAMS,
                           note: str = "") -> None:
    header = (
        "# Parâmetros da projeção (metrics/projecao.py).\n"
        "# Os blocos mercados, margem e blowout são recalculados por `nbastats calibrar`;\n"
        "# os demais são escolhas fixas (ver docs/decisoes/0005-projecao.md).\n"
    )
    if note:
        header += f"# {note}\n"
    body = yaml.safe_dump(params, sort_keys=False, allow_unicode=True, default_flow_style=None)
    Path(path).write_text(header + "\n" + body, encoding="utf-8")
