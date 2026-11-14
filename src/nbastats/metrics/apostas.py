"""Registro de apostas: guardar, conferir o resultado e medir o desempenho.

Cada aposta guarda a fotografia do momento (chance calculada, projeção,
valor esperado). Depois do jogo, `settle_bets` confere sozinho:

- over ganha se o real > linha; under ganha se o real < linha;
- real == linha (linha inteira) -> devolvida (push);
- jogo terminado sem o jogador em quadra -> anulada (devolve), se configurado.

O resumo mede acerto, lucro em unidades e ROI, no total e por mercado, por
unidades apostadas e por faixa de chance calculada. É a régua para saber se
o método (e o Protocolo BetânIAG) ganha dinheiro, e não só se acerta a média.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .matchup import _COLS, _derive

DEFAULT_BET_CONFIG = Path("config/apostas.yaml")
SIDES = ("over", "under")
STATUSES = ("pendente", "ganha", "perdida", "devolvida", "anulada")


def load_bet_config(path: str | Path = DEFAULT_BET_CONFIG) -> dict[str, Any]:
    p = Path(path)
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.exists() else {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_bet(conn: sqlite3.Connection, *, day: str, player_id: int, market: str, side: str,
            line: float, odd: float, units: float, game_id: int | None = None,
            bookmaker: str | None = None, prob: float | None = None, proj: float | None = None,
            note: str | None = None) -> int:
    if side not in SIDES:
        raise ValueError(f"Lado inválido: {side}. Use over ou under.")
    if odd <= 1 or units <= 0:
        raise ValueError("Odd decimal deve ser maior que 1 e unidades maiores que 0.")
    ev = prob * odd - 1 if prob is not None else None
    cur = conn.execute(
        "INSERT INTO bets (created_at, date, game_id, player_id, market, side, line, odd, units,"
        " bookmaker, prob, proj, ev, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (_now(), day, game_id, player_id, market, side, line, odd, units, bookmaker, prob, proj, ev, note))
    conn.commit()
    return cur.lastrowid


def delete_bet(conn: sqlite3.Connection, bet_id: int) -> None:
    conn.execute("DELETE FROM bets WHERE id = ?", (bet_id,))
    conn.commit()


def outcome(side: str, line: float, actual: float | None, played: bool,
            void_if_dnp: bool = True) -> str:
    """Resultado de uma aposta dado o valor real."""
    if not played:
        return "anulada" if void_if_dnp else "perdida"
    if actual == line:
        return "devolvida"
    won = actual > line if side == "over" else actual < line
    return "ganha" if won else "perdida"


def profit(status: str, odd: float, units: float) -> float:
    if status == "ganha":
        return round(units * (odd - 1), 4)
    if status == "perdida":
        return -units
    return 0.0


def _find_game(conn: sqlite3.Connection, bet: sqlite3.Row) -> sqlite3.Row | None:
    """Jogo do jogador naquele dia (pelo game_id, ou pelo time do jogador)."""
    if bet["game_id"]:
        return conn.execute("SELECT * FROM games WHERE id = ?", (bet["game_id"],)).fetchone()
    team = conn.execute("SELECT team_id FROM players WHERE id = ?", (bet["player_id"],)).fetchone()
    if not team:
        return None
    return conn.execute(
        "SELECT * FROM games WHERE date = ? AND (home_team_id = ? OR visitor_team_id = ?)",
        (bet["date"], team["team_id"], team["team_id"])).fetchone()


def settle_bets(conn: sqlite3.Connection, config: dict[str, Any] | None = None) -> dict[str, int]:
    """Confere as apostas pendentes cujo jogo já terminou (tem estatística)."""
    config = config or {}
    void_if_dnp = config.get("anular_se_nao_jogou", True)
    done = defaultdict(int)
    cols = ", ".join(f"COALESCE({c}, 0) AS {c}" for c in _COLS)
    for bet in conn.execute("SELECT * FROM bets WHERE status = 'pendente'").fetchall():
        game = _find_game(conn, bet)
        if game is None:
            continue
        finished = conn.execute("SELECT 1 FROM player_game_stats WHERE game_id = ? LIMIT 1",
                                (game["id"],)).fetchone()
        if not finished:
            continue  # ainda não aconteceu (ou sem carga)
        row = conn.execute(f"SELECT {cols} FROM player_game_stats WHERE game_id = ? AND player_id = ?",
                           (game["id"], bet["player_id"])).fetchone()
        played = bool(row) and row["minutes"] > 0
        actual = _derive(dict(row))[bet["market"]] if played else None
        status = outcome(bet["side"], bet["line"], actual, played, void_if_dnp)
        conn.execute("UPDATE bets SET status = ?, actual = ?, profit_units = ?, settled_at = ?,"
                     " game_id = ? WHERE id = ?",
                     (status, actual, profit(status, bet["odd"], bet["units"]), _now(), game["id"], bet["id"]))
        done[status] += 1
    conn.commit()
    return dict(done)


def list_bets(conn: sqlite3.Connection, status: str | None = None,
              since: str | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT b.*, p.first_name || ' ' || p.last_name AS jogador,
               h.abbreviation AS casa_time, v.abbreviation AS fora_time
        FROM bets b
        LEFT JOIN players p ON p.id = b.player_id
        LEFT JOIN games g ON g.id = b.game_id
        LEFT JOIN teams h ON h.id = g.home_team_id
        LEFT JOIN teams v ON v.id = g.visitor_team_id
        WHERE (:status IS NULL OR b.status = :status) AND (:since IS NULL OR b.date >= :since)
        ORDER BY b.date DESC, b.id DESC
    """
    return [dict(r) for r in conn.execute(sql, {"status": status, "since": since})]


def _summary(bets: list[dict[str, Any]]) -> dict[str, Any]:
    settled = [b for b in bets if b["status"] in ("ganha", "perdida", "devolvida")]
    decided = [b for b in settled if b["status"] != "devolvida"]
    staked = sum(b["units"] for b in settled)
    prof = sum(b["profit_units"] or 0 for b in settled)
    wins = sum(1 for b in decided if b["status"] == "ganha")
    with_prob = [b for b in decided if b["prob"] is not None]
    return {
        "apostas": len(bets),
        "pendentes": sum(1 for b in bets if b["status"] == "pendente"),
        "conferidas": len(settled),
        "ganhas": wins,
        "acerto_pct": round(100 * wins / len(decided), 1) if decided else None,
        # chance média calculada nas apostas decididas: compara com o acerto real
        "chance_media_pct": round(100 * sum(b["prob"] for b in with_prob) / len(with_prob), 1)
        if with_prob else None,
        "unidades_apostadas": round(staked, 2),
        "lucro_unidades": round(prof, 2),
        "roi_pct": round(100 * prof / staked, 1) if staked else None,
    }


def _band(prob: float | None) -> str:
    if prob is None:
        return "sem chance"
    for lo, hi in ((0, .5), (.5, .55), (.55, .6), (.6, .65), (.65, 1.01)):
        if lo <= prob < hi:
            return f"{int(lo * 100)}–{min(int(hi * 100), 100)}%"
    return "sem chance"


def performance(conn: sqlite3.Connection, since: str | None = None) -> dict[str, Any]:
    """Resumo geral e por mercado, por unidades e por faixa de chance, mais a
    curva de lucro acumulado (unidades) por dia."""
    bets = list_bets(conn, since=since)
    groups: dict[str, dict[str, list]] = {"mercado": defaultdict(list), "unidades": defaultdict(list),
                                           "faixa_chance": defaultdict(list), "lado": defaultdict(list)}
    for b in bets:
        groups["mercado"][b["market"]].append(b)
        groups["unidades"][f"{b['units']:g} u"].append(b)
        groups["faixa_chance"][_band(b["prob"])].append(b)
        groups["lado"][b["side"]].append(b)
    curve, total = [], 0.0
    by_day: dict[str, float] = defaultdict(float)
    for b in bets:
        if b["profit_units"] is not None and b["status"] != "pendente":
            by_day[b["date"]] += b["profit_units"]
    for day in sorted(by_day):
        total += by_day[day]
        curve.append({"data": day, "lucro_acumulado": round(total, 2)})
    return {
        "geral": _summary(bets),
        **{k: {name: _summary(v) for name, v in sorted(g.items())} for k, g in groups.items()},
        "curva": curve,
    }
