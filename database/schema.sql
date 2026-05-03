-- AgentGround Database Schema
-- MySQL 8.0+
-- Run: mysql -u root -p agentground < database/schema.sql
--
-- Architecture note: every user also gets their own agentground_<username>
-- database created automatically at registration time (see database.py).
-- Run this file only once to bootstrap the central agentground database.

CREATE DATABASE IF NOT EXISTS agentground CHARACTER SET utf8mb4;
USE agentground;

-- ──────────────────────────────────────────────────────────────────────────────
--  MASTER DB TABLES  (live in 'agentground')
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id         INT          AUTO_INCREMENT PRIMARY KEY,
    token      VARCHAR(64)  NOT NULL UNIQUE,
    user_id    INT          NOT NULL,
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME     NOT NULL,
    CONSTRAINT fk_session_user FOREIGN KEY (user_id)
        REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_session_token (token)
);

-- ──────────────────────────────────────────────────────────────────────────────
--  PER-USER DB TABLES  (live in 'agentground_<username>')
--  These are created automatically by SQLAlchemy (AppBase.metadata.create_all)
--  at user registration. The DDL below is for manual inspection / recovery only.
-- ──────────────────────────────────────────────────────────────────────────────

-- environments
-- CREATE TABLE IF NOT EXISTS environments (
--     id          INT AUTO_INCREMENT PRIMARY KEY,
--     name        VARCHAR(100) NOT NULL UNIQUE,
--     description TEXT,
--     created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
-- );

-- tools
-- CREATE TABLE IF NOT EXISTS tools (
--     id          INT AUTO_INCREMENT PRIMARY KEY,
--     name        VARCHAR(100) NOT NULL UNIQUE,
--     description TEXT,
--     is_builtin  BOOLEAN      NOT NULL DEFAULT TRUE,
--     created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
-- );

-- agents
-- CREATE TABLE IF NOT EXISTS agents (
--     id              INT AUTO_INCREMENT PRIMARY KEY,
--     environment_id  INT          NOT NULL,
--     name            VARCHAR(100) NOT NULL,
--     api_url         VARCHAR(500) NOT NULL,
--     model_name      VARCHAR(100) NOT NULL DEFAULT 'gpt-4',
--     system_prompt   TEXT         NOT NULL,
--     created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
--     updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
--     CONSTRAINT fk_agent_env FOREIGN KEY (environment_id)
--         REFERENCES environments(id) ON DELETE CASCADE,
--     CONSTRAINT uq_agent_name_per_env UNIQUE (environment_id, name)
-- );

-- agent_tools
-- CREATE TABLE IF NOT EXISTS agent_tools (
--     id         INT AUTO_INCREMENT PRIMARY KEY,
--     agent_id   INT                      NOT NULL,
--     tool_id    INT                      NOT NULL,
--     scope      ENUM('private','shared') NOT NULL DEFAULT 'private',
--     created_at DATETIME                 NOT NULL DEFAULT CURRENT_TIMESTAMP,
--     CONSTRAINT fk_at_agent FOREIGN KEY (agent_id)
--         REFERENCES agents(id) ON DELETE CASCADE,
--     CONSTRAINT fk_at_tool  FOREIGN KEY (tool_id)
--         REFERENCES tools(id) ON DELETE CASCADE,
--     CONSTRAINT uq_agent_tool UNIQUE (agent_id, tool_id)
-- );

-- runs
-- CREATE TABLE IF NOT EXISTS runs (
--     id             INT AUTO_INCREMENT PRIMARY KEY,
--     environment_id INT NOT NULL,
--     status         ENUM('pending','running','stopped','completed','failed')
--                    NOT NULL DEFAULT 'pending',
--     started_at     DATETIME,
--     ended_at       DATETIME,
--     created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
--     CONSTRAINT fk_run_env FOREIGN KEY (environment_id)
--         REFERENCES environments(id) ON DELETE CASCADE
-- );

-- audit_logs
-- CREATE TABLE IF NOT EXISTS audit_logs (
--     id          INT AUTO_INCREMENT PRIMARY KEY,
--     run_id      INT          NOT NULL,
--     agent_id    INT          NOT NULL,
--     step_number INT          NOT NULL,
--     action_type VARCHAR(50)  NOT NULL,
--     payload     JSON,
--     created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
--     CONSTRAINT fk_log_run   FOREIGN KEY (run_id)
--         REFERENCES runs(id) ON DELETE CASCADE,
--     CONSTRAINT fk_log_agent FOREIGN KEY (agent_id)
--         REFERENCES agents(id) ON DELETE CASCADE
-- );

-- user_settings
-- CREATE TABLE IF NOT EXISTS user_settings (
--     id          INT AUTO_INCREMENT PRIMARY KEY,
--     setting_key VARCHAR(100) NOT NULL UNIQUE,
--     setting_value VARCHAR(500),
--     updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
-- );

-- model_configs
-- CREATE TABLE IF NOT EXISTS model_configs (
--     id          INT AUTO_INCREMENT PRIMARY KEY,
--     display_name VARCHAR(100) NOT NULL,
--     provider    VARCHAR(50) NOT NULL,
--     model_id    VARCHAR(100) NOT NULL,
--     api_url     VARCHAR(255) NOT NULL,
--     api_keys    JSON NOT NULL,
--     intelligence_rank INT NOT NULL DEFAULT 50,
--     is_free_tier BOOLEAN NOT NULL DEFAULT FALSE,
--     is_active   BOOLEAN NOT NULL DEFAULT TRUE,
--     notes       TEXT,
--     created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
--     updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
-- );
