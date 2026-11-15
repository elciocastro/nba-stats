"""Destaques do dia para a página inicial.

- **jogos**: cada jogo com margem esperada, risco de blowout, ritmo contra a
  liga, desfalques e quantas props boas (selo Forte/Boa) ele tem;
- **em alta**: quem joga hoje e vem produzindo (L5) acima da temporada,
  com minutos e uso subindo: vale acompanhar;
- **oportunidades**: as melhores props entre os mercados principais. Com
  odd da casa, ordena pelo valor esperado; sem odd, pela chance do modelo
  (marcadas como linha de referência).

Recebe relatórios já prontos (matchup_report + attach_lines), um por mercado.
"""

from __future__ import annotations

from typing import Any

from . import betaniag as bt

HOME_MARKETS = ("pts", "reb", "ast", "pra", "fg3m")
GOOD = ("Forte", "Boa")
# média mínima (L10) para a prop entrar nos destaques: abaixo disso as casas
# nem oferecem a linha (ex.: bolas de 3 de um pivô). Sobrescrito pelo YAML.
MIN_MEDIA = {"pts": 10, "reb": 4, "ast": 3, "pra": 15, "fg3m": 1.5}


def _relevant(p: dict[str, Any], stat: str, min_media: dict[str, float]) -> bool:
    return (p.get("l10") or 0) >= min_media.get(stat, 0)


def game_cards(reports: dict[str, list[dict[str, Any]]], cfg: dict[str, Any] | None,
               min_media: dict[str, float] | None = None) -> list[dict[str, Any]]:
    """Um resumo por jogo, juntando os mercados."""
    min_media = MIN_MEDIA if min_media is None else min_media
    base = next(iter(reports.values()), [])
    cards = []
    for i, g in enumerate(base):
        j = g["jogo"]
        good, best = 0, None
        for stat, rep in reports.items():
            for p in rep[i]["jogadores"]:
                if not _relevant(p, stat, min_media):
                    continue
                s = bt.seal(p, cfg) if cfg else None
                if s and s["nivel"] in GOOD:
                    good += 1
                side = bt.best_side(p)
                if side and (best is None or side["chance"] > best["chance"]):
                    best = {"jogador": p["jogador"], "player_id": p["player_id"], "mercado": stat,
                            "lado": side["lado"], "linha": p.get("linha"), "chance": side["chance"]}
        r = g["ritmo"]
        pace = None
        if r["casa"] and r["fora"] and r["liga"]:
            pace = round((r["casa"] + r["fora"]) / 2 - r["liga"], 1)
        m = g.get("margem_esperada")
        cards.append({
            "game_id": j["id"], "casa": j["home"], "fora": j["visitor"], "status": j.get("status"),
            "placar": None if j["home_team_score"] is None
            else f"{j['visitor_team_score']}-{j['home_team_score']}",
            "favorito": None if m is None else (j["home"] if m >= 0 else j["visitor"]),
            "margem": None if m is None else abs(m), "blowout": g.get("risco_blowout"),
            "ritmo_vs_liga": pace, "desfalques": g["desfalques"], "props_boas": good, "melhor": best,
            "validacao": g.get("validacao"),
        })
    return cards


def rising(report: list[dict[str, Any]], stat: str = "pra", top: int = 10,
           min_games: int = 8) -> list[dict[str, Any]]:
    """Quem joga hoje e vem acima da própria temporada (relatório de um mercado, ex.: PRA)."""
    out = []
    for g in report:
        for p in g["jogadores"]:
            if p["jogos"] < min_games or not p.get("temporada") or p.get("l5") is None:
                continue
            out.append({
                "player_id": p["player_id"], "jogador": p["jogador"], "time": p["time"],
                "adversario": p["adversario"], "l5": p["l5"], "temporada": p["temporada"],
                "alta_pct": round(100 * (p["l5"] / p["temporada"] - 1)),
                "min_l5": p["min_l5"], "min_l10": p["min_l10"],
                "uso_l5": p.get("usg_l5"), "uso_l10": p.get("usg_l10"),
                "proj": p.get("proj"), "lesao": p.get("lesao"),
                "valores": [h[stat] for h in reversed((p.get("historico") or [])[:10])],
            })
    out.sort(key=lambda r: r["alta_pct"], reverse=True)
    return out[:top]


def opportunities(reports: dict[str, list[dict[str, Any]]], cfg: dict[str, Any] | None,
                  top: int = 10, min_media: dict[str, float] | None = None) -> dict[str, list[dict[str, Any]]]:
    """Melhores props: com odd (por valor esperado) e sem odd (por chance).
    Uma por jogador (a melhor) e só mercados com média relevante."""
    min_media = MIN_MEDIA if min_media is None else min_media
    items = []
    for stat, rep in reports.items():
        for g in rep:
            for p in g["jogadores"]:
                side = bt.best_side(p)
                if side is None or p.get("lesao") in ("Doubtful",) or not _relevant(p, stat, min_media):
                    continue
                s = bt.seal(p, cfg) if cfg else None
                items.append({
                    "player_id": p["player_id"], "jogador": p["jogador"], "time": p["time"],
                    "adversario": p["adversario"], "mercado": stat, "linha": p.get("linha"),
                    "linha_ref": p.get("linha_ref"), "proj": p.get("proj"), "lesao": p.get("lesao"),
                    **side, "selo": s, "historico": p.get("historico") or [],
                })
    def best_per_player(rows):
        seen, out = set(), []
        for r in rows:
            if r["player_id"] not in seen:
                seen.add(r["player_id"])
                out.append(r)
        return out[:top]

    with_odd = sorted((i for i in items if i["ev"] is not None), key=lambda i: i["ev"], reverse=True)
    without = sorted((i for i in items if i["ev"] is None), key=lambda i: i["chance"], reverse=True)
    return {"com_odd": best_per_player(with_odd), "sem_odd": best_per_player(without)}
