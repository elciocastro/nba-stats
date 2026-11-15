"""Ranking de "jogadores em potencial" a partir das regras em YAML."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import yaml

from .. import ajustes as _aj

from .queries import STATS, player_trends

DEFAULT_RULES = Path("config/potencial.yaml")


def load_rules(path: str | Path = DEFAULT_RULES, ajustes: bool = True) -> dict[str, Any]:
    rules = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if ajustes and Path(path) == Path(DEFAULT_RULES):
        rules = _aj.aplicar("potencial", rules)
    unknown = set(rules.get("pesos", {})) - set(STATS)
    if unknown:
        raise ValueError(f"Estatística desconhecida em pesos: {sorted(unknown)}. Válidas: {STATS}")
    return rules


def score(row: dict[str, Any], pesos: dict[str, float]) -> float:
    """Soma ponderada da variação relativa: últimos N jogos contra a temporada."""
    total = 0.0
    for stat, peso in pesos.items():
        base, recent = row.get(stat), row.get(f"{stat}_n")
        if base is None or recent is None:
            continue
        # piso de 1.0 evita que médias minúsculas (0.2 -> 0.6) dominem a nota
        total += peso * (recent - base) / max(base, 1.0)
    return round(total, 3)


def rank_potenciais(
    conn: sqlite3.Connection, season: int, rules: dict[str, Any]
) -> list[dict[str, Any]]:
    filtros = rules.get("filtros", {})
    pesos = rules.get("pesos", {})
    rows = player_trends(
        conn,
        season,
        last_n=rules.get("ultimos_jogos", 10),
        min_games=filtros.get("min_jogos", 1),
    )
    max_anos = filtros.get("max_anos_de_liga")
    min_minutos = filtros.get("min_minutos", 0)

    ranked = []
    for row in rows:
        if row["minutes"] < min_minutos:
            continue
        anos = season - row["draft_year"] if row["draft_year"] else None
        if max_anos is not None and anos is not None and anos > max_anos:
            continue
        ranked.append({**row, "anos_de_liga": anos, "nota": score(row, pesos)})
    return sorted(ranked, key=lambda r: r["nota"], reverse=True)
