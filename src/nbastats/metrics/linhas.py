"""Linhas de aposta: guardar a linha, chance de over/under, valor esperado e
taxa de acerto contra a linha.

A chance vem da projeção (metrics/projecao.py) e de uma distribuição por
mercado escolhida na calibração: binomial negativa para contagens baixas
(3FM, rebotes, tocos...) e normal para valores altos (pontos, PRA). Sem
linha informada, usa-se uma linha de referência (L10 arredondado para x,5),
marcada como tal na tela.
"""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

# ---------- distribuição ----------

def _normal_sf(line: float, mu: float, sd: float) -> float:
    sd = max(sd, 0.3)
    return 0.5 * (1 - math.erf((line - mu) / (sd * math.sqrt(2))))


def _nb_sf(line: float, mu: float, r: float) -> float:
    """P(X > linha) para binomial negativa de média ``mu`` e dispersão ``r``."""
    mu = max(mu, 0.05)
    k = math.floor(line)
    if k < 0:
        return 1.0
    if r > 1e5:  # sem dispersão extra: Poisson
        cdf = sum(math.exp(-mu + x * math.log(mu) - math.lgamma(x + 1)) for x in range(k + 1))
        return max(0.0, 1 - cdf)
    p = r / (r + mu)
    cdf = sum(math.exp(math.lgamma(x + r) - math.lgamma(r) - math.lgamma(x + 1)
                       + r * math.log(p) + x * math.log(1 - p)) for x in range(k + 1))
    return min(1.0, max(0.0, 1 - cdf))


def prob_over(mu: float | None, line: float | None, market: dict[str, Any]) -> float | None:
    """Chance de passar da linha (estritamente acima). Linha inteira empata (push)
    quando bate exato; aqui o empate conta como não-over."""
    if mu is None or line is None:
        return None
    if market.get("dist") == "normal":
        p = _normal_sf(line, mu, market.get("sd_k", 3.0) * max(mu, 0.3) ** market.get("sd_e", 0.3))
    else:
        p = _nb_sf(line, mu, market.get("r", 10.0))
    return shrink(p, market.get("encolhimento", 1.0))


def shrink(p: float, b: float) -> float:
    """Recalibração (Platt sem viés): logit(p') = b × logit(p). b < 1 aproxima a
    chance de 50%, corrigindo excesso de confiança nas pontas (ver 0012)."""
    if b == 1.0 or p <= 0.0 or p >= 1.0:
        return p
    p = min(max(p, 1e-9), 1 - 1e-9)
    return 1 / (1 + math.exp(-b * math.log(p / (1 - p))))


def reference_line(l10: float | None) -> float | None:
    """Linha de referência quando não há linha da casa: L10 arredondado para x,5."""
    if l10 is None:
        return None
    return math.floor(l10) + 0.5


def expected_value(prob: float | None, odd: float | None) -> float | None:
    """Retorno esperado por unidade apostada com odd decimal (0,05 = +5%)."""
    if prob is None or not odd:
        return None
    return prob * odd - 1


def fair_odd(prob: float | None) -> float | None:
    return 1 / prob if prob else None


def hit_rate(values: Iterable[float], line: float) -> dict[str, Any]:
    vals = list(values)
    over = sum(1 for v in vals if v > line)
    return {"over": over, "jogos": len(vals), "pct": round(100 * over / len(vals)) if vals else None}


def hit_rates(history: list[dict[str, Any]], stat: str, line: float,
              opp_id: int | None = None) -> dict[str, dict[str, Any]]:
    """Taxa de over por janela. ``history`` vem do mais recente ao mais antigo."""
    vals = [g[stat] for g in history]
    out = {
        "L5": hit_rate(vals[:5], line), "L10": hit_rate(vals[:10], line),
        "L20": hit_rate(vals[:20], line), "Temporada": hit_rate(vals, line),
        "Casa": hit_rate([g[stat] for g in history if g.get("em_casa")], line),
        "Fora": hit_rate([g[stat] for g in history if not g.get("em_casa")], line),
    }
    if opp_id is not None:
        out["Contra o adversário"] = hit_rate([g[stat] for g in history if g.get("opp_id") == opp_id], line)
    return out


# ---------- linhas guardadas ----------

def line_id(day: str, player_id: int, market: str) -> str:
    return f"{day}:{player_id}:{market}"


def save_line(conn: sqlite3.Connection, day: str, player_id: int, market: str,
              line: float | None, odd_over: float | None = None, odd_under: float | None = None,
              source: str = "manual") -> None:
    """Grava (ou apaga, com linha vazia) a linha de um jogador num mercado e dia."""
    lid = line_id(day, player_id, market)
    if line is None:
        conn.execute("DELETE FROM lines WHERE id = ?", (lid,))
    else:
        conn.execute(
            "INSERT INTO lines (id, date, player_id, market, line, odd_over, odd_under, source, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET line=excluded.line, odd_over=excluded.odd_over,"
            " odd_under=excluded.odd_under, source=excluded.source, updated_at=excluded.updated_at",
            (lid, day, player_id, market, line, odd_over, odd_under, source,
             datetime.now(timezone.utc).isoformat(timespec="seconds")))
    conn.commit()


def lines_for(conn: sqlite3.Connection, day: str, market: str) -> dict[int, dict[str, Any]]:
    cur = conn.execute("SELECT player_id, line, odd_over, odd_under, source, updated_at FROM lines"
                       " WHERE date = ? AND market = ?", (day, market))
    return {r["player_id"]: dict(r) for r in cur}


def find_player(conn: sqlite3.Connection, text: str) -> list[dict[str, Any]]:
    """Busca por parte do nome, sem acento e sem diferenciar maiúsculas."""
    from ..sources.injury_report import normalize_name

    key = normalize_name(text)
    rows = conn.execute("SELECT id, first_name, last_name FROM players").fetchall()
    return [dict(r) for r in rows if key and key in normalize_name(f"{r['first_name']}{r['last_name']}")]


# ---------- juntar com a análise ----------

def attach_lines(report: list[dict[str, Any]], stat: str, lines: dict[int, dict[str, Any]],
                 params: dict[str, Any]) -> list[dict[str, Any]]:
    """Acrescenta linha, chance de over/under, valor esperado e taxas de acerto
    a cada jogador do relatório de matchups (com projeção)."""
    market = (params.get("mercados") or {}).get(stat) or {}
    for game in report:
        for p in game["jogadores"]:
            saved = lines.get(p["player_id"])
            line = saved["line"] if saved else reference_line(p["l10"])
            p_over = prob_over(p.get("proj"), line, market)
            p["linha"] = line
            p["linha_ref"] = saved is None
            p["odd_over"] = saved["odd_over"] if saved else None
            p["odd_under"] = saved["odd_under"] if saved else None
            p["p_over"] = round(p_over, 3) if p_over is not None else None
            p["p_under"] = round(1 - p_over, 3) if p_over is not None else None
            p["ev_over"] = expected_value(p_over, p["odd_over"])
            p["ev_under"] = expected_value(p["p_under"], p["odd_under"])
            p["proj_vs_linha"] = round(p["proj"] - line, 2) if p.get("proj") is not None and line is not None else None
            hist = p.get("historico") or []
            p["acertos"] = hit_rates(hist, stat, line, p.get("adversario_id")) if line is not None else {}
    return report
