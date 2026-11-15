"""Fonte gratuita via nba_api (https://github.com/swar/nba_api), que lê o stats.nba.com.

Para validar o produto sem pagar. Limitações conhecidas:
- O stats.nba.com bloqueia IPs de nuvem (AWS, Azure, GCP, GitHub Actions).
  Funciona da sua casa/WSL; não funciona de um servidor.
- API não oficial: muda sem aviso.
- O LeagueGameLog não traz draft nem posição; vêm do PlayerIndex, numa
  chamada por temporada (método players). Conferência continua vazia.
- Posição só em G, F e C (com híbridos como 'G-F'); não há PG/SG/SF/PF.

Esta classe converte tudo para o mesmo formato de dicionário da BALLDONTLIE,
assim a ingestão não sabe de qual fonte os dados vieram.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from datetime import date
from typing import Any

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


def _default_player_index(season: str, timeout: int = 60) -> list[dict[str, Any]]:
    from nba_api.stats.endpoints import playerindex

    time.sleep(0.7)
    return playerindex.PlayerIndex(season=season, timeout=timeout).get_normalized_dict()["PlayerIndex"]


def _default_scoreboard(day: str, timeout: int = 60) -> list[dict[str, Any]]:
    from nba_api.stats.endpoints import scoreboardv3

    time.sleep(0.7)
    body = scoreboardv3.ScoreboardV3(game_date=day, league_id="00", timeout=timeout).get_dict()
    return body["scoreboard"]["games"]


def _default_shot_locations(season: str, kind: str, timeout: int = 60) -> dict[str, Any]:
    """kind 'player' (de onde cada um arremessa) ou 'team_opp' (o que cada defesa cede)."""
    from nba_api.stats.endpoints import leaguedashplayershotlocations, leaguedashteamshotlocations

    time.sleep(0.7)
    if kind == "player":
        ep = leaguedashplayershotlocations.LeagueDashPlayerShotLocations(
            season=season, distance_range="By Zone", timeout=timeout)
    else:
        ep = leaguedashteamshotlocations.LeagueDashTeamShotLocations(
            season=season, measure_type_simple="Opponent", distance_range="By Zone", timeout=timeout)
    return ep.get_dict()["resultSets"]


# nba_api não traz conferência/divisão; os 30 times mudam raramente.
DIVISIONS = {
    "Atlantic": ("BOS", "BKN", "NYK", "PHI", "TOR"), "Central": ("CHI", "CLE", "DET", "IND", "MIL"),
    "Southeast": ("ATL", "CHA", "MIA", "ORL", "WAS"), "Northwest": ("DEN", "MIN", "OKC", "POR", "UTA"),
    "Pacific": ("GSW", "LAC", "LAL", "PHX", "SAC"), "Southwest": ("DAL", "HOU", "MEM", "NOP", "SAS"),
}
EAST = ("Atlantic", "Central", "Southeast")
TEAM_DIVISION = {abbr: div for div, teams in DIVISIONS.items() for abbr in teams}


def _default_teams() -> list[dict[str, Any]]:
    from nba_api.stats.static import teams

    return teams.get_teams()


class NbaApiSource:
    def __init__(self, fetch: Fetcher | None = None,
                 teams_fn: Callable[[], list[dict[str, Any]]] | None = None,
                 player_index_fn: Callable[[str], list[dict[str, Any]]] | None = None,
                 scoreboard_fn: Callable[[str], list[dict[str, Any]]] | None = None,
                 shot_fn: Callable[[str, str], dict[str, Any]] | None = None) -> None:
        self._fetch = fetch or _default_fetcher()
        self._teams_fn = teams_fn or _default_teams
        self._player_index_fn = player_index_fn or _default_player_index
        self._scoreboard_fn = scoreboard_fn or _default_scoreboard
        self._shot_fn = shot_fn or _default_shot_locations

    # ---------- DataSource ----------

    def teams(self) -> Iterator[dict[str, Any]]:
        for t in self._teams_fn():
            yield {
                "id": t["id"],
                "abbreviation": t["abbreviation"],
                "city": t.get("city"),
                "name": t.get("nickname"),
                "full_name": t.get("full_name"),
                "conference": _conference(t["abbreviation"]),
                "division": TEAM_DIVISION.get(t["abbreviation"]),
            }

    def games(self, *, season=None, start_date=None, end_date=None) -> Iterator[dict[str, Any]]:
        for postseason, rows in self._rows("T", season, start_date, end_date):
            yield from _games_from_team_rows(rows, postseason)

    def stats(self, *, season=None, start_date=None, end_date=None) -> Iterator[dict[str, Any]]:
        for _, rows in self._rows("P", season, start_date, end_date):
            for row in rows:
                yield _stat_from_player_row(row)

    def players(self, *, season=None, start_date=None, end_date=None) -> Iterator[dict[str, Any]]:
        if season is None:
            if not start_date:
                raise ValueError("Informe season ou start_date")
            season = season_of(start_date)
        for row in self._player_index_fn(season_label(season)):
            yield _player_from_index_row(row)

    def schedule(self, *, date: str) -> Iterator[dict[str, Any]]:
        for row in self._scoreboard_fn(date):
            game = _game_from_scoreboard(row, date)
            if game:
                yield game

    def shot_zones(self, *, season: int) -> Iterator[dict[str, Any]]:
        for kind in ("player", "team_opp"):
            yield from _zones_from_result(self._shot_fn(season_label(season), kind), kind)

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
    Em quadra neutra (México, Europa, Copa em Las Vegas) as DUAS linhas vêm
    com '@'; aí vale a primeira linha e o outro time fica com o lado livre.
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
        if f"{side}_team" in game:  # quadra neutra: lado já ocupado
            side = "home" if side == "visitor" else "visitor"
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


def _int_or_none(value: Any) -> int | None:
    """'2019' -> 2019; 'Undrafted', '', None -> None."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _player_from_index_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["PERSON_ID"]),
        "first_name": row.get("PLAYER_FIRST_NAME"),
        "last_name": row.get("PLAYER_LAST_NAME"),
        "position": row.get("POSITION") or None,
        "height": row.get("HEIGHT") or None,
        "weight": str(row["WEIGHT"]) if row.get("WEIGHT") else None,
        "country": row.get("COUNTRY") or None,
        "college": row.get("COLLEGE") or None,
        "draft_year": _int_or_none(row.get("DRAFT_YEAR")),
        "draft_round": _int_or_none(row.get("DRAFT_ROUND")),
        "draft_number": _int_or_none(row.get("DRAFT_NUMBER")),
        "team_id": row.get("TEAM_ID") or None,
    }


# Segundo dígito do gameId: 2 = temporada regular, 4 = playoffs.
# Pré-temporada (1), All-Star (3), play-in (5) e final da Copa (6) ficam de fora,
# como no LeagueGameLog.
_GAME_TYPES = {"2": False, "4": True}


def _game_from_scoreboard(row: dict[str, Any], day: str) -> dict[str, Any] | None:
    game_id = str(row["gameId"])  # '0022600236'
    if game_id[2] not in _GAME_TYPES:
        return None
    final = row.get("gameStatus") == 3
    home, away = row["homeTeam"], row["awayTeam"]
    return {
        "id": int(game_id),
        "date": day,
        "season": 2000 + int(game_id[3:5]),
        "postseason": _GAME_TYPES[game_id[2]],
        "status": (row.get("gameStatusText") or "").strip() or None,
        "home_team": {"id": home["teamId"]},
        "visitor_team": {"id": away["teamId"]},
        # jogo que não terminou fica sem placar; o sync do LeagueGameLog grava o final
        "home_team_score": home.get("score") if final else None,
        "visitor_team_score": away.get("score") if final else None,
    }


# Zonas usadas (as de canto esquerdo/direito somam em "Corner 3"; meio da quadra fica de fora)
SHOT_ZONES = {
    "Restricted Area": "aro",
    "In The Paint (Non-RA)": "garrafao",
    "Mid-Range": "meia",
    "Corner 3": "canto3",
    "Above the Break 3": "frente3",
}


def _zones_from_result(rs: dict[str, Any], kind: str) -> Iterator[dict[str, Any]]:
    """Tabela larga do LeagueDash*ShotLocations -> uma linha por entidade e zona.

    Cabeçalho: nomes das zonas na 1ª linha; na 2ª, colunas fixas e depois
    FGM, FGA, FG_PCT para cada zona, na mesma ordem.
    """
    zones = rs["headers"][0]["columnNames"]
    cols = rs["headers"][1]["columnNames"]
    fixed = len(cols) - 3 * len(zones)
    for row in rs["rowSet"]:
        entity = int(row[0])
        for i, zone in enumerate(zones):
            key = SHOT_ZONES.get(zone)
            if key is None:
                continue
            fgm, fga = row[fixed + 3 * i], row[fixed + 3 * i + 1]
            yield {"kind": kind, "entity_id": entity, "zone": key,
                   "fgm": float(fgm or 0), "fga": float(fga or 0)}


def _conference(abbr: str) -> str | None:
    div = TEAM_DIVISION.get(abbr)
    return None if div is None else ("East" if div in EAST else "West")
