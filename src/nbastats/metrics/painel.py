"""Relatório do dia pronto para as telas (Streamlit e API).

Junta matchup_report + linhas da casa + histórico de todas as temporadas +
selo BetânIAG + validação. O cálculo pesado (matchup_report e históricos)
fica em cache por (dia, mercado, versão dos dados); as linhas, que mudam a
cada digitação, são aplicadas sempre por cima de uma cópia.
"""

from __future__ import annotations

import copy
import sqlite3
from typing import Any

from . import betaniag as bt
from . import historico as hs
from .linhas import attach_lines, lines_for
from .matchup import load_matchup_rules, matchup_report
from .projecao import load_projection_params

_CACHE: dict[tuple, tuple[list, dict]] = {}
_MAX = 64


def _base(conn: sqlite3.Connection, day: str, stat: str, version: str | None):
    key = (day, stat, version)
    if key not in _CACHE:
        if len(_CACHE) >= _MAX:
            _CACHE.pop(next(iter(_CACHE)))
        report = matchup_report(conn, day, stat, load_matchup_rules(), load_projection_params())
        ids = sorted({p["player_id"] for g in report for p in g["jogadores"]})
        _CACHE[key] = (report, hs.player_logs(conn, ids, day) if ids else {})
    return _CACHE[key]


def day_report(conn: sqlite3.Connection, day: str, stat: str, version: str | None,
               cfg: dict[str, Any] | None, params: dict[str, Any] | None = None,
               base: tuple[list, dict] | None = None) -> list[dict[str, Any]]:
    """Relatório do dia para ``stat``. ``cfg`` = BetânIAG ligado (ou None)."""
    params = params or load_projection_params()
    report, logs = base or _base(conn, day, stat, version)
    report = copy.deepcopy(report)
    if not report:
        return report
    report = attach_lines(report, stat, lines_for(conn, day, stat), params)
    report = hs.attach_history(report, None, day, stat, logs=logs)
    for g in report:
        g["validacao"] = bt.validation(g, cfg or bt.load_betaniag())
        for p in g["jogadores"]:
            p["selo"] = bt.seal(p, cfg) if cfg else None
    return report
