"""Protocolo BetânIAG aplicado aos números do site (docs/decisoes/0008 e 0009).

- **selo**: nível e cor de cada prop pela chance do modelo e pelo valor
  esperado; unidade sugerida só se ``unidades.habilitado`` (em espera);
- **mercado sem margem**: com as odds de over e under, a chance que a casa
  precifica e a margem dela; a vantagem é a nossa chance menos essa;
- **validação**: "pré-análise" até o injury report perto do jogo sem
  jogadores relevantes em dúvida; depois "validada";
- **checklist**: os itens do protocolo para o detalhe do jogador.

Tudo configurável em ``config/betaniag.yaml``; desligado por padrão.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from .. import ajustes as _aj

DEFAULT_BETANIAG = Path("config/betaniag.yaml")


def load_betaniag(path: str | Path = DEFAULT_BETANIAG, ajustes: bool = True) -> dict[str, Any]:
    p = Path(path)
    data = (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.exists() else {}
    return _aj.aplicar("betaniag", data) if ajustes and p == Path(DEFAULT_BETANIAG) else data


def no_vig(odd_over: float | None, odd_under: float | None) -> dict[str, float] | None:
    """Chance de over que a casa precifica, sem a margem dela (método proporcional)."""
    if not odd_over or not odd_under or odd_over <= 1 or odd_under <= 1:
        return None
    io, iu = 1 / odd_over, 1 / odd_under
    return {"p_over": io / (io + iu), "margem": io + iu - 1}


def best_side(p: dict[str, Any]) -> dict[str, Any] | None:
    """Lado que o modelo favorece, com chance, odd e valor esperado desse lado."""
    if p.get("p_over") is None:
        return None
    over = p["p_over"] >= 0.5
    prob = p["p_over"] if over else p["p_under"]
    odd = p.get("odd_over") if over else p.get("odd_under")
    ev = prob * odd - 1 if odd else None
    market = no_vig(p.get("odd_over"), p.get("odd_under"))
    mkt = None if market is None else (market["p_over"] if over else 1 - market["p_over"])
    return {"lado": "over" if over else "under", "chance": prob, "odd": odd, "ev": ev,
            "chance_mercado": mkt, "vantagem": None if mkt is None else prob - mkt,
            "margem_casa": None if market is None else market["margem"]}


def seal(p: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any] | None:
    """Selo do protocolo para um jogador com linha: nível, cores e unidade."""
    side = best_side(p)
    if side is None:
        return None
    levels = cfg.get("niveis") or []
    chosen = None
    if side["ev"] is not None and side["ev"] < 0:
        chosen = cfg.get("sem_valor") or {"nome": "Sem valor", "cor": "#7f1d1d", "texto": "#fecaca"}
    else:
        for lv in levels:
            ev_min = lv.get("ev_min")
            if side["chance"] >= lv.get("chance_min", 0) and (
                    side["ev"] is None or ev_min is None or side["ev"] >= ev_min):
                chosen = lv
                break
    chosen = chosen or {"nome": "Neutra", "cor": "#475569", "texto": "#e2e8f0"}
    cap = cfg.get("linha_ref_max")
    names = [lv["nome"] for lv in levels]
    if p.get("linha_ref") and cap in names and chosen["nome"] in names \
            and names.index(chosen["nome"]) < names.index(cap):
        chosen = levels[names.index(cap)]  # linha de referência favorece o under: teto
    units = None
    ucfg = cfg.get("unidades") or {}
    if ucfg.get("habilitado"):
        units = (ucfg.get("por_nivel") or {}).get(chosen["nome"])
    return {**side, "nivel": chosen["nome"], "cor": chosen["cor"], "texto": chosen.get("texto", "#fff"),
            "unidade": units, "sem_odd": side["odd"] is None, "linha_ref": bool(p.get("linha_ref"))}


_TIP = re.compile(r"(\d{1,2}):(\d{2})\s*([ap])m", re.I)


def tipoff(game: dict[str, Any]) -> datetime | None:
    """Horário do jogo (ET) a partir do status da agenda, ex.: '7:30 pm ET'."""
    m = _TIP.search(game.get("status") or "")
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3).lower()
    h = h % 12 + (12 if ap == "p" else 0)
    return datetime.fromisoformat(game["date"]).replace(hour=h, minute=mi)


def validation(game_item: dict[str, Any], cfg: dict[str, Any],
               injuries: dict[int, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Selo de validação de um jogo do relatório de matchups.

    ``injuries`` = {player_id: {'status', ...}} do relatório usado (opcional;
    sem ele, usa o status guardado em cada jogador do relatório).
    """
    vcfg = cfg.get("validacao") or {}
    g = game_item["jogo"]
    if g.get("home_team_score") is not None:
        return {"status": "encerrado", "motivo": "jogo já aconteceu"}
    pub = game_item.get("injury_report")
    if not pub:
        return {"status": "pré-análise", "motivo": "sem injury report para o dia"}
    tip = tipoff(g)
    near = vcfg.get("minutos_antes_do_jogo", 90)
    if tip is not None and datetime.fromisoformat(pub) < tip - timedelta(minutes=near):
        return {"status": "pré-análise",
                "motivo": f"último injury report às {pub[11:]} ET; o jogo é às {tip:%H:%M} ET"}
    doubt = set(vcfg.get("status_duvida", ["Questionable", "Doubtful"]))
    min_l10 = vcfg.get("min_minutos_l10", 20)
    pending = [p["jogador"] for p in game_item["jogadores"]
               if (p.get("lesao") in doubt or ((injuries or {}).get(p["player_id"]) or {}).get("status") in doubt)
               and (p.get("min_l10") or 0) >= min_l10]
    if pending:
        return {"status": "pré-análise", "motivo": "em dúvida: " + ", ".join(sorted(pending))}
    return {"status": "validada", "motivo": f"injury report das {pub[11:]} ET sem dúvidas relevantes"}


def checklist(p: dict[str, Any], cfg: dict[str, Any], valid: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Itens do protocolo para o detalhe do jogador. ``ok``: True/False/None (contexto)."""
    s = seal(p, cfg)
    if s is None:
        return []
    acfg = cfg.get("alertas") or {}
    items: list[dict[str, Any]] = []

    def add(item: str, valor: str, ok: bool | None = None, nota: str = "") -> None:
        items.append({"item": item, "valor": valor, "ok": ok, "nota": nota})

    lado = s["lado"].capitalize()
    add("Lado do modelo", f"{lado} {p.get('linha'):g}" if p.get("linha") is not None else lado,
        None, "linha de referência (L10)" if s["linha_ref"] else "linha da casa")
    add("Chance do modelo", f"{100 * s['chance']:.0f}%", s["chance"] >= 0.55,
        "calibrada: quando prevê 60%, dá ~60%")
    add("Odd justa", f"{1 / s['chance']:.2f}")
    if s["odd"]:
        add("Odd da casa", f"{s['odd']:.2f}", s["odd"] > 1 / s["chance"])
        add("Valor esperado", f"{100 * s['ev']:+.1f}%", s["ev"] >= 0.04, "folga mínima sugerida: +4%")
    else:
        add("Odd da casa", "—", None, "informe a odd para medir o valor")
    if s["chance_mercado"] is not None:
        add("Chance do mercado (sem margem)", f"{100 * s['chance_mercado']:.0f}%", None,
            f"margem da casa {100 * s['margem_casa']:.1f}%")
        add("Vantagem sobre o mercado", f"{100 * s['vantagem']:+.1f} p.p.", s["vantagem"] >= 0.03)

    jan = p.get("janelas") or {}
    over_side = s["lado"] == "over"
    for key in ("L5", "L10"):
        w = jan.get(key) or {}
        if w.get("pct") is not None:
            pct = w["pct"] if over_side else 100 - w["pct"]
            alert = key == "L5" and acfg.get("l5_contra", True) and pct < 50
            add(f"{key} a favor do lado", f"{pct}% ({w['jogos']} j)", None,
                "alerta: o L5 vai contra" if alert else "contexto")
    h = jan.get("H2H") or {}
    if h.get("jogos"):
        pct = h["pct"] if over_side else 100 - h["pct"]
        few = h["jogos"] < acfg.get("h2h_min_jogos", 3)
        add("H2H a favor do lado", f"{pct}% ({h['jogos']} j, média {h['media']})", None,
            "poucos jogos: só curiosidade" if few else "contexto")
    if p.get("dvp_rank"):
        add("DvP do adversário", f"{p['dvp_rank']}º de 30", None, "30 = cede mais à posição")
    if p.get("lesao"):
        add("Injury report", p["lesao"], False if p["lesao"] in ("Doubtful", "Questionable") else None,
            p.get("lesao_motivo") or "")
    if valid:
        add("Validação", valid["status"], valid["status"] == "validada", valid["motivo"])
    add("Nível", s["nivel"], s["nivel"] in ("Forte", "Boa"))
    if s["unidade"] is not None:
        add("Unidade sugerida", f"{s['unidade']:g} u")
    return items


def active_sports(cfg: dict[str, Any]) -> list[str]:
    return [k for k, v in (cfg.get("esportes") or {"nba": {"ativo": True}}).items() if (v or {}).get("ativo")]
