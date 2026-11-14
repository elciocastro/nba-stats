"""Zonas de arremesso: de onde o jogador arremessa x onde o adversário cede.

Fonte: LeagueDash*ShotLocations (temporada até a última carga). É uma
fotografia, não um histórico dia a dia: serve para o jogo de hoje, mas não
entra no teste retroativo (usaria informação do futuro).
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from typing import Any

ZONE_NAMES = {
    "aro": "Perto do aro", "garrafao": "Garrafão", "meia": "Meia distância",
    "canto3": "3 da zona morta", "frente3": "3 de frente",
}
THREE = ("canto3", "frente3")


def load_zones(conn: sqlite3.Connection, season: int) -> dict[str, Any]:
    """Tudo de uma vez: jogadores, defesas e a média da liga por zona."""
    player: dict[int, dict[str, tuple[float, float]]] = defaultdict(dict)
    defense: dict[int, dict[str, tuple[float, float]]] = defaultdict(dict)
    league: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    updated = None
    for r in conn.execute("SELECT kind, entity_id, zone, fgm, fga, updated_at FROM shot_zones"
                          " WHERE season = ?", (season,)):
        target = player if r["kind"] == "player" else defense
        target[r["entity_id"]][r["zone"]] = (r["fgm"] or 0.0, r["fga"] or 0.0)
        if r["kind"] == "team_opp":
            league[r["zone"]][0] += r["fgm"] or 0.0
            league[r["zone"]][1] += r["fga"] or 0.0
        updated = max(updated or "", r["updated_at"] or "")
    return {"player": player, "defense": defense, "league": dict(league), "updated": updated}


def _pct(m: float, a: float) -> float | None:
    return m / a if a else None


def zone_matchup(zones: dict[str, Any], player_id: int, opp_id: int,
                 only: tuple[str, ...] | None = None) -> dict[str, Any] | None:
    """Tabela por zona e o encaixe (p.p. de aproveitamento cedido acima da liga,
    ponderado pela fração dos arremessos do jogador em cada zona).

    ``only``: limita às zonas de 3 pontos, por exemplo, para o mercado 3FM.
    """
    mine, opp, league = zones["player"].get(player_id), zones["defense"].get(opp_id), zones["league"]
    if not mine or not opp:
        return None
    keys = [z for z in ZONE_NAMES if not only or z in only]
    total = sum(mine.get(z, (0, 0))[1] for z in keys)
    if not total:
        return None
    opp_total = sum(opp.get(z, (0, 0))[1] for z in ZONE_NAMES)
    league_total = sum(v[1] for v in league.values())
    rows, fit = [], 0.0
    for z in keys:
        pm, pa = mine.get(z, (0.0, 0.0))
        om, oa = opp.get(z, (0.0, 0.0))
        lm, la = league.get(z, (0.0, 0.0))
        share = pa / total
        ced, liga = _pct(om, oa), _pct(lm, la)
        if ced is not None and liga is not None:
            fit += share * (ced - liga)
        rows.append({
            "zona": ZONE_NAMES[z], "arremessos_dele_pct": round(100 * share),
            "fg_dele": round(100 * pm / pa, 1) if pa else None,
            "fg_cedido": round(100 * ced, 1) if ced is not None else None,
            "fg_liga": round(100 * liga, 1) if liga is not None else None,
            # quanto do volume adversário sai daquela zona, comparado com a liga
            "volume_cedido_pct": round(100 * oa / opp_total) if opp_total else None,
            "volume_liga_pct": round(100 * la / league_total) if league_total else None,
        })
    return {"encaixe_pp": round(100 * fit, 1), "zonas": rows, "atualizado": zones["updated"]}
