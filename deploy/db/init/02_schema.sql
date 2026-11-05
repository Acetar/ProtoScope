-- 02 原型表结构（与 server/app/db.py 的 SCHEMA_PG 一致）
-- 说明：完整 21 张表的设计见《设计文档》5.2；这里只建原型真正在读写的三张表，
--       其余（courses/lessons/sessions/packets/knowledge_chunks…）在接入解析流水线时再加。

CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    email         VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(16)  NOT NULL DEFAULT 'student',
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ,
    failed_attempts SMALLINT   NOT NULL DEFAULT 0,
    locked_until  TIMESTAMPTZ,
    llm_base_url  TEXT,
    llm_api_key   TEXT,
    llm_model     TEXT
);

CREATE TABLE IF NOT EXISTS animations (
    id              VARCHAR(16) PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    knowledge_point VARCHAR(64) NOT NULL,
    title           TEXT NOT NULL,
    duration_sec    REAL NOT NULL,
    props_json      JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_animations_user ON animations(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS captures (
    id            VARCHAR(16) PRIMARY KEY,
    user_id       BIGINT REFERENCES users(id) ON DELETE CASCADE,
    filename      TEXT NOT NULL,
    size          INTEGER NOT NULL,
    packet_count  INTEGER NOT NULL,
    session_count INTEGER NOT NULL,
    data_json     JSONB NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_captures_user ON captures(user_id, created_at DESC);
