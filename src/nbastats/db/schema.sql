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

-- Arremessos por zona, temporada até a data da carga (fotografia; não há
-- histórico dia a dia). kind: 'player' = do jogador; 'team_opp' = cedido pela defesa.
CREATE TABLE IF NOT EXISTS shot_zones (
    id          TEXT PRIMARY KEY,     -- temporada:kind:entidade:zona
    season      INTEGER NOT NULL,
    kind        TEXT NOT NULL,
    entity_id   INTEGER NOT NULL,
    zone        TEXT NOT NULL,        -- aro, garrafao, meia, canto3, frente3
    fgm         REAL, fga REAL,
    updated_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_zones_entity ON shot_zones (season, kind, entity_id);

-- Linhas de aposta (digitadas no site/CLI ou, no futuro, de uma API de odds).
CREATE TABLE IF NOT EXISTS lines (
    id          TEXT PRIMARY KEY,     -- data:jogador:mercado
    date        TEXT NOT NULL,
    player_id   INTEGER NOT NULL,
    market      TEXT NOT NULL,        -- pts, reb, pra, fg3m...
    line        REAL NOT NULL,
    odd_over    REAL,                 -- odd decimal (1.90)
    odd_under   REAL,
    source      TEXT,                 -- manual ou o nome da casa/API
    updated_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_lines_date ON lines (date, market);

-- Apostas registradas. Guarda a fotografia do momento (chance, projeção,
-- valor esperado) para medir o método depois; a conferência é automática.
CREATE TABLE IF NOT EXISTS bets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL,
    date          TEXT NOT NULL,          -- dia do jogo
    game_id       INTEGER,
    player_id     INTEGER NOT NULL,
    market        TEXT NOT NULL,
    side          TEXT NOT NULL,          -- over | under
    line          REAL NOT NULL,
    odd           REAL NOT NULL,          -- decimal
    units         REAL NOT NULL,          -- 0.5, 1, 2...
    bookmaker     TEXT,
    prob          REAL,                   -- chance calculada do lado apostado
    proj          REAL,
    ev            REAL,
    note          TEXT,
    status        TEXT NOT NULL DEFAULT 'pendente',  -- pendente, ganha, perdida, devolvida, anulada
    actual        REAL,                   -- valor real do mercado
    profit_units  REAL,
    settled_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_bets_date ON bets (date);

-- Favoritos (jogadores, times e jogos). Site de senha única: a lista é compartilhada.
CREATE TABLE IF NOT EXISTS favorites (
    id          TEXT PRIMARY KEY,     -- tipo:entidade (jogador:203999)
    kind        TEXT NOT NULL,        -- jogador | time | jogo
    entity_id   INTEGER NOT NULL,
    label       TEXT,
    created_at  TEXT NOT NULL
);
