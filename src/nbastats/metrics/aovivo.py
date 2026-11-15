"""Ao Vivo: parcial de cada jogador contra a linha (ou a média) e a projeção
do final no ritmo atual.

Para cada jogador em quadra no jogo:
- **minutos restantes** = tempo de jogo que falta × fatia de minutos que ele
  costuma jogar (minutos esperados / 48), limitado ao que falta para chegar
  aos minutos esperados (+ folga). Corta se o jogo vira blowout no 4º quarto
  (titulares saem) ou se ele tem 5+ faltas;
- **ritmo** = mistura da taxa pré-jogo (projeção / minutos esperados) com a
  taxa ao vivo (parcial / minutos jogados); a ao vivo pesa pouco porque é
  ruidosa (poucos minutos);
- **chance** de passar do alvo com a mesma distribuição calibrada da
  pré-análise (metrics/linhas.prob_over), aplicada ao que falta.

Parâmetros em ``config/projecao.yaml`` (bloco ``ao_vivo``), com padrões aqui.
"""

from __future__ import annotations

from typing import Any

from .linhas import prob_over

DEFAULTS = {
    "peso_ao_vivo": 0.3,          # peso da taxa ao vivo no ritmo
    "min_minutos_ao_vivo": 6,     # abaixo disso usa só a taxa pré-jogo
    "folga_minutos": 4,           # pode passar dos minutos esperados em até X
    "blowout_margem": 20,         # 4º quarto com esta margem: titulares saem
    "blowout_fator": 0.4,         # fração dos minutos restantes em blowout
    "faltas_limite": 5,
    "faltas_fator": 0.7,
}
REG_PERIOD, OT_PERIOD = 12.0, 5.0


def game_minutes_left(status: int, period: int, clock_seconds: float) -> float:
    """Minutos de jogo que faltam (tempo regulamentar; prorrogação conta 5)."""
    if status == 3:
        return 0.0
    if status == 1 or period == 0:
        return 48.0
    clock = clock_seconds / 60
    if period <= 4:
        return (4 - period) * REG_PERIOD + clock
    return clock  # prorrogação: só o que resta dela


def player_live(atual: float, minutos: float, faltas: int, pre: dict[str, Any], alvo: float | None,
                game: dict[str, Any], market: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """Projeção do final e chance de passar de ``alvo`` para um jogador."""
    c = {**DEFAULTS, **(cfg or {})}
    left = game_minutes_left(game["status"], game["periodo"], game["relogio_seg"])
    exp_min = pre.get("min_esperado") or 0
    proj = pre.get("proj")
    flags = []
    if left <= 0 or not exp_min or proj is None:
        restante = 0.0
    else:
        share = min(exp_min / 48, 1.0)
        restante = min(left * share, max(exp_min - minutos, 0) + c["folga_minutos"], left)
        margin = abs((game.get("placar_casa") or 0) - (game.get("placar_fora") or 0))
        if game["periodo"] >= 4 and margin >= c["blowout_margem"]:
            restante *= c["blowout_fator"]
            flags.append("blowout")
        if faltas >= c["faltas_limite"]:
            restante *= c["faltas_fator"]
            flags.append("faltas")
    rate_pre = proj / exp_min if proj is not None and exp_min else 0.0
    rate = rate_pre
    if minutos >= c["min_minutos_ao_vivo"]:
        rate = (1 - c["peso_ao_vivo"]) * rate_pre + c["peso_ao_vivo"] * atual / minutos
    mu = rate * restante
    final = atual + mu
    if alvo is None:
        chance = None
    elif atual > alvo:
        chance = 1.0
    elif restante <= 0:
        chance = 0.0
    else:
        chance = prob_over(mu, alvo - atual, market)
    if alvo is not None and atual > alvo:
        status = "bateu"
    elif chance is None:
        status = None
    elif chance >= 0.5:
        status = "a caminho"
    elif chance >= 0.2:
        status = "precisa acelerar"
    else:
        status = "longe"
    return {"atual": atual, "minutos": minutos, "restante": round(restante, 1), "final": round(final, 1),
            "chance": None if chance is None else round(chance, 3), "falta": None if alvo is None else round(alvo - atual, 1),
            "status": status, "alertas": flags}


def pre_from_report(report: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Pré-análise de cada jogador (do relatório do dia) no formato de ``live_report``."""
    return {p["player_id"]: {"proj": p.get("proj"), "min_esperado": (p.get("proj_detalhe") or {}).get("minutos"),
                             "linha": p.get("linha"), "linha_ref": p.get("linha_ref"), "media": p.get("temporada"),
                             "l10": p.get("l10"), "jogador": p["jogador"], "time": p["time"]}
            for g in report for p in g["jogadores"]}


def live_report(games: list[dict[str, Any]], pre: dict[int, dict[str, Any]], stat: str,
                params: dict[str, Any], target: str = "linha") -> list[dict[str, Any]]:
    """Jogos ao vivo com os jogadores que têm pré-análise.

    ``pre`` = {player_id: {proj, min_esperado, linha, linha_ref, media, l10,
    jogador, time}} montado do relatório do dia para ``stat``. ``target`` =
    'linha' (linha da casa ou referência) ou 'media' (média da temporada).
    """
    market = (params.get("mercados") or {}).get(stat) or {}
    cfg = params.get("ao_vivo") or {}
    out = []
    for g in games:
        players = []
        for jp in g["jogadores"]:
            info = pre.get(jp["player_id"])
            if not info or not jp.get("ativo", True):
                continue
            atual = _value(jp, stat)
            alvo = info.get("linha") if target == "linha" else info.get("media")
            row = player_live(atual, jp["minutos"], jp.get("faltas", 0), info, alvo, g, market, cfg)
            players.append({**row, "player_id": jp["player_id"], "jogador": info.get("jogador") or jp["nome"],
                            "time": info.get("time"), "alvo": alvo, "linha_ref": info.get("linha_ref"),
                            "media": info.get("media"), "proj_pre": info.get("proj"),
                            "em_quadra": jp.get("em_quadra"), "faltas": jp.get("faltas", 0)})
        players.sort(key=lambda r: (r["status"] == "bateu", r["chance"] or 0), reverse=True)
        out.append({k: v for k, v in g.items() if k != "jogadores"} | {"jogadores": players,
                   "minutos_restantes": round(game_minutes_left(g["status"], g["periodo"], g["relogio_seg"]), 1)})
    return out


def _value(p: dict[str, Any], stat: str) -> float:
    pts, reb, ast = p.get("pts", 0), p.get("reb", 0), p.get("ast", 0)
    derived = {"pra": pts + reb + ast, "pr": pts + reb, "pa": pts + ast, "ra": reb + ast,
               "fg2m": p.get("fgm", 0) - p.get("fg3m", 0), "fg2a": p.get("fga", 0) - p.get("fg3a", 0)}
    return derived.get(stat, p.get(stat, 0))
