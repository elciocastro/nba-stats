"""Fonte de dados falsa: 2 times, 3 jogos, 3 jogadores."""

import pytest

from nbastats import db

GSW = {"id": 10, "abbreviation": "GSW", "city": "Golden State", "name": "Warriors",
       "full_name": "Golden State Warriors", "conference": "West", "division": "Pacific"}
CHI = {"id": 5, "abbreviation": "CHI", "city": "Chicago", "name": "Bulls",
       "full_name": "Chicago Bulls", "conference": "East", "division": "Central"}

# novato em alta, novato em queda, veterano em alta
NOVATO_SOBE = {"id": 1, "first_name": "Novato", "last_name": "Sobe", "position": "G",
               "draft_year": 2025, "team_id": 10}
NOVATO_CAI = {"id": 2, "first_name": "Novato", "last_name": "Cai", "position": "F",
              "draft_year": 2025, "team_id": 5}
VETERANO = {"id": 3, "first_name": "Veterano", "last_name": "Sobe", "position": "C",
            "draft_year": 2012, "team_id": 10}


def _game(gid, day):
    return {"id": gid, "date": f"2026-11-{day:02d}", "season": 2026, "status": "Final",
            "postseason": False, "home_team": GSW, "visitor_team": CHI,
            "home_team_score": 110, "visitor_team_score": 100}


GAMES = [_game(100, 1), _game(101, 3), _game(102, 5)]


def _stat(sid, game, player, team, minutes, pts, reb, ast):
    return {"id": sid, "game": {"id": game["id"]}, "player": player, "team": team,
            "min": minutes, "pts": pts, "reb": reb, "ast": ast,
            "stl": 1, "blk": 0, "turnover": 2, "fg3m": 1}


STATS = [
    _stat(1, GAMES[0], NOVATO_SOBE, GSW, "30:00", 10, 4, 4),
    _stat(2, GAMES[1], NOVATO_SOBE, GSW, "30", 10, 4, 4),
    _stat(3, GAMES[2], NOVATO_SOBE, GSW, "34:30", 25, 8, 8),
    _stat(4, GAMES[0], NOVATO_CAI, CHI, "30", 20, 8, 6),
    _stat(5, GAMES[1], NOVATO_CAI, CHI, "30", 20, 8, 6),
    _stat(6, GAMES[2], NOVATO_CAI, CHI, "30", 5, 2, 1),
    _stat(7, GAMES[0], VETERANO, GSW, "30", 10, 4, 4),
    _stat(8, GAMES[1], VETERANO, GSW, "30", 10, 4, 4),
    _stat(9, GAMES[2], VETERANO, GSW, "30", 25, 8, 8),
    _stat(10, GAMES[2], {"id": 4, "first_name": "Nao", "last_name": "Jogou"}, GSW, "", 0, 0, 0),
]


class FakeSource:
    def __init__(self):
        self.calls = []

    def teams(self):
        return [GSW, CHI]

    def games(self, **params):
        self.calls.append(("games", params))
        return list(GAMES)

    def stats(self, **params):
        self.calls.append(("stats", params))
        return list(STATS)

    def players(self, **params):
        self.calls.append(("players", params))
        return []

    def shot_zones(self, *, season):
        self.calls.append(("shot_zones", {"season": season}))
        return [{"kind": "player", "entity_id": 1, "zone": "frente3", "fgm": 3.0, "fga": 10.0},
                {"kind": "team_opp", "entity_id": 5, "zone": "frente3", "fgm": 40.0, "fga": 100.0}]

    def schedule(self, *, date):
        self.calls.append(("schedule", {"date": date}))
        return [{"id": 103, "date": date, "season": 2026, "status": "7:30 pm ET",
                 "postseason": False, "home_team": CHI, "visitor_team": GSW,
                 "home_team_score": None, "visitor_team_score": None}]


@pytest.fixture
def source():
    return FakeSource()


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.init_db(c)
    return c
