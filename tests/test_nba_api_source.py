"""NbaApiSource com respostas no formato real do LeagueGameLog (sem rede)."""

import pytest

from nbastats.ingest import sync_range, sync_season
from nbastats.metrics import boxscore, player_trends
from nbastats.sources.nba_api_source import NbaApiSource, season_label, season_of

TEAMS = [
    {"id": 1610612744, "full_name": "Golden State Warriors", "abbreviation": "GSW",
     "nickname": "Warriors", "city": "Golden State", "state": "California", "year_founded": 1946},
    {"id": 1610612741, "full_name": "Chicago Bulls", "abbreviation": "CHI",
     "nickname": "Bulls", "city": "Chicago", "state": "Illinois", "year_founded": 1966},
]

TEAM_ROWS = [
    {"SEASON_ID": "22026", "TEAM_ID": 1610612744, "TEAM_ABBREVIATION": "GSW", "GAME_ID": "0022600101",
     "GAME_DATE": "2026-11-10", "MATCHUP": "GSW vs. CHI", "PTS": 118},
    {"SEASON_ID": "22026", "TEAM_ID": 1610612741, "TEAM_ABBREVIATION": "CHI", "GAME_ID": "0022600101",
     "GAME_DATE": "2026-11-10", "MATCHUP": "CHI @ GSW", "PTS": 109},
]

PLAYER_ROWS = [
    {"SEASON_ID": "22026", "PLAYER_ID": 201939, "PLAYER_NAME": "Stephen Curry", "TEAM_ID": 1610612744,
     "GAME_ID": "0022600101", "GAME_DATE": "2026-11-10", "MATCHUP": "GSW vs. CHI", "MIN": 34,
     "PTS": 31, "REB": 5, "AST": 7, "OREB": 0, "DREB": 5, "STL": 2, "BLK": 0, "TOV": 3, "PF": 1,
     "FGM": 10, "FGA": 20, "FG3M": 6, "FG3A": 12, "FTM": 5, "FTA": 5, "PLUS_MINUS": 9},
    {"SEASON_ID": "22026", "PLAYER_ID": 1630172, "PLAYER_NAME": "Patrick Williams", "TEAM_ID": 1610612741,
     "GAME_ID": "0022600101", "GAME_DATE": "2026-11-10", "MATCHUP": "CHI @ GSW", "MIN": 28.5,
     "PTS": 14, "REB": 8, "AST": 2, "OREB": 2, "DREB": 6, "STL": 1, "BLK": 1, "TOV": 1, "PF": 3,
     "FGM": 5, "FGA": 11, "FG3M": 2, "FG3A": 5, "FTM": 2, "FTA": 2, "PLUS_MINUS": -9},
]


# PlayerIndex: formato real (Curry com draft; um não draftado)
INDEX_ROWS = [
    {"PERSON_ID": 201939, "PLAYER_LAST_NAME": "Curry", "PLAYER_FIRST_NAME": "Stephen",
     "TEAM_ID": 1610612744, "POSITION": "G", "HEIGHT": "6-2", "WEIGHT": "185",
     "COLLEGE": "Davidson", "COUNTRY": "USA", "DRAFT_YEAR": 2009, "DRAFT_ROUND": 1,
     "DRAFT_NUMBER": 7},
]
UNDRAFTED = {"PERSON_ID": 1629001, "PLAYER_LAST_NAME": "Livre", "PLAYER_FIRST_NAME": "Agente",
             "TEAM_ID": 0, "POSITION": "", "HEIGHT": "", "WEIGHT": None, "COLLEGE": None,
             "COUNTRY": "USA", "DRAFT_YEAR": None, "DRAFT_ROUND": None, "DRAFT_NUMBER": None}

# ScoreboardV3: um agendado, um finalizado e um de pré-temporada
SCOREBOARD = [
    {"gameId": "0022600236", "gameStatus": 1, "gameStatusText": "7:30 pm ET ",
     "homeTeam": {"teamId": 1610612741, "score": 0}, "awayTeam": {"teamId": 1610612744, "score": 0}},
    {"gameId": "0042600101", "gameStatus": 3, "gameStatusText": "Final",
     "homeTeam": {"teamId": 1610612744, "score": 120}, "awayTeam": {"teamId": 1610612741, "score": 99}},
    {"gameId": "0012600001", "gameStatus": 1, "gameStatusText": "8:00 pm ET",
     "homeTeam": {"teamId": 1610612744, "score": 0}, "awayTeam": {"teamId": 1610612741, "score": 0}},
]


class FakeFetch:
    def __init__(self):
        self.calls = []

    def __call__(self, kind, season, season_type, date_from, date_to):
        self.calls.append((kind, season, season_type, date_from, date_to))
        if season_type != "Regular Season":
            return []
        return TEAM_ROWS if kind == "T" else PLAYER_ROWS


@pytest.fixture
def fetch():
    return FakeFetch()


@pytest.fixture
def source(fetch):
    return NbaApiSource(fetch=fetch, teams_fn=lambda: TEAMS,
                        player_index_fn=lambda season: INDEX_ROWS,
                        scoreboard_fn=lambda day: SCOREBOARD)


def test_season_helpers():
    assert season_label(2025) == "2025-26"
    assert season_label(2099) == "2099-00"
    assert season_of("2026-11-14") == 2026
    assert season_of("2027-03-01") == 2026


def test_duas_linhas_de_time_viram_um_jogo(source):
    [game] = list(source.games(season=2026))
    assert game["id"] == 22600101
    assert game["home_team"]["id"] == 1610612744 and game["home_team_score"] == 118
    assert game["visitor_team"]["id"] == 1610612741 and game["visitor_team_score"] == 109
    assert game["season"] == 2026 and game["postseason"] is False


def test_busca_temporada_regular_e_playoffs(source, fetch):
    list(source.games(season=2026))
    assert [c[2] for c in fetch.calls] == ["Regular Season", "Playoffs"]
    assert fetch.calls[0][:2] == ("T", "2026-27")


def test_intervalo_de_datas_no_formato_americano(source, fetch):
    list(source.stats(start_date="2026-11-10", end_date="2026-11-12"))
    assert fetch.calls[0] == ("P", "2026-27", "Regular Season", "11/10/2026", "11/12/2026")


def test_ingestao_completa_e_consultas(conn, source):
    assert sync_season(conn, source, 2026) == {"games": 1, "stats": 2, "players": 1}
    assert sync_range(conn, source, "2026-11-10", "2026-11-10") == {"games": 1, "stats": 2, "players": 1}
    assert conn.execute("SELECT COUNT(*) FROM player_game_stats").fetchone()[0] == 2  # idempotente

    found = boxscore(conn, "chi", "gsw")
    assert found["jogo"]["home"] == "GSW" and found["jogo"]["home_team_score"] == 118
    assert [p["jogador"] for p in found["jogadores"]] == ["Patrick Williams", "Stephen Curry"]

    curry = next(r for r in player_trends(conn, 2026) if r["jogador"] == "Stephen Curry")
    assert (curry["pts"], curry["minutes"], curry["time"]) == (31, 34, "GSW")


def test_quadra_neutra_nao_perde_o_mandante(fetch):
    """Resposta real de 07/11/2026 (DEN x IND): as duas linhas vêm com '@'."""
    neutral = [
        {"SEASON_ID": "22026", "TEAM_ID": 1610612743, "GAME_ID": "0022600189",
         "GAME_DATE": "2026-11-07", "MATCHUP": "DEN @ IND", "PTS": 114},
        {"SEASON_ID": "22026", "TEAM_ID": 1610612754, "GAME_ID": "0022600189",
         "GAME_DATE": "2026-11-07", "MATCHUP": "IND @ DEN", "PTS": 102},
    ]
    src = NbaApiSource(fetch=lambda kind, *a: neutral if kind == "T" and a[1] == "Regular Season" else [],
                       teams_fn=lambda: TEAMS)
    [game] = list(src.games(season=2026))
    assert game["visitor_team"]["id"] == 1610612743 and game["visitor_team_score"] == 114
    assert game["home_team"]["id"] == 1610612754 and game["home_team_score"] == 102


def test_players_do_player_index():
    src = NbaApiSource(fetch=FakeFetch(), teams_fn=lambda: TEAMS,
                       player_index_fn=lambda season: [*INDEX_ROWS, UNDRAFTED])
    curry, livre = list(src.players(start_date="2026-11-10"))
    assert (curry["position"], curry["draft_year"], curry["team_id"]) == ("G", 2009, 1610612744)
    assert livre["position"] is None and livre["draft_year"] is None and livre["team_id"] is None


def test_agenda_do_scoreboard(source):
    agendado, playoff = list(source.schedule(date="2026-11-15"))  # pré-temporada fica de fora
    assert agendado["id"] == 22600236 and agendado["season"] == 2026
    assert agendado["status"] == "7:30 pm ET" and agendado["home_team_score"] is None
    assert playoff["postseason"] is True and playoff["home_team_score"] == 120


def test_posicao_do_player_index_sobrevive_ao_game_log(conn, source):
    sync_season(conn, source, 2026)  # o game log manda o Curry sem posição
    row = conn.execute("SELECT position, draft_year FROM players WHERE id = 201939").fetchone()
    assert (row["position"], row["draft_year"]) == ("G", 2009)


def test_zonas_de_arremesso_formato_real(conn):
    """Formato do LeagueDashTeamShotLocations: zonas na 1ª linha do cabeçalho,
    FGM/FGA/FG_PCT de cada zona na 2ª."""
    zones = ["Restricted Area", "In The Paint (Non-RA)", "Mid-Range", "Left Corner 3",
             "Right Corner 3", "Above the Break 3", "Backcourt", "Corner 3"]
    rs = {"headers": [{"columnNames": zones},
                      {"columnNames": ["TEAM_ID", "TEAM_NAME"] + ["OPP_FGM", "OPP_FGA", "OPP_FG_PCT"] * 8}],
          "rowSet": [[1610612737, "Atlanta Hawks", 275, 390, .705, 69, 178, .388, 46, 95, .484,
                      20, 50, .4, 18, 40, .45, 100, 300, .333, 0, 2, 0, 38, 90, .422]]}
    src = NbaApiSource(fetch=FakeFetch(), teams_fn=lambda: TEAMS,
                       shot_fn=lambda season, kind: rs if kind == "team_opp" else {
                           "headers": [{"columnNames": zones}, {"columnNames": ["PLAYER_ID"] + ["FGM", "FGA", "FG_PCT"] * 8}],
                           "rowSet": []})
    rows = {r["zone"]: r for r in src.shot_zones(season=2026)}
    assert set(rows) == {"aro", "garrafao", "meia", "canto3", "frente3"}  # cantos somados; meio da quadra fora
    assert (rows["aro"]["fgm"], rows["aro"]["fga"]) == (275, 390)
    assert (rows["canto3"]["fgm"], rows["canto3"]["fga"]) == (38, 90)
    assert rows["frente3"]["kind"] == "team_opp" and rows["frente3"]["entity_id"] == 1610612737

    from nbastats.ingest import sync_shot_zones
    assert sync_shot_zones(conn, src, 2026)["stats"] == 5
    assert sync_shot_zones(conn, src, 2026)["stats"] == 5
    assert conn.execute("SELECT COUNT(*) FROM shot_zones").fetchone()[0] == 5  # idempotente
