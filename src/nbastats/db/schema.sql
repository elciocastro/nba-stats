-- Schema do nbastats. Idempotente: pode rodar quantas vezes quiser.

CREATE TABLE IF NOT EXISTS teams (
    id            INTEGER PRIMARY KEY,
    abbreviation  TEXT,
    city          TEXT,
    name          TEXT,
    full_name     TEXT,
    conference    TEXT,
    division      TEXT
);

CREATE TABLE IF NOT EXISTS players (
    id            INTEGER PRIMARY KEY,
    first_name    TEXT,
    last_name     TEXT,
    position      TEXT,
    height        TEXT,
    weight        TEXT,
    country       TEXT,
    college       TEXT,
    draft_year    INTEGER,
    draft_round   INTEGER,
    draft_number  INTEGER,
    team_id       INTEGER
);

CREATE TABLE IF NOT EXISTS games (
    id                  INTEGER PRIMARY KEY,
    date                TEXT NOT NULL,      -- AAAA-MM-DD
    season              INTEGER NOT NULL,   -- ano de início: 2025 = temporada 2025-26
    postseason          INTEGER NOT NULL DEFAULT 0,
    status              TEXT,
    home_team_id        INTEGER,
    visitor_team_id     INTEGER,
    home_team_score     INTEGER,
    visitor_team_score  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_games_season_date ON games (season, date);

CREATE TABLE IF NOT EXISTS player_game_stats (
    id          INTEGER PRIMARY KEY,
    game_id     INTEGER NOT NULL,
    player_id   INTEGER NOT NULL,
    team_id     INTEGER,
    minutes     REAL NOT NULL DEFAULT 0,
    pts         INTEGER, reb  INTEGER, ast  INTEGER,
    oreb        INTEGER, dreb INTEGER,
    stl         INTEGER, blk  INTEGER, turnover INTEGER, pf INTEGER,
    fgm         INTEGER, fga  INTEGER,
    fg3m        INTEGER, fg3a INTEGER,
    ftm         INTEGER, fta  INTEGER,
    plus_minus  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_stats_player ON player_game_stats (player_id);
CREATE INDEX IF NOT EXISTS idx_stats_game ON player_game_stats (game_id);

CREATE TABLE IF NOT EXISTS sync_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    kind         TEXT NOT NULL,
    params       TEXT,
    games        INTEGER DEFAULT 0,
    stats        INTEGER DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'running',
    error        TEXT
);

-- Injury report oficial (um PDF a cada 15 min). id = AAAAMMDDHHMM (horário ET).
CREATE TABLE IF NOT EXISTS injury_reports (
    id            INTEGER PRIMARY KEY,
    published_at  TEXT NOT NULL,      -- AAAA-MM-DDTHH:MM (ET)
    url           TEXT,
    fetched_at    TEXT
);

-- Uma linha por jogador em cada relatório. id = report_id * 1000 + posição.
CREATE TABLE IF NOT EXISTS injuries (
    id           INTEGER PRIMARY KEY,
    report_id    INTEGER NOT NULL,
    game_date    TEXT,
    matchup      TEXT,
    team_id      INTEGER,
    player_id    INTEGER,             -- NULL se o nome não bateu com a base
    player_name  TEXT,
    status       TEXT,                -- Out, Doubtful, Questionable, Probable, Available
    reason       TEXT
);
CREATE INDEX IF NOT EXISTS idx_injuries_report ON injuries (report_id);
CREATE INDEX IF NOT EXISTS idx_injuries_date ON injuries (game_date);
