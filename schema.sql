-- ========================================
-- 口琴谱生成器 Jianpu to BD · PostgreSQL Schema
-- 与 create_db.py 配合使用；也可直接在 Neon/Supabase 控制台执行
-- ========================================

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(50)  UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email         VARCHAR(100) UNIQUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_login    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS conversions (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    input_text      TEXT,
    input_image     TEXT,
    key_signature   VARCHAR(10) NOT NULL,
    harmonica_type  VARCHAR(10) NOT NULL,
    bd_text         TEXT        NOT NULL,
    bd_image        TEXT,
    analysis        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessions (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token      VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversions_user    ON conversions(user_id);
CREATE INDEX IF NOT EXISTS idx_conversions_created ON conversions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_user       ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires    ON sessions(expires_at);
