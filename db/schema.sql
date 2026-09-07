-- Kaggriculture Meta-Registry — schema v1
-- Banco: Postgres 16+ (container kaggle-meta-db na VPS 147.79.87.117)

-- Snapshot do leaderboard (top-N, periódico)
CREATE TABLE IF NOT EXISTS leaderboard_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    rank            INT NOT NULL,
    team_id         BIGINT NOT NULL,
    team_name       TEXT,
    score           NUMERIC,
    submission_id   BIGINT,
    submission_date TIMESTAMPTZ,
    UNIQUE (captured_at, rank)
);
CREATE INDEX IF NOT EXISTS idx_lb_captured ON leaderboard_snapshots (captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_lb_team   ON leaderboard_snapshots (team_id, captured_at DESC);

-- Nossas submissões no Kaggle (tracking)
CREATE TABLE IF NOT EXISTS submissions (
    id           BIGSERIAL PRIMARY KEY,
    submitted_at TIMESTAMPTZ NOT NULL,
    status       TEXT,
    public_score NUMERIC,
    private_score NUMERIC,
    file         TEXT,
    sha          TEXT,
    message      TEXT
);
CREATE INDEX IF NOT EXISTS idx_sub_time ON submissions (submitted_at DESC);

-- Episódios (partidas) capturados dos times observados
CREATE TABLE IF NOT EXISTS episodes (
    id            BIGSERIAL PRIMARY KEY,
    episode_id    BIGINT UNIQUE,
    submission_id BIGINT,
    team_id       BIGINT,
    team_name     TEXT,
    rank          INT,
    captured_at   TIMESTAMPTZ DEFAULT now(),
    replay_path   TEXT,
    n_steps       INT,
    agents        INT
);
CREATE INDEX IF NOT EXISTS idx_ep_sub ON episodes (submission_id);

-- Experimentos locais h2h/liga
CREATE TABLE IF NOT EXISTS experiments (
    id        BIGSERIAL PRIMARY KEY,
    ran_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    agent_a   TEXT NOT NULL,
    agent_b   TEXT NOT NULL,
    seeds     TEXT,
    wins_a    INT,
    wins_b    INT,
    ties      INT,
    mean_d    NUMERIC,
    json_path TEXT,
    git_sha   TEXT,
    verdict   TEXT,          -- campeao | refutado | neutro
    notes     TEXT
);
CREATE INDEX IF NOT EXISTS idx_exp_time ON experiments (ran_at DESC);
CREATE INDEX IF NOT EXISTS idx_exp_pair ON experiments (agent_a, agent_b);
