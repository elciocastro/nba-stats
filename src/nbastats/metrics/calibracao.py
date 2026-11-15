"""Calibração pública: "quando o site disse X% para um lado, bateu quanto?".

Três fontes, da mais à menos numerosa:
- **backtest**: jogos já disputados, com o que se sabia antes de cada um
  (``projecao.build_dataset``) e a linha de referência (L10 arredondado). Só
  vale fora da amostra usada para calibrar (``config/projecao.yaml``);
- **previsoes**: o que o site mostrou antes de cada jogo (linha da casa ou de
  referência), guardado por ``nbastats previsoes`` e conferido depois;
- **apostas**: as apostas registradas (chance do momento × resultado).

Para cada palpite, o lado escolhido é o mais provável (over ou under); a
tabela agrupa por faixa dessa chance e compara com o acerto real. Brier
score = erro quadrático médio da chance (0 = perfeito; 0,25 = chutar 50%).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from .linhas import prob_over, reference_line

FAIXAS = [(0.50, 0.55), (0.55, 0.60), (0.60, 0.65), (0.65, 0.70), (0.70, 0.80), (0.80, 1.01)]

# mercado -> expressão SQL sobre player_game_stats (s)
REAL_SQL = {
    "pts": "s.pts", "reb": "s.reb", "ast": "s.ast", "pra": "s.pts + s.reb + s.ast", "pr": "s.pts + s.reb",
    "pa": "s.pts + s.ast", "ra": "s.reb + s.ast", "fg3m": "s.fg3m", "fg3a": "s.fg3a", "ftm": "s.ftm",
    "fta": "s.fta", "stl": "s.stl", "blk": "s.blk", "turnover": "s.turnover",
    "fg2m": "s.fgm - s.fg3m", "fg2a": "s.fga - s.fg3a",
}
MERCADOS_PREVISAO = ("pts", "reb", "ast", "pra", "fg3m")


def _faixa(p: float) -> str:
    for lo, hi in FAIXAS:
        if lo <= p < hi:
            return f"{round(100 * lo)}–{min(round(100 * hi), 100)}%"
    return "?"


def resumo(pontos: Iterable[tuple[float, bool | None]]) -> dict[str, Any]:
    """``pontos`` = (chance de over, bateu o over?). Push (None) fica de fora."""
    pts = [(p, y) for p, y in pontos if p is not None and y is not None]
    if not pts:
        return {"n": 0, "brier": None, "acerto_pct": None, "chance_media_pct": None, "faixas": []}
    side = [(max(p, 1 - p), y if p >= 0.5 else not y) for p, y in pts]
    rows = []
    for lo, hi in FAIXAS:
        grp = [(c, ok) for c, ok in side if lo <= c < hi]
        if grp:
            rows.append({"faixa": _faixa(lo), "n": len(grp),
                         "chance_media_pct": round(100 * sum(c for c, _ in grp) / len(grp), 1),
                         "acerto_pct": round(100 * sum(ok for _, ok in grp) / len(grp), 1)})
    return {"n": len(pts),
            "brier": round(sum((p - (1.0 if y else 0.0)) ** 2 for p, y in pts) / len(pts), 4),
            "acerto_pct": round(100 * sum(ok for _, ok in side) / len(side), 1),
            "chance_media_pct": round(100 * sum(c for c, _ in side) / len(side), 1),
            "faixas": rows}


# ---------- backtest ----------

def backtest_points(data: list[dict[str, Any]], params: dict[str, Any], stat: str) -> list[tuple[float, bool | None]]:
    """Chance (com os parâmetros atuais) contra a linha de referência, e o resultado."""
    m = (params.get("mercados") or {}).get(stat) or {}
    out = []
    for r in data:
        base, l10 = r["proj_base"].get(stat), r["l10"].get(stat)
        line = reference_line(l10)
        if base is None or line is None:
            continue
        mu = base * (m.get("nivel", 1) + m.get("ausencia", 0) * r["ausencia"])
        y = r["real"][stat]
        out.append((prob_over(mu, line, m), None if y == line else y > line))
    return out


def save_backtest(conn: sqlite3.Connection, season: int, desde: str | None, result: dict[str, dict[str, Any]],
                  now: datetime | None = None) -> None:
    now = now or datetime.now(timezone.utc)
    conn.execute("INSERT INTO calibration (id, fonte, temporada, desde, dados, atualizado_em) VALUES (?, ?, ?, ?, ?, ?)"
                 " ON CONFLICT(id) DO UPDATE SET desde = excluded.desde, dados = excluded.dados,"
                 " atualizado_em = excluded.atualizado_em",
                 (f"backtest:{season}", "backtest", season, desde, json.dumps(result), now.isoformat(timespec="seconds")))
    conn.commit()


def load_backtest(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [{"temporada": r["temporada"], "desde": r["desde"], "atualizado_em": r["atualizado_em"],
             "mercados": json.loads(r["dados"])}
            for r in conn.execute("SELECT * FROM calibration WHERE fonte = 'backtest' ORDER BY temporada DESC")]


# ---------- previsões guardadas antes do jogo ----------

def save_predictions(conn: sqlite3.Connection, day: str, stat: str, report: list[dict[str, Any]],
                     now_et: datetime, tipoff=None, now: datetime | None = None) -> int:
    """Guarda a chance de cada jogador de jogos que ainda não começaram.

    Atualiza até o início do jogo (a última foto antes do jogo vale). Jogo
    com placar ou já começado (pelo horário da agenda) não é mexido.
    """
    now = now or datetime.now(timezone.utc)
    n = 0
    for g in report:
        jogo = g["jogo"]
        if jogo.get("home_team_score") is not None:
            continue
        tip = tipoff(jogo) if tipoff else None
        if tip is not None and now_et >= tip:
            continue
        for p in g["jogadores"]:
            if p.get("p_over") is None or p.get("linha") is None:
                continue
            conn.execute(
                "INSERT INTO predictions (id, date, game_id, player_id, market, line, line_ref, proj, p_over, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET line = excluded.line,"
                " line_ref = excluded.line_ref, proj = excluded.proj, p_over = excluded.p_over, updated_at = excluded.updated_at",
                (f"{day}:{p['player_id']}:{stat}", day, p.get("game_id") or jogo.get("id"), p["player_id"], stat,
                 p["linha"], int(bool(p.get("linha_ref"))), p.get("proj"), p["p_over"], now.isoformat(timespec="seconds")))
            n += 1
    conn.commit()
    return n


def prediction_points(conn: sqlite3.Connection, stat: str | None = None, so_casa: bool = False,
                      desde: str | None = None) -> dict[str, list[tuple[float, bool | None]]]:
    """Previsões já conferidas, por mercado. ``so_casa``: só linhas da casa."""
    out: dict[str, list[tuple[float, bool | None]]] = {}
    for market, expr in REAL_SQL.items():
        if stat and market != stat:
            continue
        sql = f"""
            SELECT pr.p_over, pr.line, {expr} AS real FROM predictions pr
            JOIN player_game_stats s ON s.game_id = pr.game_id AND s.player_id = pr.player_id
            WHERE pr.market = ? AND s.minutes > 0 {"AND pr.line_ref = 0" if so_casa else ""}
              {"AND pr.date >= ?" if desde else ""}
        """
        args = [market] + ([desde] if desde else [])
        pts = [(r["p_over"], None if r["real"] == r["line"] else r["real"] > r["line"]) for r in conn.execute(sql, args)]
        if pts:
            out[market] = pts
    return out


def bet_points(conn: sqlite3.Connection) -> list[tuple[float, bool | None]]:
    """Apostas conferidas: a chance do lado apostado vira chance de 'acertar'."""
    rows = conn.execute("SELECT prob, status FROM bets WHERE prob IS NOT NULL AND status IN ('ganha', 'perdida')")
    return [(r["prob"], r["status"] == "ganha") for r in rows]


def report(conn: sqlite3.Connection, desde: str | None = None) -> dict[str, Any]:
    prev = prediction_points(conn, desde=desde)
    casa = prediction_points(conn, so_casa=True, desde=desde)
    todas = [x for v in prev.values() for x in v]
    return {"backtest": load_backtest(conn),
            "previsoes": {"geral": resumo(todas), "mercados": {k: resumo(v) for k, v in prev.items()},
                          "so_linha_da_casa": resumo([x for v in casa.values() for x in v])},
            "apostas": resumo(bet_points(conn))}
