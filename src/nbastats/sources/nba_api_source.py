"""Fonte gratuita via nba_api (https://github.com/swar/nba_api), que lê o stats.nba.com.

Para validar o produto sem pagar. Limitações conhecidas:
- O stats.nba.com bloqueia IPs de nuvem (AWS, Azure, GCP, GitHub Actions).
  Funciona da sua casa/WSL; não funciona de um servidor.
- API não oficial: muda sem aviso.
- Não traz draft, posição nem conferência; o filtro de "anos de liga" do
  ranking de potencial fica sem efeito com esta fonte.

Esta classe converte tudo para o mesmo formato de dicionário da BALLDONTLIE,
assim a ingestão não sabe de qual fonte os dados vieram.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Any, Callable, Iterator

SEASON_TYPES = (("Regular Season", False), ("Playoffs", True))

# fetch(player_or_team, season, season_type, date_from, date_to) -> linhas (dicts)
Fetcher = Callable[[str, str, str, str, str], list[dict[str, Any]]]


def season_label(season: int) -> str:
    """2025 -> '2025-26'."""
    return f"{season}-{str(season + 1)[-2:]}"


def season_of(day: str) -> int:
    """Temporada de uma data: a partir de outubro já é a temporada seguinte."""
    d = date.fromisoformat(day)
    return d.year if d.month >= 10 else d.year - 1


def _us_date(day: str | None) -> str:
    """'2026-11-14' -> '11/14/2026' (formato que o stats.nba.com espera)."""
    if not day:
        return ""
    d = date.fromisoformat(day)
    return f"{d.month:02d}/{d.day:02d}/{d.year}"


def _default_fetcher(pause: float = 0.7, timeout: int = 60) -> Fetcher:
    from nba_api.stats.endpoints import leaguegamelog  # import tardio: dependência opcional

    def fetch(player_or_team, season, season_type, date_from, date_to):
        time.sleep(pause)  # o site derruba quem chama rápido demais
        endpoint = leaguegamelog.LeagueGameLog(
            player_or_team_abbreviation=player_or_team,
            season=season,
            season_type_all_star=season_type,
            date_from_nullable=date_from,
            date_to_nullable=date_to,
            timeout=timeout,
        )
        return endpoint.get_normalized_dict()["LeagueGameLog"]

    return fetch


def _default_teams() -> list[dict[str, Any]]:
    from nba_api.stats.static import teams

    return teams.get_teams()


class NbaApiSource:
    def __init__(self, fetch: Fetcher | None = None,
                 teams_fn: Callable[[], list[dict[str, Any]]] | None = None) -> None:
        self._fetch = fetch or _default_fetcher()
        self._teams_fn = teams_fn or _default_teams

    # ---------- DataSource ----------

    def teams(self) -> Iterator[dict[str, Any]]:
        for t in self._teams_fn():
            yield {
                "id": t["id"],
                "abbreviation": t["abbreviation"],
                "city": t.get("city"),
                "name": t.get("nickname"),
                "full_name": t.get("full_name"),
                "conference": None,
                "division": None,
            }

    def games(self, *, season=None, start_date=None, end_date=None) -> Iterator[dict[str, Any]]:
        for postseason, rows in self._rows("T", season, start_date, end_date):
            yield from _games_from_team_rows(rows, postseason)

    def stats(self, *, season=None, start_date=None, end_date=None) -> Iterator[dict[str, Any]]:
        for _, rows in self._rows("P", season, start_date, end_date):
            for row in rows:
                yield _stat_from_player_row(row)

    # ---------- interno ----------

    def _rows(self, kind, season, start_date, end_date):
        if season is None:
            if not start_date:
                raise ValueError("Informe season ou start_date")
            season = season_of(start_date)
        for season_type, postseason in SEASON_TYPES:
            rows = self._fetch(kind, season_label(season), season_type,
                               _us_date(start_date), _us_date(end_date))
            yield postseason, rows


def _season_from_row(row: dict[str, Any]) -> int:
    # SEASON_ID vem como '22025' (2 = regular, 4 = playoffs; depois o ano)
    return int(str(row["SEASON_ID"])[-4:])


def _games_from_team_rows(rows: list[dict[str, Any]], postseason: bool) -> Iterator[dict[str, Any]]:
    """Duas linhas por jogo (uma por time) viram um jogo.

    MATCHUP: 'GSW vs. CHI' = GSW em casa; 'GSW @ CHI' = GSW visitante.
    """
    by_game: dict[str, dict[str, Any]] = {}
    for row in rows:
        game = by_game.setdefault(row["GAME_ID"], {
            "id": int(row["GAME_ID"]),
            "date": str(row["GAME_DATE"])[:10],
            "season": _season_from_row(row),
            "postseason": postseason,
            "status": "Final",
        })
        side = "visitor" if "@" in row["MATCHUP"] else "home"
        game[f"{side}_team"] = {"id": row["TEAM_ID"]}
        game[f"{side}_team_score"] = row.get("PTS")
    yield from by_game.values()


def _stat_from_player_row(row: dict[str, Any]) -> dict[str, Any]:
    first, _, last = (row.get("PLAYER_NAME") or "").partition(" ")
    game_id, player_id = int(row["GAME_ID"]), int(row["PLAYER_ID"])
    minutes = row.get("MIN")
    return {
        # id estável e único: jogo + jogador
        "id": game_id * 10**8 + player_id,
        "min": "" if minutes is None else str(minutes),
        "pts": row.get("PTS"), "reb": row.get("REB"), "ast": row.get("AST"),
        "oreb": row.get("OREB"), "dreb": row.get("DREB"),
        "stl": row.get("STL"), "blk": row.get("BLK"),
        "turnover": row.get("TOV"), "pf": row.get("PF"),
        "fgm": row.get("FGM"), "fga": row.get("FGA"),
        "fg3m": row.get("FG3M"), "fg3a": row.get("FG3A"),
        "ftm": row.get("FTM"), "fta": row.get("FTA"),
        "plus_minus": row.get("PLUS_MINUS"),
        "player": {"id": player_id, "first_name": first, "last_name": last,
                   "team_id": row.get("TEAM_ID")},
        "team": {"id": row.get("TEAM_ID")},
        "game": {"id": game_id},
    }
