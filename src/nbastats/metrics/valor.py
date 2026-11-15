"""Apostas de valor (edge): onde a nossa chance supera a chance que a odd paga.

- **chance implícita** da odd decimal: ``1 / odd`` (2,00 → 50%);
- **edge**: nossa chance − chance implícita (60% numa odd 2,00 → +10 p.p.);
- **valor esperado (EV)**: ``chance × odd − 1`` por unidade apostada;
- **odd justa**: ``1 / chance``, o empate; **odd mínima**: a que dá o edge
  mínimo configurado, ``1 / (chance − edge_minimo)``.

Valor não quer dizer que vai bater: uma prop de 60% perde 4 em cada 10. O
edge só diz que, repetida muitas vezes, a aposta tende a pagar mais do que
custa, se a nossa chance estiver bem calibrada (página Conferência).

Duas listas a partir dos relatórios (matchup_report + attach_lines), um por
mercado:
- **com_odd**: linha da casa com odd digitada; cada lado com odd é avaliado,
  e entra quem passa do edge mínimo, ordenado pelo edge;
- **sem_odd**: as maiores chances sem odd (linha da casa sem odd ou linha de
  referência), com a odd mínima que a casa precisa pagar para ter valor.

Critérios em ``config/apostas.yaml`` (seção ``valor``).
"""

from __future__ import annotations

from typing import Any

from .linhas import fair_odd

FORA = ("Out", "Doubtful")  # nem entra: provavelmente não joga


def implied(odd: float | None) -> float | None:
    """Chance implícita na odd decimal (sem tirar a margem da casa)."""
    return 1 / odd if odd and odd > 1 else None


def edge(prob: float | None, odd: float | None) -> float | None:
    imp = implied(odd)
    return None if prob is None or imp is None else prob - imp


def min_odd(prob: float | None, edge_min: float) -> float | None:
    """Menor odd que ainda dá o edge mínimo para essa chance."""
    if prob is None or prob - edge_min <= 0:
        return None
    return 1 / (prob - edge_min)


def _base(p: dict[str, Any], stat: str) -> dict[str, Any]:
    return {"player_id": p["player_id"], "jogador": p["jogador"], "time": p["time"],
            "adversario": p["adversario"], "game_id": p.get("game_id"), "mercado": stat,
            "linha": p.get("linha"), "linha_ref": bool(p.get("linha_ref")), "proj": p.get("proj"),
            "lesao": p.get("lesao"), "l10": p.get("l10")}


def _market_no_vig(p: dict[str, Any], side: str) -> float | None:
    oo, ou = p.get("odd_over"), p.get("odd_under")
    if not oo or not ou or oo <= 1 or ou <= 1:
        return None
    io, iu = 1 / oo, 1 / ou
    po = io / (io + iu)
    return po if side == "over" else 1 - po


def value_bets(reports: dict[str, list[dict[str, Any]]], cfg: dict[str, Any] | None = None,
               min_media: dict[str, float] | None = None) -> dict[str, Any]:
    cfg = cfg or {}
    edge_min = float(cfg.get("edge_minimo", 0.03))
    top = int(cfg.get("top", 40))
    min_media = min_media or {}
    com_odd: list[dict[str, Any]] = []
    sem_odd: list[dict[str, Any]] = []
    avaliadas = 0
    for stat, rep in reports.items():
        for g in rep:
            for p in g["jogadores"]:
                if p.get("p_over") is None or p.get("lesao") in FORA:
                    continue
                if (p.get("l10") or 0) < min_media.get(stat, 0):
                    continue
                sides = {"over": (p["p_over"], p.get("odd_over")), "under": (p["p_under"], p.get("odd_under"))}
                has_odd = False
                for lado, (prob, odd) in sides.items():
                    if p.get("linha_ref") or not odd:
                        continue
                    has_odd = True
                    avaliadas += 1
                    e = edge(prob, odd)
                    if e is None or e < edge_min:
                        continue
                    mkt = _market_no_vig(p, lado)
                    com_odd.append({**_base(p, stat), "lado": lado, "chance": prob, "odd": odd,
                                    "implicita": implied(odd), "edge": e, "ev": prob * odd - 1,
                                    "odd_justa": fair_odd(prob), "chance_mercado": mkt})
                if not has_odd:
                    lado = "over" if p["p_over"] >= 0.5 else "under"
                    prob = sides[lado][0]
                    sem_odd.append({**_base(p, stat), "lado": lado, "chance": prob,
                                    "odd_justa": fair_odd(prob), "odd_minima": min_odd(prob, edge_min)})
    com_odd.sort(key=lambda r: r["edge"], reverse=True)
    # linha da casa (sem odd) antes da de referência: a referência é só L10 arredondado
    sem_odd.sort(key=lambda r: (r["linha_ref"], -r["chance"]))
    seen: set[int] = set()
    melhores = []
    for r in sem_odd:  # uma por jogador: a de maior chance
        if r["player_id"] not in seen:
            seen.add(r["player_id"])
            melhores.append(r)
    return {"edge_minimo": edge_min, "avaliadas": avaliadas, "com_odd": com_odd[:top], "sem_odd": melhores[:top]}
