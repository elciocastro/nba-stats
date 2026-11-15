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

-- Acesso ao site (painel de administração). Senha com PBKDF2 (sal por usuário).
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    login         TEXT NOT NULL UNIQUE,
    nome          TEXT,
    senha_hash    TEXT NOT NULL,      -- pbkdf2_sha256$iteracoes$sal$hash
    papel         TEXT NOT NULL DEFAULT 'usuario',   -- admin | usuario
    ativo         INTEGER NOT NULL DEFAULT 1,
    expira_em     TEXT,               -- AAAA-MM-DD: acesso até esta data (opcional)
    trocar_senha  INTEGER NOT NULL DEFAULT 0,        -- pede nova senha no próximo login
    criado_em     TEXT NOT NULL,
    ultimo_acesso TEXT
);

-- Sessões: guarda só o hash do token (quem lê o banco não entra no site).
CREATE TABLE IF NOT EXISTS sessions (
    token_hash  TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    criado_em   TEXT NOT NULL,
    expira_em   TEXT NOT NULL,
    ultimo_uso  TEXT,
    ip          TEXT,
    agente      TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions (user_id);

-- Tentativas de login (certas e erradas), para o painel e o bloqueio.
CREATE TABLE IF NOT EXISTS access_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    quando    TEXT NOT NULL,
    login     TEXT,
    user_id   INTEGER,
    ok        INTEGER NOT NULL,
    ip        TEXT,
    motivo    TEXT
);
CREATE INDEX IF NOT EXISTS idx_access_quando ON access_log (quando);

-- Previsões mostradas antes do jogo (para a calibração pública).
-- id = data:jogador:mercado; atualiza até o início do jogo.
CREATE TABLE IF NOT EXISTS predictions (
    id          TEXT PRIMARY KEY,
    date        TEXT NOT NULL,
    game_id     INTEGER,
    player_id   INTEGER NOT NULL,
    market      TEXT NOT NULL,
    line        REAL NOT NULL,
    line_ref    INTEGER NOT NULL DEFAULT 0,   -- 1 = linha de referência (L10), 0 = da casa
    proj        REAL,
    p_over      REAL NOT NULL,
    updated_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_predictions_market ON predictions (market, date);

-- Resultados de calibração calculados offline (backtest). id = fonte:temporada.
CREATE TABLE IF NOT EXISTS calibration (
    id             TEXT PRIMARY KEY,
    fonte          TEXT NOT NULL,
    temporada      INTEGER,
    desde          TEXT,
    dados          TEXT NOT NULL,      -- JSON {mercado: resumo}
    atualizado_em  TEXT
);

-- Filtros salvos da página Props (por usuário; user_id NULL = sem login).
CREATE TABLE IF NOT EXISTS saved_filters (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    nome        TEXT NOT NULL,
    params      TEXT NOT NULL,       -- JSON com os filtros
    criado_em   TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_filters_user_nome ON saved_filters (COALESCE(user_id, 0), nome);

-- Alertas já enviados (não repetir). key = tipo:data:...; sent_at em UTC.
CREATE TABLE IF NOT EXISTS alerts_sent (
    key      TEXT PRIMARY KEY,
    sent_at  TEXT NOT NULL
);

-- Usuários que já receberam a cópia dos favoritos compartilhados (uma vez só).
CREATE TABLE IF NOT EXISTS user_seeds (
    user_id  INTEGER PRIMARY KEY
);

-- Fotografia diária das zonas (para validar o encaixe com o que se sabia no
-- dia). id = data:temporada:kind:entidade:zona; upsert (a última carga do dia vale).
CREATE TABLE IF NOT EXISTS shot_zones_daily (
    id          TEXT PRIMARY KEY,
    date        TEXT NOT NULL,
    season      INTEGER NOT NULL,
    kind        TEXT NOT NULL,
    entity_id   INTEGER NOT NULL,
    zone        TEXT NOT NULL,
    fgm         REAL, fga REAL
);
CREATE INDEX IF NOT EXISTS idx_zones_daily ON shot_zones_daily (date, season, kind, entity_id);
