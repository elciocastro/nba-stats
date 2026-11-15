"""Efeito cascata da lesão: quando um jogador importante fica fora, quem do
time ganha e quanto, com a projeção do dia contra a linha.

Usa o relatório do dia (``painel.day_report``): cada jogador traz
``com_sem`` (a média dele nos jogos com e sem os companheiros desfalcados
hoje) e a projeção, que já desconta a produção dos ausentes. Aqui só se
reorganiza por desfalque: "Embiid fora → Maxey +4,1 de PRA sem ele (6
jogos); projeção 38,2 contra linha 35,5".

``novidades`` (nomes que entraram ou pioraram no último injury report)
marca o que mudou agora, que é quando a linha da casa pode ainda não ter
se ajustado.
"""

from __future__ import annotations

from typing import Any, Iterable

MIN_JOGOS_SEM = 2   # com menos jogos sem o companheiro, a média "sem" é ruído


def cascata(report: list[dict[str, Any]], novidades: Iterable[str] = (),
            min_jogos_sem: int = MIN_JOGOS_SEM) -> list[dict[str, Any]]:
    """Um item por desfalque com os companheiros que mais mudam sem ele."""
    novos = {n.strip().lower() for n in novidades if n}
    by_absent: dict[tuple[str, str], dict[str, Any]] = {}
    for g in report:
        jogo = g["jogo"]
        for p in g["jogadores"]:
            for cs in p.get("com_sem") or []:
                if cs.get("com") is None or cs.get("sem") is None or (cs.get("jogos_sem") or 0) < min_jogos_sem:
                    continue
                key = (p["time"], cs["companheiro"])
                item = by_absent.setdefault(key, {
                    "fora": cs["companheiro"], "time": p["time"], "adversario": p["adversario"],
                    "game_id": jogo.get("id"), "novo": cs["companheiro"].strip().lower() in novos,
                    "companheiros": []})
                linha = p.get("linha")
                item["companheiros"].append({
                    "player_id": p["player_id"], "jogador": p["jogador"],
                    "com": cs["com"], "sem": cs["sem"], "ganho": round(cs["sem"] - cs["com"], 1),
                    "jogos_com": cs["jogos_com"], "jogos_sem": cs["jogos_sem"],
                    "l10": p.get("l10"), "proj": p.get("proj"), "linha": linha, "linha_ref": p.get("linha_ref"),
                    "p_over": p.get("p_over"),
                    "diff": None if p.get("proj") is None or linha is None else round(p["proj"] - linha, 1),
                })
    out = []
    for item in by_absent.values():
        item["companheiros"].sort(key=lambda c: c["ganho"], reverse=True)
        item["ganho_total"] = round(sum(c["ganho"] for c in item["companheiros"] if c["ganho"] > 0), 1)
        out.append(item)
    out.sort(key=lambda i: (i["novo"], i["ganho_total"]), reverse=True)
    return out
