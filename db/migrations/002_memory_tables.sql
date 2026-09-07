-- 002_memory_tables.sql — memória do kaggle-brain v0
-- Aplica no kaggle-meta-db: docker exec -i kaggle-meta-db psql -U postgres -d kaggriculture < 002_memory_tables.sql

-- eixo de pesquisa no experiments (market|producao|execucao|estrutura|revalidacao|...)
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS axis TEXT;
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS notes TEXT;

-- Hipóteses geradas pelo Scientist
CREATE TABLE IF NOT EXISTS hypotheses (
    id           BIGSERIAL PRIMARY KEY,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    statement    TEXT NOT NULL,
    axis         TEXT,
    rationale    TEXT,
    status       TEXT DEFAULT 'proposta',  -- proposta | testando | suportada | rejeitada
    experiment_id BIGINT REFERENCES experiments(id)
);

-- Achados de pesquisa (memória semântica estruturada; embeddings ficam p/ depois)
CREATE TABLE IF NOT EXISTS research_findings (
    id           BIGSERIAL PRIMARY KEY,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    summary      TEXT NOT NULL,
    axis         TEXT,
    confidence   NUMERIC,
    experiment_ids BIGINT[],
    source       TEXT
);

-- Runs do cérebro (checkpoint/estado)
CREATE TABLE IF NOT EXISTS agent_runs (
    id         BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    run_type   TEXT,            -- observer | scientist | planner | gate | worker
    status     TEXT DEFAULT 'running',  -- running | done | failed
    payload    JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
