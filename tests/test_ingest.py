import pytest

from nbastats.ingest import sync_range, sync_season
from nbastats.ingest.sync import parse_minutes


def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


@pytest.mark.parametrize("raw,expected", [("34:30", 34.5), ("34", 34.0), ("", 0.0), (None, 0.0), ("x", 0.0)])
def test_parse_minutes(raw, expected):
    assert parse_minutes(raw) == expected


def test_sync_season_carrega_tudo(conn, source):
    result = sync_season(conn, source, 2026)
    assert result == {"games": 3, "stats": 10}
    assert _count(conn, "teams") == 2
    assert _count(conn, "players") == 4
    assert source.calls[0] == ("games", {"season": 2026})


def test_sync_e_idempotente(conn, source):
    sync_season(conn, source, 2026)
    sync_season(conn, source, 2026)
    assert _count(conn, "games") == 3
    assert _count(conn, "player_game_stats") == 10
    assert _count(conn, "sync_log") == 2


def test_sync_atualiza_linha_existente(conn, source):
    sync_season(conn, source, 2026)
    source.games = lambda **_: [{"id": 100, "date": "2026-11-01", "season": 2026,
                                 "status": "Final", "home_team_score": 120,
                                 "visitor_team_score": 100}]
    sync_range(conn, source, "2026-11-01", "2026-11-01")
    assert conn.execute("SELECT home_team_score FROM games WHERE id=100").fetchone()[0] == 120


def test_falha_fica_no_log(conn, source):
    def boom(**_):
        raise RuntimeError("api fora")

    source.stats = boom
    with pytest.raises(RuntimeError):
        sync_season(conn, source, 2026)
    row = conn.execute("SELECT status, error FROM sync_log").fetchone()
    assert row["status"] == "error" and "api fora" in row["error"]
